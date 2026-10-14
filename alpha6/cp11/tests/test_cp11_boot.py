"""Byte-level FAT32 fixture tests plus offline CP08 gate preservation checks."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cp11_extract_validate import extract_and_validate,store_outputs,AuditRejected,R3_SIZE,R3_SHA,HOOK
from layout_preview import geometry,GIB

START=2048
SECTORS=8192
FATSZ=64
CLUSTER_SECT=1
SIZE=(START+SECTORS)*512

def boot_source():
    source=(b'if gpio input b12\nthen\n echo yes\nfi\n'
            b'if env exists PanelNum\nthen\n echo ${PanelPathSlash}\nfi\n'
            b'setenv bootargs "root=UUID=e139ce78-9841-40fe-8823-96a304a09859 rootwait rw"\n'
            b'load mmc 1:1 ${loadaddr} Image\n'
            b'load mmc 1:1 ${initrd_loadaddr} uInitrd\n'
            b'load mmc 1:1 ${dtb_loadaddr} "${PanelPathSlash}rk3326-r35s-linux.dtb"\n'
            b'booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}\n')
    return b'# '+b' '*(R3_SIZE-len(source)-3)+b'\n'+source

def synthetic_image(path, boot, *, altered_sha=False, duplicate=False, cycle=False):
    with path.open('wb') as f:
        f.truncate(SIZE)
        mbr=bytearray(512)
        mbr[446+4]=0x0b
        struct.pack_into('<II',mbr,446+8,START,SECTORS)
        mbr[510:]=b'\x55\xaa'
        f.seek(0);f.write(mbr)
        bp=bytearray(512)
        bp[11:13]=struct.pack('<H',512)
        bp[13]=CLUSTER_SECT
        struct.pack_into('<H',bp,14,32)
        bp[16]=2
        struct.pack_into('<I',bp,32,SECTORS)
        struct.pack_into('<I',bp,36,FATSZ)
        struct.pack_into('<I',bp,44,2)
        bp[71:82]=b'BOOT       '
        bp[82:90]=b'FAT32   '
        bp[510:512]=b'\x55\xaa'
        f.seek(START*512);f.write(bp)
        entries=[0x0ffffff8,0x0fffffff,0x0fffffff]
        needed=(len(boot)+511)//512
        for i in range(needed):
            entries.append((3+i+1) if i<needed-1 else 0x0fffffff)
        if cycle: entries[-1]=3
        table=bytearray(FATSZ*512)
        for i,e in enumerate(entries): struct.pack_into('<I',table,i*4,e)
        fatstart=(START+32)*512
        for off in (0,FATSZ*512):f.seek(fatstart+off);f.write(table)
        data=(START+32+2*FATSZ)*512
        ent=bytearray(32)
        ent[0:11]=b'BOOT    INI'
        ent[11]=0x20
        struct.pack_into('<H',ent,26,3)
        struct.pack_into('<I',ent,28,len(boot))
        f.seek(data);f.write(ent)
        if duplicate:f.write(ent)
        for i in range(needed):
            f.seek(data+(1+i)*512);f.write(boot[i*512:(i+1)*512])

class Cp11BootValidation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.img=self.root/'R3-fixture.img'
        self.boot=boot_source()
        synthetic_image(self.img,self.boot)

    def check(self,*,expected_sha=None):
        return extract_and_validate(self.img,expected_image_size=SIZE,
           expected_partition_start=START,expected_partition_sectors=SECTORS,
           expected_boot_sha=expected_sha or hashlib.sha256(self.boot).hexdigest(),
           expected_boot_size=R3_SIZE,allow_test_reference=True)

    def test_good_fixture_and_exact_original(self):
        original,candidate,checks=self.check()
        self.assertEqual(original,self.boot)
        self.assertEqual(candidate.replace(HOOK,b'',1),self.boot)
        self.assertTrue(checks['original_bytes_recoverable'])

    def test_gate_is_uninstalled_and_after_panel_chooser(self):
        original,candidate,_=self.check()
        self.assertLess(candidate.index(b'R36OS/RECOVERY.ON'),candidate.index(b'root=UUID'))
        self.assertIn(b'rdinit=/init',candidate)
        self.assertIn(b'R36OS/rescue.uInitrd',candidate)
        self.assertEqual(candidate.count(HOOK),1)

    def test_output_non_destructive_and_new_folder(self):
        original,candidate,checks=self.check()
        a=store_outputs(self.root,self.img,original,candidate,checks)
        b=store_outputs(self.root,self.img,original,candidate,checks)
        self.assertNotEqual(a,b)
        self.assertEqual((a/'R36OS_CP11_VERIFIED_R3_BOOT_ORIGINAL.bin').read_bytes(),original)
        self.assertEqual((b/'R36OS_CP11_BOOT_CANDIDATE_UNTESTED.txt').read_bytes(),candidate)
        self.assertEqual(json.loads((a/'R36OS_CP11_BOOT_VALIDATION.json').read_text())['status'],'PASS_READ_ONLY_BOOT_SCRIPT_VALIDATION')
        self.assertEqual(self.img.stat().st_size,SIZE)

    def test_production_reference_rejects_test_image(self):
        with self.assertRaisesRegex(AuditRejected,'length'):
            extract_and_validate(self.img)

    def test_corrupt_image_size_rejected(self):
        with self.img.open('ab') as f:f.write(b'X')
        with self.assertRaisesRegex(AuditRejected,'length'):self.check()

    def test_corrupt_boot_hash_rejected(self):
        with self.assertRaisesRegex(AuditRejected,'SHA-256'):self.check(expected_sha='0'*64)

    def test_wrong_boot_partition_location_rejected(self):
        with self.assertRaisesRegex(AuditRejected,'BOOT partition'):
            extract_and_validate(self.img,expected_image_size=SIZE,
             expected_partition_start=START+2048,expected_partition_sectors=SECTORS,
             expected_boot_sha=hashlib.sha256(self.boot).hexdigest(),expected_boot_size=R3_SIZE,
             allow_test_reference=True)

    def test_duplicate_boot_ini_rejected(self):
        synthetic_image(self.img,self.boot,duplicate=True)
        with self.assertRaisesRegex(AuditRejected,'exactly one'):self.check()

    def test_fake_boot_ini_filename_rejected(self):
        with self.img.open('r+b') as f:
            dataoff=(START+32+2*FATSZ)*512
            f.seek(dataoff);f.write(b'MAIN')
        with self.assertRaisesRegex(AuditRejected,'exactly one'):self.check()

    def test_boot_file_read_does_not_modify_image(self):
        before=hashlib.sha256(self.img.read_bytes()).hexdigest()
        self.check()
        after=hashlib.sha256(self.img.read_bytes()).hexdigest()
        self.assertEqual(before,after)

    def test_fat_cycle_beyond_file_length_is_not_fsck(self):
        synthetic_image(self.img,self.boot,cycle=True)
        # The file is short enough to read before following the last cyclic link;
        # content can still be valid. This is not a full FAT consistency checker.
        original,candidate,_=self.check()
        self.assertEqual(original,self.boot)

    def test_detects_wrong_boot_size(self):
        synthetic_image(self.img,self.boot[:-1])
        with self.assertRaisesRegex(AuditRejected,'byte length'):
            self.check()

class Cp11PartitionSimulation(unittest.TestCase):
    def test_64gb_preview_no_overlap(self):
        for root in (8,12):
            r=geometry(64*10**9,root)
            self.assertEqual(len(r['partitions']),4)
            self.assertGreater(r['state_gib'],45)
            for i,a in enumerate(r['partitions']):
                self.assertEqual(a['start_sector']%2048,0)
                if i: self.assertGreaterEqual(a['start_sector'],r['partitions'][i-1]['start_sector']+r['partitions'][i-1]['sectors'])
    def test_root_options_affect_state(self):
        a=geometry(64*10**9,8)['state_gib'];b=geometry(64*10**9,12)['state_gib']
        self.assertGreater(a,b)
        self.assertAlmostEqual(a-b,4,places=1)
    def test_32gb_has_state(self):
        self.assertGreater(geometry(32*10**9,12)['state_gib'],12)
    def test_reject_unsupported_root(self):
        with self.assertRaisesRegex(ValueError,'only 8 or 12'):
            geometry(64*10**9,99)

if __name__=='__main__':unittest.main()