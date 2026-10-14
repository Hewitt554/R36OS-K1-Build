"""CP10 tests must execute on an Ubuntu CI runner with e2fsprogs installed."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"offline"))
from ext4_image_fixture import Sandbox, Rejected, SimulatedPowerLoss, sha256_file, ext4_identity

@unittest.skipUnless(shutil.which('mke2fs') and shutil.which('e2fsck') and shutil.which('debugfs'), 'requires e2fsprogs')
class Ext4ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/('r36os-cp10-sandbox-'+uuid.uuid4().hex)
        self.f=Sandbox.create(self.folder)
        seed=self.folder/'seed'
        (seed/'usr'/'local'/'bin').mkdir(parents=True)
        (seed/'etc').mkdir()
        (seed/'etc'/'r36os-release').write_text('VERSION=known-good\n')
        script=seed/'usr'/'local'/'bin'/'r36os-test'
        script.write_text('#!/bin/sh\necho R36OS\n')
        script.chmod(0o751)
        (seed/'usr'/'local'/'bin'/'agent-link').symlink_to('r36os-test')
        self.f.make_ext4(seed)
    def damage(self):
        self.f.snapshot()
        active=self.folder/'active.ext4'
        # Damage with a DIFFERENT valid ext4 filesystem to imitate an incompatible upgrade.
        with active.open('wb') as x:x.truncate(32*1024*1024)
        subprocess.run(['mke2fs','-q','-F','-t','ext4','-L','BROKEN',str(active)],check=True)
        self.f.assert_clean(active)
        self.f.prepare()
    def test_ext4_snapshot_roundtrip_byte_exact(self):
        old=sha256_file(self.folder/'active.ext4')
        self.damage();self.f.commit()
        self.assertEqual(sha256_file(self.folder/'active.ext4'),old)
        self.assertTrue((self.folder/'quarantine.ext4').is_file())
        self.assertTrue(self.f.normal_boot_allowed())
    def test_legacy_ext4_uuid_preserved(self):
        old=ext4_identity(self.folder/'active.ext4')
        self.damage();self.f.commit()
        self.assertEqual(ext4_identity(self.folder/'active.ext4'),old)
    def test_regular_file_and_symlink_are_preserved(self):
        self.damage();self.f.commit()
        p=self.folder/'active.ext4'
        x=subprocess.run(['debugfs','-R','stat /usr/local/bin/r36os-test',str(p)],text=True,capture_output=True,check=True)
        self.assertIn('Type: regular',x.stdout)
        self.assertIn('0751',x.stdout)
        y=subprocess.run(['debugfs','-R','stat /usr/local/bin/agent-link',str(p)],text=True,capture_output=True,check=True)
        self.assertIn('Type: symlink',y.stdout)
    def test_ext4_fsck_ok_after_restore(self):
        self.damage();self.f.commit()
        self.assertEqual(self.f.assert_clean(self.folder/'active.ext4'),ext4_identity(self.folder/'active.ext4'))
    def test_corrupted_archive_rejected(self):
        self.f.snapshot()
        with (self.folder/'backup.ext4.gz').open('ab') as x:x.write(b'garbage')
        with self.assertRaisesRegex(Rejected,'compressed backup checksum'):self.f.prepare()
    def test_mutated_manifest_rejected(self):
        self.f.snapshot()
        p=self.folder/'backup.json';s=json.loads(p.read_text());s['format']='OTHER';p.write_text(json.dumps(s))
        with self.assertRaisesRegex(Rejected,'manifest format'):self.f.prepare()
    def test_tampered_stage_does_not_move_original(self):
        self.damage()
        with (self.folder/'staged.ext4').open('r+b') as x:x.write(b'X')
        with self.assertRaisesRegex(Rejected,'checksum'):self.f.commit()
        self.assertTrue((self.folder/'active.ext4').exists())
        self.assertFalse((self.folder/'quarantine.ext4').exists())
    def test_missing_stage_does_not_quarantine_original(self):
        self.damage();(self.folder/'staged.ext4').unlink()
        with self.assertRaisesRegex(Rejected,'missing staged'):self.f.commit()
        self.assertTrue((self.folder/'active.ext4').exists())
    def test_crash_after_journal_resume(self):
        self.damage()
        with self.assertRaises(SimulatedPowerLoss):self.f.commit('after_journal')
        self.assertFalse(self.f.normal_boot_allowed())
        Sandbox(self.folder).commit();self.assertTrue(self.f.normal_boot_allowed())
    def test_crash_after_quarantine_resume(self):
        self.damage()
        with self.assertRaises(SimulatedPowerLoss):self.f.commit('after_quarantine')
        self.assertFalse((self.folder/'active.ext4').exists())
        Sandbox(self.folder).commit();self.assertTrue(self.f.normal_boot_allowed())
    def test_crash_after_activation_resume(self):
        self.damage()
        with self.assertRaises(SimulatedPowerLoss):self.f.commit('after_activation')
        self.assertFalse(self.f.normal_boot_allowed())
        Sandbox(self.folder).commit();self.assertTrue(self.f.normal_boot_allowed())
    def test_corrupt_stage_after_quarantine_does_not_allow_boot(self):
        self.damage()
        with self.assertRaises(SimulatedPowerLoss):self.f.commit('after_quarantine')
        with (self.folder/'staged.ext4').open('r+b') as x:x.write(b'X')
        with self.assertRaisesRegex(Rejected,'checksum'):Sandbox(self.folder).commit()
        self.assertFalse(self.f.normal_boot_allowed())
    def test_symlink_staged_image_refused(self):
        self.f.snapshot();(self.folder/'staged.ext4').symlink_to(self.folder/'active.ext4')
        with self.assertRaisesRegex(Rejected,'symlink'):self.f.prepare()
    def test_rejects_real_disk_paths(self):
        for p in ('/','/dev','/boot',str(Path.home())):
            with self.assertRaises(Rejected):Sandbox(Path(p))
    def test_refuses_nonregular_active_image(self):
        p=self.folder/'active.ext4';p.unlink();p.mkdir()
        with self.assertRaisesRegex(Rejected,'non-regular'):self.f.snapshot()
    def test_no_overwrite_existing_quarantine(self):
        self.damage();(self.folder/'quarantine.ext4').write_bytes(b'pretend')
        with self.assertRaises(Rejected):self.f.commit()

if __name__ == '__main__':unittest.main()