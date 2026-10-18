#!/usr/bin/env python3
"""Package just enough checksum-pinned K1 assets for a first diagnostic.

NO flashable image; consumes GH artifacts as input and creates a self-contained
Windows BOOT-partition overlay kit. User flashes original R3 IMG separately.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import zipfile

K1_SHA='d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8'
DTB_SHA='e2145905b1beb8d0f5b9dee6c5a21d31c29474be8762c893e81506fc40e627f4'
R3_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
BOOTFILES=('Image','diag.uInitrd','rk3326-r36s-k1.dtb','boot.ini')

class Reject(ValueError):pass

def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def read_archive(k1:Path,verifier_path:Path)->dict:
    if k1.is_symlink() or not k1.is_file():raise Reject('no regular K1 archive')
    spec=importlib.util.spec_from_file_location('cp13_for_cp26',verifier_path)
    m=importlib.util.module_from_spec(spec)
    if spec.loader is None:raise Reject('no verifier loader')
    spec.loader.exec_module(m)
    checked=m.verify(k1)
    if (checked['source_archive_sha256']!=K1_SHA or
        checked['candidate']['kernel_release']!='6.12.94-r36os-k1' or
        checked['safe_to_flash'] is not False or checked['boot_tested'] is not False):
        raise Reject('K1 identity mismatch')
    with tarfile.open(k1,'r:gz') as tf:
        prefix=checked['candidate_prefix']
        # GNU tar records the same member as ./candidate/K1/Image while
        # CP13's verified candidate_prefix is normalized to candidate/K1/.
        # Resolve by the EXACT CP13 path normalizer; don't assume raw spellings.
        indexed={}
        for member in tf.getmembers():
            if not member.isfile(): continue
            logical=m.norm_member(member.name)
            if logical in indexed:raise Reject('duplicate normalized K1 archive member')
            indexed[logical]=member
        def safe_read(name,maxsize):
            t=indexed.get(prefix+name)
            if t is None:raise Reject('missing normalized K1 archive member '+name)
            if not t.isfile() or t.size<32 or t.size>maxsize:raise Reject('invalid '+name+' size')
            inp=tf.extractfile(t)
            if inp is None:raise Reject('missing '+name)
            out=inp.read(maxsize+1)
            if len(out)!=t.size:raise Reject('truncated '+name)
            return out
        image=safe_read('Image',128*1024*1024)
        dtb=safe_read('rk3326-r36s-k1.dtb',512*1024)
    if digest(dtb)!=DTB_SHA:raise Reject('DTB different from renewed verified CP17 K1')
    if image[0x38:0x3c]!=b'ARM\x64':raise Reject('not ARM64 Image')
    if len(image)>96*1024*1024:raise Reject('K1 kernel too big for BOOT test')
    return {'Image':image,'rk3326-r36s-k1.dtb':dtb}

def read_diag(zippath:Path)->bytes:
    if not zippath.is_file() or zippath.is_symlink():raise Reject('missing CP17 artifact')
    with zipfile.ZipFile(zippath) as z:
        names=z.namelist()
        def one(suffix):
            found=[n for n in names if n.endswith(suffix)]
            if len(found)!=1:raise Reject('CP17 expected one '+suffix)
            return z.read(found[0])
        report=json.loads(one('/cp17-diagnostic-report.json'))
        if report.get('kernel_target')!='6.12.94-r36os-k1' or report.get('safe_to_flash') is not False or report.get('boot_tested') is not False:
            raise Reject('CP17 diagnostic not the expected untested version')
        evidence=json.loads(one('cp17-k1-panel4-dtb-report.json'))
        if evidence.get('k1_source_sha256')!=K1_SHA or evidence.get('dtb_sha256')!=DTB_SHA:
            raise Reject('CP17 does not match pinned K1 DTB')
        a=one('/CP17-ARCH2-DIAGNOSTIC-UNTESTED.uInitrd')
        ref=report['variants']['2']
        if digest(a)!=ref['sha256'] or len(a)!=ref['bytes'] or a[:4]!=bytes.fromhex('27051956'):
            raise Reject('diagnostic ramdisk wrong header/hash/size')
        return a

def guard_boot(boot:bytes)->None:
    if not boot.startswith(b'odroidgoa-uboot-config\n') or boot.count(b'booti ' )!=1:
        raise Reject('unexpected diagnostic boot.ini')
    if any(x in boot for x in (b'fatwrite',b'saveenv',b' env delete',b'RECOVERY.ON',b'mmc write')):
        raise Reject('persistent mutation in diagnostic U-Boot script')
    for name in ('Image','diag.uInitrd','rk3326-r36s-k1.dtb'):
        if ('R36OS/CP26/'+name).encode() not in boot:raise Reject('boot missing '+name)

def make(k1:Path,cp17:Path,source:Path,verifier:Path,destination:Path)->dict:
    if destination.exists():raise Reject('refuse overwrite of result')
    f=read_archive(k1,verifier)
    f['diag.uInitrd']=read_diag(cp17)
    f['boot.ini']=(source/'boot.ini').read_bytes()
    guard_boot(f['boot.ini'])
    # Non-overlapping load addresses from the source R3 U-Boot boot.ini.
    if len(f['diag.uInitrd']) >= 0xE00000 or len(f['rk3326-r36s-k1.dtb']) >= 0x100000:
        raise Reject('unsafe U-Boot pre-kernel address overlap')
    entries={key:{'sha256':digest(v),'bytes':len(v)} for key,v in f.items()}
    manifest={
     'format':'R36OS_CP26_BOOT_DIAGNOSTIC_BUNDLE_V1',
     'status':'OFFLINE_VERIFIED_COMPONENTS_NOT_PHYSICAL_BOOT',
     'kernel_release':'6.12.94-r36os-k1',
     'k1_inner_archive_sha256':K1_SHA,
     'original_r3_boot_sha256':R3_SHA,
     'cp17_dtb_sha256':DTB_SHA,
     'sd1_original_image_name':'R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img',
     'files':entries,
     'user_must_flash_original_r3_image_first':True,
     'external_r3_image_not_included':True,
     'does_not_contain_native_debian_root':True,
     'no_sd2_writes':True,
     'no_automatic_rollback':True,
     'bootloader_load_addresses':{'Image':'0x02000000','diag.uInitrd':'0x01100000','dtb':'0x01f00000'},
     'panel4_screen_unverified':True,
     'safe_to_flash':False,'hardware_boot_tested':False,
    }
    def add_zip(z,name,data):z.writestr(name,data,compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(destination,'x') as z:
        add_zip(z,'CP26_PACKAGE_MANIFEST.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        for name,data in f.items():
            add_zip(z,'BOOT_PAYLOAD/'+('' if name=='boot.ini' else 'R36OS/CP26/')+name,data)
        for p in sorted(source.glob('*.cmd')):
            add_zip(z,p.name,p.read_bytes())
        for p in sorted((source/'tools').glob('*.py')):
            add_zip(z,'tools/'+p.name,p.read_bytes())
        add_zip(z,'READ_ME_FIRST.txt',(source/'READ_ME_FIRST.txt').read_bytes())
        add_zip(z,'CI_VALIDATED_COMPONENT_REPORT.json',json.dumps({
            'status':'PASS_CHECKSUM_PINNED_COMPONENTS_ONLY','safe_to_flash':False,
            'hardware_boot_tested':False,'k1_source_hash':K1_SHA,
            'files':entries,'no_disk_image_produced':True},indent=2)+'\n')
    with zipfile.ZipFile(destination) as z:
        if z.testzip():raise Reject('bad output ZIP CRC')
        names=set(z.namelist());assert 'BOOT_PAYLOAD/boot.ini' in names
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--k1',type=Path,required=True);p.add_argument('--cp17',type=Path,required=True)
    p.add_argument('--src',type=Path,required=True);p.add_argument('--cp13-verifier',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    v=make(a.k1,a.cp17,a.src,a.cp13_verifier,a.output)
    print('CP26 verified K1 and CP17; diagnostics-only kit ZIP',a.output, 'parts',list(v['files']))
if __name__=='__main__':main()