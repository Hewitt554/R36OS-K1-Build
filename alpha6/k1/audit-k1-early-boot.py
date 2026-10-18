#!/usr/bin/env python3
"""CP16: strictly read-only early-driver evidence audit for pinned K1 result.

No block-device access; this does not make hardware boots safe. Reuses CP13's
archive+SHA256 verifier before reading a nested, version-specific module tree.
"""
from __future__ import annotations
import argparse
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import lzma
import gzip

KREL = '6.12.94-r36os-k1'
MAX_METADATA = 10 * 1024 * 1024
MAX_KERNEL = 128 * 1024 * 1024
MAX_CONFIG = 3 * 1024 * 1024
MAX_ENTRIES = 35000

# Driver lookup is evidence, not an assertion that a specific RK3326 board
# topology has been validated. All /dev/mmc and Panel4 DTB tests need hardware.
DRIVERS = {
    'ext4': {'paths': ('fs/ext4/ext4.ko',), 'kconfig': 'CONFIG_EXT4_FS'},
    'jbd2': {'paths': ('fs/jbd2/jbd2.ko',), 'kconfig': 'CONFIG_JBD2'},
    'mbcache': {'paths': ('fs/mbcache.ko',), 'kconfig': 'CONFIG_MBCACHE'},
    'mmc_core': {'paths': ('drivers/mmc/core/mmc_core.ko',), 'kconfig': 'CONFIG_MMC'},
    'mmc_block': {'paths': ('drivers/mmc/core/mmc_block.ko',), 'kconfig': 'CONFIG_MMC_BLOCK'},
    'dw_mmc': {'paths': ('drivers/mmc/host/dw_mmc.ko',), 'kconfig': 'CONFIG_MMC_DW'},
    'dw_mmc_rockchip': {'paths': ('drivers/mmc/host/dw_mmc-rockchip.ko', 'drivers/mmc/host/dw_mmc_rockchip.ko'), 'kconfig': 'CONFIG_MMC_DW_ROCKCHIP'},
    'pinctrl_rockchip': {'paths': ('drivers/pinctrl/pinctrl-rockchip.ko',), 'kconfig': 'CONFIG_PINCTRL_ROCKCHIP'},
}
CRITICAL_KCONFIG = {
    'CONFIG_ARM64': 'y',
    'CONFIG_OF': 'y',
    'CONFIG_BLK_DEV_INITRD': 'y',
    'CONFIG_DEVTMPFS': 'y',
    'CONFIG_PROC_FS': 'y',
    'CONFIG_SYSFS': 'y',
    'CONFIG_TMPFS': 'y',
    'CONFIG_BINFMT_ELF': 'y',
}
# Strictly diagnostic, not necessarily mandated for storage boot if other
# hardware wiring/drivers are used by the actual DTB.
ADDITIONAL = ('CONFIG_ARCH_ROCKCHIP', 'CONFIG_CLK_RK3328',
              'CONFIG_REGULATOR', 'CONFIG_MFD_RK8XX',
              'CONFIG_REGULATOR_RK808', 'CONFIG_DRM_ROCKCHIP',
              'CONFIG_DRM_PANEL_SIMPLE')

class AuditError(ValueError):
    pass


def normalize_member(name: str) -> str:
    if not name or name.startswith('/') or '\\' in name or '\x00' in name:
        raise AuditError('unsafe archive path')
    p = PurePosixPath(name)
    if '..' in p.parts:
        raise AuditError('archive traversal')
    return str(p)


def module_relative(name: str, kernel_release: str = KREL) -> str | None:
    name = normalize_member(name)
    parts = PurePosixPath(name).parts
    if not parts or name == '.':
        return None
    if parts[0] == 'modules-' + kernel_release:
        return '/'.join(parts[1:])
    for i in range(len(parts) - 2):
        if parts[i:i+3] == ('lib', 'modules', kernel_release):
            return '/'.join(parts[i+3:])
    if parts[0].startswith('modules-') or ('lib' in parts and 'modules' in parts):
        raise AuditError('modules from different kernel ABI: '+name)
    return None


def normalize_modpath(path: str) -> str:
    path = path.strip()
    # All inventory entries are relative to the ABI root; discard only the
    # 'kernel/' logical prefix, not driver subpaths.
    if path.startswith('kernel/'):
        path = path[7:]
    return path


def parse_lines(data: bytes) -> set[str]:
    try:
        return {normalize_modpath(line) for line in data.decode('utf-8').splitlines() if line.strip()}
    except UnicodeDecodeError as e:
        raise AuditError('invalid module inventory encoding') from e


def parse_dep(data: bytes) -> dict[str, tuple[str, ...]]:
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError as e:
        raise AuditError('invalid module dependency encoding') from e
    out = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if ':' not in line:
            raise AuditError('malformed modules.dep')
        lhs, rhs = line.split(':', 1)
        lhs = normalize_modpath(lhs)
        if lhs in out:
            raise AuditError('duplicate modules.dep key')
        deps = tuple(normalize_modpath(x) for x in rhs.split())
        for p in (lhs, *deps):
            if not p or p.startswith('/') or '..' in PurePosixPath(p).parts:
                raise AuditError('unsafe module dependency path')
        out[lhs] = deps
    return out


def config_values(data: bytes) -> dict[str, str]:
    if len(data) > MAX_CONFIG:
        raise AuditError('kernel config too large')
    try:
        decoded = data.decode('ascii')
    except UnicodeDecodeError as e:
        raise AuditError('kernel config contains non-ASCII') from e
    out = {}
    for line in decoded.splitlines():
        m = re.fullmatch(r'(CONFIG_[A-Z0-9_]+)=(y|m|n|"[^"]*"|[0-9A-Za-z_x-]+)', line)
        if m:
            if m.group(1) in out:
                raise AuditError('duplicate config key: '+m.group(1))
            out[m.group(1)] = m.group(2)
        else:
            off = re.fullmatch(r'# (CONFIG_[A-Z0-9_]+) is not set', line)
            if off:
                if off.group(1) in out:
                    raise AuditError('duplicate config key: '+off.group(1))
                out[off.group(1)] = 'n'
    if len(out) < 30:
        raise AuditError('not a complete Linux kernel config')
    return out


def find_ikconfig(raw: bytes) -> bytes | None:
    start = raw.find(b'IKCFG_ST')
    if start < 0:
        return None
    end = raw.find(b'IKCFG_ED', start+8)
    if end < 0 or end - start > MAX_CONFIG:
        raise AuditError('malformed IKCONFIG payload')
    try:
        # Bounded compressed span, downstream uncompressed limit checked.
        contents = gzip.decompress(raw[start+8:end])
    except (OSError, EOFError) as e:
        raise AuditError('invalid embedded compressed kernel config') from e
    if len(contents) > MAX_CONFIG:
        raise AuditError('oversized embedded config')
    return contents


def _read_bounded(tar: tarfile.TarFile, item: tarfile.TarInfo, limit: int = MAX_METADATA) -> bytes:
    if not item.isfile() or item.size > limit:
        raise AuditError('metadata is not bounded regular file: '+item.name)
    stream = tar.extractfile(item)
    if stream is None:
        raise AuditError('missing metadata stream')
    with stream:
        data = stream.read(limit+1)
    if len(data) != item.size:
        raise AuditError('metadata truncated')
    return data


def read_archive_evidence(archive: Path, provenance: dict) -> dict:
    prefix = provenance['candidate_prefix']
    expected_krel = provenance['candidate']['kernel_release']
    if expected_krel != KREL:
        raise AuditError('pinned K1 version changed')
    inventory = {}
    observed_modules = set()
    module_bytes = 0
    outer_config = None
    config_source = None
    with tarfile.open(archive, 'r:gz') as outer:
        entries = outer.getmembers()
        target = [m for m in entries if normalize_member(m.name).lstrip('./') == (prefix+'modules.tar.xz').lstrip('./') and m.isfile()]
        if len(target) != 1:
            raise AuditError('expected unique nested K1 modules tar.xz')
        # Explicit config candidates in the original K1 result (if present).
        options = [m for m in entries if m.isfile() and m.size <= MAX_CONFIG
                   and (PurePosixPath(m.name).name in ('.config', 'kernel.config', 'config-'+KREL)
                        or m.name.endswith('/K1/.config'))]
        for candidate in options:
            try:
                data = _read_bounded(outer, candidate, MAX_CONFIG)
                values = config_values(data)
            except AuditError:
                continue
            if outer_config is not None:
                raise AuditError('ambiguous archived kernel config')
            outer_config = values
            config_source = 'K1 result archive: '+candidate.name
        with outer.extractfile(target[0]) as inner_stream:
            if inner_stream is None:
                raise AuditError('cannot open nested K1 modules stream')
            with tarfile.open(fileobj=inner_stream, mode='r|xz') as nested:
                for index, member in enumerate(nested):
                    if index >= MAX_ENTRIES:
                        raise AuditError('nested K1 module tree exceeds entry limit')
                    rel = module_relative(member.name)
                    if rel is None:
                        if not member.isdir() and member.name not in ('.','./'):
                            raise AuditError('unexpected content outside ABI tree: '+member.name)
                        continue
                    if member.isdir():
                        continue
                    if member.issym():
                        if rel in ('build', 'source'):
                            continue
                        raise AuditError('unexpected symlink in module inventory')
                    if not member.isfile():
                        raise AuditError('unexpected special module entry')
                    if rel in inventory or rel in observed_modules:
                        raise AuditError('duplicate module archive entry: '+rel)
                    if rel in ('modules.builtin', 'modules.dep', 'modules.order', 'modules.builtin.modinfo'):
                        inventory[rel] = _read_bounded(nested, member)
                    elif rel.endswith(('.ko', '.ko.xz', '.ko.zst', '.ko.gz')):
                        observed_modules.add(normalize_modpath(rel))
                        module_bytes += member.size
        # Fall back to embedded IKCONFIG only if no external config supplied.
        if outer_config is None:
            kernel = [m for m in entries if normalize_member(m.name).lstrip('./') == (prefix+'Image').lstrip('./') and m.isfile()]
            if len(kernel) != 1 or kernel[0].size > MAX_KERNEL:
                raise AuditError('kernel Image absent or too large')
            data = _read_bounded(outer, kernel[0], MAX_KERNEL)
            raw_config = find_ikconfig(data)
            if raw_config:
                outer_config = config_values(raw_config)
                config_source = 'Linux Image embedded IKCONFIG'
    if 'modules.builtin' not in inventory or 'modules.dep' not in inventory:
        raise AuditError('modules.builtin and modules.dep are required for CP16 evidence')
    return {'builtin': parse_lines(inventory['modules.builtin']),
            'module_dep':parse_dep(inventory['modules.dep']),
            'module_files':observed_modules, 'module_payload_bytes':module_bytes,
            'config':outer_config, 'config_source':config_source}


def dependency_closure(key: str, dep: dict[str, tuple[str, ...]], found: set[str]):
    todo = [key]
    selected = set()
    while todo:
        name = todo.pop()
        if name in selected:
            continue
        if name not in found or name not in dep:
            raise AuditError('incomplete module dependency closure at '+name)
        selected.add(name)
        todo.extend(dep[name])
        if len(selected) > 2000:
            raise AuditError('unbounded module dependency closure')
    return sorted(selected)


def evaluate(evidence: dict) -> dict:
    builtin = evidence['builtin']
    modfiles = evidence['module_files']
    deps = evidence['module_dep']
    conf = evidence['config']
    drivers = {}
    closure = set()
    blockers = []
    for label, rule in DRIVERS.items():
        names = [normalize_modpath(x) for x in rule['paths']]
        built = [n for n in names if n in builtin]
        loaded = [n for n in names if n in modfiles]
        if built and loaded:
            raise AuditError('same early driver both built in and module: '+label)
        kcfg = conf.get(rule['kconfig']) if conf else None
        if built:
            status = 'BUILT_IN_INVENTORY'
        elif loaded:
            status = 'EARLY_MODULE_REQUIRED'
            closure.update(dependency_closure(loaded[0], deps, modfiles))
        else:
            status = 'NO_DRIVER_IN_MODULE_INVENTORY'
        if kcfg and ((status=='BUILT_IN_INVENTORY' and kcfg!='y') or
                     (status=='EARLY_MODULE_REQUIRED' and kcfg!='m')):
            raise AuditError('kernel config disagrees with module inventory for '+label)
        if status == 'NO_DRIVER_IN_MODULE_INVENTORY':
            blockers.append('No builtin/loadable evidence for '+label)
        elif status == 'EARLY_MODULE_REQUIRED':
            blockers.append(label+' is modular but CP15 initramfs has NO validated early module loader')
        drivers[label] = {'status':status,'config_symbol':rule['kconfig'],
                          'config_value':kcfg or 'UNAVAILABLE',
                          'matched_paths':built or loaded}
    essential = {}
    if conf is None:
        blockers.append('Exact effective kernel .config absent; cannot prove early CONFIG_* invariants')
        for key in CRITICAL_KCONFIG:
            essential[key] = 'UNAVAILABLE'
    else:
        for key, expected in CRITICAL_KCONFIG.items():
            actual = conf.get(key, 'n')
            essential[key] = actual
            if actual != expected:
                blockers.append(key+' expected y, observed '+actual)
    extra = {key:conf.get(key, 'UNAVAILABLE') if conf else 'UNAVAILABLE' for key in ADDITIONAL}
    if len([d for d in drivers.values() if d['status']=='BUILT_IN_INVENTORY']) != len(drivers):
        blockers.append('Not all enumerated early MMC/ext4 components are verified built-in')
    blockers.extend(['R36S Panel4/U-Boot boot not hardware tested',
                     'CP15 handoff to read-only Debian root not hardware tested',
                     'No independently boot-tested recovery or safe rollback'])
    return {'format':'R36OS_CP16_BOOT_CRITICAL_K1_DRIVER_AUDIT',
            'status':'EVIDENCE_CAPTURED_NOT_HARDWARE_BOOT_READY',
            'safe_to_flash':False,'boot_tested':False,
            'early_boot_verified':False,
            'kernel_release':KREL,'kernel_config_source':evidence['config_source'] or 'NOT_FOUND',
            'effective_kernel_config_available':conf is not None,
            'critical_config':essential,'additional_hardware_symbols':extra,
            'drivers':drivers,'early_module_dependency_closure':sorted(closure),
            'module_inventory_files':len(modfiles),
            'module_payload_bytes':evidence['module_payload_bytes'],
            'blockers':blockers,
            'disclaimer':'Inventory and config inspection only; no module load or hardware boot evidence'}


def audit(archive: Path) -> dict:
    verifier = Path(__file__).with_name('verify-k1-artifact.py')
    if not verifier.is_file():
        raise AuditError('CP13 archive verifier missing')
    spec = importlib.util.spec_from_file_location('cp16_k1_provenance', verifier)
    cp13 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cp13)
    verified = cp13.verify(archive)
    evidence = read_archive_evidence(archive, verified)
    result = evaluate(evidence)
    result['k1_verified_archive_sha256'] = verified['source_archive_sha256']
    result['k1_modules_verified_sha256'] = verified['required_boot_artifacts']['modules.tar.xz']['sha256']
    return result


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('verified_k1_archive', type=Path)
    a.add_argument('new_report', type=Path)
    opt = a.parse_args()
    if opt.new_report.exists() or opt.new_report.is_symlink() or opt.new_report.name != 'cp16-k1-early-boot-report.json':
        a.error('refuse existing/unexpected output report')
    result = audit(opt.verified_k1_archive)
    with opt.new_report.open('x', encoding='utf-8') as f:
        json.dump(result, f, sort_keys=True, indent=2)
        f.write('\n')
    print('CP16 evidence report produced (NOT boot-ready)')
    print('Config source:', result['kernel_config_source'])
    for key, item in result['drivers'].items():
        print(f"{key}: {item['status']}")
    print('Outstanding blockers:', len(result['blockers']))

if __name__ == '__main__':
    main()