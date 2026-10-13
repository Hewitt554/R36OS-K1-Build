import gzip
import pathlib
import struct
import sys
import zlib

HEADER = struct.Struct('>7I4B32s')
def files_newc(raw):
  out = {}
  pos = 0
  while True:
    if pos + 110 > len(raw): raise ValueError('truncated cpio header')
    h = raw[pos:pos + 110]
    if h[:6] != b'070701': raise ValueError('invalid cpio magic')
    v = [int(h[i:i+8], 16) for i in range(6, 110, 8)]
    size, namesz = v[6], v[11]
    pos += 110
    if not 1 <= namesz <= 4096 or pos + namesz > len(raw): raise ValueError('invalid name')
    name = raw[pos:pos+namesz]
    if not name.endswith(b'\0'): raise ValueError('name terminator')
    name = name[:-1].decode('utf-8')
    if name.startswith('./'): name = name[2:]
    pos = (pos + namesz + 3) & ~3
    if pos + size > len(raw): raise ValueError('truncated data')
    data = raw[pos:pos+size]
    pos = (pos + size + 3) & ~3
    if name == 'TRAILER!!!': break
    if name in out or name.startswith('/') or '..' in pathlib.PurePosixPath(name).parts: raise ValueError('unsafe or duplicate cpio entry')
    out[name] = data
  return out

def verify(blob, image):
  data, u = pathlib.Path(blob).read_bytes(), pathlib.Path(image).read_bytes()
  if len(u) < 64: raise ValueError('truncated uImage')
  magic, crc, timestamp, size, load, entry, dcrc, osid, arch, typ, comp, name = HEADER.unpack(u[:64])
  if (magic, osid, arch, typ, comp) != (0x27051956, 5, 22, 3, 1): raise ValueError('uImage identity mismatch')
  hb = bytearray(u[:64]); hb[4:8] = b'\0'*4
  if zlib.crc32(hb) & 0xffffffff != crc: raise ValueError('uImage header CRC mismatch')
  if u[64:] != data or size != len(data) or zlib.crc32(data) & 0xffffffff != dcrc: raise ValueError('uImage data CRC mismatch')
  items = files_newc(gzip.decompress(data))
  for key in ('init', 'bin/busybox', 'bin/sh', 'sbin/r36os-rescue-status', 'etc/r36os-rescue-release'):
    if key not in items: raise ValueError('missing required cpio entry: '+key)
  if not items['bin/busybox'].startswith(b'\x7fELF'): raise ValueError('BusyBox not ELF')
  for key in ('init','sbin/r36os-rescue-status'):
    code = items[key].decode('utf-8')
    for forbidden in ('mkfs.', 'wipefs ', 'sfdisk ', 'dd if=', 'mount -o rw'):
      if forbidden in code: raise ValueError('rescue write primitive in '+key)
  print('PASS: ARM64 diagnostic rescue uInitrd validated; no hardware boot claim')
if __name__ == '__main__':
  if len(sys.argv) != 3: raise SystemExit(2)
  verify(sys.argv[1], sys.argv[2])
