#!/usr/bin/env python3
"""CP25: read ONLY early R3 raw IMG sectors for pre-bootloader evidence.

No attached physical disk access. Never writes source IMG or a boot file.
This audit does NOT establish the U-Boot saveenv backend or safe fallback.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

FORMAT='R36OS_CP25_READONLY_R3_EARLY_BOOT_EVIDENCE_V1'
IMG_NAME='R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img'
EXPECTED_SIZE=18_375_245_824
PARTITIONS=((0x0b,32768,229376),(0x83,262144,20942929))
SAMPLE_BYTES=16*1024*1024  # entirely before BOOT p1 LBA32768
BPI=512
R3_BOOT_HASH='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
TOKENS=(b'U-Boot',b'bootcmd=',b'bootdelay=',b'saveenv',b'fw_env',b'env offset',b'ENV_OFFSET',b'RK33',b'RKNS')
class Reject(ValueError):pass

def disk_allowed(path:Path, *, expected_size:int=EXPECTED_SIZE, allow_fixture:bool=False)->Path:
    """Reject direct physical disks and any wrong-sized or unusual input file."""
    raw=str(path)
    if raw.startswith('\\\\.\\') or raw.startswith('/dev/') or raw.startswith('/sys/') or raw.startswith('\\\\?\\'):
        raise Reject('physical device access is prohibited: select the existing original .img FILE')
    p=path.absolute()
    if p.is_symlink() or not p.is_file() or not stat.S_ISREG(p.stat().st_mode):
        raise Reject('source must be a regular IMG file, not a symlink/device')
    if p.suffix.lower()!='.img':raise Reject('only a source .img file is accepted')
    if not allow_fixture and p.name!=IMG_NAME:raise Reject('source image filename does not match R3 reference')
    if p.stat().st_size!=expected_size:raise Reject('source image size is not the audited R3 reference')
    return p

def mbr(data:bytes)->list[dict]:
    if len(data)<512 or data[510:512]!=b'\x55\xaa':raise Reject('missing MBR signature')
    out=[]
    for i in range(4):
        x=data[446+i*16:462+i*16]
        ptype=x[4]
        start,length=struct.unpack_from('<II',x,8)
        if ptype==0 or length==0:continue
        if start==0 or start+length>2**32:raise Reject('invalid MBR partition location')
        out.append({'number':i+1,'type_hex':f'{ptype:02x}','start_lba':start,'sectors':length})
    if len(out)!=4:raise Reject('R3 must have four partitions')
    if (int(out[0]['type_hex'],16),out[0]['start_lba'],out[0]['sectors'])!=PARTITIONS[0]:
        raise Reject('BOOT partition layout differs from source audit')
    if (int(out[1]['type_hex'],16),out[1]['start_lba'],out[1]['sectors'])!=PARTITIONS[1]:
        raise Reject('R3 root partition differs from source audit')
    if out[1]['start_lba']<out[0]['start_lba']+out[0]['sectors']:
        raise Reject('overlapping R3 BOOT/root partitions')
    return out

def sample(data:bytes)->dict:
    if len(data)!=SAMPLE_BYTES:raise Reject('truncated 16 MiB early-boot sampling area')
    hits={}
    for tok in TOKENS:
        pos=[];at=0
        while len(pos)<32:
            at=data.find(tok,at)
            if at<0:break
            pos.append(at);at+=len(tok)
        hits[tok.decode('ascii')]=pos
    return {'offset_bytes':0,'bytes_read':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'read_limit':'16 MiB before original BOOT FAT32 partition',
            'possible_uboot_string_offsets_not_verified_config':hits,
            'raw_early_boot_bytes_in_report':False}

def inspect(path:Path, *,expected_size:int=EXPECTED_SIZE,allow_fixture:bool=False)->dict:
    p=disk_allowed(path,expected_size=expected_size,allow_fixture=allow_fixture)
    with p.open('rb') as reader:
        # Read only 16 MiB, not the full 18.4 GB; this is not a full-image hash.
        sector=reader.read(512)
        reader.seek(0)
        early=reader.read(SAMPLE_BYTES)
    layout=mbr(sector)
    early_data=sample(early)
    return {'format':FORMAT,'status':'PASS_READONLY_EARLY_SECTORS_ONLY_NOT_BOOT_APPROVAL',
        'image_name':p.name,'source_img_bytes':p.stat().st_size,
        'source_img_fully_sha256_verified_this_run':False,
        'original_r3_boot_ini_known_sha256':R3_BOOT_HASH,
        'mbr_partitions':layout,'early_area':early_data,
        'persistent_uboot_env_storage_location_proven':False,
        'saveenv_targets_internal_storage_ruled_out':False,
        'independent_manual_fallback_physically_proven':False,
        'original_card_physically_rebooted':False,
        'spare_card_confirmed':False,
        'physical_sd_card_opened':False,
        'source_image_opened_read_only':True,
        'source_image_modified':False,
        'flashable_image_created':False,
        'safe_to_flash':False,'hardware_boot_tested':False,
        'next_step':'review early U-Boot evidence; confirm separate spare and original SD1 still boots; hardware safety remains unproven'}

def report_to_new_dir(script_root:Path, payload:dict, *,stamp:str|None=None)->Path:
    root=script_root.resolve(strict=True)
    if root.is_symlink() or not root.is_dir():raise Reject('invalid output directory')
    date=stamp or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z',date):raise Reject('invalid UTC output timestamp')
    for i in range(100):
        dest=root/('CP25_RESULTS_'+date+(f'_{i}' if i else ''))
        try:dest.mkdir(mode=0o700,exist_ok=False)
        except FileExistsError:continue
        with (dest/'CP25_R3_EARLY_BOOT_READONLY_REPORT.json').open('x',encoding='utf8') as out:
            json.dump(payload,out,indent=2,sort_keys=True);out.write('\n')
        return dest
    raise Reject('could not create new report folder')

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source_image',type=Path,help='existing original R3 raw .img FILE on Windows, never a physical disk')
    a=p.parse_args(argv)
    try:
        d=inspect(a.source_image)
        dest=report_to_new_dir(Path(__file__).resolve().parent,d)
    except (Reject,OSError,ValueError) as e:p.error(str(e))
    print('CP25 READ-ONLY inspection PASSED, report:',dest/'CP25_R3_EARLY_BOOT_READONLY_REPORT.json')
    print('THIS DOES NOT VERIFY saveenv backend, U-Boot compatibility or hardware boot. DO NOT FLASH.')
    return 0
if __name__=='__main__':raise SystemExit(main())