#!/usr/bin/env python3
"""Validate rebuilt K1 build artifact via existing CP13; write nonbootable JSON only."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

FORMAT='R36OS_CP20_REBUILT_K1_ARCHIVE_UNTESTED_NOT_FLASHABLE'
KREL='6.12.94-r36os-k1'

class Reject(ValueError):pass

def make_record(check:dict)->dict:
    if not isinstance(check,dict): raise Reject('CP13 archive verification result missing')
    if (check.get('candidate',{}).get('kernel_release')!=KREL or
        check.get('candidate',{}).get('panel')!='PANEL4_NV3051D_640X480' or
        check.get('boot_tested') is not False or check.get('safe_to_flash') is not False or
        not check.get('source_archive_sha256') or len(check['source_archive_sha256'])!=64 or
        check.get('checked_manifest_entries',0)<4):
        raise Reject('K1 rebuild provenance or nonbootable safety mismatch')
    return {'format':FORMAT,'status':'REBUILT_ARCHIVE_INTEGRITY_VERIFIED_NOT_BOOT_TESTED',
            'new_archive_sha256':check['source_archive_sha256'],
            'new_archive_bytes':check['source_archive_bytes'],
            'kernel_release':KREL,
            'panel':check['candidate']['panel'],
            'source_pin':'bootstrap_r36os_k1.sh BASE_COMMIT 89719bd08a8a8b32fb0448b58e0e55df20acd0f4, blob 7afd3b5032f78371f687e3bab0a38fc076a6c966',
            'historical_artifact_id_11124161537_available':False,
            'checked_manifest_entries':check['checked_manifest_entries'],
            'compatibility_gaps':check.get('compatibility_gaps',[]),
            'safe_to_flash':False,'hardware_boot_tested':False,'bootloader_or_sd_written':False,
            'integrity_is_not_authenticity':True,
            'bit_for_bit_reproducibility_proven':False,
            'artifact_retention_days_requested':90,
            'downstream_workflows_re_pinned':False,
            'next_step':'Re-pin CP13-18 exact newly verified workflow artifact after successful build; separate SD recovery before boot'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate_archive',type=Path)
    p.add_argument('report_json',type=Path)
    a=p.parse_args(argv)
    target=a.report_json
    if target.suffix.lower()!='.json' or target.name.lower() in ('boot.ini','flash.img'):
        p.error('JSON output only')
    if target.is_symlink() or target.exists():p.error('refusing report overwrite')
    src=Path(__file__).with_name('verify-k1-artifact.py')
    if not src.is_file():p.error('existing CP13 verifier missing')
    spec=importlib.util.spec_from_file_location('cp13_for_cp20',src)
    mod=importlib.util.module_from_spec(spec);assert spec.loader
    spec.loader.exec_module(mod)
    report=make_record(mod.verify(a.candidate_archive))
    with target.open('x',encoding='utf8') as out:
        json.dump(report,out,indent=2,sort_keys=True);out.write('\n')
    print('CP20 NEW K1 provenance PASS; not flashable; historical artifact not reused')

if __name__=='__main__':main()