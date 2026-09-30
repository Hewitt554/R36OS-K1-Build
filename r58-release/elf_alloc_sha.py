#!/usr/bin/env python3
from pathlib import Path
import hashlib
import struct
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: elf_alloc_sha.py <elf64-le>")

b = Path(sys.argv[1]).read_bytes()
if len(b) < 64 or b[:4] != b"\x7fELF" or b[4] != 2 or b[5] != 1:
    raise SystemExit("expected ELF64 little-endian input")

e_shoff = struct.unpack_from("<Q", b, 0x28)[0]
e_shentsize = struct.unpack_from("<H", b, 0x3A)[0]
e_shnum = struct.unpack_from("<H", b, 0x3C)[0]
if not e_shoff or e_shentsize < 64 or not e_shnum:
    raise SystemExit("missing section table")

h = hashlib.sha256()
alloc_count = 0
for i in range(e_shnum):
    off = e_shoff + i * e_shentsize
    if off + 64 > len(b):
        raise SystemExit("section table outside file")
    sh_type = struct.unpack_from("<I", b, off + 4)[0]
    sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from("<QQQQ", b, off + 8)
    sh_addralign = struct.unpack_from("<Q", b, off + 48)[0]
    if not (sh_flags & 0x2):  # SHF_ALLOC
        continue
    alloc_count += 1
    h.update(struct.pack("<IQQQQ", sh_type, sh_flags, sh_addr, sh_size, sh_addralign))
    if sh_type != 8:  # SHT_NOBITS
        end = sh_offset + sh_size
        if end > len(b):
            raise SystemExit("allocated section outside file")
        h.update(b[sh_offset:end])

if not alloc_count:
    raise SystemExit("no SHF_ALLOC sections")
print(h.hexdigest())
