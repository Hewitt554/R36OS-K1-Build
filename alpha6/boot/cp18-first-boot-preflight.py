#!/usr/bin/env python3
"""CP18 offline preflight: audit verified K1 + diagnostic assets, NEVER install.

Inputs: historical K1 tar.gz, two uninstalled CP17 ramdisks, and the
selected-lines R3 user audit. Output: JSON evidence only, no bootable artifact.
Files are staged transiently only within a fresh marked /tmp workspace.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
import tempfile

R3_BOOT_HASH = 'b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
R3_UUID = 'e139ce78-9841-40fe-8823-96a304a09859'
KERNEL = '6.12.94-r36os-k1'
EXPECTED_IMAGES = {'2': 'CP17-ARCH2-DIAGNOSTIC-UNTESTED.uInitrd',
                   '22': 'CP17-ARCH22-DIAGNOSTIC-UNTESTED.uInitrd'}
FORBIDDEN_NAMES = {'boot.ini','idbloader.img','uboot.img','u-boot.bin','flash.img',
                   'update.img', 'RECOVERY.ON'}
OUTPUT_MARKER = 'R36OS_CP18_EVIDENCE_ONLY_UNINSTALLABLE'

class Reject(ValueError):
    pass

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024*1024:
        raise Reject('missing, symlinked, or oversized JSON evidence')
    result = json.loads(path.read_bytes())
    if not isinstance(result,dict): raise Reject('expected JSON object')
    return result

def inspect_r3_evidence(data: dict) -> dict:
    if data.get('source_kind') != 'R36OS_CP01_R3_USER_AUDIT_SELECTED_LINES_NOT_RAW_BOOT_SCRIPT':
        raise Reject('unexpected original R3 report provenance')
    if data.get('original_boot_ini_full_bytes_available') is not False:
        raise Reject('original R3 boot bytes not supplied: provenance must say so')
    scripts=data.get('boot_scripts')
    if not isinstance(scripts,list) or len(scripts)!=1:
        raise Reject('expected exactly one audited R3 boot.ini')
    entry=scripts[0]
    if (entry.get('name'),entry.get('size'),entry.get('sha256')) != ('boot.ini',5108,R3_BOOT_HASH):
        raise Reject('R3 boot fingerprint does not match CP01')
    lines=entry.get('relevant_lines')
    if not isinstance(lines,list) or not all(isinstance(x,str) for x in lines):
        raise Reject('R3 selected-line audit absent')
    present=set()
    for line in lines:
        text=line.strip()
        if re.match(r'^fatwrite(?:\s|$)',text):present.add('fatwrite')
        if re.match(r'^saveenv(?:\s|$)',text):present.add('saveenv')
    if not {'fatwrite','saveenv'} <= present:
        raise Reject('R3 mutating boot commands missing from purported audit; verify source')
    if not any(R3_UUID in x for x in lines):
        raise Reject('legacy root identifier missing from source audit')
    if not any('PanelPathSlash' in x for x in lines):
        raise Reject('panel selection evidence missing')
    return {
      'boot_ini_sha256':R3_BOOT_HASH,
      'source':'read-only selected-line CP01 report (NOT original bytes)',
      'original_boot_ini_available':False,
      'legacy_boot_write_commands':sorted(present),
      'legacy_boot_may_write_boot_partition_or_uboot_env':True,
      'legacy_boot_treat_as_read_only_fallback':False,
      'candidate_boot_script_tested_against_original_bytes':False,
      'safe_to_install_boot_gate':False,
    }

def regular(path:Path) -> bool:
    try: return stat.S_ISREG(path.lstat().st_mode)
    except OSError:return False

def inspect_diagnostic_bundle(folder:Path) -> dict:
    if folder.is_symlink() or not folder.is_dir():raise Reject('CP17 input must be a real folder')
    files={x.name for x in folder.iterdir() if x.is_file() and not x.is_symlink()}
    expected=set(EXPECTED_IMAGES.values()) | {'cp17-diagnostic-report.json','DO_NOT_FLASH.txt','cp17-k1-panel4-dtb-report.json'}
    if files!=expected or len(list(folder.iterdir()))!=len(expected):
        raise Reject('unexpected or missing CP17 artifact file; no boot.ini or raw disk accepted')
    if files & FORBIDDEN_NAMES:raise Reject('CP17 contains forbidden installable boot name')
    report=load_json(folder/'cp17-diagnostic-report.json')
    if (report.get('status'),report.get('format'),report.get('kernel_target')) != (
       'BUILT_UNTESTED','R36OS_CP17_DIAGNOSTIC_RAMDISK',KERNEL):
        raise Reject('CP17 report not the expected verified diagnostic type')
    if (report.get('safe_to_flash') is not False or
        report.get('boot_tested') is not False or
        report.get('writes_persistent_storage') is not False or
        report.get('automatic_recovery') is not False):
        raise Reject('CP17 report must prohibit flash, boot-ready and persistent writes')
    variants=report.get('variants')
    if not isinstance(variants,dict) or set(variants)!=set(EXPECTED_IMAGES):
        raise Reject('CP17 variant set mismatch')
    # The U-Boot image reader from CP15 validates header CRC, payload CRC,
    # GZIP and CPIO header. Both variants must share exactly the same payload.
    source=Path(__file__).resolve().parents[1]/'boot'/'build-cp15-initrd.py'
    if not source.is_file():raise Reject('CP15 verifier missing')
    spec=importlib.util.spec_from_file_location('cp15_for_cp18',source)
    mod=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    hashes={};payloads=[]
    for arch,name in EXPECTED_IMAGES.items():
        ref=variants[arch]
        if ref.get('name')!=name:raise Reject('variant filename mismatch')
        path=folder/name
        if not regular(path) or path.stat().st_size>12*1024*1024:raise Reject('unsafe oversized diagnostic image')
        data=path.read_bytes()
        try: mod.verify_uimage(data,int(arch))
        except Exception as e:raise Reject('CP17 U-Boot header failed integrity: '+name) from e
        if digest(data)!=ref.get('sha256') or len(data)!=ref.get('bytes'):
            raise Reject('CP17 manifest digest/size mismatch: '+name)
        hashes[name]={'sha256':digest(data),'bytes':len(data),'uboot_arch_id':int(arch)}
        payloads.append(data[64:])
    if payloads[0]!=payloads[1] or len(payloads[0])!=report.get('payload',{}).get('payload_bytes'):
        raise Reject('CP17 U-Boot variants must share identical payload')
    fdt=load_json(folder/'cp17-k1-panel4-dtb-report.json')
    if (fdt.get('format')!='R36OS_CP17_STATIC_PANEL4_FDT_AUDIT_V1' or
        fdt.get('status')!='PASS_STATIC_STRUCTURE_NOT_HARDWARE_BOOT' or
        fdt.get('kernel_release')!=KERNEL or
        fdt.get('safe_to_flash') is not False or
        fdt.get('boot_tested') is not False or
        fdt.get('display_tested') is not False or
        fdt.get('nv3051d_compatible_explicit') is not False or
        fdt.get('rk3326_root_compatible') is not True or
        len(fdt.get('enabled_mmc_nodes',[]))!=2 or
        'rocknix,generic-dsi' not in fdt.get('panel_node_compatible',[])):
        raise Reject('CP17 K1 DTB report incompatible with untested generic Panel4 audit')
    if 'NOT BOOT' not in (folder/'DO_NOT_FLASH.txt').read_text(errors='replace').upper():
        raise Reject('CP17 not-boot-tested notice absent')
    return {'diagnostic_status':'OFFLINE_CRC_AND_HASH_VERIFIED_HARDWARE_UNTESTED',
            'diagnostic_payload_sha256':digest(payloads[0]),
            'panel4_dtb_sha256':fdt.get('dtb_sha256'),
            'k1_source_sha256':fdt.get('k1_source_sha256'),
            'panel4_dsi_compatible':fdt.get('panel_node_compatible'),
            'panel4_display_tested':False,
            'variant_files':hashes}

def pinned_k1(archive:Path) -> dict:
    source=Path(__file__).resolve().parents[1]/'k1'/'verify-k1-artifact.py'
    if not source.is_file():raise Reject('CP13 verifier missing')
    spec=importlib.util.spec_from_file_location('cp13_for_cp18',source)
    mod=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    data=mod.verify(archive)
    if (data['candidate']['kernel_release'] != KERNEL or
        data['candidate']['panel'] != 'PANEL4_NV3051D_640X480' or
        data['safe_to_flash'] is not False):
        raise Reject('unexpected K1 candidate or unsafe provenance')
    return {'candidate_id':data['candidate']['candidate_id'],
            'archive_sha256':data['source_archive_sha256'],
            'kernel_release':KERNEL,
            'root_uuid_inherited':data['candidate']['root_uuid'],
            'modules_archived_sha256':data['required_boot_artifacts']['modules.tar.xz']['sha256'],
            'kernel_image':data['required_boot_artifacts']['Image'],
            'panel4_dtb':data['required_boot_artifacts']['rk3326-r36s-k1.dtb']}

def workspace(path:Path)->Path:
    if path.is_symlink() or not path.is_dir():raise Reject('CP18 output workspace must be real directory')
    root=path.resolve(strict=True)
    temp=Path(tempfile.gettempdir()).resolve(strict=True)
    if temp not in root.parents or not root.name.startswith('r36os-cp18-preflight-'):
        raise Reject('output must be a uniquely named /tmp CP18 workspace')
    if list(root.iterdir()):raise Reject('CP18 workspace must be empty')
    return root

def create_report(k1:dict, diag:dict, r3:dict)->dict:
    if k1.get('root_uuid_inherited')!=R3_UUID:raise Reject('unverified K1/R3 root identity')
    if diag.get('k1_source_sha256') != k1.get('archive_sha256') or diag.get('panel4_dtb_sha256') != k1.get('panel4_dtb',{}).get('sha256'):
        raise Reject('CP17 device-tree provenance does not match pinned K1 artifact')
    return {
      'format':OUTPUT_MARKER,
      'status':'PASS_COMPONENT_INTEGRITY_BUT_BOOT_NOT_PERMITTED',
      'safe_to_flash':False,'safe_to_install_boot_script':False,
      'boot_tested':False,'recovery_boot_tested':False,
      'flashable_disk_image_generated':False,'bootloader_generated':False,
      'boot_script_generated':False,'installable_files':[],
      'k1':k1,'cp17':diag,'r3_original_boot':r3,
      'blockers':[
        'Original R3 boot.ini full bytes and U-Boot execution semantics unverified',
        'Audited legacy R3 boot contains FAT32 fatwrite and persistent saveenv; not read-only fallback',
        'Safe boot-once/failure detection and independently booted fallback not implemented',
        'Panel4 K1 generic DSI panel compatible, timing and framebuffer output not hardware tested',
        'U-Boot ARM versus ARM64 ramdisk header support and load addresses untested',
        'No physical R36S boot, real root handoff, power-loss rollback or flashable image',
      ]}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--k1-archive',type=Path,required=True)
    a.add_argument('--cp17-folder',type=Path,required=True)
    a.add_argument('--r3-evidence',type=Path,required=True)
    a.add_argument('--output-workspace',type=Path,required=True)
    args=a.parse_args()
    try:
        out=workspace(args.output_workspace)
        r3=inspect_r3_evidence(load_json(args.r3_evidence))
        diag=inspect_diagnostic_bundle(args.cp17_folder)
        k1=pinned_k1(args.k1_archive)
        result=create_report(k1,diag,r3)
        # JSON only: no kernel, initramfs, bootloader, boot.ini, or disk images.
        with (out/'cp18-boot-preflight-report.json').open('x',encoding='utf-8') as f:
            json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
        (out/'CP18_REQUIRES_HARDWARE_VALIDATION.txt').write_text(
            'R36OS CP18: Component hashes passed. Do not flash, install or replace boot.ini.\n'
            'The original R3 boot script contains fatwrite and saveenv; not a read-only fallback.\n'
            'Physical Panel4 K1 boot and independent recovery have NOT been tested.\n'
            'This folder is evidence only; no executable boot files are shipped.\n')
        print('CP18 PASS: K1/CP17 hashes verified; R3 legacy FAT/env writes detected; boot readiness BLOCKED')
        print('CP18 report:',out/'cp18-boot-preflight-report.json')
    except (Reject,OSError,ValueError,tarfile.TarError) as e:
        a.error(str(e))

if __name__=='__main__':main()