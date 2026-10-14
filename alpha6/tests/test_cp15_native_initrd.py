"""CP15: unprivileged tests of fail-closed boot contract and uImage build."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]
file=P/'boot/build-cp15-initrd.py'
spec=importlib.util.spec_from_file_location('cp15_initrd',file)
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
SCRIPT=(P/'boot/cp15-init').read_bytes()
UUID='abbacafe-1111-2222-3333-0123456789ab'

def stub_busybox():
    # Synthetic ARM64 ELF64 with no program headers. Never execute it.
    b=bytearray(128)
    b[:6]=bytes.fromhex('7f454c460201')
    struct.pack_into('<H',b,18,183)
    struct.pack_into('<Q',b,32,64)
    struct.pack_into('<HH',b,54,56,0)
    return bytes(b)

class CP15NativeTests(unittest.TestCase):
    def test_known_good_native_uuid(self):
        self.assertEqual(c.require_uuid(UUID),UUID)
    def test_reject_legacy_r3_uuid(self):
        with self.assertRaises(c.UnsafeInput):c.require_uuid('e139ce78-9841-40fe-8823-96a304a09859')
    def test_reject_uppercase_and_short_uuid(self):
        for v in ('ABBACAFE-1111-2222-3333-0123456789AB','abcd','../device',''):
            with self.subTest(v=v),self.assertRaises(c.UnsafeInput):c.require_uuid(v)
    def test_reject_unmarked_workspace(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(c.UnsafeInput):c.safe_dir(Path(t))
    def test_reject_output_collisions(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp15-initrd-') as t:
            (Path(t)/'CP15-ARM-UNTESTED.uInitrd').touch()
            with self.assertRaises(c.UnsafeInput):c.safe_dir(Path(t))
    def test_busybox_reject_foreign_arch(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'busybox';b=bytearray(stub_busybox());struct.pack_into('<H',b,18,62);p.write_bytes(b)
            with self.assertRaisesRegex(c.UnsafeInput,'ARM64'):c.read_busybox(p)
    def test_busybox_reject_dynamic_binary(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'busybox';b=bytearray(stub_busybox());struct.pack_into('<HH',b,54,56,1);struct.pack_into('<I',b,64,3);p.write_bytes(b)
            with self.assertRaisesRegex(c.UnsafeInput,'dynamically'):c.read_busybox(p)
    def test_valid_arm64_static_header(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'busybox';p.write_bytes(stub_busybox())
            self.assertEqual(c.read_busybox(p),stub_busybox())
    def test_recovery_cpio_contains_required_nodes(self):
        content=c.pack_cpio(SCRIPT,stub_busybox(),UUID,stub_busybox())
        self.assertIn(b'dev/console\x00',content)
        self.assertIn(b'bin/r36os-probe-root\x00',content)
        self.assertIn(b'bin/switch_root\x00',content)
        self.assertIn(b'etc/cp15-boot-contract\x00',content)
        self.assertIn(UUID.encode(),content)
    def test_both_arch_headers_verify(self):
        import gzip
        src=gzip.compress(c.pack_cpio(SCRIPT,stub_busybox(),UUID,stub_busybox()),mtime=0)
        for arch in (2,22):
            with self.subTest(arch=arch):
                self.assertTrue(c.verify_uimage(c.uimage(src,arch),arch,src))
    def test_header_arch_mismatch_fails(self):
        import gzip
        src=gzip.compress(c.pack_cpio(SCRIPT,stub_busybox(),UUID,stub_busybox()),mtime=0)
        with self.assertRaisesRegex(c.UnsafeInput,'architecture'):c.verify_uimage(c.uimage(src,2),22)
    def test_corrupt_payload_fails(self):
        import gzip
        src=gzip.compress(c.pack_cpio(SCRIPT,stub_busybox(),UUID,stub_busybox()),mtime=0)
        u=bytearray(c.uimage(src,22));u[-1]^=1
        with self.assertRaisesRegex(c.UnsafeInput,'CRC'):c.verify_uimage(u,22)
    def test_staging_produces_offline_report(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);f=root/'busybox';f.write_bytes(stub_busybox())
            with tempfile.TemporaryDirectory(prefix='r36os-cp15-initrd-') as out:
                report=c.generate(f,P/'boot/cp15-init',f,Path(out),UUID)
                self.assertFalse(report['safe_to_flash'])
                self.assertFalse(report['boot_tested'])
                self.assertEqual(report['native_root_uuid'],UUID)
                self.assertEqual(len(report['initrd_files']),2)
                self.assertEqual(json.loads((Path(out)/'cp15-initrd-report.json').read_text())['format'],c.MARKER)
    def test_boot_script_fails_closed_and_no_writes(self):
        text=SCRIPT.decode()
        for x in ('r36os.root_uuid=','r36os.kernel_release=','r36os.boot_mode=',
                  'matching-uuid-has-wrong-filesystem-or-label','r36os-probe-root',
                  'native-release-mismatch','k1-modules-abi-not-found',
                  'flash_image_ready=false','mount -t ext4 -o ro,noload'):
            self.assertIn(x,text)
        for bad in ('mkfs.','wipefs','sfdisk','fatwrite','mount -o remount,rw','/dev/mmcblk0p2','/dev/mmcblk1p2'):
            self.assertNotIn(bad,text)
    def test_script_no_old_root_uuid(self):
        self.assertNotIn('e139ce78-9841-40fe-8823-96a304a09859',SCRIPT.decode())
    def test_busybox_options_compatible(self):
        text=SCRIPT.decode()
        self.assertNotIn('/bin/blkid ',text)
        self.assertNotIn('mount --move',text.split('exec /bin/switch_root')[0].split('# BusyBox mount commonly lacks GNU --move.')[0])
    def test_probe_source_readonly_block_contract(self):
        source=(P/'boot/cp15-probe-root.c').read_text()
        for required in ('O_RDONLY','O_NOFOLLOW','S_ISBLK','pread','R36SYS','0x68','0x38'):
            self.assertIn(required,source)
        for disallowed in ('O_WRONLY','O_RDWR','pwrite(','mkfs.'):
            self.assertNotIn(disallowed,source)
    def test_posix_shell_syntax(self):
        proc=subprocess.run(['sh','-n',str(P/'boot/cp15-init')],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)

if __name__=='__main__':unittest.main()