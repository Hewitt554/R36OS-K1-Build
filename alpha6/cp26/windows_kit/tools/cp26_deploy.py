#!/usr/bin/env python3
"""CP26 Windows FAT32 BOOT-only diagnostic installer. No raw-disk writer.

Only works after an external image writer restores the exact original R3 IMG
on an explicitly selected SD1. Requires the exact original R3 boot.ini hash.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

R3_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
ROOT='R36OS/CP26'
BOOT_NAME='boot.ini'
BACKUP_NAME='R3BOOT.BAK'
MARKER='CP26_TEST_MANIFEST.json'
ALLOWED={'Image','diag.uInitrd','rk3326-r36s-k1.dtb'}
CHALLENGE='I CONFIRM SD1 BOOT'

class Refuse(ValueError): pass

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def volume_name(drive:str)->tuple[str,str]:
    if os.name!='nt':raise Refuse('Live deploy only works on Windows')
    import ctypes.wintypes
    label=ctypes.create_unicode_buffer(261)
    fs=ctypes.create_unicode_buffer(261)
    flags=ctypes.wintypes.DWORD();serial=ctypes.wintypes.DWORD();maxpart=ctypes.wintypes.DWORD()
    ok=ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(drive+'\\'),label,261,
        ctypes.byref(serial),ctypes.byref(maxpart),ctypes.byref(flags),fs,261)
    if not ok:raise Refuse('Cannot read volume identity')
    return label.value,fs.value

def select_root(letter:str, inspect_volume=volume_name)->Path:
    if not isinstance(letter,str) or not re.fullmatch(r'[A-Z]',letter.upper()):
        raise Refuse('Select one drive LETTER only, e.g. E')
    letter=letter.upper()
    if letter=='C':raise Refuse('C: is never a candidate BOOT target')
    vol,fs=inspect_volume(letter+':')
    if vol.upper()!='BOOT' or fs.upper()!='FAT32':
        raise Refuse('Drive is not labelled BOOT with a FAT32 filesystem')
    return Path(letter+':\\')

def verify_manifest(package:Path)->dict:
    p=package/'CP26_PACKAGE_MANIFEST.json'
    if p.is_symlink() or not p.is_file():raise Refuse('Missing package integrity manifest')
    manifest=json.loads(p.read_text(encoding='utf8'))
    if (manifest.get('format')!='R36OS_CP26_BOOT_DIAGNOSTIC_BUNDLE_V1' or
        manifest.get('safe_to_flash') is not False or
        manifest.get('hardware_boot_tested') is not False or
        manifest.get('original_r3_boot_sha256')!=R3_SHA or
        manifest.get('k1_inner_archive_sha256')!='d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8'):
        raise Refuse('Unexpected or unsafe package manifest')
    fs=manifest.get('files')
    if not isinstance(fs,dict) or set(fs)!=ALLOWED|{'boot.ini'}:
        raise Refuse('Package files unexpectedly changed')
    for name,ref in fs.items():
        src=package/'BOOT_PAYLOAD'/ (name if name=='boot.ini' else ROOT+'/'+name)
        if src.is_symlink() or not src.is_file():raise Refuse('Missing/linked package file '+name)
        if src.stat().st_size!=ref['bytes'] or sha(src)!=ref['sha256']:
            raise Refuse('Package file checksum mismatch: '+name)
    contents=(package/'BOOT_PAYLOAD/boot.ini').read_bytes()
    forbidden=(b'fatwrite',b'saveenv',b'env delete',b'run update',b' mmc write',b'RECOVERY.ON')
    if any(x in contents for x in forbidden):raise Refuse('Unexpected persistent boot command')
    if b'odroidgoa-uboot-config' not in contents or contents.count(b'booti ')!=1:
        raise Refuse('Boot script does not match expected conservative diagnostic')
    return manifest

def original_boot(root:Path)->Path:
    p=root/BOOT_NAME
    if p.is_symlink() or not p.is_file() or p.stat().st_size!=5108 or sha(p)!=R3_SHA:
        raise Refuse('This is NOT the unmodified verified R3 BOOT; first flash your original IMG to SD1')
    for name in ('Image','uInitrd'):
        if not (root/name).is_file():raise Refuse('Original R3 BOOT missing '+name)
    return p

def sync_copy(src:Path,dst:Path)->None:
    # Exclusive create means no unexpected overwrite. Caller supplies staging name.
    with src.open('rb') as inp,dst.open('xb') as out:
        for b in iter(lambda:inp.read(1024*1024),b''):out.write(b)
        out.flush();os.fsync(out.fileno())
    if sha(src)!=sha(dst):raise Refuse('Readback mismatch: '+dst.name)

def install(root:Path,package:Path,challenge:str,*,is_windows=True,volume_ok=True)->dict:
    if not is_windows or not volume_ok:raise Refuse('Windows FAT32 volume verification required')
    if challenge != CHALLENGE:raise Refuse('Confirmation phrase did not match')
    manifest=verify_manifest(package)
    original=original_boot(root)
    target=root/ROOT
    backup=root/BACKUP_NAME
    if backup.exists() or backup.is_symlink() or target.exists() or target.is_symlink():
        raise Refuse('Test files already exist: refuse re-install or overwrite; restore first')
    required=sum(x['bytes'] for x in manifest['files'].values())+8192
    if shutil.disk_usage(root).free < required+8*1024*1024:
        raise Refuse('BOOT volume lacks space (keep 8 MiB minimum free)')
    backup_created=False
    try:
        # Backup original known-good bytes BEFORE boot.ini replacement.
        sync_copy(original,backup)
        backup_created=True
        if backup.stat().st_size!=5108 or sha(backup)!=R3_SHA:raise Refuse('Original backup failed checksum')
        target.mkdir(parents=True,exist_ok=False)
        for name in sorted(ALLOWED):
            source=package/'BOOT_PAYLOAD'/ROOT/name
            sync_copy(source,target/name)
        data={'format':'R36OS_CP26_INSTALLED_ON_VERIFIED_R3_BOOT',
              'original_r3_boot_sha256':R3_SHA,'files':manifest['files'],
              'safe_to_flash':False,'physical_boot_tested':False,
              'restore_from_windows':'02_RESTORE_R3_BOOT.cmd',
              'no_automatic_rollback':True,'original_sd1_previous_contents_overwritten_if_flashing_r3':True}
        marker=target/MARKER
        with marker.open('x',encoding='utf8') as f:json.dump(data,f,indent=2);f.flush();os.fsync(f.fileno())
        tmp=root/'CP26BOOT.TMP'
        if tmp.exists():raise Refuse('Unexpected boot temp file')
        sync_copy(package/'BOOT_PAYLOAD/boot.ini',tmp)
        os.replace(tmp,original) # Single final filename switch, not power-loss atomic guarantee.
        if sha(original)!=manifest['files']['boot.ini']['sha256']:
            raise Refuse('Failed final boot.ini readback, restore original with option 02')
        return {'status':'INSTALLED_DIAGNOSTIC_BOOT_FILES_NOT_HARDWARE_TESTED',
                'boot_drive':str(root),'bytes_in_payload':required,
                'restore':'Run 02_RESTORE_R3_BOOT.cmd with the same BOOT drive letter',
                'safe_to_flash':False}
    except Exception:
        # Best effort only. If boot.ini changed, leave it for explicit RESTORE command.
        # Never delete verified R3 backup or any existing original user files.
        raise

def restore(root:Path,challenge:str)->dict:
    if challenge != CHALLENGE:raise Refuse('Confirmation phrase mismatch')
    backup=root/BACKUP_NAME
    original=root/BOOT_NAME
    if backup.is_symlink() or not backup.is_file() or backup.stat().st_size!=5108 or sha(backup)!=R3_SHA:
        raise Refuse('Verified R3 backup missing; cannot auto-restore')
    # Restore only boot.ini, not card partitions. R3 itself might not boot.
    tmp=root/'CP26REST.TMP'
    if tmp.exists() or tmp.is_symlink():raise Refuse('Unexpected restore temp')
    sync_copy(backup,tmp)
    os.replace(tmp,original)
    if sha(original)!=R3_SHA:raise Refuse('Restored original BOOT hash mismatch')
    return {'status':'VERIFIED_R3_BOOT_INI_RESTORED','boots_os_guaranteed':False,
            'note':'Current SD1 previously did not boot; this only restores boot.ini, not full R3 disk.'}

def status(root:Path,package:Path)->dict:
    manifest=verify_manifest(package)
    script=root/BOOT_NAME
    observed=sha(script) if script.is_file() and not script.is_symlink() else None
    original=R3_SHA
    return {'drive':str(root),'volume_boot_ini_sha256':observed,
            'mode':'R3_ORIGINAL' if observed==original else 'CP26_DIAGNOSTIC' if observed==manifest['files']['boot.ini']['sha256'] else 'UNKNOWN_OR_DAMAGED',
            'verified_backup_present':(root/BACKUP_NAME).is_file() and sha(root/BACKUP_NAME)==original,
            'safe_to_flash':False}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('install','restore','status'))
    ap.add_argument('--drive',help='single drive letter e.g. E')
    ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1])
    a=ap.parse_args()
    try:
        drive=(a.drive or input('Enter Windows BOOT drive letter (e.g. E, NOT C): ')).strip().upper().rstrip(':')
        root=select_root(drive)
        print('Target:',str(root),'label=BOOT filesystem=FAT32')
        print('IMPORTANT: this is BOOT on the SD1 you explicitly selected; no SD2 changes are intended.')
        if a.action=='status': result=status(root,a.package)
        else:
            print('Expected original boot.ini SHA256:',R3_SHA)
            if a.action=='install':
                print('INSTALL overwrites boot.ini only on selected BOOT after verifying it is original R3.')
                print('R3 must ALREADY have been flashed to SD1; we do NOT write your disk image.')
            else:print('RESTORE overwrites current boot.ini with saved original R3 boot.ini.')
            challenge=input('Type exactly "'+CHALLENGE+'" to confirm: ')
            result=install(root,a.package,challenge) if a.action=='install' else restore(root,challenge)
        print(json.dumps(result,indent=2))
    except (Refuse,PermissionError,OSError,ValueError,KeyError) as e:
        print('\nCP26 REFUSED / FAILED:',e,file=sys.stderr)
        return 1
    return 0
if __name__=='__main__':raise SystemExit(main())