#!/usr/bin/env python3
"""R36OS native-migration dependency scanner.

Read-only scanner for extracted R36OS source snapshots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from collections import Counter

LEGACY_MARKERS = [
    "ArkOS",
    "AeUX",
    "PortMaster",
    "westonwrap",
    "weston_pkg.squashfs",
    "Crusty",
    "crusty_gbm",
    "libcrusty",
    "Bifrost",
    "r13p0",
    "/opt/system/Tools",
    "/roms/ports/PortMaster",
    "/opt/tools/PortMaster",
]

ABS_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"(/(?:usr|lib|etc|opt|run|dev|sys|proc|boot|roms|home|mnt|tmp|var)/"
    r"[A-Za-z0-9_./\${}:+@=~-]+)"
)
CMDV_RE = re.compile(r"\bcommand\s+-v\s+([A-Za-z0-9_.+-]+)")
UNIT_RE = re.compile(r"\b([A-Za-z0-9_.@-]+\.(?:service|path|timer|target|socket))\b")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_text_if_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:65536]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", "replace")


def file_kind(path: Path) -> str:
    try:
        out = subprocess.check_output(["file", "-b", str(path)], text=True)
        return out.strip()
    except Exception:
        return ""


def elf_deps(path: Path) -> dict:
    if not shutil.which("readelf"):
        return {}
    kind = file_kind(path)
    if "ELF" not in kind:
        return {}
    result = {"file": path.name, "kind": kind, "interpreter": None, "needed": []}
    try:
        ph = subprocess.check_output(
            ["readelf", "-l", str(path)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        m = re.search(r"Requesting program interpreter:\s*([^\]]+)", ph)
        if m:
            result["interpreter"] = m.group(1).strip()
    except Exception:
        pass
    try:
        dyn = subprocess.check_output(
            ["readelf", "-d", str(path)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        result["needed"] = re.findall(r"Shared library: \[([^\]]+)\]", dyn)
    except Exception:
        pass
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--json", dest="json_path", type=Path)
    ap.add_argument("--text", dest="text_path", type=Path)
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")

    paths = Counter()
    commands = Counter()
    units = Counter()
    legacy_hits = []
    elfs = []
    files = []

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = str(path.relative_to(root))
        files.append({"path": rel, "size": path.stat().st_size, "sha256": sha256(path)})
        text = read_text_if_text(path)
        if text is not None:
            for m in CMDV_RE.finditer(text):
                commands[m.group(1)] += 1
            for m in ABS_PATH_RE.finditer(text):
                paths[m.group(1).rstrip(".,;:)\"'")] += 1
            for m in UNIT_RE.finditer(text):
                units[m.group(1)] += 1
            low = text.lower()
            for marker in LEGACY_MARKERS:
                if marker.lower() in low:
                    legacy_hits.append({"path": rel, "marker": marker})
        dep = elf_deps(path)
        if dep:
            dep["path"] = rel
            elfs.append(dep)

    result = {
        "format": "R36OS_NATIVE_DEPENDENCY_SCAN_V1",
        "root": str(root),
        "file_count": len(files),
        "files": files,
        "command_v_dependencies": dict(commands.most_common()),
        "absolute_paths": dict(paths.most_common()),
        "systemd_units": dict(units.most_common()),
        "legacy_hits": legacy_hits,
        "elf_dependencies": elfs,
    }

    lines = [
        "R36OS native dependency scan",
        f"root={root}",
        f"file_count={len(files)}",
        "",
        "[command-v]",
    ]
    lines.extend(f"{count}\t{name}" for name, count in commands.most_common())
    lines += ["", "[systemd-units]"]
    lines.extend(f"{count}\t{name}" for name, count in units.most_common())
    lines += ["", "[legacy-markers]"]
    lines.extend(f"{x['marker']}\t{x['path']}" for x in legacy_hits)
    lines += ["", "[elf-needed]"]
    for e in elfs:
        lines.append(
            f"{e['path']}\tinterp={e.get('interpreter') or '-'}"
            f"\tneeded={','.join(e.get('needed') or [])}"
        )
    lines += ["", "[absolute-paths]"]
    lines.extend(f"{count}\t{name}" for name, count in paths.most_common())
    text_out = "\n".join(lines) + "\n"

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if args.text_path:
        args.text_path.parent.mkdir(parents=True, exist_ok=True)
        args.text_path.write_text(text_out)
    if not args.json_path and not args.text_path:
        print(text_out, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
