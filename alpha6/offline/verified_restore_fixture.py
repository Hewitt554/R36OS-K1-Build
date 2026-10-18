#!/usr/bin/env python3
"""CP09 disposable-filesystem recovery test harness; cannot operate on SD or mounted root.

Real file backup, validation, two-rename restore and restart logic, but intentionally
restricted to temporary test fixtures. NOT production R36OS recovery software.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile

MARKER = b"R36OS_CP09_DISPOSABLE_FIXTURE_V1\n"
MAX_FILES = 2000
MAX_BYTES = 64 * 1024 * 1024

class Reject(ValueError):
    pass

class InjectedPowerLoss(RuntimeError):
    pass

def fsync_parent(p):
    if os.name != "posix":
        return
    fd = os.open(str(p.parent), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def atomic_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    with tmp.open("x", encoding="utf-8") as out:
        json.dump(data, out, sort_keys=True, separators=(",", ":"))
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)
    fsync_parent(path)

def sha(data):
    return hashlib.sha256(data).hexdigest()

class Fixture:
    def __init__(self, base):
        base = Path(base)
        if base.is_symlink() or not base.is_dir():
            raise Reject("sandbox directory absent or symlink")
        self.base = base.resolve(strict=True)
        allowed = Path(tempfile.gettempdir()).resolve(strict=True)
        if allowed not in self.base.parents or not self.base.name.startswith("r36os-cp09-sandbox-"):
            raise Reject("refusing anything outside specially named temporary sandbox")
        if not (self.base / ".fixture-id").is_file() or (self.base / ".fixture-id").read_bytes() != MARKER:
            raise Reject("sandbox identity absent or invalid")
        for name in ("active", "staged", "quarantine", "snapshot.zip", "snapshot.json", "journal.json"):
            if (self.base / name).is_symlink():
                raise Reject("symlink in recovery fixture infrastructure")

    @staticmethod
    def create(base):
        base = Path(base)
        allowed = Path(tempfile.gettempdir()).resolve(strict=True)
        if base.is_symlink() or allowed not in base.resolve().parents or not base.name.startswith("r36os-cp09-sandbox-"):
            raise Reject("not a safe fixture path")
        base.mkdir(mode=0o700)
        (base / ".fixture-id").write_bytes(MARKER)
        (base / "active").mkdir()
        atomic_json(base / "journal.json", {"state": "READY"})
        return Fixture(base)

    def journal(self):
        try:
            obj = json.loads((self.base / "journal.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Reject("journal missing or corrupt") from exc
        if obj.get("state") not in {"READY", "VERIFIED", "PREPARED", "SWAPPING", "RESTORED"}:
            raise Reject("unexpected journal state")
        return obj["state"]

    def state(self, value):
        atomic_json(self.base / "journal.json", {"state": value})

    def all_files(self, root):
        if not root.is_dir() or root.is_symlink():
            raise Reject("root must be a real directory")
        found = []
        total = 0
        for d, subdirs, files in os.walk(root, followlinks=False):
            for item in subdirs:
                p = Path(d) / item
                if p.is_symlink():
                    raise Reject("directory symlink not supported")
            for item in files:
                p = Path(d) / item
                info = p.lstat()
                if not stat.S_ISREG(info.st_mode):
                    raise Reject("symbolic links, devices and FIFOs not allowed")
                rel = p.relative_to(root).as_posix()
                if rel.startswith("/") or ".." in PurePosixPath(rel).parts or rel.startswith("."):
                    raise Reject("unsafe archived filename")
                if info.st_size > MAX_BYTES:
                    raise Reject("file too large for sandbox")
                total += info.st_size
                if total > MAX_BYTES or len(found) >= MAX_FILES:
                    raise Reject("fixture test limit exceeded")
                found.append((rel, p))
        return sorted(found)

    def snapshot(self):
        if self.journal() != "READY":
            raise Reject("fixture is already in a recovery transaction")
        files = self.all_files(self.base / "active")
        if not files:
            raise Reject("refuse empty snapshot")
        archive = self.base / "snapshot.zip"
        if archive.exists() or (self.base / "snapshot.json").exists():
            raise Reject("refuse to overwrite previous snapshot")
        expected = {}
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for name, path in files:
                value = path.read_bytes()
                expected[name] = sha(value)
                z.writestr(name, value)
        atomic_json(self.base / "snapshot.json", {"format": 1, "archive_sha256": sha(archive.read_bytes()), "files": expected})
        self.verify_snapshot()
        self.state("VERIFIED")

    def verify_snapshot(self):
        try:
            manifest = json.loads((self.base / "snapshot.json").read_text(encoding="utf-8"))
            archive = (self.base / "snapshot.zip").read_bytes()
        except (OSError, ValueError) as exc:
            raise Reject("snapshot metadata unreadable") from exc
        if manifest.get("format") != 1:
            raise Reject("invalid manifest format")
        if sha(archive) != manifest.get("archive_sha256"):
            raise Reject("backup checksum mismatch")
        expected = manifest.get("files")
        if not isinstance(expected, dict) or not expected or len(expected) > MAX_FILES:
            raise Reject("invalid backup manifest")
        total = 0
        try:
            with zipfile.ZipFile(self.base / "snapshot.zip", "r") as z:
                if sorted(z.namelist()) != sorted(expected):
                    raise Reject("unexpected or missing archived files")
                for info in z.infolist():
                    name = info.filename
                    if (not name or name.startswith("/") or ".." in PurePosixPath(name).parts
                            or name.startswith(".") or "\\" in name or info.is_dir()):
                        raise Reject("unsafe archive member")
                    if (info.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                        raise Reject("symlink inside archive")
                    total += info.file_size
                    if total > MAX_BYTES:
                        raise Reject("archive exceeds fixture limit")
                    with z.open(info) as stream:
                        h = hashlib.sha256()
                        for chunk in iter(lambda: stream.read(65536), b""):
                            h.update(chunk)
                        if h.hexdigest() != expected[name]:
                            raise Reject("archived file hash mismatch")
        except (zipfile.BadZipFile, EOFError, KeyError) as exc:
            raise Reject("invalid snapshot archive") from exc
        return expected

    def prepare(self):
        if self.journal() != "VERIFIED":
            raise Reject("recovery was not verified")
        expected = self.verify_snapshot()
        stage = self.base / "staged"
        if stage.exists():
            raise Reject("staging area already present")
        stage.mkdir()
        with zipfile.ZipFile(self.base / "snapshot.zip") as z:
            for name in sorted(expected):
                p = stage / name
                p.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as inp, p.open("xb") as out:
                    for chunk in iter(lambda: inp.read(65536), b""):
                        out.write(chunk)
                    out.flush(); os.fsync(out.fileno())
        self.verify_stage(expected)
        fsync_parent(stage)
        self.state("PREPARED")

    def verify_stage(self, expected=None):
        if expected is None:
            expected = self.verify_snapshot()
        files = self.all_files(self.base / "staged")
        if sorted(name for name, _ in files) != sorted(expected):
            raise Reject("staged files differ from verified snapshot")
        for name, path in files:
            if sha(path.read_bytes()) != expected[name]:
                raise Reject("staged file mutated")

    def commit(self, crash=None):
        current = self.journal()
        if current not in ("PREPARED", "SWAPPING"):
            raise Reject("restore not prepared")
        self.verify_snapshot()
        active, staged, old = (self.base / x for x in ("active", "staged", "quarantine"))
        if current == "PREPARED":
            if not staged.exists():
                raise Reject("staged restore missing before original was moved")
            self.verify_stage()
            self.state("SWAPPING")
            if crash == "after_journal":
                raise InjectedPowerLoss("after_journal")
        if staged.exists():
            self.verify_stage()
        elif not active.exists():
            raise Reject("neither staged nor active root exists")
        if not staged.exists() and not old.exists():
            raise Reject("staged restore missing before original was moved")
        if not old.exists():
            if not active.exists():
                raise Reject("no original active root to quarantine")
            os.rename(active, old)
            fsync_parent(active)
            if crash == "after_old_rename":
                raise InjectedPowerLoss("after_old_rename")
        if staged.exists():
            if active.exists():
                raise Reject("active and staged both present in swap phase")
            os.rename(staged, active)
            fsync_parent(active)
            if crash == "after_new_rename":
                raise InjectedPowerLoss("after_new_rename")
        expected = self.verify_snapshot()
        current_files = self.all_files(active)
        if sorted(n for n, _ in current_files) != sorted(expected):
            raise Reject("restored root files do not match snapshot")
        for name, path in current_files:
            if sha(path.read_bytes()) != expected[name]:
                raise Reject("restored root content invalid")
        self.state("RESTORED")
        # Quarantine intentionally retained for analysis; never delete original.

    def normal_boot_allowed(self):
        return self.journal() in ("READY", "RESTORED")
