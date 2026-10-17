#!/usr/bin/env python3
"""CP12 four-partition disposable image assembler. NEVER accepts device paths.

Input files must have exact allowlisted names in a marker-bound TEMP workspace.
Creates a separate normal regular file with O_EXCL; no flash or SD access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import tempfile

SECTOR = 512
MIB = 1024 * 1024
GAP_MIB = 16
MARKER = b'R36OS_CP12_NONBOOTABLE_DISK_FIXTURE_V1\n'
PARTITIONS = (
    ('boot.fat', 'R36BOOT', 0x0c, 128),
    ('root.ext4', 'R36SYS', 0x83, 1024),
    ('update.fat', 'R36UPDATE', 0x0c, 64),
    ('state.ext4', 'R36STATE', 0x83, 128),
)
OUTPUT = 'cp12-NONBOOTABLE.img'
REPORT = 'cp12-image-report.json'


class Reject(ValueError):
    pass


def regular(p: Path) -> bool:
    try:
        return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError:
        return False


def safe_workspace(base: Path) -> Path:
    base = Path(base)
    if base.is_symlink() or not base.is_dir():
        raise Reject('workspace is not a real directory')
    resolved = base.resolve(strict=True)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if temp not in resolved.parents or not resolved.name.startswith('r36os-cp12-image-'):
        raise Reject('only disposable temporary workspaces allowed')
    marker = resolved/'.cp12-fixture-id'
    if not regular(marker) or marker.read_bytes() != MARKER:
        raise Reject('missing CP12 disposable identity')
    for name in [x[0] for x in PARTITIONS] + [OUTPUT, REPORT]:
        p = resolved/name
        if p.is_symlink() or (p.exists() and not regular(p)):
            raise Reject('unexpected image path or symlink: '+name)
    return resolved


def layout():
    sector = GAP_MIB * MIB // SECTOR
    entries = []
    for name, label, ptype, mib in PARTITIONS:
        count = mib*MIB//SECTOR
        if sector+count >= 2**32:
            raise Reject('MBR sector range exceeded')
        entries.append({'name': name, 'label': label, 'type': ptype,
                        'start': sector, 'sectors': count, 'bytes': mib*MIB})
        sector += count
    return entries, sector*SECTOR


def mbr(entries):
    result = bytearray(512)
    # Disk ID fixed for reproducible CI only. This is NOT a release disk ID.
    result[440:444] = bytes.fromhex('c012a612')
    for index, entry in enumerate(entries):
        offset = 446+16*index
        result[offset+4] = entry['type']
        struct.pack_into('<II', result, offset+8, entry['start'], entry['sectors'])
    result[510:512] = b'\x55\xaa'
    return bytes(result)


def parse_mbr(data: bytes):
    if len(data) != 512 or data[-2:] != b'\x55\xaa':
        raise Reject('invalid MBR signature')
    entries=[]
    for index in range(4):
        e = data[446+16*index:446+16*(index+1)]
        start, sectors = struct.unpack_from('<II',e,8)
        if e[0] != 0 or e[4] not in (0x0c,0x83) or not start or not sectors:
            raise Reject('unexpected MBR entry')
        entries.append((e[4], start, sectors))
    for i in range(1,len(entries)):
        if entries[i][1] < entries[i-1][1]+entries[i-1][2]:
            raise Reject('overlapping MBR partitions')
    return entries


def sha256_file(p: Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4*MIB),b''):
            h.update(b)
    return h.hexdigest()


def validate_partition(p: Path, entry: dict):
    if not regular(p) or p.stat().st_size != entry['bytes']:
        raise Reject('missing or wrong-sized source image '+entry['name'])
    with p.open('rb') as f:
        if entry['type'] == 0x83:
            f.seek(1080)
            if f.read(2) != b'\x53\xef':
                raise Reject('ext4 superblock magic invalid '+entry['name'])
        else:
            f.seek(0)
            sector=f.read(512)
            if sector[510:512] != b'\x55\xaa' or sector[0x52:0x5a] != b'FAT32   ':
                raise Reject('FAT32 VBR invalid '+entry['name'])
    return {'sha256':sha256_file(p),'bytes':p.stat().st_size}


def copy_nonzero(src: Path, output, offset: int):
    with src.open('rb') as f:
        at=offset
        while block := f.read(4*MIB):
            if block.strip(b'\x00'):
                output.seek(at)
                output.write(block)
            at += len(block)
    output.flush()
    os.fsync(output.fileno())


def segment_sha256(path: Path, start: int, length: int) -> str:
    h=hashlib.sha256()
    with path.open('rb') as stream:
        stream.seek(start)
        while length:
            block=stream.read(min(4*MIB,length))
            if not block:
                raise Reject('unexpected end of assembled partition')
            h.update(block)
            length -= len(block)
    return h.hexdigest()


def assemble(base: Path):
    base=safe_workspace(base)
    parts, total=layout()
    if (base/OUTPUT).exists() or (base/REPORT).exists():
        raise Reject('will not overwrite a previous artifact')
    checks={p['name']:validate_partition(base/p['name'],p) for p in parts}
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,'O_NOFOLLOW'):flags |= os.O_NOFOLLOW
    output=base/OUTPUT
    with os.fdopen(os.open(output, flags, 0o600),'w+b') as stream:
        stream.truncate(total)
        stream.write(mbr(parts))
        for part in parts:
            copy_nonzero(base/part['name'],stream,part['start']*SECTOR)
        stream.flush()
        os.fsync(stream.fileno())
    with output.open('rb') as f:
        parsed=parse_mbr(f.read(512))
        if parsed != [(p['type'],p['start'],p['sectors']) for p in parts]:
            raise Reject('assembled MBR validation mismatch')
        for p in parts:
            if segment_sha256(output, p['start']*SECTOR, p['bytes']) != checks[p['name']]['sha256']:
                raise Reject('assembled partition bytes differ from verified source '+p['name'])
            f.seek(p['start']*SECTOR + (1080 if p['type']==0x83 else 0))
            head=f.read(2 if p['type']==0x83 else 3)
            if head != (b'\x53\xef' if p['type']==0x83 else b'\xeb\x58\x90') and not (p['type']==0x0c and head[:1] in (b'\xeb', b'\xe9')):
                raise Reject('assembled partition signature mismatch')
        # The first 16 MiB is deliberately devoid of ROM bootloader bytes.
        f.seek(512)
        if any(f.read((GAP_MIB*MIB)-512)):
            raise Reject('early boot gap not empty: unsafe test media')
    report={
        'format':'R36OS_CP12_NONBOOTABLE_IMAGE_FIXTURE',
        'safe_to_flash':False,
        'bootloader':'ABSENT; first 16 MiB after MBR contains no bootloader',
        'boot_script':'ABSENT; no working original R3 boot.ini',
        'kernel':'ABSENT; K1 physical boot not verified',
        'rootfs':'CP06 native ARM64 Debian root; not a complete R36OS UI',
        'recovery':'CP07 ramdisk staged only; no installed boot gate or restore capability',
        'total_bytes':total,
        'sha256':sha256_file(output),
        'partitions':[{**p,**checks[p['name']]} for p in parts],
        'notes':'Scaled CI fixture only, NOT the proposed 512MiB/8GiB/1GiB layout',
    }
    (base/REPORT).write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('workspace',type=Path)
    args=cli.parse_args()
    info=assemble(args.workspace)
    print('CP12 disposable 4-partition image assembled, size:',info['total_bytes'])
    print('CP12 NONBOOTABLE; do NOT flash this fixture')
    print('sha256:',info['sha256'])

if __name__=='__main__':main()