#!/usr/bin/env python3
"""CP24 prepare a first-boot *plan*, never an install script or SD image.

The plan is deliberately unapproved until the original card is independently
verified working, and a separate spare-card + recovery strategy is confirmed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

R3_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
R3_SIZE=5108
K1_SHA='d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8'
R3_UUID='e139ce78-9841-40fe-8823-96a304a09859'
R3_IMAGE_BYTES=18375245824

class Reject(ValueError):pass

def prepare(original:bytes,pin:dict,manifest:dict)->dict:
    if len(original)!=R3_SIZE or hashlib.sha256(original).hexdigest()!=R3_SHA:
        raise Reject('exact original R3 boot.ini SHA/size required')
    if original.count(b'fatwrite ')<1 or original.count(b'saveenv')<1:
        raise Reject('legacy persistent writes must not be concealed')
    if original.count(b'booti ')!=1 or R3_UUID.encode() not in original:
        raise Reject('unexpected original boot loader or root UUID')
    if (pin.get('status')!='PINNED_CI_VERIFIED_NOT_BOOT_TESTED' or
        pin.get('archive_sha256')!=K1_SHA or pin.get('run_id')!=39038977056 or
        pin.get('hardware_boot_tested') is not False or pin.get('safe_to_flash') is not False):
        raise Reject('K1 pin not verified, or false hardware claims')
    if manifest.get('format')!='R36OS_CP24_ARTIFACT_LEDGER_V1':
        raise Reject('artifact ledger missing')
    if not (manifest.get('safe_to_flash') is False and manifest.get('independent_recovery_proven') is False):
        raise Reject('unexpected boot gate claims')
    if manifest.get('artifacts',{}).get('k1',{}).get('archive_sha256')!=K1_SHA:
        raise Reject('K1 ledger mismatch')
    # Explicit phases: this checkpoint has no mutating installer. A user may
    # later verify original card works and identify the correct spare SD.
    return {'format':'R36OS_CP24_SPARE_SD_FIRST_BOOT_PREP_ONLY',
      'status':'PREPARED_BUT_NOT_AUTHORIZED_FOR_HARDWARE_BOOT',
      'original_r3_boot_ini_sha256':R3_SHA,
      'original_r3_image_bytes':R3_IMAGE_BYTES,
      'k1_archive_sha256':K1_SHA,
      'target_device':'R36XX RK3326 Panel 4 640x480',
      'existing_original_card_must_remain_unmodified':True,
      'spare_card_physical_capacity_and_identity_confirmed':False,
      'known_good_original_card_independently_rebooted':False,
      'working_recovery_route_physically_verified':False,
      'test_card_image_assembled':False,'bootloader_compatibility_verified':False,
      'test_kit_contains_boot_ini':False,'flashable_image_produced':False,
      'safe_to_flash':False,'boot_tested':False,
      'blocking_requirements':[
        'Confirm a separate spare SD1, not the working original card or SD2',
        'Confirm the known-good original card still boots and can be reinserted unchanged',
        'Identify and preserve the correct early U-Boot sectors + Panel4 choice on spare card',
        'Proof of isolated fallback independent of candidate K1 kernel/boot.ini',
        'Spare image capacity and USB SD writer destination must be explicitly checked',
        'Do not flash candidate or alter original SD1/SD2 until the above tests pass'],
      'proposed_observations':['Power on / known-good startup baseline','Panel4 screen test or black-screen evidence',
        'Buttons and input detection','Two MMC hosts and card detection','RK817 battery/power nodes',
        'Safe shutdown + returning to the original card'],
      'first_boot_target_checkpoint':'CP25_PENDING_SAFETY_GATES'}

def main()->int:
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--verified-r3-boot',type=Path,required=True)
    a.add_argument('--pin',type=Path,required=True)
    a.add_argument('--ledger',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    p=a.parse_args()
    if p.out.exists() or p.out.is_symlink() or p.out.suffix!='.json':a.error('requires NEW JSON-only report')
    try:
        if p.verified_r3_boot.is_symlink():raise Reject('original script symlink rejected')
        if p.verified_r3_boot.stat().st_size != R3_SIZE:raise Reject('wrong original size')
        output=prepare(p.verified_r3_boot.read_bytes(),json.loads(p.pin.read_text()),json.loads(p.ledger.read_text()))
        p.out.write_text(json.dumps(output,indent=2)+'\n',encoding='utf8')
    except (OSError,ValueError,TypeError,KeyError) as e:a.error(str(e))
    print(output['status'], '- never flash')
    return 0
if __name__=='__main__':raise SystemExit(main())