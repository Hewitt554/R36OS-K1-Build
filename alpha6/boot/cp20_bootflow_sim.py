#!/usr/bin/env python3
"""CP20 deterministic *model* of VERIFIED R3 boot.ini branches. Not a U-Boot VM.

No block-device access, no boot file generation, no raw R3 script in GitHub.
Source of truth: sha256-bound CP19 derived boot-flow audit. Optional --original
checks a local 5108-byte CP11 original, but never publishes or writes it.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any

SHA = 'b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
ROOT_UUID = 'e139ce78-9841-40fe-8823-96a304a09859'
FORMAT = 'R36OS_CP20_OFFLINE_LEGACY_BOOT_FLOW_MODEL_NOT_A_UBOOT_EMULATOR'
EXPECTED_LINES = {'bootargs':174, 'booti':200, 'reset':203, 'panel4':116}
BUTTON_PRIORITY = ('up', 'right', 'down', 'left', 'x', 'a')
BUTTON_TO_PANEL = {'up':1, 'right':2, 'down':3, 'left':4, 'x':5, 'a':0}
ALLOWED = {'r1', 'volume_minus', 'nopanelchooser', 'unsetpanelchooser',
           'buttons', 'saved_panel', 'boot_ini_read_ok', 'fatwrite_ok',
           'saveenv_ok', 'panel_dtb_read_ok', 'legacy_image_read_ok',
           'legacy_initrd_read_ok', 'legacy_dtb_read_ok',
           'panel5_image_read_ok', 'booti_returns'}
BOOLEANS = ALLOWED - {'buttons','saved_panel'}

class UnsafeEvidence(ValueError):
    pass


def verify_audit(report:dict, original:bytes|None=None) -> dict:
    if not isinstance(report,dict):
        raise UnsafeEvidence('expected CP19 evidence object')
    if (report.get('format')!='R36OS_CP19_EXACT_R3_BOOT_REVIEW_NOT_INSTALLABLE'
        or report.get('source_sha256')!=SHA or report.get('source_length')!=5108):
        raise UnsafeEvidence('original R3 provenance mismatch')
    if (report.get('safe_to_flash') is not False or
        report.get('cp08_recovery_gate_approved') is not False or
        report.get('cp08_recovery_gate_retired') is not True or
        report.get('original_boot_ini_modified') is not False):
        raise UnsafeEvidence('untrusted install/CP08 safety flags')
    if (report.get('legacy_root_uuid')!=ROOT_UUID or
        report.get('legacy_bootargs_line')!=EXPECTED_LINES['bootargs'] or
        report.get('legacy_booti_line')!=EXPECTED_LINES['booti'] or
        report.get('post_booti_reset_line')!=EXPECTED_LINES['reset'] or
        report.get('panel4_select_line')!=EXPECTED_LINES['panel4'] or
        report.get('cp08_insertion_before_address_initialization') is not False):
        raise UnsafeEvidence('original boot-line contract changed')
    memory=report.get('memory_load_addresses',{})
    expected={'loadaddr':('0x02000000',170),
              'initrd_loadaddr':('0x01100000',171),
              'dtb_loadaddr':('0x01f00000',172)}
    for key,(addr,line) in expected.items():
        if memory.get(key)!={'value':addr,'line':line}:
            raise UnsafeEvidence('unverified legacy U-Boot memory address '+key)
    counts={'fatwrite':(7,[13,73,90,107,123,139,158]),
            'saveenv':(7,[31,67,86,103,119,135,154])}
    for key,(count,lines) in counts.items():
        if report.get('persistent_write_commands',{}).get(key)!={'count':count,'lines':lines}:
            raise UnsafeEvidence('original persistent-write evidence differs: '+key)
    if (report.get('legacy_kernel_loads_error_checked') is not False or
        report.get('legacy_initrd_load_error_checked') is not False or
        report.get('legacy_dtb_load_error_checked') is not False):
        raise UnsafeEvidence('false success checking for original boot loads')
    if original is not None:
        if len(original)!=5108 or hashlib.sha256(original).hexdigest()!=SHA:
            raise UnsafeEvidence('original boot.ini SHA-256 failed')
        # Recalculate CP19 line structure using exact existing parser, not only
        # comparing the uploaded derived JSON. Never output original bytes.
        src=Path(__file__).with_name('cp19_audit_original.py')
        if not src.exists():
            raise UnsafeEvidence('local CP19 original audit parser missing')
        spec=importlib.util.spec_from_file_location('cp20_cp19_parser',src)
        module=importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(module)
        actual=module.audit(original)
        for key in ('persistent_write_commands','memory_load_addresses',
                    'legacy_bootargs_line','legacy_booti_line','panel4_select_line'):
            if actual.get(key)!=report.get(key):
                raise UnsafeEvidence('original boot script does not match derived evidence: '+key)
    return report


def validate_scenario(scenario:dict) -> dict:
    if not isinstance(scenario,dict) or set(scenario)-ALLOWED:
        raise UnsafeEvidence('scenario contains unknown fields')
    defaults={key:False for key in BOOLEANS}
    defaults.update({'boot_ini_read_ok':True, 'fatwrite_ok':True,'saveenv_ok':True,
                     'panel_dtb_read_ok':True,'legacy_image_read_ok':True,
                     'legacy_initrd_read_ok':True,'legacy_dtb_read_ok':True,
                     'panel5_image_read_ok':True,'buttons':[], 'saved_panel':None})
    defaults.update(scenario)
    for key in BOOLEANS:
        if type(defaults[key]) is not bool:
            raise UnsafeEvidence('scenario bool expected: '+key)
    panel=defaults['saved_panel']
    if panel is not None and (type(panel)!=int or panel not in range(6)):
        raise UnsafeEvidence('saved_panel must be 0 through 5 or null')
    buttons=defaults['buttons']
    if (not isinstance(buttons,list) or any(type(x)!=str or x not in BUTTON_PRIORITY for x in buttons)
        or len(set(buttons))!=len(buttons)):
        raise UnsafeEvidence('invalid panel chooser buttons')
    return defaults


def simulate(report:dict, raw_scenario:dict)->dict:
    verify_audit(report)
    s=validate_scenario(raw_scenario)
    trace=[];writes=[];risks=[]
    def record(line:int, event:str, **extra): trace.append({'line':line,'event':event,**extra})
    def persist(line:int, command:str, target:str, success:bool):
        writes.append({'line':line,'command':command,'target':target,'assumed_success':success})
        record(line,'persistent_write_attempt',command=command,target=target,assumed_success=success)
        if not success:risks.append('Persistence operation failed; actual U-Boot state cannot be inferred')
    flag=s['nopanelchooser']; panel=s['saved_panel']
    record(1,'R3_legacy_script_start',fixed_root_uuid=ROOT_UUID)
    # CP19 lines 4-16: R1+Vol- writes 'nopanelchooser' if source file loaded.
    if s['r1'] and s['volume_minus']:
        record(10,'read_boot_ini_for_nopanelchooser',succeeded=s['boot_ini_read_ok'])
        if s['boot_ini_read_ok']:
            persist(13,'fatwrite','BOOT_FAT32:nopanelchooser',s['fatwrite_ok'])
            if s['fatwrite_ok']:flag=True
    # CP19 lines 21-37: nopanelchooser takes precedence over R1 chooser.
    chooser=False
    if flag:
        record(22,'nopanelchooser_present_skip_chooser')
        if s['unsetpanelchooser']:
            record(28,'clear_saved_panel_environment',previous_panel=panel)
            panel=None
            persist(31,'saveenv','UBOOT_PERSISTENT_ENV',s['saveenv_ok'])
    elif s['r1']:
        chooser=True
        record(33,'R1_enables_panel_chooser')
    # CP19 lines 40-167. Each successful chooser choice powers off, not boot.
    if chooser:
        chosen=next((x for x in BUTTON_PRIORITY if x in s['buttons']),None)
        if chosen is not None:
            panel=BUTTON_TO_PANEL[chosen]
            sel_line={'up':62,'right':83,'down':100,'left':116,'x':132,'a':151}[chosen]
            env_line={'up':67,'right':86,'down':103,'left':119,'x':135,'a':154}[chosen]
            write_line={'up':73,'right':90,'down':107,'left':123,'x':139,'a':158}[chosen]
            record(sel_line,'select_panel',panel_number=panel,button=chosen)
            persist(env_line,'saveenv','UBOOT_PERSISTENT_ENV',s['saveenv_ok'])
            record(write_line-2,'load_panel_dtb_for_boot_copy',succeeded=s['panel_dtb_read_ok'])
            if s['panel_dtb_read_ok']:
                persist(write_line,'fatwrite','BOOT_FAT32:rg351mp-kernel.dtb',s['fatwrite_ok'])
            record(write_line+3,'sleep_5_then_poweroff')
            return outcome(s,trace,writes,risks,'poweroff_after_panel_selection',panel,booti_attempted=False)
        record(165,'chooser_no_button_continue_legacy_boot')
    # CP19 lines 170-203: three known fixed buffers and unchecked file reads.
    record(170,'set_memory_buffers',kernel='0x02000000',initrd='0x01100000',dtb='0x01f00000')
    record(174,'set_legacy_root_bootargs',root_uuid=ROOT_UUID)
    if panel==5:
        record(182,'panel5_custom_image_load',succeeded=s['panel5_image_read_ok'])
        record(185,'default_image_overrides_panel5_if_successful',succeeded=s['legacy_image_read_ok'])
        risks.append('Panel 5 custom kernel path followed by default Image load')
    else:
        record(185 if panel is not None else 189,'default_image_load',succeeded=s['legacy_image_read_ok'])
    record(193,'load_legacy_initrd',succeeded=s['legacy_initrd_read_ok'])
    record(198,'load_panel_relative_legacy_dtb',succeeded=s['legacy_dtb_read_ok'])
    missing=[key for key,ok in [('Image',s['legacy_image_read_ok']),('uInitrd',s['legacy_initrd_read_ok']),('DTB',s['legacy_dtb_read_ok'])] if not ok]
    if missing:risks.append('Unchecked legacy boot files failed to load: '+', '.join(missing)+'; stale RAM contents possible')
    record(200,'booti_invoked_without_guarded_loads',missing_assets=missing)
    if missing:
        status='indeterminate_after_unchecked_load_failure'
        record(201,'unknown_kernel_handoff_due_to_missing_file')
    elif s['booti_returns']:
        status='reset_after_return_from_booti'
        record(202,'sleep_3')
        record(203,'reset_called')
    else:
        status='assumed_kernel_handoff_NOT_HARDWARE_PROVEN'
        record(200,'modeled_kernel_handoff_unverified')
    return outcome(s,trace,writes,risks,status,panel,booti_attempted=True)


def outcome(s,trace,writes,risks,status,panel,booti_attempted):
    return {
        'format':FORMAT,'scenario':s,'status':status,
        'modeled_actions':trace,'persistent_write_attempts':writes,
        'persistent_write_count':len(writes),'resulting_panel_environment_in_RAM':panel,
        'booti_attempted':booti_attempted,'real_uboot_emulated':False,
        'actual_boot_tested':False,'fallback_exercised':False,
        'independent_recovery_available':False,
        'writes_to_actual_media':False,'safe_to_flash':False,
        'warnings':risks,
        'limitations':['Derived branch model, NOT an interpreter for original U-Boot binaries',
                       'Actual GPIO, U-Boot command errors, filesystem and eMMC behaviour unknown',
                       'Effects of saveenv/fatwrite assume success flags supplied by test',
                       'No attempt to exercise CP08 or any new recovery scheme',
                       'Kernel execution/Panel4 display/SD1 boot remain untested']}


MATRIX={
 'normal_legacy':{},
 'r1_panel4_choice':{'r1':True,'buttons':['left']},
 'r1_and_volume_minus':{'r1':True,'volume_minus':True},
 'already_nopanelchooser':{'r1':True,'nopanelchooser':True,'buttons':['left']},
 'unset_saved_panel':{'nopanelchooser':True,'unsetpanelchooser':True,'saved_panel':4},
 'chooser_no_button':{'r1':True},
 'kernel_load_failed':{'legacy_image_read_ok':False},
 'initrd_load_failed':{'legacy_initrd_read_ok':False},
 'dtb_load_failed':{'legacy_dtb_read_ok':False},
 'returned_from_booti':{'booti_returns':True},
 'panel5_default_override':{'saved_panel':5},
 'panel4_fatwrite_failed':{'r1':True,'buttons':['left'],'fatwrite_ok':False},
 'panel4_saveenv_failed':{'r1':True,'buttons':['left'],'saveenv_ok':False},
 'boot_ini_marker_load_failed':{'r1':True,'volume_minus':True,'boot_ini_read_ok':False},
 'both_chooser_inputs':{'r1':True,'buttons':['up','left']},
}


def run_matrix(report:dict, original:bytes|None=None)->dict:
    verify_audit(report, original)
    data={name:simulate(report,scenario) for name,scenario in MATRIX.items()}
    return {'format':FORMAT, 'original_boot_sha256':SHA, 'model_only':True,
            'actual_uboot_boot_tested':False,'safe_to_flash':False,
            'installation_artifacts':[], 'script_source_published':False,
            'scenarios':data,
            'summary':{'scenario_count':len(data),
                       'scenarios_with_persistent_writes':sum(bool(s['persistent_write_count']) for s in data.values()),
                       'scenarios_with_unchecked_load_failure':sum(s['status']=='indeterminate_after_unchecked_load_failure' for s in data.values()),
                       'recovery_paths_physically_verified':0}}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--original',type=Path,help='local CP11 original (read-only). NEVER published')
    ap.add_argument('--output',type=Path,help='new JSON report path, never boot.ini or image')
    args=ap.parse_args(argv)
    if args.audit.is_symlink() or not args.audit.is_file():ap.error('audit file missing or symlink')
    try:
        report=json.loads(args.audit.read_text())
        if args.original:
            if args.original.is_symlink() or not args.original.is_file():raise UnsafeEvidence('unsafe original path')
            orig=args.original.read_bytes()
        else:orig=None
        result=run_matrix(report,orig)
        if args.output:
            dest=args.output.resolve()
            if dest.name.lower() in ('boot.ini','flash.img','uinitrd') or dest.suffix.lower()!='.json':
                raise UnsafeEvidence('JSON output only, no boot files')
            with dest.open('x',encoding='utf8') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
        print('CP20 MODEL ONLY: '+str(result['summary'])+'; NOT hardware boot tested or installable')
        return 0
    except (UnsafeEvidence,OSError,UnicodeError,ValueError) as e:
        ap.error(str(e))

if __name__=='__main__':raise SystemExit(main())