import pathlib
import tempfile
import unittest
import uuid
import zipfile

from sys import path as syspath
syspath.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "offline"))
from verified_restore_fixture import Fixture, Reject, InjectedPowerLoss

class TestRestore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = pathlib.Path(self.tmp.name) / ("r36os-cp09-sandbox-" + uuid.uuid4().hex)
        self.f = Fixture.create(self.p)
        (self.p/"active"/"etc").mkdir()
        (self.p/"active"/"etc"/"r36os-release").write_text("VERSION=good\n")
        (self.p/"active"/"lib").mkdir()
        (self.p/"active"/"lib"/"driver.bin").write_bytes(b"approved-driver-v1")
    def seed(self):
        self.f.snapshot()
        (self.p/"active"/"etc"/"r36os-release").write_text("VERSION=broken\n")
        self.f.prepare()
    def test_verified_round_trip(self):
        self.seed();self.f.commit()
        self.assertEqual((self.p/"active"/"etc"/"r36os-release").read_text(),"VERSION=good\n")
        self.assertEqual((self.p/"quarantine"/"etc"/"r36os-release").read_text(),"VERSION=broken\n")
        self.assertTrue(self.f.normal_boot_allowed())
    def test_corrupt_archive_rejected(self):
        self.f.snapshot()
        with (self.p/"snapshot.zip").open("ab") as out:out.write(b"corruption")
        with self.assertRaisesRegex(Reject,"checksum"):self.f.prepare()
    def test_mutated_manifest_rejected(self):
        self.f.snapshot()
        p=self.p/"snapshot.json"
        p.write_text(p.read_text().replace('"format":1','"format":2'))
        with self.assertRaisesRegex(Reject,"manifest"):self.f.prepare()
    def test_symlink_source_rejected(self):
        (self.p/"active"/"bad").symlink_to(self.p/"active"/"etc")
        with self.assertRaisesRegex(Reject,"symlink"):self.f.snapshot()
    def test_refuses_nontemp_target(self):
        with self.assertRaisesRegex(Reject,"outside"):Fixture(pathlib.Path.home())
    def test_refuses_missing_fixture_marker(self):
        (self.p/".fixture-id").unlink()
        with self.assertRaisesRegex(Reject,"identity"):Fixture(self.p)
    def test_repeated_snapshot_blocked(self):
        self.f.snapshot()
        with self.assertRaisesRegex(Reject,"already"):self.f.snapshot()
    def test_refuse_stage_mutation(self):
        self.seed()
        (self.p/"staged"/"lib"/"driver.bin").write_bytes(b"injected")
        with self.assertRaisesRegex(Reject,"mutated"):self.f.commit()
        self.assertEqual((self.p/"active"/"etc"/"r36os-release").read_text(),"VERSION=broken\n")
    def test_crash_after_journal_resumes(self):
        self.seed()
        with self.assertRaises(InjectedPowerLoss):self.f.commit("after_journal")
        self.assertFalse(self.f.normal_boot_allowed())
        Fixture(self.p).commit()
        self.assertTrue(self.f.normal_boot_allowed())
    def test_crash_after_quarantine_resumes(self):
        self.seed()
        with self.assertRaises(InjectedPowerLoss):self.f.commit("after_old_rename")
        self.assertFalse((self.p/"active").exists())
        self.assertFalse(self.f.normal_boot_allowed())
        Fixture(self.p).commit()
        self.assertEqual((self.p/"active"/"etc"/"r36os-release").read_text(),"VERSION=good\n")
    def test_crash_after_activation_resumes(self):
        self.seed()
        with self.assertRaises(InjectedPowerLoss):self.f.commit("after_new_rename")
        self.assertFalse(self.f.normal_boot_allowed())
        Fixture(self.p).commit()
        self.assertEqual((self.p/"active"/"lib"/"driver.bin").read_bytes(),b"approved-driver-v1")
    def test_corrupt_stage_after_crash_rejected(self):
        self.seed()
        with self.assertRaises(InjectedPowerLoss):self.f.commit("after_old_rename")
        (self.p/"staged"/"lib"/"driver.bin").write_bytes(b"bad")
        with self.assertRaisesRegex(Reject,"mutated"):Fixture(self.p).commit()
        self.assertFalse(self.f.normal_boot_allowed())
    def test_disappearing_stage_does_not_move_active(self):
        self.seed()
        import shutil
        shutil.rmtree(self.p / "staged")
        with self.assertRaisesRegex(Reject,"staged restore missing"):
            self.f.commit()
        self.assertTrue((self.p / "active").is_dir())
    def test_path_traversal_archive_rejected(self):
        self.f.snapshot()
        import json
        with zipfile.ZipFile(self.p/"snapshot.zip", "a") as z:
            z.writestr("../outside.txt",b"bad")
        manifest=json.loads((self.p/"snapshot.json").read_text())
        from verified_restore_fixture import sha
        manifest["archive_sha256"]=sha((self.p/"snapshot.zip").read_bytes())
        (self.p/"snapshot.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(Reject,"archived files"):
            self.f.prepare()
    def test_cannot_commit_without_prepare(self):
        self.f.snapshot()
        with self.assertRaisesRegex(Reject,"not prepared"):self.f.commit()
    def test_snapshot_verifies_all_files(self):
        self.f.snapshot()
        self.assertEqual(len(self.f.verify_snapshot()),2)

if __name__ == "__main__":unittest.main()
