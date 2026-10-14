"""K1 early-boot drivers must be proven, not assumed from successful CI compilation."""
from __future__ import annotations
import importlib.util
import io
from pathlib import Path
import sys
import tarfile
import unittest

p = Path(__file__).resolve().parents[1] / 'k1' / 'audit-k1-early-boot.py'
s = importlib.util.spec_from_file_location('cp16_audit', p)
a = importlib.util.module_from_spec(s)
sys.modules[s.name] = a
s.loader.exec_module(a)


def valid_config():
    return {**a.CRITICAL_KCONFIG,
            **{r['kconfig']: 'y' for r in a.DRIVERS.values()}}


def fixture():
    builtins = {r['paths'][0] for r in a.DRIVERS.values()}
    return {'builtin':builtins, 'module_files':set(), 'module_dep':{},
            'config':valid_config(), 'config_source':'testfixture', 'module_payload_bytes':0}


class CP16Tests(unittest.TestCase):
    def test_every_critical_config_built_in(self):
        x=a.evaluate(fixture())
        self.assertTrue(x['effective_kernel_config_available'])
        self.assertFalse(any('Not all' in z for z in x['blockers']))
        self.assertTrue(all(z['status']=='BUILT_IN_INVENTORY' for z in x['drivers'].values()))
        self.assertFalse(x['safe_to_flash'])
        self.assertFalse(x['early_boot_verified'])

    def test_missing_config_is_explicit_blocker(self):
        e=fixture();e['config']=None;e['config_source']=None
        x=a.evaluate(e)
        self.assertEqual(x['kernel_config_source'],'NOT_FOUND')
        self.assertIn('Exact effective kernel .config absent; cannot prove early CONFIG_* invariants',x['blockers'])

    def test_module_requires_early_loader(self):
        e=fixture();e['builtin'].remove('fs/ext4/ext4.ko')
        e['module_files']={'fs/ext4/ext4.ko', 'crypto/crc32c_generic.ko'}
        e['module_dep']={'fs/ext4/ext4.ko':('crypto/crc32c_generic.ko',), 'crypto/crc32c_generic.ko':()}
        e['config']['CONFIG_EXT4_FS']='m'
        x=a.evaluate(e)
        self.assertEqual(x['drivers']['ext4']['status'],'EARLY_MODULE_REQUIRED')
        self.assertEqual(x['early_module_dependency_closure'],['crypto/crc32c_generic.ko','fs/ext4/ext4.ko'])
        self.assertTrue(any('NO validated early module loader' in z for z in x['blockers']))

    def test_cross_incorrect_config_rejected(self):
        e=fixture();e['config']['CONFIG_MMC_BLOCK']='m'
        with self.assertRaisesRegex(a.AuditError,'config disagrees'):
            a.evaluate(e)

    def test_modular_but_missing_dependency_rejected(self):
        e=fixture();e['builtin'].remove('fs/ext4/ext4.ko')
        e['module_files']={'fs/ext4/ext4.ko'}
        e['module_dep']={'fs/ext4/ext4.ko':('fs/jbd2/jbd2.ko',)}
        e['config']['CONFIG_EXT4_FS']='m'
        with self.assertRaisesRegex(a.AuditError,'incomplete module'):
            a.evaluate(e)

    def test_two_forms_same_driver_rejected(self):
        e=fixture();e['module_files'].add('fs/ext4/ext4.ko')
        with self.assertRaisesRegex(a.AuditError,'both built in'):
            a.evaluate(e)

    def test_module_missing_is_blocker(self):
        e=fixture();e['builtin'].remove('drivers/mmc/host/dw_mmc-rockchip.ko')
        x=a.evaluate(e)
        self.assertEqual(x['drivers']['dw_mmc_rockchip']['status'],'NO_DRIVER_IN_MODULE_INVENTORY')
        self.assertTrue(any('dw_mmc_rockchip' in z for z in x['blockers']))

    def test_missing_initrd_config_is_blocker(self):
        e=fixture();e['config']['CONFIG_BLK_DEV_INITRD']='n'
        x=a.evaluate(e)
        self.assertIn('CONFIG_BLK_DEV_INITRD expected y, observed n',x['blockers'])

    def test_dep_path_traversal_rejected(self):
        with self.assertRaisesRegex(a.AuditError,'unsafe module dependency'):
            a.parse_dep(b'kernel/fs/ext4/ext4.ko: ../../etc/passwd\n')

    def test_dep_duplicate_rejected(self):
        with self.assertRaisesRegex(a.AuditError,'duplicate'):
            a.parse_dep(b'a.ko:\na.ko:\n')

    def test_wrong_kernel_abi_rejected(self):
        with self.assertRaisesRegex(a.AuditError,'different kernel ABI'):
            a.module_relative('modules-6.12.90-r36os-k1/kernel/mmc.ko')

    def test_archive_path_traversal_rejected(self):
        with self.assertRaisesRegex(a.AuditError,'traversal'):
            a.module_relative('modules-6.12.94-r36os-k1/../../usr/lib')

    def test_module_path_under_lib_modules(self):
        self.assertEqual(a.module_relative('lib/modules/6.12.94-r36os-k1/kernel/fs/ext4/ext4.ko'),
                         'kernel/fs/ext4/ext4.ko')

    def test_builtins_inventory(self):
        x=a.parse_lines(b'kernel/fs/ext4/ext4.ko\nkernel/drivers/mmc/core/mmc_core.ko\n')
        self.assertEqual(x,{'fs/ext4/ext4.ko','drivers/mmc/core/mmc_core.ko'})

    def test_config_parser(self):
        c='CONFIG_ARM64=y\n# CONFIG_X is not set\n'+'\n'.join(f'CONFIG_TEST{i}=m' for i in range(31))
        got=a.config_values(c.encode())
        self.assertEqual(got['CONFIG_ARM64'],'y')
        self.assertEqual(got['CONFIG_X'],'n')

    def test_config_duplicate_rejected(self):
        c='CONFIG_ARM64=y\nCONFIG_ARM64=m\n'+'\n'.join(f'CONFIG_TEST{i}=y' for i in range(32))
        with self.assertRaisesRegex(a.AuditError,'duplicate'):
            a.config_values(c.encode())

    def test_ikconfig_absent(self):
        self.assertIsNone(a.find_ikconfig(b'Linux Image no embedded config here'))

    def test_bad_ikconfig_rejected(self):
        with self.assertRaisesRegex(a.AuditError,'invalid embedded'):
            a.find_ikconfig(b'IKCFG_STgarbageIKCFG_ED')

    def test_cycle_dep_closure_stable(self):
        x=a.dependency_closure('a.ko', {'a.ko':('b.ko',), 'b.ko':('a.ko',)}, {'a.ko','b.ko'})
        self.assertEqual(x,['a.ko','b.ko'])

    def test_missing_modules_inventory_rejected(self):
        # Model does not infer driver availability from a kernel compile alone.
        x=fixture();x['builtin']=set()
        r=a.evaluate(x)
        self.assertTrue(any('No builtin/loadable evidence' in z for z in r['blockers']))

if __name__=='__main__':unittest.main()