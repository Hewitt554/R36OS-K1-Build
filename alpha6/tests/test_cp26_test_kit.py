"""CP26 external-writer-free installer regression tests, including negative paths."""
from __future__ import annotations
import hashlib,importlib.util,json,os
from pathlib import Path
import tempfile,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]/'cp26'
SOURCE=ROOT/'windows_kit/tools/cp26_deploy.py'
spec=importlib.util.spec_from_file_location('cp26',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

ORIGINAL=Path('/mnt/data/R36OS_CP11_VERIFIED_R3_BOOT_ORIGINAL.bin')

def original_bytes():
    # An exact reproduction of the private source's on-disk digest is
    # unnecessary in PUBLIC CI; fixture bytes are patched with sha in tests.
    return (b'R36OS R3 test placeholder\n' * 204)[:5108].ljust(5108,b' ')

class TestCP26(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)
        self.drive=self.p/'BOOT';self.drive.mkdir()
        self.bundle=self.p/'package';(self.bundle/'BOOT_PAYLOAD/R36OS/CP26').mkdir(parents=True)
        self.o=original_bytes()
        self.hash=hashlib.sha256(self.o).hexdigest()
        self.old_sha=m.R3_SHA
        m.R3_SHA=self.hash
        self.addCleanup(lambda:setattr(m,'R3_SHA',self.old_sha))
        (self.drive/'boot.ini').write_bytes(self.o)
        (self.drive/'Image').write_bytes(b'original Image')
        (self.drive/'uInitrd').write_bytes(b'old ramdisk')
        self.assets={'Image':b'arm64 test image', 'diag.uInitrd':b'ram disk', 'rk3326-r36s-k1.dtb':b'\xd0\x0d\xfe\xed'}
        for name,data in self.assets.items(): (self.bundle/'BOOT_PAYLOAD/R36OS/CP26'/name).write_bytes(data)
        boot=(ROOT/'windows_kit/boot.ini').read_bytes()
        (self.bundle/'BOOT_PAYLOAD/boot.ini').write_bytes(boot)
        self.entries={name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in {**self.assets,'boot.ini':boot}.items()}
        self.manifest={'format':'R36OS_CP26_BOOT_DIAGNOSTIC_BUNDLE_V1','safe_to_flash':False,'hardware_boot_tested':False,
                       'original_r3_boot_sha256':self.hash,'k1_inner_archive_sha256':'d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8',
                       'files':self.entries}
        (self.bundle/'CP26_PACKAGE_MANIFEST.json').write_text(json.dumps(self.manifest))
        # use fake exact R3 reference for tests but don't modify released data
        self.orig_verify=m.original_boot
        def good_original(path):
            f=path/'boot.ini'
            if m.sha(f)!=self.hash:raise m.Refuse('not original')
            return f
        m.original_boot=good_original
        self.addCleanup(lambda:setattr(m,'original_boot',self.orig_verify))
    def test_source_has_only_readonly_boot_commands(self):
        s=(ROOT/'windows_kit/boot.ini').read_bytes()
        self.assertNotIn(b'saveenv',s);self.assertNotIn(b'fatwrite',s)
        self.assertEqual(s.count(b'booti '),1)
        self.assertIn(b'rdinit=/init',s)
    def test_volume_refuses_c(self):
        with self.assertRaises(m.Refuse):m.select_root('C',lambda _:('BOOT','FAT32'))
    def test_volume_refuses_wrong_label(self):
        with self.assertRaises(m.Refuse):m.select_root('E',lambda _:('ROMS','FAT32'))
    def test_volume_refuses_ntfs(self):
        with self.assertRaises(m.Refuse):m.select_root('E',lambda _:('BOOT','NTFS'))
    def test_volume_refuses_unexpected_path(self):
        with self.assertRaises(m.Refuse):m.select_root('E:\\test',lambda _:('BOOT','FAT32'))
    def test_package_rejects_extra_unexpected_file(self):
        p=self.bundle/'CP26_PACKAGE_MANIFEST.json';v=dict(self.manifest)
        v['files']=dict(v['files']);v['files']['bootloader.bin']={'bytes':1,'sha256':'0'*64}
        p.write_text(json.dumps(v))
        with self.assertRaises(m.Refuse):m.verify_manifest(self.bundle)
    def test_package_rejects_wrong_sha(self):
        (self.bundle/'BOOT_PAYLOAD/boot.ini').write_bytes(b'bad')
        with self.assertRaises(m.Refuse):m.verify_manifest(self.bundle)
    def test_package_rejects_flash_claim(self):
        p=self.bundle/'CP26_PACKAGE_MANIFEST.json';v=dict(self.manifest);v['safe_to_flash']=True
        p.write_text(json.dumps(v))
        with self.assertRaises(m.Refuse):m.verify_manifest(self.bundle)
    def test_package_rejects_missing_dtbs(self):
        (self.bundle/'BOOT_PAYLOAD/R36OS/CP26/rk3326-r36s-k1.dtb').unlink()
        with self.assertRaises(m.Refuse):m.verify_manifest(self.bundle)
    def test_confirm_required(self):
        with self.assertRaises(m.Refuse):m.install(self.drive,self.bundle,'YES')
    def test_install_and_restore_original(self):
        result=m.install(self.drive,self.bundle,m.CHALLENGE)
        self.assertEqual(result['status'],'INSTALLED_DIAGNOSTIC_BOOT_FILES_NOT_HARDWARE_TESTED')
        self.assertEqual(m.sha(self.drive/'R3BOOT.BAK'),self.hash)
        self.assertEqual(m.sha(self.drive/'boot.ini'),self.entries['boot.ini']['sha256'])
        self.assertEqual(m.status(self.drive,self.bundle)['mode'],'CP26_DIAGNOSTIC')
        with self.assertRaises(m.Refuse):m.install(self.drive,self.bundle,m.CHALLENGE)
        restored=m.restore(self.drive,m.CHALLENGE)
        self.assertEqual(restored['status'],'VERIFIED_R3_BOOT_INI_RESTORED')
        self.assertEqual((self.drive/'boot.ini').read_bytes(),self.o)
    def test_installer_refuses_changed_r3_boot(self):
        (self.drive/'boot.ini').write_bytes(b'user-modified')
        with self.assertRaises(m.Refuse):m.install(self.drive,self.bundle,m.CHALLENGE)
        self.assertFalse((self.drive/'R3BOOT.BAK').exists())
    def test_installer_does_not_copy_to_neighbor_sd2(self):
        (self.p/'SD2').mkdir();(self.p/'SD2/game.sav').write_bytes(b'game data')
        m.install(self.drive,self.bundle,m.CHALLENGE)
        self.assertEqual((self.p/'SD2/game.sav').read_bytes(),b'game data')
    def test_reject_prior_backup(self):
        (self.drive/'R3BOOT.BAK').write_bytes(b'already exists')
        with self.assertRaises(m.Refuse):m.install(self.drive,self.bundle,m.CHALLENGE)
    def test_restoration_requires_backup(self):
        with self.assertRaises(m.Refuse):m.restore(self.drive,m.CHALLENGE)
    def test_restore_rejects_corrupt_backup(self):
        (self.drive/'R3BOOT.BAK').write_bytes(b'bad')
        with self.assertRaises(m.Refuse):m.restore(self.drive,m.CHALLENGE)
    def test_restore_rejects_confirmation(self):
        with self.assertRaises(m.Refuse):m.restore(self.drive,'y')
    def test_unknown_boot_status(self):
        (self.drive/'boot.ini').write_bytes(b'garbage')
        self.assertEqual(m.status(self.drive,self.bundle)['mode'],'UNKNOWN_OR_DAMAGED')
    def test_no_raw_disk_writer_in_windows_source(self):
        s=SOURCE.read_text();self.assertNotIn('PhysicalDrive',s)
        self.assertNotIn('Clear-Disk',s);self.assertNotIn('diskpart',s)
    def test_package_is_windows_scripts_no_intermediate_img(self):
        for p in (ROOT/'windows_kit').rglob('*'):
            self.assertNotEqual(p.suffix.lower(),'.img')
    def test_on_windows_only_runtime(self):
        with self.assertRaises(m.Refuse):m.install(self.drive,self.bundle,m.CHALLENGE,is_windows=False)

if __name__=='__main__':unittest.main()