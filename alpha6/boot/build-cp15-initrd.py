#!/usr/bin/env python3
"""R36OS CP15: make two diagnostic-only K1 native-root initramfs header variants.

No block I/O, SD writes, U-Boot installation or automatic recovery.
Requires a pinned K1 ABI and an explicitly verified *scratch* ext4 root UUID.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import zlib

VERSION = '6.12.94-r36os-k1'
UUID_PATTERN = re.compile(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z')
APPLET_NAMES = ('sh', 'mount', 'mdev', 'mkdir', 'sleep', 'cat', 'blkid', 'grep',
                'uname', 'switch_root')
U_HEADER = struct.Struct('>7I4B32s')
MARKER = 'CP15_K1_NATIVE_ROOT_NOT_BOOT_TESTED'

class UnsafeInput(ValueError):
    pass


def require_uuid(value: str) -> str:
    if not UUID_PATTERN.fullmatch(value) or value == 'e139ce78-9841-40fe-8823-96a304a09859':
        raise UnsafeInput('requires distinct lowercase native scratch ext4 UUID')
    return value


def safe_dir(path: Path) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise UnsafeInput('output workspace missing or unsafe')
    result = path.resolve(strict=True)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if temp not in result.parents or not result.name.startswith('r36os-cp15-initrd-'):
        raise UnsafeInput('output must be a specially named disposable temporary directory')
    for name in ('CP15-ARM-UNTESTED.uInitrd', 'CP15-ARM64-UNTESTED.uInitrd',
                 'CP15-BOOTARGS-SAMPLE-NOT-INSTALL.txt', 'cp15-initrd-report.json'):
        if (result / name).exists() or (result / name).is_symlink():
            raise UnsafeInput('refusing output overwrite: ' + name)
    return result


def read_busybox(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise UnsafeInput('BusyBox must be a regular executable file')
    b = path.read_bytes()
    if not 64 <= len(b) <= 10 * 1024 * 1024 or b[:6] != b'\x7fELF\x02\x01':
        raise UnsafeInput('not expected 64-bit little-endian ELF BusyBox')
    if struct.unpack_from('<H', b, 18)[0] != 183:  # EM_AARCH64
        raise UnsafeInput('BusyBox ELF is not ARM64')
    phoff = struct.unpack_from('<Q', b, 32)[0]
    phentsize, phnum = struct.unpack_from('<HH', b, 54)
    if phnum > 256 or phentsize < 56 and phnum > 0 or phoff + phentsize*phnum > len(b):
        raise UnsafeInput('invalid BusyBox ELF program header')
    for i in range(phnum):
        if struct.unpack_from('<I', b, phoff + i*phentsize)[0] == 3:  # PT_INTERP
            raise UnsafeInput('BusyBox is dynamically linked; rescue needs static binary')
    return b


def cpio_entry(name: str, mode: int, contents: bytes, number: int, rdevmajor=0, rdevminor=0) -> bytes:
    path = name.encode('ascii') + b'\0'
    fields = (number, mode, 0, 0, 1, 0, len(contents), 0, 0,
              rdevmajor, rdevminor, len(path), 0)
    header = b'070701' + b''.join(('%08x' % n).encode('ascii') for n in fields)
    result = header + path
    result += b'\0' * ((-len(result)) % 4)
    result += contents
    result += b'\0' * ((-len(result)) % 4)
    return result


def pack_cpio(init_script: bytes, busybox: bytes, uuid: str) -> bytes:
    files = [('dev', stat.S_IFDIR | 0o755, b'', 0, 0),
             ('proc', stat.S_IFDIR | 0o755, b'', 0, 0),
             ('sys', stat.S_IFDIR | 0o755, b'', 0, 0),
             ('run', stat.S_IFDIR | 0o755, b'', 0, 0),
             ('newroot', stat.S_IFDIR | 0o755, b'', 0, 0),
             ('bin', stat.S_IFDIR | 0o755, b'', 0, 0),
             ('dev/console', stat.S_IFCHR | 0o600, b'', 5, 1),
             ('dev/null', stat.S_IFCHR | 0o666, b'', 1, 3),
             ('bin/busybox', stat.S_IFREG | 0o755, busybox, 0, 0),
             ('init', stat.S_IFREG | 0o755, init_script, 0, 0)]
    for applet in APPLET_NAMES:
        files.append(('bin/' + applet, stat.S_IFLNK | 0o777, b'busybox', 0, 0))
    files.append(('etc', stat.S_IFDIR | 0o755, b'', 0, 0))
    files.append(('etc/cp15-boot-contract', stat.S_IFREG | 0o444,
                  ('CP15_PREVIEW_ONLY=1\nROOT_UUID=' + uuid + '\nKERNEL_RELEASE=' + VERSION + '\n').encode(),0,0))
    files = sorted(files, key=lambda x: x[0])
    result = b''
    for i, (name, mode, body, maj, minr) in enumerate(files, 1):
        result += cpio_entry(name,mode,body,i,maj,minr)
    result += cpio_entry('TRAILER!!!',0,b'',len(files)+1)
    return result


def uimage(gzip_payload: bytes, arch: int) -> bytes:
    if arch not in (2,22):
        raise UnsafeInput('unsupported U-Boot architecture ID')
    name = b'R36OS CP15 K1 NATIVE TEST'
    header = bytearray(U_HEADER.pack(0x27051956,0,0,len(gzip_payload),0,0,
                     zlib.crc32(gzip_payload) & 0xffffffff,5,arch,3,1,name.ljust(32,b'\0')))
    header[4:8] = struct.pack('>I',zlib.crc32(header) & 0xffffffff)
    return bytes(header) + gzip_payload


def verify_uimage(u: bytes, expected_arch: int, source: bytes | None = None):
    if len(u) < 65: raise UnsafeInput('short U-Boot image')
    m, hc, _, size, _, _, dc, osid, arch, typ, comp, _ = U_HEADER.unpack(u[:64])
    h=bytearray(u[:64]); h[4:8] = bytes(4)
    if (m,osid,arch,typ,comp)!=(0x27051956,5,expected_arch,3,1):
        raise UnsafeInput('U-Boot header identity or architecture mismatch')
    if zlib.crc32(h)&0xffffffff!=hc or size!=len(u)-64 or zlib.crc32(u[64:])&0xffffffff!=dc:
        raise UnsafeInput('U-Boot header CRC, length or payload CRC mismatch')
    if source is not None and u[64:] != source:
        raise UnsafeInput('U-Boot payload differs from expected initramfs')
    if not gzip.decompress(u[64:]).startswith(b'070701'):
        raise UnsafeInput('payload not newc CPIO')
    return True


def generate(busybox_path: Path, init_path: Path, output_dir: Path, native_uuid: str):
    native_uuid = require_uuid(native_uuid)
    output = safe_dir(output_dir)
    bb=read_busybox(busybox_path)
    if init_path.is_symlink() or not init_path.is_file():
        raise UnsafeInput('native init source missing')
    script=init_path.read_bytes()
    if not script.startswith(b'#!/bin/sh\n') or b'r36os.root_uuid=' not in script or b'/bin/switch_root' not in script:
        raise UnsafeInput('required native boot identity and handoff absent')
    if b'e139ce78-9841-40fe-8823-96a304a09859' in script:
        raise UnsafeInput('inherited R3 UUID must not be referenced')
    raw=pack_cpio(script,bb,native_uuid)
    gz=gzip.compress(raw,compresslevel=9,mtime=0)
    output_files={}
    for arch,filename in ((2,'CP15-ARM-UNTESTED.uInitrd'),(22,'CP15-ARM64-UNTESTED.uInitrd')):
        data=uimage(gz,arch)
        verify_uimage(data,arch,gz)
        target=output/filename
        with target.open('xb') as f: f.write(data)
        output_files[str(arch)]={'file':filename,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    args=('console=ttyFIQ0,115200 rdinit=/init r36os.boot_mode=native-dev '
          'r36os.root_uuid=' + native_uuid + ' r36os.kernel_release=' + VERSION + '\n')
    with (output/'CP15-BOOTARGS-SAMPLE-NOT-INSTALL.txt').open('x') as f:
        f.write('SAMPLE ONLY - DO NOT INSTALL BOOT.INI OR FLASH SD\n'+args)
    report={'format':MARKER,'safe_to_flash':False,'boot_tested':False,
            'native_root_uuid':native_uuid,'kernel_release':VERSION,
            'initrd_files':output_files,'compressed_payload_bytes':len(gz),
            'cpio_filesystem_bytes':len(raw),'busybox_bytes':len(bb),
            'root_mount':'READ_ONLY; ext4 noload; no partition updates',
            'boot_critical_module_support':'NOT VERIFIED: MMC/ext4 must be built into K1 or included in an early module bundle',
            'hardware_compatibility':'UNTESTED Panel4/U-Boot; ARM and ARM64 header variants are alternatives, not interchangeable claims'}
    with (output/'cp15-initrd-report.json').open('x') as f:
        json.dump(report,f,indent=2,sort_keys=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--busybox',type=Path,required=True)
    p.add_argument('--init-script',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--native-root-uuid',required=True)
    a=p.parse_args()
    r=generate(a.busybox,a.init_script,a.output_dir,a.native_root_uuid)
    print('CP15 ARM64 native initrd staging PASS; NOT BOOT TESTED;',r['compressed_payload_bytes'],'bytes payload')
if __name__=='__main__':main()