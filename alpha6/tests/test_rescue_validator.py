import importlib.util
import pathlib
import struct
import tempfile
import unittest
import zlib
import gzip

src = pathlib.Path(__file__).resolve().parents[1] / 'recovery' / 'verify-rescue.py'
spec = importlib.util.spec_from_file_location('verify_rescue', src)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

def cpio_entry(name, data):
  name = name.encode()+b'\0'
  vals = [1,0o100755,0,0,1,0,len(data),0,0,0,0,len(name),0]
  b = b'070701'+b''.join(('%08x'%x).encode() for x in vals)+name
  b += b'\0'*((-len(b))%4)
  b += data
  return b+b'\0'*((-len(b))%4)

def sample():
  required = ['./init','./bin/busybox','./bin/sh','./sbin/r36os-rescue-status','./etc/r36os-rescue-release']
  content = [b'#!/bin/sh\necho rescue',b'\x7fELFexample',b'busybox',b'#!/bin/sh\necho status',b'WRITE_POLICY=DIAGNOSTIC_ONLY']
  cpio = b''.join(cpio_entry(k, d) for k,d in zip(required,content))+cpio_entry('TRAILER!!!',b'')
  d = gzip.compress(cpio)
  h = bytearray(v.HEADER.pack(0x27051956,0,0,len(d),0,0,zlib.crc32(d)&0xffffffff,5,22,3,1,b'test'.ljust(32,b'\0')))
  h[4:8] = struct.pack('>I',zlib.crc32(h)&0xffffffff)
  return d,bytes(h)+d

class RescueTest(unittest.TestCase):
  def run_verify(self, data, image):
    with tempfile.TemporaryDirectory() as folder:
      d = pathlib.Path(folder)
      p,q=d/'rescue.gz',d/'rescue.uInitrd'
      p.write_bytes(data);q.write_bytes(image)
      v.verify(p,q)
  def test_valid(self):
    self.run_verify(*sample())
  def test_corrupt_header(self):
    d,u=sample(); u=u[:10]+bytes([u[10]^1])+u[11:]
    with self.assertRaisesRegex(ValueError,'header CRC'): self.run_verify(d,u)
  def test_corrupt_payload(self):
    d,u=sample();u=u[:-1]+bytes([u[-1]^1])
    with self.assertRaisesRegex(ValueError,'data CRC'):self.run_verify(d,u)
  def test_duplicate(self):
    c=cpio_entry('./init',b'A')+cpio_entry('./init',b'B')+cpio_entry('TRAILER!!!',b'')
    with self.assertRaisesRegex(ValueError,'duplicate'):v.files_newc(c)
  def test_traversal(self):
    with self.assertRaisesRegex(ValueError,'unsafe'):v.files_newc(cpio_entry('../etc',b'x')+cpio_entry('TRAILER!!!',b''))
if __name__ == '__main__':
  unittest.main()
