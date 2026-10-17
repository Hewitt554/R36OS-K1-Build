import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'k1/cp20_verify_rebuilt_candidate.py'
spec=importlib.util.spec_from_file_location('cp20_k1', SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def sample():
    return {'candidate':{'kernel_release':'6.12.94-r36os-k1','panel':'PANEL4_NV3051D_640X480'},
            'boot_tested':False,'safe_to_flash':False,
            'source_archive_sha256':'2'*64,'source_archive_bytes':1234,
            'checked_manifest_entries':7,'compatibility_gaps':['old initrd root UUID']}

class RebuiltArtifactTests(unittest.TestCase):
    def test_valid_record_does_not_claim_boot(self):
        x=m.make_record(sample())
        self.assertFalse(x['safe_to_flash'])
        self.assertFalse(x['hardware_boot_tested'])
        self.assertFalse(x['bit_for_bit_reproducibility_proven'])
        self.assertFalse(x['downstream_workflows_re_pinned'])
        self.assertEqual(x['new_archive_sha256'],'2'*64)
        self.assertEqual(x['artifact_retention_days_requested'],90)
    def test_reject_wrong_release(self):
        x=sample();x['candidate']['kernel_release']='6.12.93'
        with self.assertRaises(m.Reject):m.make_record(x)
    def test_reject_wrong_panel(self):
        x=sample();x['candidate']['panel']='PANEL5'
        with self.assertRaises(m.Reject):m.make_record(x)
    def test_reject_flash_ready(self):
        x=sample();x['safe_to_flash']=True
        with self.assertRaises(m.Reject):m.make_record(x)
    def test_reject_boot_tested_claim(self):
        x=sample();x['boot_tested']=True
        with self.assertRaises(m.Reject):m.make_record(x)
    def test_reject_incomplete_manifest(self):
        x=sample();x['checked_manifest_entries']=3
        with self.assertRaises(m.Reject):m.make_record(x)
    def test_reject_missing_sha(self):
        x=sample();x['source_archive_sha256']=''
        with self.assertRaises(m.Reject):m.make_record(x)

if __name__=='__main__':unittest.main()