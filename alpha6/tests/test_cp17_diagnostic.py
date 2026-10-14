import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

HOME=Path(__file__).resolve().parents[1]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
b=load(HOME/'diag'/'build-cp17-diag.py','cp17_build')
f=load(HOME/'diag'/'audit-k1-panel4-dtb.py','cp17_dtb')

def build_dtb(with_mmc=True, with_display=True, corrupt=False):
    table=b'compatible\0model\0status\0'
    key={'compatible':0,'model':11,'status':17}
    out=b''
    def align(x):return x+b'\0'*((-len(x))%4)
    def begin(s):
        nonlocal out
        out+=struct.pack('>I',1)+align(s.encode()+b'\0')
    def end():
        nonlocal out
        out+=struct.pack('>I',2)
    def prop(k,v):
        nonlocal out
        out+=struct.pack('>III',3,len(v),key[k])+align(v)
    begin('');prop('compatible',b'r36os,handheld\0rockchip,rk3326\0');prop('model',b'Panel 4 test fixture\0')
    begin('soc');
    if with_mmc:
        begin('mmc@ff510000');prop('compatible',b'rockchip,rk3326-dw-mshc\0');prop('status',b'okay\0');end()
    if with_display:
        begin('dsi@ff960000');begin('panel@0');prop('compatible',b'newvision,nv3051d\0');end();end()
    end();end();out+=struct.pack('>I',9)
    off_struct=56
    off_strings=off_struct+len(out)
    result=struct.pack('>10I',0xd00dfeed,off_strings+len(table),off_struct,off_strings,40,17,16,0,len(table),len(out))+b'\0'*16+out+table
    assert len(result)==off_strings+len(table)
    if corrupt:return b'XXXX'+result[4:]
    return result

INIT=(HOME/'diag'/'cp17-init').read_bytes()

class CP17Tests(unittest.TestCase):
    def test_valid_fdt_rk3326_panel_and_mmc(self):
        r=f.classify(f.parse_fdt(build_dtb()))
        self.assertTrue(r['rk3326_root_compatible'])
        self.assertEqual(len(r['enabled_mmc_nodes']),1)
        self.assertEqual(len(r['display_candidates']),2)
        self.assertFalse(r['boot_tested'])
        self.assertFalse(r['safe_to_flash'])
    def test_no_mmc_is_blocker(self):
        r=f.classify(f.parse_fdt(build_dtb(with_mmc=False)))
        self.assertTrue(any('No enabled MMC' in x for x in r['blockers']))
    def test_no_panel_is_blocker(self):
        r=f.classify(f.parse_fdt(build_dtb(with_display=False)))
        self.assertTrue(any('No panel' in x for x in r['blockers']))
    def test_corrupt_fdt_magic_rejected(self):
        with self.assertRaisesRegex(f.FDTError,'header'):
            f.parse_fdt(build_dtb(corrupt=True))
    def test_truncated_fdt_rejected(self):
        with self.assertRaisesRegex(f.FDTError,'header'):
            f.parse_fdt(build_dtb()[:-1])
    def test_bad_fdt_offset_rejected(self):
        raw=bytearray(build_dtb());struct.pack_into('>I',raw,8,len(raw)+100)
        with self.assertRaises(f.FDTError):f.parse_fdt(raw)
    def test_overlapping_fdt_sections_rejected(self):
        raw=bytearray(build_dtb());struct.pack_into('>I',raw,12,60)
        with self.assertRaisesRegex(f.FDTError,'overlap'):
            f.parse_fdt(raw)
    def test_unknown_fdt_token_rejected(self):
        raw=bytearray(build_dtb());struct.pack_into('>I',raw,56,0xff)
        with self.assertRaisesRegex(f.FDTError,'token'):f.parse_fdt(raw)
    def test_diagnostic_script_does_not_write_sd(self):
        self.assertTrue(b.verify_script(INIT))
        self.assertNotIn(b'mount -t ext4', INIT)
        self.assertNotIn(b'mkfs.', INIT)
    def test_reject_malicious_shell_script(self):
        with self.assertRaisesRegex(b.Unsafe,'prohibited'):
            b.verify_script(INIT+b'\nmkfs.ext4 /dev/sda1\n')
    def test_reject_incomplete_diagnostic(self):
        with self.assertRaisesRegex(b.Unsafe,'missing diagnostic'):
            b.verify_script(b'#!/bin/sh\necho no hardware checks\n')
    def test_sandbox_requires_special_temp_name(self):
        with tempfile.TemporaryDirectory() as p:
            with self.assertRaisesRegex(b.Unsafe,'scratch'):
                b.safe_out(Path(p))
    def test_sandbox_empty_and_disposable(self):
        with tempfile.TemporaryDirectory(prefix='r36os-cp17-diag-') as p:
            self.assertEqual(b.safe_out(Path(p)),Path(p).resolve())
            (Path(p)/'existing.txt').write_text('do not overwrite')
            with self.assertRaisesRegex(b.Unsafe,'empty'):
                b.safe_out(Path(p))
    def test_script_inspection_paths_present(self):
        for path in (b'/sys/class/graphics/',b'/sys/class/input/',b'/sys/class/power_supply/',b'/sys/block/mmcblk'):
            self.assertIn(path,INIT)
    def test_script_console_no_persistent_logging(self):
        for bad in (b' /r36state/',b' /r36update/',b'fatwrite',b'fw_setenv',b'curl',b'wget'):
            self.assertNotIn(bad,INIT)
        self.assertIn(b'/dev/console',INIT)
    def test_build_uses_verifiable_cp15_header(self):
        # This tests real image packer with dummy executable contents; architecture
        # and static ELF constraints are separately enforced by read_busybox.
        images,meta=b.make_image(INIT,b'B'*256,b'C'*192)
        mod=b.cp15_helpers()
        self.assertTrue(mod.verify_uimage(images[2],2))
        self.assertTrue(mod.verify_uimage(images[22],22))
        self.assertEqual(images[2][64:],images[22][64:])
        self.assertGreater(meta['uncompressed_cpio_bytes'],0)
    def test_corrupt_generated_uimage_rejected(self):
        imgs,_=b.make_image(INIT,b'B'*256,b'C'*192)
        data=imgs[22][:-1]+bytes([imgs[22][-1]^0x01])
        with self.assertRaises(Exception):b.cp15_helpers().verify_uimage(data,22)

if __name__=='__main__':unittest.main()