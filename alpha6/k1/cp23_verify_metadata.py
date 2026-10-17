#!/usr/bin/env python3
"""CP23: fail-closed GitHub K1 run & artifact metadata verifier. No SD writes."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

ARTIFACT_ID=12103773756
RUN_ID=39038977056
RUN_SHA='b593608d9cdc5f0275cc7f6471e31ff4db5bb366'
ARCHIVE_SHA='d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8'
ARTIFACT_NAME='r36os-alpha6-cp20-REBUILT-K1-HARDWARE-UNTESTED'
FORMAT='R36OS_CP23_VERIFIED_K1_METADATA_DEVELOPMENT_ONLY'

class Reject(ValueError):pass

def cp21_module():
    src=Path(__file__).with_name('cp21_pinned_artifact.py')
    spec=importlib.util.spec_from_file_location('r36os_cp21_for_cp23',src)
    mod=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod

def verify(pin:dict, run:dict, listing:dict) -> dict:
    mod=cp21_module()
    mod.valid_pin(pin,True)
    mod.check_run(pin,run)
    if (pin['run_id']!=RUN_ID or pin['head_sha']!=RUN_SHA or
        pin['archive_sha256']!=ARCHIVE_SHA):
        raise Reject('CP23 reviewed source/build/archive identity changed')
    if type(listing) is not dict or type(listing.get('artifacts')) is not list:
        raise Reject('GitHub artifact response missing or malformed')
    matches=[a for a in listing['artifacts'] if a.get('id')==ARTIFACT_ID]
    if len(matches)!=1:raise Reject('reviewed artifact ID unavailable or duplicated')
    a=matches[0]
    if (a.get('name')!=ARTIFACT_NAME or a.get('expired') is not False or
        type(a.get('size_in_bytes')) is not int or a['size_in_bytes']<500_000_000 or
        a['size_in_bytes']>650_000_000):
        raise Reject('reviewed artifact absent, expired or incorrect size')
    if type(a.get('workflow_run')) is dict and a['workflow_run'].get('id')!=RUN_ID:
        raise Reject('artifact belongs to another workflow run')
    return {'format':FORMAT,'status':'PASS_VERIFIED_PIN_AND_GITHUB_ARTIFACT_METADATA',
            'run_id':RUN_ID,'run_head_sha':RUN_SHA,'artifact_id':ARTIFACT_ID,
            'archive_sha256':ARCHIVE_SHA,'artifact_name':ARTIFACT_NAME,
            'artifact_zip_bytes':a['size_in_bytes'],'artifact_expires_at':a.get('expires_at'),
            'full_archive_sha256_was_checked_during_cp20':True,
            'new_archive_rechecked_here':False,'safe_to_flash':False,
            'boot_tested':False,'recovery_tested':False,
            'cp18_new_panel4_provenance_resolved':False,
            'warnings':['GitHub metadata and pinned checksum are not a hardware boot test',
                        'CP13-17 binary recheck must be rerun on actual uploaded archive',
                        'CP18 must wait for a freshly rebuilt CP17 Panel4 report']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pin',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--artifacts',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists() or a.report.is_symlink() or a.report.suffix!='.json':p.error('new JSON report only')
    r=verify(json.loads(a.pin.read_text()),json.loads(a.run.read_text()),json.loads(a.artifacts.read_text()))
    a.report.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print('CP23 GitHub pinned run/artifact metadata PASS. NOT boot tested or flashable.')

if __name__=='__main__':main()