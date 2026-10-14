#!/usr/bin/env python3
"""Build CP17 diagnostic-only ARM64 initramfs and alternative U-Boot headers.

Strictly scratch-only: no BOOT, sdcard, raw flash image, or original boot.ini.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import tempfile

class Unsafe(ValueError): pass

def cp15_helpers():
    p=Path(__file__).resolve().parents[1]/'boot'/'build-cp15-initrd.py'
    spec=importlib.util.spec_from_file_location('r36os_cp15_cpio',p)
    if spec is None or spec.loader is None: raise Unsafe('CP15 U-Boot builder missing')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def verify_script(data: bytes):
    if not data.startswith(b'#!/bin/sh\n'):
        raise Unsafe('diagnostic init must start with POSIX sh shebang')
    for bad in (b'fatwrite',b'mkfs.',b'fsck ',b'fsck.',b' sfdisk',b' wipefs',
                b' dd ',b' /dev/mmcblk',b'open("/dev/mmc',b'mount -t ext4',
                b'fw_setenv',b'saveenv',b'reboot ',b'poweroff '):
        if bad in data: raise Unsafe('diagnostic script contains prohibited persistent-disk action '+repr(bad))
    for required in (b'/proc/device-tree/model',b'/sys/class/input/',b'/sys/class/power_supply/',
                     b'/sys/block/mmcblk',b'/sys/class/graphics/',b'/bin/r36os-fbdiag'):
        if required not in data: raise Unsafe('missing diagnostic hardware inspection '+repr(required))
    return True

def safe_out(path: Path):
    if path.is_symlink() or not path.is_dir(): raise Unsafe('scratch output directory missing')
    root=path.resolve(strict=True)
    temp=Path(tempfile.gettempdir()).resolve(strict=True)
    if temp not in root.parents or not root.name.startswith('r36os-cp17-diag-'):
        raise Unsafe('output path is not a CP17 scratch directory')
    if list(root.iterdir()): raise Unsafe('scratch output directory must be empty')
    return root

def make_image(script: bytes,busybox: bytes,fb_binary: bytes):
    mod=cp15_helpers()
    files=[('bin',stat.S_IFDIR|0o755,b'',0,0),('dev',stat.S_IFDIR|0o755,b'',0,0),
           ('proc',stat.S_IFDIR|0o755,b'',0,0),('sys',stat.S_IFDIR|0o755,b'',0,0),
           ('run',stat.S_IFDIR|0o755,b'',0,0),('dev/console',stat.S_IFCHR|0o600,b'',5,1),
           ('dev/null',stat.S_IFCHR|0o666,b'',1,3),
           ('init',stat.S_IFREG|0o755,script,0,0),
           ('bin/busybox',stat.S_IFREG|0o755,busybox,0,0),
           ('bin/r36os-fbdiag',stat.S_IFREG|0o755,fb_binary,0,0)]
    for name in ('sh','mount','mdev','mkdir','cat','tr','uname','sleep'):
        files.append(('bin/'+name,stat.S_IFLNK|0o777,b'busybox',0,0))
    data=b''
    for i,(name,mode,body,maj,minr) in enumerate(sorted(files,key=lambda f:f[0]),1):
        data+=mod.cpio_entry(name,mode,body,i,maj,minr)
    data+=mod.cpio_entry('TRAILER!!!',0,b'',len(files)+1)
    gz=gzip.compress(data,compresslevel=9,mtime=0)
    images={}
    for arch in (2,22):
        u=mod.uimage(gz,arch)
        mod.verify_uimage(u,arch,gz)
        images[arch]=u
    return images,{'payload_bytes':len(gz),'uncompressed_cpio_bytes':len(data)}

def generate(bb_path: Path,fb_path: Path,init_path: Path,out_path: Path):
    mod=cp15_helpers()
    out=safe_out(out_path)
    bb=mod.read_busybox(bb_path)
    fb=mod.read_busybox(fb_path)   # must be a static ARM64 ELF
    script=init_path.read_bytes()
    verify_script(script)
    imgs,details=make_image(script,bb,fb)
    result={'format':'R36OS_CP17_DIAGNOSTIC_RAMDISK','status':'BUILT_UNTESTED',
            'safe_to_flash':False,'boot_tested':False,
            'writes_persistent_storage':False,'automatic_recovery':False,
            'panel4_screen_output':'NOT_VERIFIED','kernel_target':'6.12.94-r36os-k1',
            'payload':details,'variants':{}}
    for arch,data in imgs.items():
        name=f'CP17-ARCH{arch}-DIAGNOSTIC-UNTESTED.uInitrd'
        (out/name).write_bytes(data)
        result['variants'][str(arch)]={'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    (out/'cp17-diagnostic-report.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    (out/'DO_NOT_FLASH.txt').write_text('NOT BOOT TESTED: neither header is proven compatible with R36S U-Boot. NO boot.ini, bootloader or recovery handoff. Never copy these files to production SD1.\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--busybox',type=Path,required=True)
    p.add_argument('--framebuffer-tool',type=Path,required=True)
    p.add_argument('--init-script',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    r=generate(a.busybox,a.framebuffer_tool,a.init_script,a.output_dir)
    print('CP17 hardware diagnostic initrd BUILT (NO BOOT TEST); payload bytes',r['payload']['payload_bytes'])
if __name__=='__main__':main()