#!/usr/bin/env python3
"""Read-only, Windows-friendly inspector for Alpha 5R3 MBR + FAT32 boot files.

No mounting, drivers, writes to source image, or third-party dependencies.
Output is written only alongside this script. This is not a filesystem fsck.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

REFERENCE_SHA256 = '5cdec71b14a94845efe696ea73aacb4f629d0925a3c5c484439738b755cc2219'
REFERENCE_IMAGE_SIZE = 18375245824
REFERENCE_BOOT_START = 32768
REFERENCE_BOOT_SECTORS = 229376


def le16(b: bytes, pos: int) -> int:
    return struct.unpack_from('<H', b, pos)[0]


def le32(b: bytes, pos: int) -> int:
    return struct.unpack_from('<I', b, pos)[0]


class FAT32Boot:
    def __init__(self, fileobj):
        self.f = fileobj
        self.f.seek(0, os.SEEK_END)
        self.image_size = self.f.tell()
        if self.image_size < 512:
            raise ValueError('Image too short to contain an MBR')
        self.f.seek(0)
        mbr = self.f.read(512)
        if mbr[510:512] != b'\x55\xaa':
            raise ValueError('Missing MBR 0x55AA signature')
        p1 = mbr[446:462]
        self.partition_type = p1[4]
        self.partition_start = le32(p1, 8)
        self.partition_sectors = le32(p1, 12)
        if self.partition_type not in (0x0b, 0x0c):
            raise ValueError('Partition 1 is not FAT32 (type 0x0B/0x0C)')
        self.part_off = self.partition_start * 512
        self.f.seek(self.part_off)
        bp = self.f.read(512)
        if bp[510:512] != b'\x55\xaa':
            raise ValueError('Missing FAT32 boot-sector signature')
        self.sector_size = le16(bp, 11)
        self.cluster_sectors = bp[13]
        self.reserved_sectors = le16(bp, 14)
        self.fat_count = bp[16]
        self.fat_sectors = le32(bp, 36)
        self.root_cluster = le32(bp, 44)
        self.fs_label = bp[71:82].decode('ascii', 'replace').strip()
        fs_magic = bp[82:90]
        self.data_start = self.part_off + (self.reserved_sectors + self.fat_count * self.fat_sectors) * self.sector_size
        self.fat_start = self.part_off + self.reserved_sectors * self.sector_size
        if self.sector_size != 512 or not 1 <= self.cluster_sectors <= 128 or (self.cluster_sectors & (self.cluster_sectors - 1)):
            raise ValueError('Unexpected FAT32 sector/cluster geometry')
        if not self.fat_count or not self.reserved_sectors or not self.fat_sectors or self.root_cluster < 2 or fs_magic[:5] != b'FAT32':
            raise ValueError('Invalid or unsupported FAT32 boot parameters')
        total_bytes = self.partition_sectors * 512
        if self.part_off + total_bytes > self.image_size:
            raise ValueError('FAT32 partition extends past image size')
        data_sectors = total_bytes // self.sector_size - (self.reserved_sectors + self.fat_count * self.fat_sectors)
        self.max_cluster = 1 + data_sectors // self.cluster_sectors
        if self.max_cluster < 2:
            raise ValueError('No usable FAT32 data clusters')

    def cluster_offset(self, cluster: int) -> int:
        if not (2 <= cluster <= self.max_cluster):
            raise ValueError('FAT32 cluster out of range: ' + str(cluster))
        return self.data_start + (cluster - 2) * self.cluster_sectors * self.sector_size

    def clusters(self, start: int, max_clusters: int = 16384):
        seen = set()
        c = start
        while True:
            if c in seen:
                raise ValueError('FAT32 cluster loop')
            if len(seen) >= max_clusters:
                raise ValueError('FAT32 cluster chain exceeds safety limit')
            seen.add(c)
            self.cluster_offset(c)
            yield c
            self.f.seek(self.fat_start + c * 4)
            nxt_bytes = self.f.read(4)
            if len(nxt_bytes) != 4:
                raise ValueError('Truncated FAT32 FAT')
            nxt = le32(nxt_bytes, 0) & 0x0fffffff
            if nxt >= 0x0ffffff8:
                break
            if nxt == 0 or nxt == 1 or nxt == 0x0ffffff7:
                raise ValueError('Unexpected FAT32 free/reserved/bad cluster in chain')
            c = nxt

    def directory(self, cluster: int, max_bytes: int = 2 * 1024 * 1024):
        result = []
        bytes_read = 0
        pending_lfn = []
        for c in self.clusters(cluster, max_clusters=512):
            self.f.seek(self.cluster_offset(c))
            block = self.f.read(self.cluster_sectors * self.sector_size)
            bytes_read += len(block)
            if bytes_read > max_bytes:
                raise ValueError('Directory exceeds safety limit')
            for off in range(0, len(block), 32):
                entry = block[off:off + 32]
                if not entry or entry[0] == 0:
                    return result
                if entry[0] == 0xe5:
                    pending_lfn = []
                    continue
                attr = entry[11]
                if attr == 0x0f:
                    b = entry[1:11] + entry[14:26] + entry[28:32]
                    pending_lfn.append((entry[0] & 0x1f, b.decode('utf-16le', 'replace').rstrip('\uffff\x00')))
                    continue
                if attr & 0x08:
                    pending_lfn = []
                    continue
                short = entry[:8].decode('ascii','replace').strip()
                ext = entry[8:11].decode('ascii','replace').strip()
                if short[:1] == '\x05':
                    short = '\xe5' + short[1:]
                short = short + ('.' + ext if ext else '')
                name = ''.join(s for _, s in sorted(pending_lfn)) if pending_lfn else short
                pending_lfn = []
                result.append({'name': name, 'short': short,
                               'cluster': (le16(entry, 20) << 16) | le16(entry, 26),
                               'size': le32(entry, 28), 'directory': bool(attr & 0x10)})
        return result

    def read_file(self, item, max_bytes=2 * 1024 * 1024) -> bytes:
        if item['directory']:
            raise ValueError('Cannot read a directory as a file')
        size = item['size']
        if size > max_bytes:
            raise ValueError('File larger than maximum inspection size')
        if size == 0:
            return b''
        b = bytearray()
        for c in self.clusters(item['cluster'], max_clusters=max_bytes // (self.sector_size * self.cluster_sectors) + 2):
            self.f.seek(self.cluster_offset(c))
            b.extend(self.f.read(min(size-len(b), self.cluster_sectors * self.sector_size)))
            if len(b) >= size:
                break
        if len(b) != size:
            raise ValueError('File truncated in FAT32 cluster chain')
        return bytes(b)


def boot_lines(content: str):
    # Only show boot-choice-relevant commands. Do not echo network credentials or tokens.
    lines=[]
    for line in content.splitlines():
        s=line.strip()
        if (s.startswith('setenv bootargs ') or
            re.match(r'^(?:if|then|else|fi|fatload|fatls|fatwrite|fatsize|load|source|booti|bootm|bootz|run|test|env|saveenv|ext4load|setexpr|echo)\b', s, re.I)):
            if any(x in s.lower() for x in ('password','token=','secret','github_pat','bearer ')):
                continue
            lines.append(s[:280])
    return lines[:120]


def audit(path: Path):
    with path.open('rb') as f:
        fat = FAT32Boot(f)
        entries = fat.directory(fat.root_cluster)
        bootfiles = [e for e in entries if e['name'].casefold() in ('boot.ini','boot.scr','boot.cmd','boot.txt')]
        files=[]
        for e in bootfiles:
            b=fat.read_file(e)
            files.append({'name':e['name'],'size':e['size'], 'sha256':hashlib.sha256(b).hexdigest(),
                          'relevant_lines':boot_lines(b.decode('utf-8','replace'))})
        return {
            'status':'PASS', 'read_only':True,
            'image_basename':path.name,
            'image_size':fat.image_size,
            'reference_image_size_matches':fat.image_size == REFERENCE_IMAGE_SIZE,
            'mbr_partition1':{'type':hex(fat.partition_type),'start_sector':fat.partition_start,
                              'sectors':fat.partition_sectors,'matches_reference':fat.partition_start==REFERENCE_BOOT_START and fat.partition_sectors==REFERENCE_BOOT_SECTORS},
            'fat32':{'label':fat.fs_label,'sector_size':fat.sector_size,'cluster_sectors':fat.cluster_sectors,
                     'reserved_sectors':fat.reserved_sectors,'fat_count':fat.fat_count,'fat_sectors':fat.fat_sectors,
                     'root_cluster':fat.root_cluster},
            'root_entries':[{k:v for k,v in e.items() if k in ('name','short','size','directory')} for e in entries],
            'boot_scripts': files, 'warnings': [] if files else ['No top-level boot.ini/boot script found; inspect root_entries'],
            'note':'Only FAT32 boot metadata and selected boot scripts inspected; this is NOT a boot or ext4 filesystem test.'
        }


def main(argv):
    if len(argv) != 2:
        print('Usage: python audit_r36os_boot.py "C:\\path\\R36OS-Alpha5R3....img"')
        return 2
    p=Path(argv[1]).expanduser()
    output = Path(__file__).resolve().parent
    try:
        result = audit(p)
    except (ValueError, OSError, struct.error) as e:
        result = {'status':'FAIL','image_basename':p.name,'error':str(e),'read_only':True}
    (output/'R36OS_R3_BOOT_AUDIT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['R36OS CP01 -- FAT32 boot-content audit', 'Status: '+result['status'],
           'Source image (read only): '+str(result['image_basename'])]
    if result['status'] == 'PASS':
        lines+=['Partition 1 reference match: '+str(result['mbr_partition1']['matches_reference']),
                'FAT volume: '+result['fat32']['label'],
                'Root directory files: '+str(len(result['root_entries'])),
                'Boot script matches: '+str(len(result['boot_scripts']))]
        for item in result['boot_scripts']:
            lines+=['', '== '+item['name']+' ('+str(item['size'])+' bytes) ==', 'SHA256: '+item['sha256']]
            lines.extend(item['relevant_lines'])
        lines+=['','Warnings: '+(', '.join(result['warnings']) if result['warnings'] else 'none'),
                'This tool did not modify or mount your image.']
    else:
        lines+=['Error: '+result['error']]
    (output/'R36OS_R3_BOOT_AUDIT.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines[:9]))
    print('\nReports saved beside audit_r36os_boot.py')
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main(sys.argv))