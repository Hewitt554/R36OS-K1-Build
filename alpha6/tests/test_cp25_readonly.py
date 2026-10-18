"""CP25: negative tests and an actual disposable MBR IMG. No physical disks."""
import importlib.util
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

CODE=Path(__file__).resolve().parents[1]/'cp25/cp25_readonly_r3_inspect.py'
spec=importlib.util.spec_from_file_location('cp25',CODE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def fake_mbr():
    out=bytearray(512)
    for i,(typ,start,length) in enumerate(((0x0b,32768,229376),(0x83,262144,20942929),(0x0b,21205073,262144),(0x83,21467217,4096000))):
        base=446+16*i
        out[base+4]=typ
        struct.pack_into('<II',out,base+8,start,length)
    out[510:512]=b'\x55\xaa'
    return bytes(out)

class InspectTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.img=self.root/'tiny-fixture.img'
        with self.img.open('wb') as f:
            f.truncate(m.SAMPLE_BYTES)
            f.seek(0);f.write(fake_mbr())
            f.seek(4096);f.write(b'U-Boot bootdelay=3 saveenv')
    def test_genuine_fixture_bytes_are_not_modified(self):
        old=hashlib.sha256(self.img.read_bytes()).hexdigest()
        report=m.inspect(self.img,expected_size=m.SAMPLE_BYTES,allow_fixture=True)
        self.assertEqual(report['source_img_bytes'],m.SAMPLE_BYTES)
        self.assertEqual(hashlib.sha256(self.img.read_bytes()).hexdigest(),old)
        self.assertFalse(report['source_image_modified'])
        self.assertFalse(report['safe_to_flash'])
        self.assertFalse(report['persistent_uboot_env_storage_location_proven'])
    def test_uboot_offset_inference_only(self):
        x=m.inspect(self.img,expected_size=m.SAMPLE_BYTES,allow_fixture=True)
        self.assertEqual(x['early_area']['possible_uboot_string_offsets_not_verified_config']['U-Boot'],[4096])
        self.assertEqual(x['early_area']['possible_uboot_string_offsets_not_verified_config']['saveenv'],[4115])
        self.assertFalse(x['saveenv_targets_internal_storage_ruled_out'])
    def test_full_source_hash_not_claimed(self):
        r=m.inspect(self.img,expected_size=m.SAMPLE_BYTES,allow_fixture=True)
        self.assertFalse(r['source_img_fully_sha256_verified_this_run'])
        self.assertEqual(r['early_area']['bytes_read'],m.SAMPLE_BYTES)
    def test_wrong_image_name_rejected(self):
        with self.assertRaises(m.Reject):m.inspect(self.img,expected_size=m.SAMPLE_BYTES)
    def test_wrong_image_size_rejected(self):
        with self.assertRaises(m.Reject):m.inspect(self.img,expected_size=100,allow_fixture=True)
    def test_symlink_rejected(self):
        p=self.root/'link.img';p.symlink_to(self.img)
        with self.assertRaises(m.Reject):m.inspect(p,expected_size=m.SAMPLE_BYTES,allow_fixture=True)
    def test_missing_path_rejected(self):
        with self.assertRaises(m.Reject):m.inspect(self.root/'absent.img',allow_fixture=True)
    def test_wrong_suffix_rejected(self):
        a=self.root/'disk.txt';a.write_text('hi')
        with self.assertRaises(m.Reject):m.disk_allowed(a,expected_size=2,allow_fixture=True)
    def test_dev_rejected(self):
        for s in ('/dev/sda','/sys/class/block/mmcblk0','\\\\.\\PhysicalDrive1','\\\\?\\PhysicalDrive0'):
            with self.subTest(path=s),self.assertRaises(m.Reject):m.disk_allowed(Path(s),allow_fixture=True)
    def test_reject_invalid_mbr(self):
        with self.assertRaises(m.Reject):m.mbr(b'')
        with self.assertRaises(m.Reject):m.mbr(bytes(512))
    def test_reject_missing_mbr_partition(self):
        mbr=bytearray(fake_mbr());mbr[446+4]=0
        with self.assertRaises(m.Reject):m.mbr(mbr)
    def test_reject_corrupted_mbr_partition(self):
        mbr=bytearray(fake_mbr());struct.pack_into('<I',mbr,446+8,32769)
        with self.assertRaises(m.Reject):m.mbr(mbr)
    def test_truncated_sample_rejected(self):
        with self.assertRaises(m.Reject):m.sample(b'hello')
    def test_report_unique_directory(self):
        p={'safe_to_flash':False}
        a=m.report_to_new_dir(self.root,p,stamp='20261017T130000Z')
        b=m.report_to_new_dir(self.root,p,stamp='20261017T130000Z')
        self.assertNotEqual(a,b)
        self.assertTrue((a/'CP25_R3_EARLY_BOOT_READONLY_REPORT.json').is_file())
    def test_reject_bad_output_timestamp(self):
        with self.assertRaises(m.Reject):m.report_to_new_dir(self.root,{},stamp='../escape')
    def test_original_image_reference_declared(self):
        self.assertEqual(m.EXPECTED_SIZE,18375245824)
        self.assertEqual(m.IMG_NAME,'R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img')
    def test_ps1_read_only_allowlist(self):
        p=CODE.with_name('cp25_list_disks_readonly.ps1').read_text()
        self.assertIn('Get-Disk',p)
        self.assertIn('Get-Partition',p)
        for prohibited in ('Set-Disk ','Clear-Disk ','Initialize-Disk ','Format-Volume ', 'Remove-Partition ','New-Partition ','Set-Partition ','diskpart.exe','PhysicalDrive'):
            self.assertNotIn(prohibited,p)
    def test_windows_launcher_no_disk_writes(self):
        p=CODE.with_name('CP25_INSPECT_ORIGINAL_R3.cmd').read_text().lower()
        self.assertIn('cp25_readonly_r3_inspect.py',p)
        for token in ('diskpart','format.com','dd.exe','rufus','diskimager','flash.img','boot.ini'):
            self.assertNotIn(token,p)
    def test_card_inventory_nonflash_claim(self):
        s=CODE.with_name('cp25_list_disks_readonly.ps1').read_text()
        self.assertIn('SafeToFlash = $false',s)
        self.assertIn('UBootSavedEnvironmentBackendConfirmed = $false',s)
    def test_mbr_no_overlapping_root(self):
        mbr=bytearray(fake_mbr());struct.pack_into('<I',mbr,446+16+8,100000)
        with self.assertRaises(m.Reject):m.mbr(mbr)
    def test_no_physical_storage_calls(self):
        src=CODE.read_text()
        for token in ('open("wb")','open("r+b")','os.system(','subprocess.run(','/dev/mmcblk','win32file','DeviceIoControl'):
            self.assertNotIn(token,src)
if __name__=='__main__':unittest.main()