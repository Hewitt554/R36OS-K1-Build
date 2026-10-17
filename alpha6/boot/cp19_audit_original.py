#!/usr/bin/env python3
"""CP19: Audit the exact, user-extracted R3 boot.ini; NEVER output a boot script.

The trusted SHA derives from the user's read-only CP11 extraction. Its raw 5108
bytes are intentionally not embedded in the public GitHub repository.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

R3_SHA = 'b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
R3_LENGTH = 5108
LEGACY_UUID = 'e139ce78-9841-40fe-8823-96a304a09859'
MEMORY_VARS = ('loadaddr','initrd_loadaddr','dtb_loadaddr')
EXPECTED_MEMORY = {'loadaddr':'0x02000000','initrd_loadaddr':'0x01100000','dtb_loadaddr':'0x01f00000'}
PERSISTENT = ('fatwrite', 'saveenv')
AUDIT_FORMAT = 'R36OS_CP19_EXACT_R3_BOOT_REVIEW_NOT_INSTALLABLE'

class Reject(ValueError):
    pass

def normalize(text: str):
    return [(n, s.strip()) for n, s in enumerate(text.splitlines(), 1)
            if s.strip() and not s.lstrip().startswith('#')]

def find_commands(commands, pattern):
    expr = re.compile(pattern)
    return [n for n,s in commands if expr.search(s)]

def audit(data:bytes, *, reference_sha=R3_SHA, reference_length=R3_LENGTH) -> dict:
    if len(data) != reference_length:
        raise Reject('original R3 boot.ini size mismatch')
    if hashlib.sha256(data).hexdigest() != reference_sha:
        raise Reject('original R3 boot.ini SHA-256 mismatch')
    try: text = data.decode('utf-8', 'strict')
    except UnicodeError as e: raise Reject('original boot.ini is not UTF-8') from e
    if '\x00' in text: raise Reject('boot.ini contains NUL')
    commands = normalize(text)
    if not commands or commands[0][1] != 'odroidgoa-uboot-config':
        raise Reject('original boot script header changed')
    memory = {}
    mem_line = {}
    for var in MEMORY_VARS:
        matches = [(n,s) for n,s in commands if re.fullmatch(r'setenv\s+'+var+r'\s+"?(0x[0-9a-fA-F]+)"?',s)]
        if len(matches) != 1: raise Reject('missing or duplicated setenv '+var)
        n,s=matches[0]; m=re.search(r'0x[0-9a-fA-F]+',s)
        memory[var]=m.group(0);mem_line[var]=n
    if memory != EXPECTED_MEMORY:
        raise Reject('unexpected legacy U-Boot memory layout')
    bootis=find_commands(commands,r'^booti(?:\s|$)')
    if len(bootis) != 1:raise Reject('expected exactly one original booti invocation')
    end=bootis[0]
    bootarg=find_commands(commands,r'^setenv\s+bootargs\s+"root=UUID=')
    if len(bootarg)!=1 or not (min(mem_line.values()) < bootarg[0] < end):
        raise Reject('bootargs / memory address ordering changed')
    if LEGACY_UUID not in data.decode('utf-8'):raise Reject('old root UUID absent')
    writes={cmd:find_commands(commands,r'^'+cmd+r'(?:\s|$)') for cmd in PERSISTENT}
    if not all(writes.values()):raise Reject('unexpected missing original persistent-write instructions')
    loads=[{'line':n,'command':s} for n,s in commands if re.match(r'^load\s+mmc\s+1:1\b',s)]
    if len(loads)<4:raise Reject('expected audited mmc 1:1 load operations')
    after=[(n,s) for n,s in commands if n>end]
    reset=[n for n,s in after if s=='reset']
    sleep=[n for n,s in after if s=='sleep 3']
    if len(reset)!=1 or len(sleep)!=1 or sleep[0]>reset[0]:
        raise Reject('missing original post-boot reset')
    # Check that the panel 5 custom kernel command is followed by an
    # unconditional default kernel load within the same 'if' branch.
    panel5=[n for n,s in commands if re.search(r'load\s+mmc\s+1:1\s+\$\{loadaddr\}\s+"\$\{PanelPath\}/Image"',s)]
    default_loads=[n for n,s in commands if re.search(r'^load\s+mmc\s+1:1\s+\$\{loadaddr\}\s+Image$',s)]
    panel5_override = bool(panel5 and any(panel5[0]<n<end for n in default_loads))
    final_image=[n for n,s in commands if s == 'load mmc 1:1 ${loadaddr} Image']
    final_initrd=[n for n,s in commands if s=='load mmc 1:1 ${initrd_loadaddr} uInitrd']
    final_dtb=[n for n,s in commands if s=='load mmc 1:1 ${dtb_loadaddr} "${PanelPathSlash}rk3326-r35s-linux.dtb"']
    if not all((final_image,final_initrd,final_dtb)):
        raise Reject('expected legacy load commands absent')
    if not (max(final_image)<final_initrd[0]<final_dtb[0]<end):
        raise Reject('unexpected kernel/initrd/DTB load order')
    # The CP08 hook was inserted by replace(ANCHOR, HOOK+ANCHOR). This
    # necessarily executes before R3's memory-address initialisation.
    cp08_insertion_line=bootarg[0]
    unsafe_gate = cp08_insertion_line<min(mem_line.values())
    # When memory vars precede bootargs, gate is placed after the variables;
    # the REAL placement here is after variables; but CP08 loads before the
    # final DTB and kernel commands and may fall through on failed booti.
    # CP08 is unsafe regardless, due to no boot-once proof/independent fallback.
    panel4=[n for n,s in commands if s=='setenv PanelNum "4"']
    if len(panel4)!=1: raise Reject('Panel 4 chooser contract changed')
    return {
        'format':AUDIT_FORMAT,
        'source_length':len(data),'source_sha256':hashlib.sha256(data).hexdigest(),
        'source_kind':'user_uploaded_cp11_original_full_bytes_verified_locally',
        'source_full_bytes_published':False,
        'bootloader_script_header':commands[0][1],
        'memory_load_addresses':{k:{'value':memory[k],'line':mem_line[k]} for k in MEMORY_VARS},
        'load_commands':loads,
        'legacy_root_uuid':LEGACY_UUID,
        'legacy_bootargs_line':bootarg[0],
        'legacy_booti_line':end,
        'post_booti_sleep_line':sleep[0],
        'post_booti_reset_line':reset[0],
        'persistent_write_commands':{k:{'count':len(v),'lines':v} for k,v in writes.items()},
        'panel4_select_line':panel4[0],
        'panel4_select_button':'LEFT (gpio b14) when chooser enabled',
        'panel4_state_saved_in_bootloader_env':True,
        'panel5_custom_kernel_line':panel5[0] if panel5 else None,
        'panel5_default_kernel_override':panel5_override,
        'legacy_kernel_loads_error_checked':False,
        'legacy_initrd_load_error_checked':False,
        'legacy_dtb_load_error_checked':False,
        'cp08_insertion_before_address_initialization':unsafe_gate,
        'cp08_insertion_line':cp08_insertion_line,
        'cp08_recovery_gate_approved':False,
        'cp08_recovery_gate_retired':True,
        'safe_to_flash':False,
        'hardware_boot_tested':False,
        'original_boot_ini_modified':False,
        'automatic_fallback_tested':False,
        'next_action':'Develop independent boot selection using actual panel/memory flow; spare-SD hardware test only after fallback verified',
        'blockers':[
            'R3 boot.ini contains persistent fatwrite and saveenv; never assume a read-only fallback',
            'K1/CP17 boot and framebuffer output not proven on physical Panel 4',
            'CP08 synthetic recovery gate lacks a validated boot-once and fallback design',
            'Normal legacy kernel/initrd/DTB loads are not fail-checked before booti',
            'Normal legacy boot resets when booti returns, with no independent recovery root',
            'No verified power-loss-safe rollback, boot counter or spare-SD hardware validation',
        ]
    }

def validate_report(report:dict)->bool:
    if report.get('format')!=AUDIT_FORMAT or report.get('source_sha256')!=R3_SHA or report.get('source_length')!=R3_LENGTH:
        raise Reject('invalid full-original provenance')
    if report.get('safe_to_flash') is not False or report.get('cp08_recovery_gate_approved') is not False or report.get('cp08_recovery_gate_retired') is not True:
        raise Reject('unsafe CP19 conclusions')
    for cmd in PERSISTENT:
        count=report['persistent_write_commands'][cmd]
        if count['count']<1 or len(count['lines'])!=count['count']:raise Reject('missing write command evidence')
    if report.get('original_boot_ini_modified') is not False:
        raise Reject('cannot approve modified original')
    return True

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--original', type=Path,help='original, verified CP11 boot.ini file; read-only')
    ap.add_argument('--output-report',type=Path,help='new JSON only; refuses overwrite')
    ap.add_argument('--check-report',type=Path,help='verify derived CP19 report, never rebuild boot script')
    args=ap.parse_args(argv)
    if args.check_report:
        try:validate_report(json.loads(args.check_report.read_text()))
        except (Reject,ValueError,OSError) as e:ap.error(str(e))
        print('CP19 derived report safety gates PASS (original bytes not present in this check)')
        return 0
    if not args.original or not args.output_report:ap.error('--original and --output-report required')
    original=args.original.resolve(strict=True)
    output=args.output_report.resolve()
    if original==output or output.suffix.lower()!='.json' or output.name.lower() in ('boot.ini','flash.img'):
        ap.error('output must be a new standalone .json file')
    try:
        report=audit(original.read_bytes())
        validate_report(report)
        with output.open('x',encoding='utf8') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
    except (OSError,Reject) as e:ap.error(str(e))
    print('CP19 exact R3 boot.ini AUDITED. No boot.ini or flash image generated. DO NOT FLASH.')
    return 0

if __name__=='__main__':raise SystemExit(main())