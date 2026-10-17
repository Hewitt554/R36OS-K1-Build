"""CP23 reviewed-artifact metadata controls using synthetic fixtures only."""
import copy,importlib.util,json,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cp23',BASE/'k1/cp23_verify_metadata.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
pin=json.loads((BASE/'k1/k1-candidate-pin.json').read_text())

def run_fixture():
    return dict(id=m.RUN_ID,head_sha=m.RUN_SHA,head_branch=pin['branch'],path=pin['workflow'],status='completed',conclusion='success',event='push',repository={'full_name':pin['repository']},run_attempt=1)

def artifact_fixture():
    return {'total_count':1,'artifacts':[dict(id=m.ARTIFACT_ID,name=m.ARTIFACT_NAME,expired=False,size_in_bytes=560334073,expires_at='2027-01-15T14:01:22Z',workflow_run={'id':m.RUN_ID})]}

class CP23Metadata(unittest.TestCase):
    def test_valid(self):
        x=m.verify(copy.deepcopy(pin),run_fixture(),artifact_fixture())
        self.assertFalse(x['safe_to_flash']);self.assertFalse(x['new_archive_rechecked_here']);self.assertEqual(x['artifact_id'],m.ARTIFACT_ID)
    def test_pending_rejected(self):
        q=copy.deepcopy(pin);q.update(status='PENDING_REBUILD',run_id=None,head_sha=None,archive_sha256=None)
        with self.assertRaises(Exception):m.verify(q,run_fixture(),artifact_fixture())
    def test_changed_hash_rejected(self):
        q=copy.deepcopy(pin);q['archive_sha256']='a'*64
        with self.assertRaises(m.Reject):m.verify(q,run_fixture(),artifact_fixture())
    def test_changed_run_rejected(self):
        q=copy.deepcopy(pin);q['run_id']=7
        with self.assertRaises(Exception):m.verify(q,run_fixture(),artifact_fixture())
    def test_branch_wrong(self):
        r=run_fixture();r['head_branch']='main'
        with self.assertRaises(Exception):m.verify(pin,r,artifact_fixture())
    def test_wrong_source_commit(self):
        r=run_fixture();r['head_sha']='b'*40
        with self.assertRaises(Exception):m.verify(pin,r,artifact_fixture())
    def test_failed_run(self):
        r=run_fixture();r['conclusion']='failure'
        with self.assertRaises(Exception):m.verify(pin,r,artifact_fixture())
    def test_wrong_repo(self):
        r=run_fixture();r['repository']={'full_name':'SomeoneElse/not-this'}
        with self.assertRaises(Exception):m.verify(pin,r,artifact_fixture())
    def test_no_artifact(self):
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),{'artifacts':[]})
    def test_expired_artifact(self):
        a=artifact_fixture();a['artifacts'][0]['expired']=True
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),a)
    def test_wrong_artifact_id(self):
        a=artifact_fixture();a['artifacts'][0]['id']=999
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),a)
    def test_wrong_artifact_name(self):
        a=artifact_fixture();a['artifacts'][0]['name']='random-zip'
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),a)
    def test_other_run_artifact(self):
        a=artifact_fixture();a['artifacts'][0]['workflow_run']['id']=999
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),a)
    def test_undersized_artifact(self):
        a=artifact_fixture();a['artifacts'][0]['size_in_bytes']=1
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),a)
    def test_oversized_artifact(self):
        a=artifact_fixture();a['artifacts'][0]['size_in_bytes']=900_000_000
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),a)
    def test_malformed_artifact_response(self):
        with self.assertRaises(m.Reject):m.verify(pin,run_fixture(),{'artifacts':None})
    def test_wrong_event(self):
        r=run_fixture();r['event']='workflow_dispatch'
        with self.assertRaises(Exception):m.verify(pin,r,artifact_fixture())
    def test_unsafe_flag_in_pin(self):
        q=copy.deepcopy(pin);q['safe_to_flash']=True
        with self.assertRaises(Exception):m.verify(q,run_fixture(),artifact_fixture())

if __name__=='__main__':unittest.main()