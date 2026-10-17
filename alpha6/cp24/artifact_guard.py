#!/usr/bin/env python3
"""CP24 read-only GitHub Actions artifact retention/provenance safety guard.

Accepts caller-supplied metadata JSON; the CI workflow obtains metadata using
read-only GitHub APIs. Never downloads images, updates refs or modifies SD media.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

FORMAT = 'R36OS_CP24_ARTIFACT_LEDGER_V1'
REPO = 'Hewitt554/R36OS-K1-Build'
BRANCH = 'alpha6-native-root-cp06'
KERNEL = '6.12.94-r36os-k1'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')

class Reject(ValueError): pass

def read_json(path: Path) -> dict:
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 1024*1024:
        raise Reject('metadata missing, symlinked, or too large')
    d=json.loads(p.read_text(encoding='utf8'))
    if not isinstance(d,dict):raise Reject('metadata must be JSON object')
    return d

def stamp(value: str) -> datetime:
    if not isinstance(value,str):raise Reject('missing ISO UTC expiration timestamp')
    try: dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as e:raise Reject('bad timestamp') from e
    if dt.tzinfo is None:raise Reject('timezone must be specified')
    return dt.astimezone(timezone.utc)

def validate_ledger(d:dict)->dict:
    if not isinstance(d,dict) or d.get('format')!=FORMAT:
        raise Reject('wrong CP24 ledger')
    if d.get('repository')!=REPO or d.get('branch')!=BRANCH:
        raise Reject('wrong repo/branch')
    if d.get('kernel_release')!=KERNEL or d.get('safe_to_flash') is not False or d.get('hardware_boot_tested') is not False:
        raise Reject('kernel identity or safety claims violated')
    entries=d.get('artifacts')
    if not isinstance(entries,dict) or set(entries)!= {'k1','panel4'}:
        raise Reject('exact K1 and Panel4 identities required')
    for key,v in entries.items():
        if not isinstance(v,dict):raise Reject('entry must be object')
        for field in ('artifact_id','run_id'):
            if type(v.get(field)) is not int or v[field]<=0:raise Reject('bad '+field)
        if not HEX40.fullmatch(str(v.get('head_sha',''))):raise Reject('invalid head SHA')
        if not isinstance(v.get('name'),str) or not v['name'].startswith('r36os-alpha6-'):
            raise Reject('unsafe artifact name')
        if not isinstance(v.get('workflow_path'),str) or not v['workflow_path'].startswith('.github/workflows/'):
            raise Reject('unsafe workflow path')
        if v.get('retention_requested_days') != 90:
            raise Reject('retention policy must request 90 days')
    if entries['k1'].get('archive_sha256')!='d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8':
        raise Reject('K1 whole archive checksum changed without approved repin')
    if entries['k1']['run_id']!=39038977056 or entries['k1']['head_sha']!='b593608d9cdc5f0275cc7f6471e31ff4db5bb366':
        raise Reject('K1 run identity changed without CP21 source pin')
    if entries['panel4']['name']!='r36os-alpha6-cp17-PANEL4-DIAGNOSTICS-UNTESTED':
        raise Reject('unexpected Panel4 artifact')
    if d.get('panel4_has_been_physically_tested') is not False or d.get('independent_recovery_proven') is not False:
        raise Reject('hardware readiness misrepresented')
    return d

def check_entry(expected:dict, artifact:dict, run:dict, now:datetime, warn_days:int=21)->dict:
    if type(artifact.get('id')) is not int or artifact['id']!=expected['artifact_id']:
        raise Reject('artifact ID mismatch')
    if artifact.get('name') != expected['name'] or artifact.get('expired') is not False:
        raise Reject('artifact name or expired status mismatch')
    if type(artifact.get('size_in_bytes')) is not int or artifact['size_in_bytes']<1000:
        raise Reject('artifact missing/implausibly small')
    if not isinstance(run,dict):raise Reject('run metadata missing')
    checks={'id':expected['run_id'],'head_sha':expected['head_sha'],
            'head_branch':BRANCH,'path':expected['workflow_path'],
            'status':'completed','conclusion':'success'}
    for k,v in checks.items():
        if type(run.get(k)) is not type(v) or run[k]!=v:
            raise Reject('workflow run mismatch: '+k)
    if run.get('event') not in ('push','pull_request','workflow_dispatch'):
        raise Reject('unexpected artifact workflow event')
    if not isinstance(run.get('repository'),dict) or run['repository'].get('full_name')!=REPO:
        raise Reject('wrong workflow repository')
    if not isinstance(now,datetime) or now.tzinfo is None:raise Reject('current date must be UTC-aware')
    workflow_artifact=artifact.get('workflow_run')
    if not isinstance(workflow_artifact,dict) or (
        workflow_artifact.get('id')!=expected['run_id'] or
        workflow_artifact.get('head_sha')!=expected['head_sha']):
        raise Reject('artifact is not linked to exact pinned run')
    created=stamp(artifact.get('created_at'))
    expiration=stamp(artifact.get('expires_at'))
    retained=(expiration-created).total_seconds()/86400
    if retained<85 or retained>95:
        raise Reject('artifact does not have expected ~90-day retention')
    days=(expiration-now.astimezone(timezone.utc)).total_seconds()/86400
    if days<=0:raise Reject('artifact expired even if API flag is false')
    return {'artifact_id':expected['artifact_id'],'days_left':round(days,2),
            'expiration_utc':expiration.isoformat(),
            'needs_renewal':days<=warn_days,
            'status':'VERIFIED_UNEXPIRED_METADATA_ONLY',
            'binary_hash_rechecked':False,'safe_to_flash':False}

def validate_all(ledger:dict, inputs:dict, now:datetime)->dict:
    validate_ledger(ledger)
    if not isinstance(inputs,dict) or set(inputs)!=set(ledger['artifacts']):
        raise Reject('missing artifact/run metadata pair')
    result={}
    for key,entry in ledger['artifacts'].items():
        pair=inputs[key]
        if not isinstance(pair,dict) or set(pair)!= {'artifact','run'}:
            raise Reject('missing artifact/run input for '+key)
        result[key]=check_entry(entry,pair['artifact'],pair['run'],now)
    return {'format':'R36OS_CP24_METADATA_AUDIT_V1',
            'status':'PASS_METADATA_RENEWAL_REQUIRED' if any(x['needs_renewal'] for x in result.values()) else 'PASS_METADATA_FRESH',
            'artifacts':result,'safe_to_flash':False,'hardware_boot_tested':False,
            'binary_hash_rechecked':False,
            'note':'Metadata check only. CP13/CP18 integrity workflows provide separate binary-hash validation.'}

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ledger',type=Path,required=True)
    ap.add_argument('--api-input',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if a.out.exists() or a.out.is_symlink() or a.out.suffix!='.json':
        ap.error('output must be a NEW .json file')
    try:
        r=validate_all(read_json(a.ledger),read_json(a.api_input),datetime.now(timezone.utc))
        a.out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf8')
    except (OSError,ValueError,TypeError,KeyError) as e:ap.error(str(e))
    print(r['status'], '(no hardware boot or binary-hash claim)')
    return 0
if __name__=='__main__':raise SystemExit(main())