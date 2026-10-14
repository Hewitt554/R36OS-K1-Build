"""Offline CP14 extraction and safety tests using synthetic XZ tarballs."""
import importlib.util
import io
import lzma
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

p = Path(__file__).resolve().parents[1]/'k1/compose-k1-native-root.py'
spec = importlib.util.spec_from_file_location('cp14_integrator',p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
RELEASE = '6.12.94-r36os-k1'

def blob(entries):
    """entries of (name, content, type, linkname)."""
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:xz') as tar:
        for name,content,kind,link in entries:
            entry=tarfile.TarInfo(name)
            entry.mode=0o755 if name.endswith('.ko') else 0o644
            entry.type=kind
            entry.size=len(content) if kind==tarfile.REGTYPE else 0
            entry.linkname=link
            tar.addfile(entry,io.BytesIO(content) if kind==tarfile.REGTYPE else None)
    return buf.getvalue()

def standard():
    return blob([
        ('lib/modules/'+RELEASE+'/modules.dep',b'kernel/drivers/dummy.ko:\n',tarfile.REGTYPE,''),
        ('lib/modules/'+RELEASE+'/kernel/drivers/dummy.ko',b'\x7fELFfake',tarfile.REGTYPE,''),
    ])

class TestCP14(unittest.TestCase):
    def test_valid_module_tar(self):
        with tempfile.TemporaryDirectory() as d:
            res=m.extract_modules_nested(io.BytesIO(standard()),Path(d)/'stage',RELEASE)
            self.assertEqual(res['module_files'],1)
            self.assertTrue((Path(d)/'stage/kernel/drivers/dummy.ko').is_file())
    def test_skips_compile_time_symlinks(self):
        b=blob([
            ('lib/modules/'+RELEASE+'/source',b'',tarfile.SYMTYPE,'/unsafe/build'),
            ('lib/modules/'+RELEASE+'/modules.dep',b'x',tarfile.REGTYPE,''),
            ('lib/modules/'+RELEASE+'/x.ko',b'ELF',tarfile.REGTYPE,'')])
        with tempfile.TemporaryDirectory() as d:
            res=m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
            self.assertEqual(res['skipped_links'],['source'])
    def test_reject_bad_release(self):
        b=standard().replace(b'junk',b'nope')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'different kernel release'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage','6.12.95-r36os-k1')
    def test_reject_unsafe_tar_member(self):
        b=blob([('lib/modules/'+RELEASE+'/../evil',b'x',tarfile.REGTYPE,'')])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'traversal'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
    def test_reject_foreign_file(self):
        b=blob([('etc/shadow',b'x',tarfile.REGTYPE,'')])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'unexpected non-module'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
    def test_reject_special_file(self):
        b=blob([('lib/modules/'+RELEASE+'/x',b'',tarfile.FIFOTYPE,'')])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'unexpected special'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
    def test_reject_arbitrary_symlink(self):
        b=blob([('lib/modules/'+RELEASE+'/evil',b'',tarfile.SYMTYPE,'/tmp/out')])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'unexpected special'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
    def test_reject_missing_modules_dep(self):
        b=blob([('lib/modules/'+RELEASE+'/x.ko',b'hello',tarfile.REGTYPE,'')])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'dependency index absent'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
    def test_reject_missing_module_files(self):
        b=blob([('lib/modules/'+RELEASE+'/modules.dep',b'x',tarfile.REGTYPE,'')])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'no actual modules'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
    def test_reject_duplicate_entry(self):
        b=blob([('lib/modules/'+RELEASE+'/modules.dep',b'x',tarfile.REGTYPE,''),('lib/modules/'+RELEASE+'/modules.dep',b'x',tarfile.REGTYPE,'')])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'duplicate'):
                m.extract_modules_nested(io.BytesIO(b),Path(d)/'stage',RELEASE)
    def test_temp_outside_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(m.Reject,'specially named'):
                m.check_sandbox(Path(d))
    def test_marker_required(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp14-integration-') as d:
            with self.assertRaisesRegex(m.Reject,'disposable sandbox identity'):
                m.check_sandbox(Path(d))
    def test_marker_valid(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp14-integration-') as d:
            (Path(d)/'.cp14-fixture-id').write_bytes(m.MARKER)
            self.assertEqual(m.check_sandbox(Path(d)),Path(d).resolve())
    def test_root_requires_fail_closed_update(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'etc/r36os').mkdir(parents=True)
            (p/'etc/r36os-release').write_text('ID=r36os\n')
            (p/'etc/r36os/firstboot-policy.conf').write_text('flash_image_ready=true\n')
            (p/'lib').symlink_to('usr/lib')
            with self.assertRaisesRegex(m.Reject,'fail-closed'):
                m.check_native_root(p)
    def test_root_requires_merged_usr(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'etc/r36os').mkdir(parents=True)
            (p/'etc/r36os-release').write_text('ID=r36os\n')
            (p/'etc/r36os/firstboot-policy.conf').write_text('flash_image_ready=false\nupdate_apply_enabled=false\n')
            (p/'lib').mkdir()
            with self.assertRaisesRegex(m.Reject,'usr-merged'):
                m.check_native_root(p)
    def test_output_preexisting_refused(self):
        with tempfile.TemporaryDirectory() as d:
            st=Path(d)/'stage';st.mkdir()
            with self.assertRaisesRegex(m.Reject,'already exists'):
                m.extract_modules_nested(io.BytesIO(standard()),st,RELEASE)

if __name__=='__main__':unittest.main()