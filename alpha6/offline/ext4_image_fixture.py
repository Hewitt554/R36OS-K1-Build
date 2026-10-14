#!/usr/bin/env python3
"""CP10: real ext4 image recovery tests on temporary, marker-bound files ONLY.

Development simulator, no block-device handling or R36S SD recovery implementation.
An image-level byte-exact archive keeps ext4 modes, UUID, ACLs, xattrs and special
inodes exactly as recorded in the image (without trying to reinterpret them).
"""
from __future__ import annotations
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import uuid

SIGNATURE = "R36OS-CP10-DISPOSABLE-IMAGE-TEST-V1\n"
CHUNK = 1024 * 1024
IMAGE_BYTES = 32 * 1024 * 1024
MAX_TEST_IMAGE = 64 * 1024 * 1024
STATE = {"READY", "VERIFIED", "PREPARED", "SWAPPING", "RESTORED"}

class Rejected(ValueError):
    pass

class SimulatedPowerLoss(RuntimeError):
    pass

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for b in iter(lambda: stream.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()

def sync_parent(path: Path):
    if os.name != "posix":
        return
    d = os.open(str(path.parent), os.O_RDONLY)
    try: os.fsync(d)
    finally: os.close(d)

def write_atomic_json(path: Path, content: dict):
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("xb") as f:
        f.write((json.dumps(content, sort_keys=True, separators=(",", ":")) + "\n").encode())
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    sync_parent(path)

def ext4_identity(path: Path) -> str:
    # Filesystem superblock starts 1024 bytes from start of a raw ext4 image.
    with path.open("rb") as f:
        f.seek(1024)
        sb = f.read(256)
    if len(sb) < 0x88 or sb[0x38:0x3a] != bytes.fromhex("53ef"):
        raise Rejected("not an ext4 filesystem superblock")
    return str(uuid.UUID(bytes=sb[0x68:0x78]))

class Sandbox:
    """Guarded test workspace; all modifiable targets are named regular files in tmp."""
    FILES = ("active.ext4", "backup.ext4.gz", "backup.json", "staged.ext4", "quarantine.ext4", "journal.json")

    def __init__(self, folder: Path):
        folder = Path(folder)
        if folder.is_symlink() or not folder.is_dir():
            raise Rejected("missing sandbox / symlink")
        self.folder = folder.resolve(strict=True)
        tmp = Path(tempfile.gettempdir()).resolve(strict=True)
        if tmp not in self.folder.parents or not self.folder.name.startswith("r36os-cp10-sandbox-"):
            raise Rejected("outside restricted temporary sandbox")
        if (self.folder / ".identity").is_symlink() or not (self.folder / ".identity").is_file():
            raise Rejected("missing sandbox marker")
        if (self.folder / ".identity").read_text() != SIGNATURE:
            raise Rejected("invalid sandbox marker")
        self.check_paths()

    def check_paths(self):
        for n in self.FILES:
            p = self.folder / n
            if p.is_symlink():
                raise Rejected("symlink inside image sandbox")
            if p.exists() and not stat.S_ISREG(p.lstat().st_mode):
                raise Rejected("non-regular image sandbox artifact")

    def path(self, name):
        if name not in self.FILES:
            raise Rejected("unknown sandbox path")
        self.check_paths()
        return self.folder / name

    @classmethod
    def create(cls, folder: Path):
        folder = Path(folder)
        tmp = Path(tempfile.gettempdir()).resolve(strict=True)
        if folder.is_symlink() or tmp not in folder.resolve().parents or not folder.name.startswith("r36os-cp10-sandbox-"):
            raise Rejected("invalid scratch folder")
        folder.mkdir(mode=0o700)
        (folder / ".identity").write_text(SIGNATURE)
        write_atomic_json(folder / "journal.json", {"state":"READY"})
        return cls(folder)

    def state(self):
        try:
            d = json.loads(self.path("journal.json").read_text())
            state = d["state"]
        except Rejected:
            raise
        except (OSError, KeyError, ValueError) as e:
            raise Rejected("missing or invalid journal") from e
        if state not in STATE:
            raise Rejected("unexpected journal state")
        return state

    def set_state(self, state):
        if state not in STATE:
            raise Rejected("unexpected new state")
        write_atomic_json(self.path("journal.json"), {"state":state})

    def make_ext4(self, seed: Path):
        if self.state() != "READY":
            raise Rejected("fixture already in transaction")
        active = self.path("active.ext4")
        if active.exists():
            raise Rejected("active image already exists")
        if not seed.is_dir() or seed.is_symlink() or seed.resolve().parent != self.folder:
            raise Rejected("seed must be local test directory")
        with active.open("xb") as f:
            f.truncate(IMAGE_BYTES)
            f.flush(); os.fsync(f.fileno())
        # No block devices, mount, or root privileges: mke2fs populates a regular image.
        subprocess.run(["mke2fs", "-q", "-F", "-t", "ext4", "-L", "CP10FIX", "-d", str(seed), str(active)], check=True, capture_output=True, text=True)
        self.assert_clean(active)

    def assert_clean(self, image: Path):
        self.check_paths()
        if image not in [self.folder / n for n in self.FILES]:
            raise Rejected("image not one of allowed paths")
        if not image.is_file() or image.is_symlink() or not 0 < image.stat().st_size <= MAX_TEST_IMAGE:
            raise Rejected("invalid ext4 fixture target")
        ident = ext4_identity(image)
        # e2fsck -fn is read-only and refuses actual mounted block devices; targets are regular files.
        p = subprocess.run(["e2fsck", "-fn", str(image)], capture_output=True, text=True)
        if p.returncode != 0:
            raise Rejected("ext4 fsck did not pass: " + (p.stderr + p.stdout)[-450:])
        return ident

    def snapshot(self):
        if self.state() != "READY":
            raise Rejected("already in a transaction")
        active = self.path("active.ext4")
        fs_uuid = self.assert_clean(active)
        archive = self.path("backup.ext4.gz")
        manifest = self.path("backup.json")
        if archive.exists() or manifest.exists():
            raise Rejected("refusing to overwrite previous backup")
        with active.open("rb") as inp, archive.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=3, mtime=0) as zipout:
                shutil.copyfileobj(inp, zipout, CHUNK)
            raw.flush(); os.fsync(raw.fileno())
        metadata = {"format":"R36OS_CP10_TEST_IMAGE_V1", "image_bytes":active.stat().st_size,
                    "raw_sha256":sha256_file(active), "archive_sha256":sha256_file(archive), "ext4_uuid":fs_uuid}
        write_atomic_json(manifest, metadata)
        self.verify_archive()
        self.set_state("VERIFIED")

    def verify_archive(self):
        try: meta=json.loads(self.path("backup.json").read_text())
        except (OSError, ValueError) as e: raise Rejected("backup manifest unavailable") from e
        if meta.get("format") != "R36OS_CP10_TEST_IMAGE_V1":
            raise Rejected("wrong manifest format")
        if not isinstance(meta.get("image_bytes"), int) or not 0 < meta["image_bytes"] <= MAX_TEST_IMAGE:
            raise Rejected("invalid expected image size")
        try: uuid.UUID(meta["ext4_uuid"])
        except (KeyError, TypeError, ValueError) as e: raise Rejected("invalid manifest UUID") from e
        arch=self.path("backup.ext4.gz")
        if sha256_file(arch) != meta.get("archive_sha256"):
            raise Rejected("compressed backup checksum mismatch")
        return meta

    def prepare(self):
        if self.state() != "VERIFIED":
            raise Rejected("snapshot must be verified")
        meta = self.verify_archive()
        stage = self.path("staged.ext4")
        if stage.exists():
            raise Rejected("staging exists")
        rawhash=hashlib.sha256(); written=0
        with gzip.open(self.path("backup.ext4.gz"), "rb") as inp, stage.open("xb") as output:
            while True:
                chunk=inp.read(CHUNK)
                if not chunk: break
                written+=len(chunk)
                if written>meta["image_bytes"]:
                    raise Rejected("decompressed snapshot exceeds manifest size")
                rawhash.update(chunk)
                output.write(chunk)
            output.flush(); os.fsync(output.fileno())
        sync_parent(stage)
        if written!=meta["image_bytes"] or rawhash.hexdigest()!=meta["raw_sha256"]:
            raise Rejected("raw image checksum or size mismatch")
        if self.assert_clean(stage)!=meta["ext4_uuid"]:
            raise Rejected("staged filesystem UUID mismatch")
        self.set_state("PREPARED")

    def verify_staged(self):
        meta=self.verify_archive()
        stage=self.path("staged.ext4")
        if not stage.exists():
            raise Rejected("staged image missing")
        if stage.stat().st_size!=meta["image_bytes"] or sha256_file(stage)!=meta["raw_sha256"]:
            raise Rejected("staged image checksum mismatch")
        if self.assert_clean(stage)!=meta["ext4_uuid"]:
            raise Rejected("staged UUID mismatch")

    def commit(self, crash=None):
        state=self.state()
        if state not in ("PREPARED", "SWAPPING"):
            raise Rejected("restore not prepared")
        meta=self.verify_archive()
        active=self.path("active.ext4"); stage=self.path("staged.ext4"); quarantine=self.path("quarantine.ext4")
        if state=="PREPARED":
            if not stage.exists():
                raise Rejected("missing staged image before original quarantine")
            self.verify_staged()
            self.set_state("SWAPPING")
            if crash=="after_journal":raise SimulatedPowerLoss("after_journal")
        # Refuse changing original if stage disappeared before first rename.
        if stage.exists():
            self.verify_staged()
        elif not quarantine.exists():
            raise Rejected("missing staged image before original quarantine")
        if not quarantine.exists():
            if not active.exists():raise Rejected("missing active image")
            if not stage.exists():raise Rejected("missing staged image")
            os.rename(active, quarantine)
            sync_parent(active)
            if crash=="after_quarantine":raise SimulatedPowerLoss("after_quarantine")
        if stage.exists():
            if active.exists():raise Rejected("unexpected active image while staged restore exists")
            os.rename(stage, active)
            sync_parent(active)
            if crash=="after_activation":raise SimulatedPowerLoss("after_activation")
        if not active.exists():raise Rejected("no restored active image")
        if active.stat().st_size!=meta["image_bytes"] or sha256_file(active)!=meta["raw_sha256"]:
            raise Rejected("activated image hash mismatch")
        if self.assert_clean(active)!=meta["ext4_uuid"]:
            raise Rejected("activated ext4 UUID mismatch")
        if not quarantine.is_file():raise Rejected("quarantined original missing")
        self.set_state("RESTORED")

    def normal_boot_allowed(self):
        return self.state() in ("READY", "RESTORED")