#!/usr/bin/env python3
"""CP21 fail-closed K1 archive pin validator. OFFLINE by default; NO SD I/O.

On success of a rebuilt K1 CI run, a maintainer may make and review a proposed
pin; production scripts never auto-trust the newest Actions artifact.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat

FORMAT = 'R36OS_CP21_REPRODUCIBLE_K1_SOURCE_PIN_V1'
STATUS_PENDING = 'PENDING_REBUILD'
STATUS_READY = 'PINNED_CI_VERIFIED_NOT_BOOT_TESTED'
REPO = 'Hewitt554/R36OS-K1-Build'
BRANCH = 'alpha6-native-root-cp06'
WORKFLOW = '.github/workflows/r36os-alpha6-cp20-refresh-k1.yml'
ARTIFACT = 'r36os-alpha6-cp20-REBUILT-K1-HARDWARE-UNTESTED'
KREL = '6.12.94-r36os-k1'
PANEL = 'PANEL4_NV3051D_640X480'
OLD_ID = 11124161537
HEX64 = re.compile(r'[a-f0-9]{64}\Z')
HEX40 = re.compile(r'[a-f0-9]{40}\Z')

class Reject(ValueError):
    pass

def issha(x, pattern):
    return isinstance(x, str) and pattern.fullmatch(x) is not None

def valid_pin(data, require_ready=False):
    if not isinstance(data,dict): raise Reject('pin document must be a JSON object')
    exact={'format':FORMAT,'repository':REPO,'branch':BRANCH,'workflow':WORKFLOW,
           'artifact_name':ARTIFACT,'kernel_release':KREL,'panel':PANEL,
           'historical_artifact_id_expired':OLD_ID, 'safe_to_flash':False,
           'hardware_boot_tested':False,'reproducible_bit_for_bit':False}
    for k,v in exact.items():
        if type(data.get(k)) is not type(v) or data[k]!=v:
            raise Reject('pin identity/safety mismatch: '+k)
    if set(data) != set(exact) | {'status','run_id','head_sha','archive_sha256'}:
        raise Reject('unknown or missing pin fields')
    state=data.get('status')
    if state==STATUS_PENDING:
        if any(data[k] is not None for k in ('run_id','head_sha','archive_sha256')):
            raise Reject('pending pin must contain no run, commit or checksum')
        if require_ready: raise Reject('K1 archive is NOT PINNED; rebuild pending')
    elif state==STATUS_READY:
        if type(data['run_id']) is not int or data['run_id']<=0:
            raise Reject('ready pin requires a positive exact GitHub run id')
        if not issha(data['head_sha'],HEX40) or not issha(data['archive_sha256'],HEX64):
            raise Reject('ready pin requires lowercase exact commit and archive SHA256')
    else:
        raise Reject('unsupported pin status')
    return data

def read_json(path, max_bytes=1024*1024):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>max_bytes:
        raise Reject('unsafe or missing JSON file')
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError,json.JSONDecodeError) as e: raise Reject('invalid JSON file') from e

def check_run(pin, data):
    valid_pin(pin,True)
    if not isinstance(data,dict): raise Reject('run API JSON is not an object')
    checks={'id':pin['run_id'],'head_sha':pin['head_sha'], 'head_branch':BRANCH,
            'path':WORKFLOW,'status':'completed','conclusion':'success','event':'push'}
    for k,v in checks.items():
        if type(data.get(k)) is not type(v) or data[k]!=v:
            raise Reject('K1 workflow run API provenance mismatch: '+k)
    repo=data.get('repository')
    if not isinstance(repo,dict) or repo.get('full_name') != REPO:
        raise Reject('K1 run source repository does not match')
    if not data.get('run_attempt') or type(data['run_attempt']) is not int:
        raise Reject('missing workflow run attempt')
    return True

def sha_file(path):
    p=Path(path)
    if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode) or p.stat().st_size<1024:
        raise Reject('unsafe/short K1 archive file')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify_archive(pin, archive, verifier=None):
    valid_pin(pin,True)
    p=Path(archive)
    if sha_file(p)!=pin['archive_sha256']:
        raise Reject('rebuilt K1 archive SHA256 not pinned checksum')
    if verifier is None:
        source=Path(__file__).with_name('verify-k1-artifact.py')
        if not source.is_file(): raise Reject('CP13 K1 archive verifier unavailable')
        spec=importlib.util.spec_from_file_location('cp13_for_cp21',source)
        mod=importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        verifier=mod.verify
    inspected=verifier(p)
    if (inspected.get('source_archive_sha256')!=pin['archive_sha256'] or
        inspected.get('candidate',{}).get('kernel_release')!=KREL or
        inspected.get('candidate',{}).get('panel')!=PANEL or
        inspected.get('boot_tested') is not False or inspected.get('safe_to_flash') is not False or
        inspected.get('ready_for_alpha6_boot_integration') is not False):
        raise Reject('K1 CP13 integrity or development safety contract failed')
    return {'status':'PASS_CI_ARCHIVE_INTEGRITY_ONLY', 'kernel_release':KREL,
            'archive_sha256':pin['archive_sha256'], 'source_run_id':pin['run_id'],
            'safe_to_flash':False,'hardware_boot_tested':False}

def proposed_pin(pending, report, run):
    valid_pin(pending)
    if pending['status']!=STATUS_PENDING:
        raise Reject('make-proposal requires a pending pin, never overwrites ready pins')
    if (not isinstance(report,dict) or
        report.get('format')!='R36OS_CP20_REBUILT_K1_ARCHIVE_UNTESTED_NOT_FLASHABLE' or
        report.get('status')!='REBUILT_ARCHIVE_INTEGRITY_VERIFIED_NOT_BOOT_TESTED' or
        report.get('safe_to_flash') is not False or
        report.get('hardware_boot_tested') is not False or
        report.get('bootloader_or_sd_written') is not False or
        report.get('kernel_release')!=KREL or report.get('panel')!=PANEL or
        report.get('downstream_workflows_re_pinned') is not False or
        not issha(report.get('new_archive_sha256'),HEX64)):
        raise Reject('invalid new CP20 verifier report; no proposed pin')
    if not isinstance(run,dict) or not issha(run.get('head_sha'),HEX40):
        raise Reject('missing workflow API run SHA')
    p={**pending,'status':STATUS_READY,'run_id':run.get('id'),
       'head_sha':run['head_sha'],'archive_sha256':report['new_archive_sha256']}
    valid_pin(p,True)
    check_run(p,run)
    return p

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pin',type=Path)
    grp=ap.add_mutually_exclusive_group(required=True)
    grp.add_argument('--check-pending',action='store_true')
    grp.add_argument('--get',choices=('run-id','artifact-name','sha256','status'))
    grp.add_argument('--validate-run',type=Path)
    grp.add_argument('--verify-archive',type=Path)
    grp.add_argument('--propose-report',type=Path)
    ap.add_argument('--run-json',type=Path)
    ap.add_argument('--output',type=Path)
    a=ap.parse_args(argv)
    try:
        pin=valid_pin(read_json(a.pin))
        if a.check_pending:
            if pin['status']!=STATUS_PENDING:raise Reject('this command is only for pending state')
            print('CP21 pin is PENDING — downstream artifact access blocked, not flashable')
        elif a.get:
            valid_pin(pin,True)
            print({'run-id':pin['run_id'],'artifact-name':pin['artifact_name'],
                   'sha256':pin['archive_sha256'],'status':pin['status']}[a.get])
        elif a.validate_run:
            check_run(pin,read_json(a.validate_run));print('CP21 pinned GitHub run provenance PASS')
        elif a.verify_archive:
            print(json.dumps(verify_archive(pin,a.verify_archive),sort_keys=True))
        else:
            if a.run_json is None or a.output is None or a.output.suffix!='.json' or a.output.is_symlink() or a.output.exists():
                raise Reject('proposal requires run JSON and a new .json output file')
            draft=proposed_pin(pin,read_json(a.propose_report),read_json(a.run_json))
            with a.output.open('x') as f: json.dump(draft,f,indent=2,sort_keys=True);f.write('\n')
            print('CP21 proposed pin written for REVIEW; not activated or installed')
    except (Reject,OSError) as e: ap.error(str(e))
    return 0

if __name__=='__main__':raise SystemExit(main())