import importlib.util
from pathlib import Path
import sys
import unittest
p = Path(__file__).resolve().parents[1]/"boot"/"recovery-transaction-model.py"
spec = importlib.util.spec_from_file_location("transaction",p)
m = importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
def armed():
    t=m.Transaction()
    for action in ("stage","snapshot_verified","arm_rescue"):t=t.step(action)
    return t
class TestRecoveryModel(unittest.TestCase):
    def test_staging_cannot_write(self):self.assertFalse(m.Transaction().step("stage").may_write())
    def test_unverified_snapshot_blocks_apply(self):
        with self.assertRaises(ValueError):m.Transaction().step("stage").step("offline_apply")
    def test_arming_only_does_not_write(self):self.assertFalse(armed().may_write())
    def test_offline_apply_writes(self):self.assertTrue(armed().step("offline_apply").may_write())
    def test_failed_apply_blocks_normal_boot(self):
        t=armed().step("offline_apply").step("apply_failed")
        self.assertFalse(t.may_boot_normal())
    def test_failed_trial_requires_restore(self):
        t=armed().step("offline_apply").step("apply_ok").step("unhealthy")
        self.assertEqual(t.state,"need_restore")
        self.assertTrue(t.step("restore_begin").may_write())
    def test_interrupted_trial_requires_restore(self):
        t=armed().step("offline_apply").step("apply_ok").step("interrupted")
        self.assertEqual(t.state,"need_restore")
    def test_failed_restore_stays_blocked(self):
        t=armed().step("offline_apply").step("apply_failed").step("restore_begin").step("restore_failed")
        self.assertFalse(t.may_boot_normal())
        self.assertTrue(t.step("retry").may_write())
    def test_restored_becomes_stable(self):
        t=armed().step("offline_apply").step("apply_failed").step("restore_begin").step("restore_verified").step("clear_recovery")
        self.assertEqual(t,m.Transaction())
    def test_successful_trial_commit(self):
        t=armed().step("offline_apply").step("apply_ok").step("healthy").step("cleanup")
        self.assertEqual(t,m.Transaction())
if __name__=="__main__":unittest.main()
