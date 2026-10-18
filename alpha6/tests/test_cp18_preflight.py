"""CP18 strict component-only preflight tests. No actual SD devices used."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod
    spec.loader.exec_module(mod)
    return mod
cp18=module(BASE/'boot/cp18-first-boot-preflight.py','r36os_cp18')
cp15=module(BASE/'boot/build-cp15-initrd.py','r36os_cp15_for_cp18')
REAL=json.loads((BASE/'boot/cp18-r3-boot-evidence.json').read_text())

def sample_k1():
    return {'root_uuid_inherited':cp18.R3_UUID,'candidate_id':'a'*24,
      'kernel_release':cp18.KERNEL,'archive_sha256':'1'*64,
      'modules_archived_sha256':'2'*64,
      'kernel_image':{'sha256':'3'*64,'bytes':100},
      'panel4_dtb':{'sha256':'4'*64,'bytes':10}}

def sample_cp17(folder):
    packed=gzip.compress(b'070701' + b'\0'*120)
    files={}
    for id,name in cp18.EXPECTED_IMAGES.items():
        blob=cp15.uimage(packed,int(id))
        (folder/name).write_bytes(blob)
        files[id]={'name':name,'sha256':cp18.digest(blob),'bytes':len(blob)}
    (folder/'cp17-diagnostic-report.json').write_text(json.dumps({
       'format':'R36OS_CP17_DIAGNOSTIC_RAMDISK','status':'BUILT_UNTESTED',
       'safe_to_flash':False,'boot_tested':False,'writes_persistent_storage':False,
       'automatic_recovery':False,'kernel_target':cp18.KERNEL,
       'payload':{'payload_bytes':len(packed)},'variants':files}))
    (folder/'cp17-k1-panel4-dtb-report.json').write_text(json.dumps({
      'format':'R36OS_CP17_STATIC_PANEL4_FDT_AUDIT_V1',
      'status':'PASS_STATIC_STRUCTURE_NOT_HARDWARE_BOOT',
      'kernel_release':cp18.KERNEL,'safe_to_flash':False,'boot_tested':False,'display_tested':False,
      'nv3051d_compatible_explicit':False,'rk3326_root_compatible':True,
      'enabled_mmc_nodes':[{},{}],'panel_node_compatible':['rocknix,generic-dsi'],
      'dtb_sha256':'4'*64,'k1_source_sha256':'1'*64}))
    (folder/'DO_NOT_FLASH.txt').write_text('NOT BOOT TESTED. NO FLASH.')

class CP18Preflight(unittest.TestCase):
    def test_real_r3_evidence_detects_persistent_commands(self):
        result=cp18.inspect_r3_evidence(REAL)
        self.assertEqual(result['legacy_boot_write_commands'],['fatwrite','saveenv'])
        self.assertFalse(result['legacy_boot_treat_as_read_only_fallback'])
        self.assertFalse(result['original_boot_ini_available'])
    def test_r3_requires_exact_original_hash(self):
        r=json.loads(json.dumps(REAL));r['boot_scripts'][0]['sha256']='0'*64
        with self.assertRaisesRegex(cp18.Reject,'fingerprint'):cp18.inspect_r3_evidence(r)
    def test_r3_selected_lines_not_full_boot(self):
        r=json.loads(json.dumps(REAL));r['original_boot_ini_full_bytes_available']=True
        with self.assertRaisesRegex(cp18.Reject,'not supplied'):cp18.inspect_r3_evidence(r)
    def test_r3_stored_writes_not_suppressed(self):
        r=json.loads(json.dumps(REAL));r['boot_scripts'][0]['relevant_lines']=[x for x in r['boot_scripts'][0]['relevant_lines'] if not x.strip().startswith('fatwrite')]
        with self.assertRaisesRegex(cp18.Reject,'mutating boot'):cp18.inspect_r3_evidence(r)
    def test_r3_missing_panel_chooser_rejected(self):
        r=json.loads(json.dumps(REAL));r['boot_scripts'][0]['relevant_lines']=[x for x in r['boot_scripts'][0]['relevant_lines'] if 'PanelPathSlash' not in x]
        with self.assertRaisesRegex(cp18.Reject,'panel selection'):cp18.inspect_r3_evidence(r)
    def test_r3_wrong_script_count_rejected(self):
        r=json.loads(json.dumps(REAL));r['boot_scripts'].append(r['boot_scripts'][0])
        with self.assertRaisesRegex(cp18.Reject,'exactly one'):cp18.inspect_r3_evidence(r)
    def test_cp17_valid_variants(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sample_cp17(p)
            out=cp18.inspect_diagnostic_bundle(p)
            self.assertEqual(len(out['variant_files']),2)
    def test_cp17_one_corrupted_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sample_cp17(p)
            f=p/cp18.EXPECTED_IMAGES['22'];b=bytearray(f.read_bytes());b[-1]^=1;f.write_bytes(b)
            with self.assertRaisesRegex(cp18.Reject,'header failed'):cp18.inspect_diagnostic_bundle(p)
    def test_cp17_extra_boot_ini_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sample_cp17(p);(p/'boot.ini').write_bytes(b'danger')
            with self.assertRaisesRegex(cp18.Reject,'unexpected'):cp18.inspect_diagnostic_bundle(p)
    def test_cp17_unsafe_mutating_flag_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sample_cp17(p)
            f=p/'cp17-diagnostic-report.json';x=json.loads(f.read_text());x['writes_persistent_storage']=True;f.write_text(json.dumps(x))
            with self.assertRaisesRegex(cp18.Reject,'prohibit'):cp18.inspect_diagnostic_bundle(p)
    def test_cp17_wrong_panel_claim_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sample_cp17(p)
            f=p/'cp17-k1-panel4-dtb-report.json';data=json.loads(f.read_text())
            data['nv3051d_compatible_explicit']=True;f.write_text(json.dumps(data))
            with self.assertRaisesRegex(cp18.Reject,'DTB report incompatible'):cp18.inspect_diagnostic_bundle(p)
    def test_cp17_missing_header_variant_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sample_cp17(p);(p/cp18.EXPECTED_IMAGES['2']).unlink()
            with self.assertRaisesRegex(cp18.Reject,'unexpected or missing'):cp18.inspect_diagnostic_bundle(p)
    def test_cp17_arch_variants_same_payload_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sample_cp17(p)
            other=gzip.compress(b'070701' + b'\0'*121)
            blob=cp15.uimage(other,22)
            f=p/cp18.EXPECTED_IMAGES['22'];f.write_bytes(blob)
            report=p/'cp17-diagnostic-report.json';x=json.loads(report.read_text());x['variants']['22']['sha256']=cp18.digest(blob);x['variants']['22']['bytes']=len(blob);report.write_text(json.dumps(x))
            with self.assertRaisesRegex(cp18.Reject,'identical'):cp18.inspect_diagnostic_bundle(p)
    def test_workspace_must_be_disposable_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(cp18.Reject,'uniquely named'):cp18.workspace(Path(d))
    def test_workspace_existing_files_rejected(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp18-preflight-') as d:
            p=Path(d);(p/'old').touch()
            with self.assertRaisesRegex(cp18.Reject,'empty'):cp18.workspace(p)
    def test_workspace_safe_fixture(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp18-preflight-') as d:
            self.assertEqual(cp18.workspace(Path(d)),Path(d))
    def test_report_explicitly_not_installable(self):
        rep=cp18.create_report(sample_k1(),{'k1_source_sha256':'1'*64,'panel4_dtb_sha256':'4'*64},cp18.inspect_r3_evidence(REAL))
        self.assertFalse(rep['safe_to_flash']);self.assertFalse(rep['boot_script_generated'])
        self.assertEqual(rep['installable_files'],[])
        self.assertGreaterEqual(len(rep['blockers']),5)
    def test_report_rejects_non_r3_pinned_root(self):
        k=sample_k1();k['root_uuid_inherited']='0'*36
        with self.assertRaisesRegex(cp18.Reject,'K1/R3'):cp18.create_report(k,{'k1_source_sha256':'1'*64,'panel4_dtb_sha256':'4'*64},cp18.inspect_r3_evidence(REAL))
    def test_mismatched_panel_source_rejected(self):
        with self.assertRaisesRegex(cp18.Reject,'does not match'):
            cp18.create_report(sample_k1(),{'k1_source_sha256':'0'*64,'panel4_dtb_sha256':'4'*64},cp18.inspect_r3_evidence(REAL))
    def test_no_code_to_stage_boot_scripts(self):
        src=(BASE/'boot/cp18-first-boot-preflight.py').read_text()
        self.assertNotIn('fatwrite mmc',src)
        self.assertNotIn('sfdisk /dev/',src)
        self.assertNotIn('mkfs.ext4 /dev/',src)
        self.assertNotIn('flash_image_ready=true',src)

if __name__=='__main__':unittest.main()