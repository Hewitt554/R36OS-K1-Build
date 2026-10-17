from __future__ import annotations
import hashlib, importlib.util, json
from pathlib import Path
import tempfile, unittest

SOURCE=Path(__file__).resolve().parents[1]/'boot'/'cp19_audit_original.py'
spec=importlib.util.spec_from_file_location('cp19_audit',SOURCE)
cp19=importlib.util.module_from_spec(spec);spec.loader.exec_module(cp19)

SYNTHETIC='''odroidgoa-uboot-config
if gpio input b14
then
  setenv PanelNum "4"
  saveenv
  fatwrite mmc 1:1 0x02000000 rg351mp-kernel.dtb ${filesize}
fi
setenv loadaddr "0x02000000"
setenv initrd_loadaddr "0x01100000"
setenv dtb_loadaddr "0x01f00000"
setenv bootargs "root=UUID='e139ce78-9841-40fe-8823-96a304a09859' rootwait rw"
if env exists PanelNum
then
 if test $PanelNum = 5
 then
  load mmc 1:1 ${loadaddr} "${PanelPath}/Image"
 fi
 load mmc 1:1 ${loadaddr} Image
else
 load mmc 1:1 ${loadaddr} Image
fi
load mmc 1:1 ${initrd_loadaddr} uInitrd
load mmc 1:1 ${dtb_loadaddr} "${PanelPathSlash}rk3326-r35s-linux.dtb"
booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}
sleep 3
reset
'''.encode()

def good(b=SYNTHETIC):
    return cp19.audit(b,reference_sha=hashlib.sha256(b).hexdigest(),reference_length=len(b))

class ExactBootAuditTests(unittest.TestCase):
    def test_known_reference(self):
        self.assertEqual(cp19.R3_LENGTH,5108)
        self.assertEqual(cp19.R3_SHA,'b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e')
    def test_synthetic_valid(self):
        x=good()
        self.assertEqual(x['memory_load_addresses']['loadaddr']['value'],'0x02000000')
        self.assertFalse(x['safe_to_flash'])
        self.assertTrue(x['cp08_recovery_gate_retired'])
    def test_real_reference_rejects_synthetic(self):
        with self.assertRaisesRegex(cp19.Reject,'size mismatch'):cp19.audit(SYNTHETIC)
    def test_bad_size(self):
        with self.assertRaisesRegex(cp19.Reject,'size mismatch'):
            cp19.audit(SYNTHETIC,reference_length=len(SYNTHETIC)+1,reference_sha=hashlib.sha256(SYNTHETIC).hexdigest())
    def test_bad_hash(self):
        with self.assertRaisesRegex(cp19.Reject,'SHA-256'):
            cp19.audit(SYNTHETIC,reference_length=len(SYNTHETIC),reference_sha='0'*64)
    def test_missing_readonly_root_marker(self):
        with self.assertRaisesRegex(cp19.Reject,'old root UUID'):
            good(SYNTHETIC.replace(b'e139ce78-9841-40fe-8823-96a304a09859',b'00000000-0000-0000-0000-000000000000'))
    def test_address_change_rejected(self):
        with self.assertRaisesRegex(cp19.Reject,'memory layout'):
            good(SYNTHETIC.replace(b'0x01100000',b'0x01200000'))
    def test_duplicate_address_rejected(self):
        with self.assertRaisesRegex(cp19.Reject,'duplicated'):
            good(SYNTHETIC+b'setenv loadaddr 0x02000000\n')
    def test_legacy_has_writes(self):
        x=good()
        self.assertEqual(x['persistent_write_commands']['saveenv']['count'],1)
        self.assertEqual(x['persistent_write_commands']['fatwrite']['count'],1)
    def test_missing_writes_rejected(self):
        with self.assertRaisesRegex(cp19.Reject,'persistent-write'):
            good(SYNTHETIC.replace(b'  fatwrite mmc',b'  echoxxxx mmc'))
    def test_reset_required(self):
        with self.assertRaisesRegex(cp19.Reject,'post-boot reset'):
            good(SYNTHETIC.replace(b'\nreset\n',b'\necho noreset\n'))
    def test_wrong_boot_order(self):
        with self.assertRaisesRegex(cp19.Reject,'load order'):
            bad=SYNTHETIC.replace(b'load mmc 1:1 ${initrd_loadaddr} uInitrd\nload mmc 1:1 ${dtb_loadaddr}',b'load mmc 1:1 ${dtb_loadaddr} "${PanelPathSlash}rk3326-r35s-linux.dtb"\nload mmc 1:1 ${initrd_loadaddr} uInitrd\n# load mmc 1:1 ${dtb_loadaddr}')
            good(bad)
    def test_panel5_overridden(self):self.assertTrue(good()['panel5_default_kernel_override'])
    def test_cp08_addresses_preceding_insertion(self):self.assertFalse(good()['cp08_insertion_before_address_initialization'])
    def test_unsafe_report_fails_schema(self):
        x=good();x['source_sha256']=cp19.R3_SHA;x['source_length']=cp19.R3_LENGTH;x['safe_to_flash']=True
        with self.assertRaisesRegex(cp19.Reject,'unsafe'):cp19.validate_report(x)
    def test_validated_report_needs_exact_original(self):
        x=good()
        with self.assertRaisesRegex(cp19.Reject,'provenance'):cp19.validate_report(x)
    def test_utf8_required(self):
        with self.assertRaisesRegex(cp19.Reject,'UTF-8'):good(SYNTHETIC+b'\xff')
    def test_full_original_file_not_in_repository(self):
        base=Path(__file__).resolve().parents[1]
        self.assertFalse((base/'boot/R36OS_CP11_VERIFIED_R3_BOOT_ORIGINAL.bin').exists())

if __name__=='__main__':unittest.main()