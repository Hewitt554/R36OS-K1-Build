import importlib.util
from pathlib import Path
import tempfile
import unittest

p=Path(__file__).resolve().parents[1]/'image'/'assemble-disk-fixture.py'
spec=importlib.util.spec_from_file_location('cp12',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class TestLayout(unittest.TestCase):
    def test_four_partition_types(self):
        entries,total=m.layout()
        self.assertEqual([x['type'] for x in entries],[0x0c,0x83,0x0c,0x83])
        self.assertEqual(len(entries),4)
        self.assertEqual(entries[0]['start'],32768)
    def test_mbr_signature_and_disk_id(self):
        b=m.mbr(m.layout()[0])
        self.assertEqual(b[-2:],b'\x55\xaa')
        self.assertEqual(b[440:444],bytes.fromhex('c012a612'))
    def test_mbr_roundtrip(self):
        entries,_=m.layout()
        got=m.parse_mbr(m.mbr(entries))
        self.assertEqual(got,[(x['type'],x['start'],x['sectors']) for x in entries])
    def test_mbr_overlap_rejected(self):
        entries,_=m.layout()
        b=bytearray(m.mbr(entries))
        b[446+16+8:446+16+12]=entries[0]['start'].to_bytes(4,'little')
        with self.assertRaisesRegex(m.Reject,'overlapping'):m.parse_mbr(b)
    def test_mbr_signature_rejected(self):
        b=m.mbr(m.layout()[0])[:-2]+b'xx'
        with self.assertRaisesRegex(m.Reject,'signature'):m.parse_mbr(b)
    def test_no_dev_folder_workspace(self):
        with self.assertRaises(m.Reject):m.safe_workspace(Path('/dev'))
    def test_marker_required(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp12-image-') as tmp:
            with self.assertRaisesRegex(m.Reject,'identity'):m.safe_workspace(Path(tmp))
    def test_real_workspace_allowed(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp12-image-') as tmp:
            (Path(tmp)/'.cp12-fixture-id').write_bytes(m.MARKER)
            self.assertEqual(m.safe_workspace(Path(tmp)),Path(tmp))
    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp12-image-') as tmp:
            base=Path(tmp)
            (base/'.cp12-fixture-id').write_bytes(m.MARKER)
            (base/'root.ext4').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(m.Reject,'symlink'):m.safe_workspace(base)
    def test_fat32_source_signature_rejected(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp12-image-') as tmp:
            p=Path(tmp)/'boot.fat';p.write_bytes(b'bad')
            with self.assertRaisesRegex(m.Reject,'wrong-sized'):m.validate_partition(p,m.layout()[0][0])
if __name__=='__main__':unittest.main()