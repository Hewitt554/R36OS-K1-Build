"""CP21 pin lifecycle/fail-closed contract. No network, block or SD IO."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'k1/cp21_pinned_artifact.py'
spec=importlib.util.spec_from_file_location('cp21_pinning',SOURCE)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
PENDING=json.loads((SOURCE.with_name('k1-candidate-pin.json')).read_text())
SHA='a'*64
COMMIT='b'*40
RUN_ID=39038977056

def ready():
    return {**PENDING, 'status':m.STATUS_READY,'run_id':RUN_ID,'head_sha':COMMIT,'archive_sha256':SHA}

def api():
    return {'id':RUN_ID,'head_sha':COMMIT,'head_branch':m.BRANCH,'path':m.WORKFLOW,
            'status':'completed','conclusion':'success','event':'push', 'run_attempt':1,
            'repository':{'full_name':m.REPO}}

def report():
    return {'format':'R36OS_CP20_REBUILT_K1_ARCHIVE_UNTESTED_NOT_FLASHABLE',
            'status':'REBUILT_ARCHIVE_INTEGRITY_VERIFIED_NOT_BOOT_TESTED',
            'safe_to_flash':False,'hardware_boot_tested':False,'bootloader_or_sd_written':False,
            'kernel_release':m.KREL,'panel':m.PANEL,'downstream_workflows_re_pinned':False,
            'new_archive_sha256':SHA}

class PinTests(unittest.TestCase):
    def test_checked_pending(self):
        self.assertEqual(m.valid_pin(PENDING)['status'],m.STATUS_PENDING)
    def test_pending_is_not_ready(self):
        with self.assertRaisesRegex(m.Reject,'NOT PINNED'):m.valid_pin(PENDING,True)
    def test_valid_ready(self):
        self.assertTrue(m.valid_pin(ready(),True))
    def test_pending_cannot_claim_hash(self):
        p=copy.deepcopy(PENDING);p['archive_sha256']=SHA
        with self.assertRaises(m.Reject):m.valid_pin(p)
    def test_no_unknown_fields(self):
        p=ready();p['download_latest']=True
        with self.assertRaises(m.Reject):m.valid_pin(p)
    def test_no_false_hardware_proof(self):
        p=ready();p['hardware_boot_tested']=True
        with self.assertRaises(m.Reject):m.valid_pin(p)
    def test_no_flash_safety_override(self):
        p=ready();p['safe_to_flash']=True
        with self.assertRaises(m.Reject):m.valid_pin(p)
    def test_uppercase_sha_rejected(self):
        p=ready();p['archive_sha256']='F'*64
        with self.assertRaises(m.Reject):m.valid_pin(p)
    def test_impossible_sha_lengths(self):
        p=ready();p['head_sha']='b'*39
        with self.assertRaises(m.Reject):m.valid_pin(p)
    def test_exact_git_run_verified(self):
        self.assertTrue(m.check_run(ready(),api()))
    def test_wrong_run_id_rejected(self):
        r=api();r['id']=RUN_ID+1
        with self.assertRaises(m.Reject):m.check_run(ready(),r)
    def test_wrong_branch_rejected(self):
        r=api();r['head_branch']='main'
        with self.assertRaises(m.Reject):m.check_run(ready(),r)
    def test_wrong_repo_rejected(self):
        r=api();r['repository']['full_name']='attacker/other'
        with self.assertRaises(m.Reject):m.check_run(ready(),r)
    def test_wrong_workflow_rejected(self):
        r=api();r['path']='.github/workflows/other.yml'
        with self.assertRaises(m.Reject):m.check_run(ready(),r)
    def test_pull_request_run_rejected(self):
        r=api();r['event']='pull_request'
        with self.assertRaises(m.Reject):m.check_run(ready(),r)
    def test_incomplete_workflow_run_rejected(self):
        r=api();r['status']='in_progress';r['conclusion']=None
        with self.assertRaises(m.Reject):m.check_run(ready(),r)
    def test_fail_workflow_rejected(self):
        r=api();r['conclusion']='failure'
        with self.assertRaises(m.Reject):m.check_run(ready(),r)
    def test_valid_draft_pin_approved_for_review_only(self):
        p=m.proposed_pin(PENDING,report(),api());self.assertEqual(p,ready())
    def test_draft_rejects_fake_verified_archive(self):
        x=report();x['safe_to_flash']=True
        with self.assertRaises(m.Reject):m.proposed_pin(PENDING,x,api())
    def test_draft_rejects_already_pinned(self):
        with self.assertRaises(m.Reject):m.proposed_pin(ready(),report(),api())
    def test_draft_rejects_wrong_source_sha(self):
        x=api();x['head_sha']='c'*40
        # This is an entirely new commit, so proposal accepts its own verified run.
        # Verifying the pin against any OTHER run must reject it.
        p=m.proposed_pin(PENDING,report(),x)
        with self.assertRaises(m.Reject):m.check_run(p,api())
    def test_draft_does_not_repin_downstream_by_itself(self):
        p=m.proposed_pin(PENDING,report(),api());self.assertEqual(p['status'],m.STATUS_READY)
        self.assertFalse(p['safe_to_flash'])
    def test_archive_hash_mismatch_blocks_before_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'candidate.tar.gz';path.write_bytes(b'A'*2048)
            def verifier(_):raise AssertionError('must not run on wrong checksum')
            with self.assertRaisesRegex(m.Reject,'not pinned checksum'):
                m.verify_archive(ready(),path,verifier)
    def test_archive_mock_pinned_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'candidate.tar.gz';path.write_bytes(b'A'*2048)
            p=ready();p['archive_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            v=lambda _: {'source_archive_sha256':p['archive_sha256'],
                         'candidate':{'kernel_release':m.KREL,'panel':m.PANEL},
                         'boot_tested':False,'safe_to_flash':False,
                         'ready_for_alpha6_boot_integration':False}
            result=m.verify_archive(p,path,v)
            self.assertEqual(result['status'],'PASS_CI_ARCHIVE_INTEGRITY_ONLY')
            self.assertFalse(result['safe_to_flash'])
    def test_archive_claims_ready_to_boot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'candidate.tar.gz';path.write_bytes(b'A'*2048)
            p=ready();p['archive_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            v=lambda _: {'source_archive_sha256':p['archive_sha256'],
                         'candidate':{'kernel_release':m.KREL,'panel':m.PANEL},
                         'boot_tested':False,'safe_to_flash':False,
                         'ready_for_alpha6_boot_integration':True}
            with self.assertRaisesRegex(m.Reject,'integrity or development'):
                m.verify_archive(p,path,v)
    def test_symlink_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'real.json').write_text('{}');(p/'ref.json').symlink_to(p/'real.json')
            with self.assertRaises(m.Reject):m.read_json(p/'ref.json')
    def test_shell_never_discovers_latest_artifact(self):
        s=(SOURCE.with_name('cp21-download-pinned-k1.sh')).read_text()
        self.assertIn('--get run-id',s)
        self.assertIn('--validate-run',s)
        self.assertIn('--verify-archive',s)
        self.assertNotIn('gh run list',s)
        self.assertNotIn('gh run download 36763257082',s)
        self.assertNotIn('11124161537',s)

if __name__=='__main__':unittest.main()