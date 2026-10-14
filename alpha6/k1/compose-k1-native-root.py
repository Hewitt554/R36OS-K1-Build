#!/usr/bin/env python3
"""CP14: install verified K1 modules into a DISPOSABLE native-root staging tree.

Reads a pinned GitHub K1 tarball with the CP13 verifier, streams its nested
modules.tar.xz to a fresh staging tree and injects only its /lib/modules ABI
into a CI-created Debian rootfs. Does not touch SD cards, /boot or live roots.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile

MARKER = b'R36OS_CP14_DISPOSABLE_NATIVE_ROOT_V1\n'
MAX_FILES = 25000
MAX_TOTAL = 4 * 1024**3
MAX_ONE = 256 * 1024**2

class Reject(ValueError):
    pass

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()

def file_regular(path):
    try:
        return stat.S_ISREG(Path(path).lstat().st_mode)
    except FileNotFoundError:
        return False

def check_sandbox(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise Reject('sandbox must be a real directory')
    path = path.resolve(strict=True)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if temp not in path.parents or not path.name.startswith('r36os-cp14-integration-'):
        raise Reject('workspace must be specially named directory under temp')
    marker = path/'.cp14-fixture-id'
    if not file_regular(marker) or marker.read_bytes() != MARKER:
        raise Reject('missing or mismatched disposable sandbox identity')
    return path

def check_native_root(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise Reject('root is not a directory')
    root = root.resolve(strict=True)
    sysroot = root/'etc/r36os-release'
    policy = root/'etc/r36os/firstboot-policy.conf'
    if not file_regular(sysroot) or 'ID=r36os\n' not in sysroot.read_text():
        raise Reject('not CP06 R36OS native root')
    if not file_regular(policy) or 'flash_image_ready=false\n' not in policy.read_text() or 'update_apply_enabled=false\n' not in policy.read_text():
        raise Reject('native root is missing fail-closed update policy')
    lib = root/'lib'
    if not lib.is_symlink() or os.readlink(lib) != 'usr/lib':
        raise Reject('expected Debian usr-merged lib symlink')
    native_modules = root/'usr/lib/modules'
    if native_modules.is_symlink() or (native_modules.exists() and not native_modules.is_dir()):
        raise Reject('native modules path unsafe')
    return root

def archive_member_path(name, release):
    if '\\' in name or '\x00' in name or name.startswith('/'):
        raise Reject('unsafe archive member name')
    p = PurePosixPath(name)
    if '..' in p.parts:
        raise Reject('archive contains traversal')
    parts = [x for x in p.parts if x not in ('.', '')]
    # The nested archive must contain the exact /lib/modules ABI; an optional
    # enclosing packaging folder is tolerated but no other ABI is extracted.
    for i in range(len(parts)-2):
        if parts[i:i+2] == ['lib','modules']:
            if parts[i+2] != release:
                raise Reject('modules archive contains a different kernel release')
            return parts[i+3:]
    if p.as_posix() in ('','.') or not parts:
        return None
    # Allow wrapper directories only, never unexpected data files.
    return None

def extract_modules_nested(stream, destination: Path, release: str):
    """Stream-safe, refuses all non-regular special filesystem writes."""
    if destination.exists() or destination.is_symlink():
        raise Reject('module staging destination already exists')
    destination.mkdir(parents=True, mode=0o700)
    count = byte_count = modules = 0
    present = set()
    skipped_links = []
    with tarfile.open(fileobj=stream, mode='r|xz') as inner:
        for member in inner:
            if member.name in ('.','./') and member.isdir():
                continue
            suffix = archive_member_path(member.name, release)
            if suffix is None:
                if not member.isdir():
                    raise Reject('unexpected non-module file in tar: '+member.name)
                continue
            if not suffix:
                if not member.isdir():
                    raise Reject('non-directory at module ABI root')
                continue
            count += 1
            if count > MAX_FILES:
                raise Reject('too many files in kernel modules tar')
            relative = PurePosixPath(*suffix)
            if str(relative) in present:
                raise Reject('duplicate module archive path')
            present.add(str(relative))
            target = destination.joinpath(*suffix)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise Reject('output path escapes stage')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            # K1 build/source symlinks would point to discarded compiler paths.
            # Skip only these nonruntime references and record the omission.
            if member.issym() and str(relative) in ('build','source'):
                skipped_links.append(str(relative))
                continue
            if not member.isfile():
                raise Reject('unexpected special file / symlink / hardlink in modules archive: '+member.name)
            if member.size > MAX_ONE or byte_count+member.size > MAX_TOTAL:
                raise Reject('kernel modules exceed extraction bounds')
            target.parent.mkdir(parents=True, exist_ok=True)
            # Refuse following any links from a prior unsafe entry.
            for anc in target.parents:
                if anc == destination.parent:
                    break
                if anc.is_symlink():
                    raise Reject('symlink ancestor in extracted modules')
            with inner.extractfile(member) as src, open(target,'xb') as out:
                if src is None:
                    raise Reject('module member unreadable')
                copied = shutil.copyfileobj(src, out, 1024*1024)
            if target.stat().st_size != member.size:
                raise Reject('truncated module entry')
            target.chmod(member.mode & 0o755)
            byte_count += member.size
            if target.name.endswith(('.ko','.ko.xz','.ko.zst','.ko.gz')):
                modules += 1
    if not (destination/'modules.dep').is_file():
        raise Reject('kernel module dependency index absent')
    if modules < 1:
        raise Reject('kernel module archive contains no actual modules')
    return {'entries':count,'module_files':modules,'payload_bytes':byte_count,'skipped_links':skipped_links}

def module_inner_stream(outer, prefix):
    members = [m for m in outer.getmembers() if m.name.lstrip('./') == (prefix+'modules.tar.xz').lstrip('./') and m.isfile()]
    if len(members) != 1:
        raise Reject('expected one nested modules.tar.xz in verified K1 result')
    return outer.extractfile(members[0])

def integrate(archive, work):
    work = check_sandbox(work)
    root = work/'native-root'
    if root.resolve().parent != work or root.is_symlink():
        raise Reject('root outside sandbox')
    root = check_native_root(root)
    report_path = work/'cp14-compatibility-report.json'
    if report_path.exists() or report_path.is_symlink():
        raise Reject('refusing to replace an existing compatibility report')
    stage = work/'.k1-modules-staging'
    if stage.exists() or stage.is_symlink():
        raise Reject('module staging directory already exists')
    # Verify complete K1 build manifest before accepting nested module bytes.
    cp13 = Path(__file__).resolve().with_name('verify-k1-artifact.py')
    if not cp13.is_file():
        raise Reject('CP13 verifier module missing')
    spec = importlib.util.spec_from_file_location('cp13_verified', cp13)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    provenance = mod.verify(archive)
    release = provenance['candidate']['kernel_release']
    if release != '6.12.94-r36os-k1':
        raise Reject('unexpected K1 kernel ABI '+release)
    target = root/'usr/lib/modules'/release
    if target.exists() or target.is_symlink():
        raise Reject('target modules ABI already exists; never overlay')
    with tarfile.open(archive, 'r:gz') as outer:
        stream = module_inner_stream(outer, provenance['candidate_prefix'])
        if stream is None: raise Reject('nested modules archive missing')
        with stream:
            details = extract_modules_nested(stream, stage, release)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Install into disposable CI native-root staging only, after full validation.
    os.replace(stage,target)
    report = {
        'format':'R36OS_CP14_K1_NATIVE_MODULE_INTEGRATION',
        'status':'PASS_KERNEL_MODULES_INSTALLED_TO_DISPOSABLE_NATIVE_ROOT',
        'safe_to_flash':False,'boot_tested':False,'bootloader_integrated':False,
        'kernel_release':release,'module_details':details,
        'native_root_policy':'flash_image_ready=false',
        'k1_root_uuid':provenance['candidate'].get('root_uuid'),
        'k1_state_uuid':provenance['candidate'].get('state_uuid'),
        'uboot_ramdisk_arch_id':provenance['uboot_ramdisk_arch_id'],
        'compatibility_gaps':provenance['compatibility_gaps'] + [
            'K1 uInitrd still refers to R3 root identity; CP14 new ext4 root UUID not bound',
            'K1 and Panel 4 boot not tested on physical R36S',
            'K1 initramfs rescue boot selection and fallback not integrated'
        ],
        'candidate_archive_sha256':provenance['source_archive_sha256'],
        'modules_archive_sha256':provenance['required_boot_artifacts']['modules.tar.xz']['sha256']
    }
    with report_path.open('x') as f:
        json.dump(report,f,indent=2,sort_keys=True)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('verified_k1_result_tar_gz',type=Path)
    parser.add_argument('temporary_workspace',type=Path)
    a=parser.parse_args()
    report=integrate(a.verified_k1_result_tar_gz,a.temporary_workspace)
    print('CP14 native K1 module integration PASS:',report['module_details'])
    print('CP14 NOT boot-ready; compatibility gaps:',len(report['compatibility_gaps']))
if __name__ == '__main__':main()