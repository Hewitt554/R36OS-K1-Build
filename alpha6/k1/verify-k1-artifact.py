#!/usr/bin/env python3
"""Read-only validation of a K1 result archive. NOT a flashing or boot utility."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, tarfile, zlib
from pathlib import Path, PurePosixPath

REQUIRED=('Image','uInitrd','rk3326-r36s-k1.dtb','modules.tar.xz','K1.conf','BUILD_INFO.txt','MANIFEST.sha256')
STAGE=('Image','uInitrd','rk3326-r36s-k1.dtb')
EXPECTED_ROOT='e139ce78-9841-40fe-8823-96a304a09859'
EXPECTED_STATE='a25488c6-742d-4555-82d1-e28ffc848af3'

class Invalid(ValueError): pass

def norm_member(name):
    p=PurePosixPath(name)
    if not name or name.startswith('/') or '\\' in name or '..' in p.parts or '\x00' in name:
        raise Invalid('unsafe member path')
    value=str(p)
    if value=='.': raise Invalid('invalid member path')
    return value

def digest(stream, size=None):
    h=hashlib.sha256(); count=0
    for block in iter(lambda:stream.read(4*1024*1024),b''):
        count+=len(block); h.update(block)
    if size is not None and count!=size: raise Invalid('truncated archive member')
    return h.hexdigest(),count

def parse_manifest(data):
    try: text=data.decode('utf-8')
    except UnicodeDecodeError as e: raise Invalid('non-UTF8 K1 manifest') from e
    result={}
    for line in text.splitlines():
        if not line.strip(): continue
        m=re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.+)',line)
        if not m: raise Invalid('invalid K1 checksum line')
        name=norm_member(m.group(2))
        if name in result: raise Invalid('duplicate K1 manifest entry')
        result[name]=m.group(1).lower()
    if not all(name in result for name in STAGE+('modules.tar.xz',)):
        raise Invalid('incomplete K1 manifest')
    return result

def parse_conf(data):
    result={}
    for line in data.decode('utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        if '=' not in line: raise Invalid('bad K1.conf')
        k,value=line.split('=',1)
        if k in result: raise Invalid('duplicate K1.conf key')
        result[k]=value
    checks={'hardware':'R36XX-RK3326','panel':'PANEL4_NV3051D_640X480',
            'root_uuid':EXPECTED_ROOT,'state_uuid':EXPECTED_STATE,
            'boot_mode':'R36OS_K1_BOOT_ONCE','modules_storage':'R36STATE_BIND'}
    for key,value in checks.items():
        if result.get(key)!=value: raise Invalid('K1.conf mismatch '+key)
    if not re.fullmatch(r'6\.12\.\d+[-.A-Za-z0-9]*',result.get('kernel_release','')):
        raise Invalid('invalid kernel_release')
    if not re.fullmatch(r'[0-9a-f]{24}',result.get('candidate_id','')):
        raise Invalid('invalid candidate_id')
    return result

def read_small(tar,member,limit=1048576):
    if not member.isfile() or member.size>limit: raise Invalid('unsafe metadata size')
    f=tar.extractfile(member)
    if f is None: raise Invalid('archive metadata absent')
    result=f.read(limit+1)
    if len(result)!=member.size: raise Invalid('truncated metadata')
    return result

def verify(archive_path, stage_dir=None):
    archive_path=Path(archive_path)
    if archive_path.is_symlink() or not archive_path.is_file(): raise Invalid('source not regular file')
    with archive_path.open('rb') as f: source_hash,source_size=digest(f)
    with tarfile.open(archive_path,'r:gz') as tar:
        entries={}
        for member in tar:
            # GNU tar archives commonly include a harmless root directory './'.
            # Ignore only that directory, never an unsafe file or path.
            if member.isdir() and member.name in ('.','./'):
                continue
            name=norm_member(member.name)
            if name in entries: raise Invalid('duplicate archive member')
            entries[name]=member
        prefixes=set(name[:-len('K1.conf')] for name in entries if name.endswith('/K1/K1.conf') or name=='K1/K1.conf')
        candidates=[prefix for prefix in prefixes if all(prefix+n in entries and entries[prefix+n].isfile() for n in REQUIRED)]
        if len(candidates)!=1: raise Invalid('expected exactly one complete K1 candidate')
        prefix=candidates[0]
        conf=parse_conf(read_small(tar,entries[prefix+'K1.conf']))
        manifest=parse_manifest(read_small(tar,entries[prefix+'MANIFEST.sha256']))
        checked={}
        for rel,sha in manifest.items():
            name=prefix+rel
            if name not in entries or not entries[name].isfile(): raise Invalid('missing K1 manifest entry '+rel)
            f=tar.extractfile(entries[name])
            if f is None: raise Invalid('cannot extract member '+rel)
            observed,length=digest(f,entries[name].size)
            if observed!=sha: raise Invalid('K1 manifest hash mismatch: '+rel)
            checked[rel]={'sha256':sha,'bytes':length}
        k=tar.extractfile(entries[prefix+'Image'])
        if k is None or (len((h:=k.read(60)))!=60) or h[0x38:0x3c]!=b'ARM\x64':
            raise Invalid('not ARM64 Linux Image')
        d=tar.extractfile(entries[prefix+'rk3326-r36s-k1.dtb'])
        dt=d.read(8) if d else b''
        if len(dt)!=8 or dt[:4]!=bytes.fromhex('d00dfeed') or int.from_bytes(dt[4:8],'big')>entries[prefix+'rk3326-r36s-k1.dtb'].size:
            raise Invalid('DTB FDT magic or size invalid')
        f=tar.extractfile(entries[prefix+'uInitrd'])
        head=f.read(64) if f else b''
        if len(head)!=64: raise Invalid('short uInitrd')
        values=struct.unpack('>7I4B32s',head)
        magic,hcrc,stamp,size,load,ep,dcrc,osid,arch,typ,comp,title=values
        h=bytearray(head);h[4:8]=bytes(4)
        if magic!=0x27051956 or osid!=5 or arch!=22 or typ!=3 or size!=entries[prefix+'uInitrd'].size-64 or comp not in (0,1):
            raise Invalid('invalid uInitrd header')
        if zlib.crc32(h)&0xffffffff!=hcrc: raise Invalid('uInitrd header CRC mismatch')
        mod=tar.extractfile(entries[prefix+'modules.tar.xz'])
        if not mod or mod.read(6)!=bytes.fromhex('fd377a585a00'):
            raise Invalid('modules archive is not xz')
        report={'result':'PASS_ARCHIVE_INTEGRITY_ONLY','safe_to_flash':False,'boot_tested':False,
                'source_archive':archive_path.name,'source_archive_bytes':source_size,
                'source_archive_sha256':source_hash,'candidate_prefix':prefix,'candidate':conf,
                'checked_manifest_entries':len(checked),
                'required_boot_artifacts':{n:checked[n] for n in STAGE+('modules.tar.xz',)},
                'warnings':['SHA256 manifest is not authenticated or signed',
                            'K1 physical Panel4 boot NOT TESTED','Original U-Boot not staged']}
        if stage_dir is not None:
            stage_dir=Path(stage_dir)
            if stage_dir.exists() or stage_dir.is_symlink() or stage_dir.name!='CP13_UNTESTED_K1_BOOT_FILES':
                raise Invalid('refusing overwrite or unexpected output path')
            stage_dir.mkdir(mode=0o700)
            for name in STAGE:
                f=tar.extractfile(entries[prefix+name])
                if f is None: raise Invalid('missing staging member')
                path=stage_dir/name
                with path.open('xb') as out:
                    for block in iter(lambda:f.read(1048576),b''): out.write(block)
                with path.open('rb') as inp: got,_=digest(inp)
                if got!=checked[name]['sha256']: raise Invalid('staged file hash mismatch')
            (stage_dir/'CP13-NOT-FLASHABLE.txt').write_text('Development K1 kernel files only. NOT BOOT TESTED. Do not copy to SD/BOOT.\n')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('report',type=Path)
    p.add_argument('--stage',type=Path)
    a=p.parse_args()
    if a.report.exists() or a.report.is_symlink(): p.error('refusing to overwrite report')
    result=verify(a.archive,a.stage)
    with a.report.open('x') as f: json.dump(result,f,indent=2,sort_keys=True)
    print('CP13 verified archived K1 candidate, NOT hardware boot tested:',result['candidate']['kernel_release'])

if __name__=='__main__':main()
