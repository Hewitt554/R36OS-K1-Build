#!/usr/bin/env python3
from pathlib import Path
import struct, sys

if len(sys.argv) != 3 or sys.argv[1] not in {"dirty", "assert-clean"}:
    raise SystemExit("usage: fat_fixture_tool.py dirty|assert-clean IMAGE")
mode, name = sys.argv[1], sys.argv[2]
p = Path(name)
b = bytearray(p.read_bytes())
if len(b) < 4096:
    raise SystemExit("image too small")
sector_size = struct.unpack_from("<H", b, 11)[0]
reserved = struct.unpack_from("<H", b, 14)[0]
fats = b[16]
fat_len = struct.unpack_from("<I", b, 36)[0]
if sector_size not in (512,1024,2048,4096) or reserved < 1 or fats < 1 or fat_len < 1:
    raise SystemExit("not expected FAT32 layout")
fat0 = reserved * sector_size

def entry1_at(off):
    return struct.unpack_from("<I", b, off + 4)[0]

if mode == "dirty":
    b[65] |= 0x01
    for i in range(fats):
        off = fat0 + i * fat_len * sector_size
        e = entry1_at(off) & ~0x08000000
        struct.pack_into("<I", b, off + 4, e)
    p.write_bytes(b)
else:
    if b[65] & 1:
        raise SystemExit(f"boot dirty bit remains: {b[65]:02x}")
    for i in range(fats):
        off = fat0 + i * fat_len * sector_size
        e = entry1_at(off)
        if not (e & 0x08000000):
            raise SystemExit(f"FAT copy {i} clean-shutdown bit remains clear: {e:08x}")
