#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: make_rootfs_manifest.py <root>")

root = Path(sys.argv[1]).resolve()

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

print("path\ttype\tmode\tuid\tgid\tsize\tsha256_or_target")
for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
    dirnames.sort()
    filenames.sort()
    base = Path(dirpath)
    names = list(dirnames) + list(filenames)
    for name in names:
        p = base / name
        rel = "/" + str(p.relative_to(root))
        st = os.lstat(p)
        mode = f"{stat.S_IMODE(st.st_mode):04o}"
        if stat.S_ISLNK(st.st_mode):
            typ = "symlink"
            size = st.st_size
            value = os.readlink(p)
        elif stat.S_ISREG(st.st_mode):
            typ = "file"
            size = st.st_size
            value = digest(p)
        elif stat.S_ISDIR(st.st_mode):
            typ = "dir"
            size = 0
            value = "-"
        elif stat.S_ISCHR(st.st_mode):
            typ = "char"
            size = 0
            value = f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"
        elif stat.S_ISBLK(st.st_mode):
            typ = "block"
            size = 0
            value = f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"
        elif stat.S_ISFIFO(st.st_mode):
            typ = "fifo"
            size = 0
            value = "-"
        else:
            typ = "other"
            size = st.st_size
            value = "-"
        print(f"{rel}\t{typ}\t{mode}\t{st.st_uid}\t{st.st_gid}\t{size}\t{value}")
