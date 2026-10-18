import hashlib
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/"boot"/"build-recovery-gate.py"
spec=importlib.util.spec_from_file_location("boot_gate",p)
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
SOURCE=(b"if gpio input b12\nthen\nsaveenv\nfi\n"
        b"if load mmc 1:1 0x02000000 boot.ini\nthen\necho ok\nfi\n"
        b"if env exists PanelNum\nthen\necho __D__{PanelPathSlash}\nfi\n"
        b'setenv bootargs "root=UUID=e139ce78-9841-40fe-8823-96a304a09859 rootwait rw"\n'
        b"load mmc 1:1 __D__{loadaddr} Image\n"
        b"booti __D__{loadaddr} __D__{initrd_loadaddr} __D__{dtb_loadaddr}\n").replace(b"__D__",b"$")
def make(s=SOURCE):
    return g.candidate(s,hashlib.sha256(s).hexdigest(),len(s))
class TestGate(unittest.TestCase):
    def test_real_hash_rejects_fake_input(self):
        with self.assertRaisesRegex(g.UnsafeSource,"length"):g.candidate(SOURCE)
    def test_legacy_bytes_remain_identical(self):
        out=make()
        self.assertEqual(out.replace(g.HOOK,b"",1),SOURCE)
    def test_marker_precedes_legacy_root(self):
        out=make()
        self.assertLess(out.index(b"R36OS/RECOVERY.ON"),out.index(b"root=UUID"))
    def test_rescue_uses_existing_kernel_and_initrd(self):
        out=make()
        self.assertIn(b"R36OS/rescue.uInitrd",out)
        self.assertIn(b"rdinit=/init",out)
        self.assertIn(b"PanelPathSlash",g.HOOK)
    def test_bad_digest_rejected(self):
        with self.assertRaisesRegex(g.UnsafeSource,"checksum"):
            g.candidate(SOURCE,"0"*64,len(SOURCE))
    def test_bad_size_rejected(self):
        with self.assertRaisesRegex(g.UnsafeSource,"length"):
            g.candidate(SOURCE,hashlib.sha256(SOURCE).hexdigest(),len(SOURCE)+1)
    def test_previous_hook_rejected(self):
        out=make()
        with self.assertRaisesRegex(g.UnsafeSource,"already modified"):
            make(out)
    def test_unrecognized_root_rejected(self):
        bad=SOURCE.replace(b"e139ce78-9841-40fe-8823-96a304a09859",b"00000000-0000-0000-0000-000000000000")
        with self.assertRaisesRegex(g.UnsafeSource,"UUID"):make(bad)
    def test_multiple_booti_rejected(self):
        with self.assertRaisesRegex(g.UnsafeSource,"boot structure"):
            make(SOURCE+b"booti extra\n")
    def test_real_r3_gate_is_explicitly_retired(self):
        oldsha, oldsize = g.R3_SHA, g.R3_SIZE
        try:
            # Map the synthetic fixture to the real identity constants to
            # exercise the fail-closed production branch without publishing
            # or copying the user's actual original boot script.
            g.R3_SHA = hashlib.sha256(SOURCE).hexdigest()
            g.R3_SIZE = len(SOURCE)
            with self.assertRaisesRegex(g.UnsafeSource, "CP19 RETIRED"):
                g.candidate(SOURCE, g.R3_SHA, g.R3_SIZE)
        finally:
            g.R3_SHA, g.R3_SIZE = oldsha, oldsize

    def test_hook_has_no_fat_writes(self):
        for forbidden in (b"fatwrite",b"saveenv",b"mw.b",b"erase",b"run update"):
            self.assertNotIn(forbidden,g.HOOK)
if __name__=="__main__":unittest.main()
