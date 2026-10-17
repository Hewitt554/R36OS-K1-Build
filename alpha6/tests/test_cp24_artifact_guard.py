import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1]/'cp24'/'artifact_guard.py'
spec=importlib.util.spec_from_file_location('cp24_guard', SRC)
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
NOW=datetime(2026,10,17,16,tzinfo=timezone.utc)

def ledger():
    return {'format':g.FORMAT,'repository':g.REPO,'branch':g.BRANCH,'kernel_release':g.KERNEL,
      'safe_to_flash':False,'hardware_boot_tested':False,'panel4_has_been_physically_tested':False,
      'independent_recovery_proven':False,'artifacts':{
      'k1':{'artifact_id':12103773756,'run_id':39038977056,'head_sha':'b593608d9cdc5f0275cc7f6471e31ff4db5bb366',
        'name':'r36os-alpha6-cp20-REBUILT-K1-HARDWARE-UNTESTED',
        'workflow_path':'.github/workflows/r36os-alpha6-cp20-refresh-k1.yml',
        'archive_sha256':'d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8',
        'retention_requested_days':90},
      'panel4':{'artifact_id':12300000000,'run_id':39042973635,'head_sha':'8246968e91bfc278a742967c83fbed32eaf9aeda',
        'name':'r36os-alpha6-cp17-PANEL4-DIAGNOSTICS-UNTESTED',
        'workflow_path':'.github/workflows/r36os-alpha6-cp17-panel4-diagnostics.yml',
        'retention_requested_days':90}}}

def pair(entry,days=80):
    expiration=NOW+timedelta(days=days)
    return {'artifact':{'id':entry['artifact_id'],'name':entry['name'],'expired':False,
                        'size_in_bytes':2603764,'created_at':(expiration-timedelta(days=90)).isoformat(),
                        'expires_at':expiration.isoformat(),
                        'workflow_run':{'id':entry['run_id'],'head_sha':entry['head_sha']}},
            'run':{'id':entry['run_id'],'head_sha':entry['head_sha'],'head_branch':g.BRANCH,
                   'path':entry['workflow_path'],'status':'completed','conclusion':'success',
                   'event':'push','repository':{'full_name':g.REPO}}}

def inputs(led):return {k:pair(e) for k,e in led['artifacts'].items()}

class CP24RetentionTests(unittest.TestCase):
    def test_valid_fresh(self):
        x=ledger();r=g.validate_all(x,inputs(x),NOW)
        self.assertEqual(r['status'],'PASS_METADATA_FRESH')
        self.assertFalse(r['binary_hash_rechecked']);self.assertFalse(r['safe_to_flash'])
    def test_expiration_approaching(self):
        x=ledger();d=inputs(x);d['panel4']=pair(x['artifacts']['panel4'],14)
        self.assertEqual(g.validate_all(x,d,NOW)['status'],'PASS_METADATA_RENEWAL_REQUIRED')
    def test_missing_metadata_rejected(self):
        x=ledger();d=inputs(x);del d['panel4']
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_missing_artifact_name(self):
        x=ledger();d=inputs(x);d['k1']['artifact']['name']='evil.zip'
        with self.assertRaisesRegex(g.Reject,'name'):g.validate_all(x,d,NOW)
    def test_expired_flag_rejected(self):
        x=ledger();d=inputs(x);d['k1']['artifact']['expired']=True
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_expired_clock_rejected(self):
        x=ledger();d=inputs(x);d['k1']=pair(x['artifacts']['k1'],-1)
        with self.assertRaisesRegex(g.Reject,'expired'):g.validate_all(x,d,NOW)
    def test_wrong_id_rejected(self):
        x=ledger();d=inputs(x);d['panel4']['artifact']['id']+=1
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_wrong_run_sha_rejected(self):
        x=ledger();d=inputs(x);d['panel4']['run']['head_sha']='a'*40
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_wrong_run_path_rejected(self):
        x=ledger();d=inputs(x);d['k1']['run']['path']='.github/workflows/fake.yml'
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_wrong_repo_rejected(self):
        x=ledger();d=inputs(x);d['k1']['run']['repository']['full_name']='attacker/repo'
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_cross_run_artifact_rejected(self):
        x=ledger();d=inputs(x);d['panel4']['artifact']['workflow_run']['id']=999
        with self.assertRaisesRegex(g.Reject,'not linked'):g.validate_all(x,d,NOW)
    def test_fake_retention_extension_rejected(self):
        x=ledger();d=inputs(x);d['panel4']['artifact']['created_at']=(NOW-timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(g.Reject,'90-day'):g.validate_all(x,d,NOW)
    def test_failed_run_rejected(self):
        x=ledger();d=inputs(x);d['panel4']['run']['conclusion']='failure'
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_wrong_branch_rejected(self):
        x=ledger();d=inputs(x);d['panel4']['run']['head_branch']='main'
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_forged_fresh_date_naive_rejected(self):
        x=ledger();d=inputs(x);d['panel4']['artifact']['expires_at']='2027-01-01T00:00:00'
        with self.assertRaises(g.Reject):g.validate_all(x,d,NOW)
    def test_partial_pin_rejected(self):
        x=ledger();x['artifacts']['k1']['archive_sha256']='0'*64
        with self.assertRaises(g.Reject):g.validate_ledger(x)
    def test_wrong_90day_policy_rejected(self):
        x=ledger();x['artifacts']['panel4']['retention_requested_days']=14
        with self.assertRaises(g.Reject):g.validate_ledger(x)
    def test_false_boot_claim_rejected(self):
        x=ledger();x['independent_recovery_proven']=True
        with self.assertRaises(g.Reject):g.validate_ledger(x)
    def test_symlink_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'good.json').write_text('{}');(p/'link.json').symlink_to('good.json')
            with self.assertRaises(g.Reject):g.read_json(p/'link.json')
    def test_not_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('[]')
            with self.assertRaises(g.Reject):g.read_json(p)
    def test_no_install_code_in_guard(self):
        src=SRC.read_text()
        for forbidden in ('subprocess.run(', 'open("/dev/', 'dd if=', 'mkfs.', 'fatwrite mmc', 'saveenv '):
            self.assertNotIn(forbidden,src)

if __name__=='__main__':unittest.main()