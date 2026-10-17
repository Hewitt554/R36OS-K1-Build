import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/'cp24'/'spare_test_contract.py'
spec=importlib.util.spec_from_file_location('cp24_spare',SRC)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

# Synthetic-only fixtures; no original user raw U-Boot script committed to CI.
BOOT=(b'odroidgoa-uboot-config\nfatwrite mmc 1:1 foo\nsaveenv\n'
      b'setenv bootargs "root=UUID='+s.R3_UUID.encode()+b'"\n'
      b'booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}\n')
PIN={'status':'PINNED_CI_VERIFIED_NOT_BOOT_TESTED','archive_sha256':s.K1_SHA,'run_id':39038977056,
     'hardware_boot_tested':False,'safe_to_flash':False}
LEDGER={'format':'R36OS_CP24_ARTIFACT_LEDGER_V1','safe_to_flash':False,'independent_recovery_proven':False,
        'artifacts':{'k1':{'archive_sha256':s.K1_SHA}}}

class CP24SpareTests(unittest.TestCase):
    def setUp(self):
        self.oldsha=s.R3_SHA;self.oldlen=s.R3_SIZE
        s.R3_SHA=hashlib.sha256(BOOT).hexdigest();s.R3_SIZE=len(BOOT)
        self.addCleanup(self.restore)
    def restore(self):s.R3_SHA=self.oldsha;s.R3_SIZE=self.oldlen
    def test_safe_plan_has_no_flash_artifact(self):
        x=s.prepare(BOOT,PIN,LEDGER)
        self.assertFalse(x['safe_to_flash']);self.assertFalse(x['boot_tested'])
        self.assertFalse(x['test_card_image_assembled'])
        self.assertFalse(x['known_good_original_card_independently_rebooted'])
        self.assertFalse(x['working_recovery_route_physically_verified'])
        self.assertEqual(x['first_boot_target_checkpoint'],'CP25_PENDING_SAFETY_GATES')
    def test_wrong_orig_sha_rejected(self):
        with self.assertRaises(s.Reject):s.prepare(BOOT[:-1]+b'X',PIN,LEDGER)
    def test_wrong_orig_length_rejected(self):
        with self.assertRaises(s.Reject):s.prepare(BOOT[:-1],PIN,LEDGER)
    def test_missing_saveenv_rejected(self):
        b=BOOT.replace(b'saveenv',b'nothing')
        s.R3_SHA=hashlib.sha256(b).hexdigest()
        with self.assertRaises(s.Reject):s.prepare(b,PIN,LEDGER)
    def test_missing_booti_rejected(self):
        b=BOOT.replace(b'booti ',b'badxx ');s.R3_SHA=hashlib.sha256(b).hexdigest()
        with self.assertRaises(s.Reject):s.prepare(b,PIN,LEDGER)
    def test_pending_k1_pin_rejected(self):
        p={**PIN,'status':'PENDING_REBUILD'}
        with self.assertRaises(s.Reject):s.prepare(BOOT,p,LEDGER)
    def test_false_boot_ready_rejected(self):
        p={**PIN,'hardware_boot_tested':True}
        with self.assertRaises(s.Reject):s.prepare(BOOT,p,LEDGER)
    def test_fake_sha_rejected(self):
        p={**PIN,'archive_sha256':'0'*64}
        with self.assertRaises(s.Reject):s.prepare(BOOT,p,LEDGER)
    def test_mismatched_ledger_rejected(self):
        x=copy.deepcopy(LEDGER);x['artifacts']['k1']['archive_sha256']='0'*64
        with self.assertRaises(s.Reject):s.prepare(BOOT,PIN,x)
    def test_untrue_recovery_claim_rejected(self):
        x=copy.deepcopy(LEDGER);x['independent_recovery_proven']=True
        with self.assertRaises(s.Reject):s.prepare(BOOT,PIN,x)
    def test_no_boot_script_or_writer_generated(self):
        src=SRC.read_text()
        for marker in ('subprocess.run(', 'open("/dev/', 'mkfs.ext4(', 'boot.scr', 'fatwrite mmc 1:1 ${loadaddr}', 'saveenv\n'):
            self.assertNotIn(marker,src)

if __name__=='__main__':unittest.main()