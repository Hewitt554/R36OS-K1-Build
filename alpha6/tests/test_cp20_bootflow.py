"""CP20 branch model: explicit fixtures, no actual U-Boot or raw-card execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
P=BASE/'boot/cp20_bootflow_sim.py'
spec=importlib.util.spec_from_file_location('cp20_model',P)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
AUDIT=json.loads((BASE/'CP19_VERIFIED_ORIGINAL_R3_BOOT_AUDIT.json').read_text())

class CP20BootMatrixTests(unittest.TestCase):
    def test_provenance_accepts_pinned_audit(self): self.assertEqual(m.verify_audit(AUDIT)['source_sha256'],m.SHA)
    def test_wrong_hash_rejected(self):
        a=dict(AUDIT,source_sha256='0'*64)
        with self.assertRaisesRegex(m.UnsafeEvidence,'provenance'):m.verify_audit(a)
    def test_reject_invalid_original_bytes(self):
        with self.assertRaisesRegex(m.UnsafeEvidence,'SHA-256'):m.verify_audit(AUDIT,b'A'*5108)
    def test_legacy_boot_contract_lines(self):
        self.assertEqual(m.EXPECTED_LINES['booti'],200)
        self.assertEqual(AUDIT['post_booti_reset_line'],203)
    def test_wrong_boot_line_rejected(self):
        a=dict(AUDIT,legacy_booti_line=198)
        with self.assertRaisesRegex(m.UnsafeEvidence,'boot-line'):m.verify_audit(a)
    def test_wrong_address_rejected(self):
        x=dict(AUDIT,memory_load_addresses={**AUDIT['memory_load_addresses'],'loadaddr':{'value':'0x0','line':170}})
        with self.assertRaisesRegex(m.UnsafeEvidence,'memory address'):m.verify_audit(x)
    def test_wrong_write_evidence_rejected(self):
        x=dict(AUDIT,persistent_write_commands={'fatwrite':{'count':0,'lines':[]},'saveenv':AUDIT['persistent_write_commands']['saveenv']})
        with self.assertRaisesRegex(m.UnsafeEvidence,'persistent-write'):m.verify_audit(x)
    def test_installable_flag_rejected(self):
        with self.assertRaises(m.UnsafeEvidence):m.verify_audit(dict(AUDIT,safe_to_flash=True))
    def test_cp08_allowed_flag_rejected(self):
        with self.assertRaises(m.UnsafeEvidence):m.verify_audit(dict(AUDIT,cp08_recovery_gate_approved=True))
    def test_fake_load_guard_rejected(self):
        with self.assertRaises(m.UnsafeEvidence):m.verify_audit(dict(AUDIT,legacy_kernel_loads_error_checked=True))
    def test_reject_unknown_scenario_controls(self):
        with self.assertRaisesRegex(m.UnsafeEvidence,'unknown fields'):m.simulate(AUDIT,{'write_sd':True})
    def test_reject_wrong_bool(self):
        with self.assertRaisesRegex(m.UnsafeEvidence,'bool expected'):m.simulate(AUDIT,{'r1':1})
    def test_reject_bad_panel(self):
        with self.assertRaisesRegex(m.UnsafeEvidence,'saved_panel'):m.simulate(AUDIT,{'saved_panel':7})
    def test_reject_duplicate_buttons(self):
        with self.assertRaisesRegex(m.UnsafeEvidence,'buttons'):m.simulate(AUDIT,{'buttons':['left','left']})
    def test_normal_boot_no_persistent_changes(self):
        x=m.simulate(AUDIT,{})
        self.assertEqual(x['status'],'assumed_kernel_handoff_NOT_HARDWARE_PROVEN')
        self.assertEqual(x['persistent_write_count'],0)
        self.assertTrue(x['booti_attempted'])
        self.assertFalse(x['actual_boot_tested'])
    def test_panel4_chooser_saves_env_writes_dtb_powers_off(self):
        x=m.simulate(AUDIT,{'r1':True,'buttons':['left']})
        self.assertEqual(x['status'],'poweroff_after_panel_selection')
        self.assertEqual(x['resulting_panel_environment_in_RAM'],4)
        self.assertEqual([(y['line'],y['command']) for y in x['persistent_write_attempts']],[(119,'saveenv'),(123,'fatwrite')])
        self.assertFalse(x['booti_attempted'])
    def test_marker_creation_blocks_chooser_same_boot_if_write_succeeds(self):
        x=m.simulate(AUDIT,{'r1':True,'volume_minus':True,'buttons':['left']})
        self.assertEqual(x['persistent_write_count'],1)
        self.assertEqual(x['persistent_write_attempts'][0]['line'],13)
        self.assertTrue(x['booti_attempted'])
    def test_failed_marker_fatwrite_allows_chooser(self):
        x=m.simulate(AUDIT,{'r1':True,'volume_minus':True,'fatwrite_ok':False,'buttons':['left']})
        self.assertEqual(x['status'],'poweroff_after_panel_selection')
        self.assertTrue(any('failed' in w for w in x['warnings']))
    def test_existing_marker_skips_chooser(self):
        x=m.simulate(AUDIT,{'r1':True,'nopanelchooser':True,'buttons':['left']})
        self.assertTrue(x['booti_attempted'])
        self.assertEqual(x['persistent_write_count'],0)
    def test_unset_panel_saves_environment(self):
        x=m.simulate(AUDIT,{'nopanelchooser':True,'unsetpanelchooser':True,'saved_panel':4})
        self.assertEqual(x['persistent_write_count'],1)
        self.assertIsNone(x['resulting_panel_environment_in_RAM'])
    def test_chooser_priority_order(self):
        x=m.simulate(AUDIT,{'r1':True,'buttons':['left','up']})
        self.assertEqual(x['resulting_panel_environment_in_RAM'],1)
    def test_panel5_default_image_overwrite_risk(self):
        x=m.simulate(AUDIT,{'saved_panel':5})
        self.assertTrue(any('Panel 5' in w for w in x['warnings']))
        self.assertEqual([e['line'] for e in x['modeled_actions'] if 'image' in e['event']],[182,185])
    def test_unchecked_kernel_load_failure(self):
        x=m.simulate(AUDIT,{'legacy_image_read_ok':False})
        self.assertTrue(x['booti_attempted'])
        self.assertIn('indeterminate',x['status'])
    def test_unchecked_initrd_load_failure(self):
        x=m.simulate(AUDIT,{'legacy_initrd_read_ok':False})
        self.assertIn('uInitrd',x['warnings'][0])
    def test_unchecked_dtb_load_failure(self):
        x=m.simulate(AUDIT,{'legacy_dtb_read_ok':False})
        self.assertIn('DTB',x['warnings'][0])
    def test_boot_return_resets_not_rescues(self):
        x=m.simulate(AUDIT,{'booti_returns':True})
        self.assertEqual(x['status'],'reset_after_return_from_booti')
        self.assertEqual(x['modeled_actions'][-1]['line'],203)
        self.assertFalse(x['fallback_exercised'])
    def test_missing_panel_dtb_still_saveenv(self):
        x=m.simulate(AUDIT,{'r1':True,'buttons':['left'],'panel_dtb_read_ok':False})
        self.assertEqual(x['persistent_write_count'],1)
        self.assertEqual(x['status'],'poweroff_after_panel_selection')
    def test_matrix_consistent_no_install_files(self):
        r=m.run_matrix(AUDIT)
        self.assertEqual(r['summary'],{'scenario_count':15,'scenarios_with_persistent_writes':6,
                       'scenarios_with_unchecked_load_failure':3,'recovery_paths_physically_verified':0})
        self.assertEqual(r['installation_artifacts'],[])
        self.assertIs(r['safe_to_flash'],False)
        self.assertFalse(r['actual_uboot_boot_tested'])
    def test_output_json_only_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/'model.json'
            self.assertEqual(m.main(['--audit',str(BASE/'CP19_VERIFIED_ORIGINAL_R3_BOOT_AUDIT.json'),'--output',str(dest)]),0)
            self.assertTrue(dest.is_file())
            with self.assertRaises(SystemExit):
                m.main(['--audit',str(BASE/'CP19_VERIFIED_ORIGINAL_R3_BOOT_AUDIT.json'),'--output',str(dest)])
    def test_no_device_access_in_model(self):
        code=P.read_text()
        for val in ('/dev/mmcblk','subprocess.run','os.system','fatwrite mmc','saveenv\\n'):
            self.assertNotIn(val,code)

if __name__=='__main__':unittest.main()