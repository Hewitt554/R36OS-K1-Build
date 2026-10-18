#!/usr/bin/env python3
"""Read-only FDT structural and RK3326 Panel4 candidate audit.

This cannot prove physical display, power, button or U-Boot operation.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile

FDT_MAGIC = 0xd00dfeed
FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 1,2,3,4,9
MAX_DTB = 1024 * 1024

class FDTError(ValueError):
    pass

def roundup(n: int) -> int:
    return (n + 3) & ~3

def parse_fdt(data: bytes) -> dict:
    if len(data) < 40 or len(data) > MAX_DTB:
        raise FDTError('FDT header length out of range')
    magic, total, off_struct, off_strings, off_rsv, version, last, cpu, strings_size, struct_size = struct.unpack_from('>10I',data)
    if magic != FDT_MAGIC or total != len(data) or version < 16 or last > version:
        raise FDTError('bad FDT header, size or version')
    if off_struct % 4 or off_strings % 4 or off_rsv % 8:
        raise FDTError('misaligned FDT section')
    if off_struct < 40 or off_strings < 40 or off_rsv < 40 or \
       off_struct + struct_size > total or off_strings + strings_size > total or \
       struct_size > MAX_DTB or strings_size > MAX_DTB:
        raise FDTError('FDT section out of bounds')
    # Deny overlapping struct/string spans.
    if max(off_struct,off_strings) < min(off_struct+struct_size,off_strings+strings_size):
        raise FDTError('FDT sections overlap')
    structs = data[off_struct:off_struct+struct_size]
    strings = data[off_strings:off_strings+strings_size]
    pos=0; stack=[]; nodes={}; finished=False
    while pos+4 <= len(structs):
        token=struct.unpack_from('>I',structs,pos)[0];pos+=4
        if token==FDT_BEGIN_NODE:
            stop=structs.find(b'\0',pos)
            if stop < 0: raise FDTError('unterminated node name')
            name=structs[pos:stop].decode('utf-8')
            if '\x00' in name or '/' in name or len(name)>255:
                raise FDTError('unsafe node name')
            pos=roundup(stop+1)
            if not stack and name!='': raise FDTError('root FDT node must be empty name')
            path='/' + '/'.join(stack[1:]+[name]) if stack else '/'
            if path in nodes: raise FDTError('duplicate node')
            nodes[path]={};stack.append(name)
            if len(stack)>64 or len(nodes)>20000: raise FDTError('unreasonable FDT complexity')
        elif token==FDT_END_NODE:
            if not stack: raise FDTError('end without node')
            stack.pop()
        elif token==FDT_PROP:
            if not stack or pos+8>len(structs): raise FDTError('malformed property header')
            count,key=struct.unpack_from('>2I',structs,pos);pos+=8
            end=pos+count
            if count>MAX_DTB or end>len(structs) or key>=len(strings):
                raise FDTError('property out of bounds')
            stop=strings.find(b'\0',key)
            if stop<0: raise FDTError('unterminated property name')
            name=strings[key:stop].decode('utf-8')
            path='/' + '/'.join(stack[1:]) if len(stack)>1 else '/'
            if name in nodes[path]: raise FDTError('duplicate property')
            nodes[path][name]=structs[pos:end]
            pos=roundup(end)
        elif token==FDT_NOP:
            pass
        elif token==FDT_END:
            if stack: raise FDTError('END inside node')
            finished=True
            if structs[pos:].strip(b'\0'): raise FDTError('nonempty trailing data')
            break
        else: raise FDTError('invalid FDT token')
    if not finished or '/' not in nodes:
        raise FDTError('incomplete device tree')
    return nodes

def dt_strings(data: bytes) -> list[str]:
    try:
        return [x.decode('utf-8') for x in data.split(b'\0') if x]
    except UnicodeDecodeError:
        return []

def classify(nodes: dict) -> dict:
    root=nodes.get('/',{})
    compat=dt_strings(root.get('compatible',b''))
    model=dt_strings(root.get('model',b''))
    is_rk3326=any('rk3326' in x for x in compat)
    mmc=[]; display=[]; power=[]; input_devices=[]
    dsi_panel_compat=[]
    for path,values in sorted(nodes.items()):
        if path=='/': continue
        kind=path.split('/')[-1].lower()
        compatibles=dt_strings(values.get('compatible',b''))
        status=dt_strings(values.get('status',b''))
        enabled=not status or status[0] in ('okay','ok')
        item={'path':path,'status':status[0] if status else 'implicit-okay',
              'compatible':compatibles[:12]}
        # Only controller nodes, not pinctrl/emmc or sdmmc pin groups.
        mmc_host=(kind.startswith(('mmc@','sdmmc@','sdhci@'))
                  or any('dw-mshc' in c or 'sdhci' in c for c in compatibles))
        if mmc_host and enabled:
            mmc.append(item)
        if ('dsi' in kind or 'panel' in kind or any('nv3051' in c or 'mipi-dsi' in c for c in compatibles)):
            display.append(item)
            if 'panel' in kind:
                dsi_panel_compat.extend(compatibles)
        if 'rk8' in kind or any('rk817' in c or 'rk808' in c for c in compatibles):
            power.append(item)
        if 'gpio-keys' in kind or 'gpio-keys' in compatibles:
            input_devices.append(item)
    blockers=[]
    if not is_rk3326: blockers.append('DTB root compatible does not advertise RK3326')
    if not mmc: blockers.append('No enabled MMC nodes evidenced in DTB')
    if not display: blockers.append('No panel/DSI candidate nodes found')
    identified_nv3051d=any('nv3051' in c.lower() for c in dsi_panel_compat)
    if display and not identified_nv3051d:
        blockers.append('Panel node does not identify NV3051D explicitly; compatible strings are not proof of Panel4 timing')
    blockers.extend(['No physical Panel4 framebuffer/display boot verification',
                     'No original R3 boot.ini or U-Boot memory layout validation',
                     'No safe independently booted fallback for a failed kernel'])
    return {'board_model':model[:2], 'root_compatible':compat,
            'rk3326_root_compatible':is_rk3326,'dtb_node_count':len(nodes),
            'enabled_mmc_nodes':mmc[:25], 'display_candidates':display[:25],
            'panel_node_compatible':sorted(set(dsi_panel_compat)),
            'nv3051d_compatible_explicit':identified_nv3051d,
            'power_candidates':power[:25], 'gpio_keys_candidates':input_devices[:25],
            'blockers':blockers,'boot_tested':False,'safe_to_flash':False,
            'display_tested':False,'recovery_boot_tested':False}

def unique_tar_member(tar, wanted: str):
    matches=[m for m in tar.getmembers()
             if str(PurePosixPath(m.name)) == wanted]
    if len(matches)!=1 or not matches[0].isfile():
        raise FDTError('missing, duplicated or unsafe verified K1 DTB')
    return matches[0]

def audit_archive(archive: Path) -> dict:
    verifier=Path(__file__).resolve().parents[1]/'k1'/'verify-k1-artifact.py'
    spec=importlib.util.spec_from_file_location('r36_cp13_validator',verifier)
    if spec is None or spec.loader is None: raise FDTError('CP13 verifier unavailable')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    provenance=mod.verify(archive)
    prefix=provenance['candidate_prefix']
    with tarfile.open(archive,'r:gz') as tar:
        # CP13 reports normalised paths (candidate/K1/...), but GNU tar
        # commonly stores the physical member name with a leading './'.
        # Match the trusted, manifest-verified logical path uniquely.
        wanted=prefix+'rk3326-r36s-k1.dtb'
        entry=unique_tar_member(tar,wanted)
        if entry.size>MAX_DTB:
            raise FDTError('DTB too large in verified K1 package')
        reader=tar.extractfile(entry)
        if reader is None: raise FDTError('cannot extract verified DTB')
        contents=reader.read(MAX_DTB+1)
    if len(contents)!=entry.size: raise FDTError('DTB extraction length mismatch')
    report=classify(parse_fdt(contents))
    report['format']='R36OS_CP17_STATIC_PANEL4_FDT_AUDIT_V1'
    report['kernel_release']=provenance['candidate']['kernel_release']
    report['k1_source_sha256']=provenance['source_archive_sha256']
    report['dtb_sha256']=provenance['required_boot_artifacts']['rk3326-r36s-k1.dtb']['sha256']
    report['status']='PASS_STATIC_STRUCTURE_NOT_HARDWARE_BOOT'
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('pinned_k1_archive',type=Path)
    p.add_argument('new_report_path',type=Path)
    a=p.parse_args()
    if a.new_report_path.exists() or a.new_report_path.is_symlink():
        p.error('will not overwrite existing report')
    r=audit_archive(a.pinned_k1_archive)
    with a.new_report_path.open('x') as f: json.dump(r,f,sort_keys=True,indent=2)
    print('CP17 static K1 DTB structure:',r['status'])
    print('RK3326 compatible:',r['rk3326_root_compatible'])
    print('Enabled MMC nodes:',len(r['enabled_mmc_nodes']))
    print('Panel/DSI candidates:',len(r['display_candidates']))
    print('Blocking conditions:',len(r['blockers']))
if __name__=='__main__':main()