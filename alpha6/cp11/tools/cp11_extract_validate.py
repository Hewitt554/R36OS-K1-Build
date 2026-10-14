#!/usr/bin/env python3
"""R36OS Alpha6 CP11: extract and validate the exact audited R3 FAT32 boot.ini.

Read-only for source IMG; emits independent UNSAFE-TO-INSTALL development files.
No external Python packages, no admin, no mounted Linux filesystem.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

from audit_r36os_boot import FAT32Boot, REFERENCE_IMAGE_SIZE, REFERENCE_BOOT_START, REFERENCE_BOOT_SECTORS
from build_recovery_gate_cp08 import candidate as cp08_candidate, R3_SHA, R3_SIZE, HOOK, UnsafeSource

OUTPUT_BASENAME = "CP11_RESULTS"
FILE_ORIGINAL = "R36OS_CP11_VERIFIED_R3_BOOT_ORIGINAL.bin"
FILE_CANDIDATE = "R36OS_CP11_BOOT_CANDIDATE_UNTESTED.txt"
FILE_REPORT = "R36OS_CP11_BOOT_VALIDATION.json"
FILE_SUMMARY = "R36OS_CP11_BOOT_VALIDATION.txt"

class AuditRejected(ValueError):
    pass

def hexsha(contents:bytes)->str:
    return hashlib.sha256(contents).hexdigest()

def extract_and_validate(image:Path, *, expected_image_size=REFERENCE_IMAGE_SIZE,
                         expected_partition_start=REFERENCE_BOOT_START,
                         expected_partition_sectors=REFERENCE_BOOT_SECTORS,
                         expected_boot_sha=R3_SHA, expected_boot_size=R3_SIZE,
                         allow_test_reference=False):
    """The production command supplies immutable defaults; test overrides are fixture-only."""
    if not image.is_file():
        raise AuditRejected("Image not found or is not a regular file")
    with image.open("rb") as reader:
        fat=FAT32Boot(reader)
        if fat.image_size != expected_image_size:
            raise AuditRejected("Image file length differs from audited R3")
        if (fat.partition_type,fat.partition_start,fat.partition_sectors)!=(0x0b,expected_partition_start,expected_partition_sectors):
            raise AuditRejected("BOOT partition differs from audited R3")
        if fat.fs_label != "BOOT" or fat.sector_size!=512:
            raise AuditRejected("Unexpected FAT32 BOOT volume")
        entries=fat.directory(fat.root_cluster)
        boot=[e for e in entries if e['name'].casefold()=="boot.ini" and not e['directory']]
        if len(boot)!=1:
            raise AuditRejected("Expected exactly one regular BOOT/boot.ini")
        if boot[0]['size'] != expected_boot_size:
            raise AuditRejected("boot.ini byte length mismatch")
        original=fat.read_file(boot[0],max_bytes=64*1024)
    if hexsha(original) != expected_boot_sha:
        raise AuditRejected("boot.ini SHA-256 differs from verified CP01 report")
    # In production, cp08_candidate() itself additionally enforces the fixed R3 reference.
    if allow_test_reference:
        modified=cp08_candidate(original, expected_boot_sha, expected_boot_size)
    else:
        modified=cp08_candidate(original)
    if modified.replace(HOOK,b"",1)!=original:
        raise AuditRejected("Candidate does not preserve original bytes")
    if b'R36OS/RECOVERY.ON' not in modified or b'R36OS/rescue.uInitrd' not in modified:
        raise AuditRejected("CP08 recovery load paths absent")
    if modified.count(HOOK)!=1:
        raise AuditRejected("Unexpected number of recovery gates")
    # Audit the structure, not a claim that U-Boot will accept or run it.
    original_text=original.decode('utf-8',errors='strict')
    if '\x00' in original_text:
        raise AuditRejected("Unexpected NUL in boot text")
    comments={"has_panel_chooser":"PanelPathSlash" in original_text,
              "has_saveenv":"saveenv" in original_text,
              "has_fatwrite":"fatwrite" in original_text,
              "original_booti_count":original.count(b'booti '),
              "candidate_booti_count":modified.count(b'booti '),
              "original_bytes_recoverable":True,
              "read_only_source":True,
              "cp08_uboot_syntax_boot_test":"NOT_TESTED",
              "panel4_rescue_boot":"NOT_TESTED",
              "automatic_failed_boot_fallback":"NOT_IMPLEMENTED",
              "kernel_rescue_compatibility":"NOT_TESTED"}
    return original,modified,comments

def store_outputs(root:Path, image:Path, original:bytes, modified:bytes, checks:dict)->Path:
    root=root.resolve(strict=True)
    if not root.is_dir():
        raise AuditRejected("Output base is not a directory")
    # Choose a unique directory; never alter existing files or the source image.
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for suffix in range(100):
        name=OUTPUT_BASENAME+'_'+stamp+(('_'+str(suffix)) if suffix else '')
        out=root/name
        try:
            out.mkdir(mode=0o700,exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        raise AuditRejected("Cannot reserve unique result folder")
    # The report refers to bare names, not paths to private Windows files.
    report={
        "status":"PASS_READ_ONLY_BOOT_SCRIPT_VALIDATION",
        "source_image_name":image.name,
        "image_bytes":image.stat().st_size,
        "r3_boot_ini_bytes":len(original),
        "r3_boot_ini_sha256":hexsha(original),
        "cp08_candidate_bytes":len(modified),
        "cp08_candidate_sha256":hexsha(modified),
        "original_file":FILE_ORIGINAL,
        "candidate_file":FILE_CANDIDATE,
        "checked":checks,
        "warning":"Candidate is not a proven U-Boot script. DO NOT install onto BOOT, SD1 or SD2.",
        "limitations":["Source IMG was not rehashed fully; prior CP00 provided that verification",
                        "Boot script syntax is unverified on the R36S U-Boot",
                        "No actual Panel4 rescue boot and no safe automatic rollback",
                        "Does not create a flashable Alpha 6 image"]
    }
    (out/FILE_ORIGINAL).write_bytes(original)
    (out/FILE_CANDIDATE).write_bytes(modified)
    (out/FILE_REPORT).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (out/FILE_SUMMARY).write_text('\n'.join([
        'R36OS CP11 verified R3 boot.ini extraction (source IMG READ ONLY)',
        'Status: PASS',
        'Original boot.ini: '+str(len(original))+' bytes',
        'SHA256: '+hexsha(original),
        'CP08 candidate: '+str(len(modified))+' bytes',
        'Candidate SHA256: '+hexsha(modified),
        'Original boot preserved: yes',
        'Hardware tested: NO',
        'Bootloader script tested: NO',
        'Recovery auto rollback: NOT IMPLEMENTED',
        'DO NOT FLASH OR REPLACE BOOT.INI WITH THESE FILES.',
    ])+'\n',encoding='utf-8')
    return out

def main(argv=None):
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('source_image',type=Path)
    arg.add_argument('output_parent',type=Path,nargs='?',default=Path(__file__).resolve().parents[1])
    a=arg.parse_args(argv)
    try:
        original,modified,checks=extract_and_validate(a.source_image)
        result=store_outputs(a.output_parent,a.source_image,original,modified,checks)
    except (OSError,ValueError,UnicodeError,UnsafeSource) as e:
        print('CP11 FAIL (image was not modified):',str(e),file=sys.stderr)
        return 1
    print('CP11 PASS: audited original boot.ini found and CP08 candidate generated')
    print('Reports and files in:',result)
    print('UPLOAD ONLY these two if requested: '+FILE_REPORT+', '+FILE_ORIGINAL)
    print('DO NOT INSTALL THE CANDIDATE; IT HAS NOT BEEN BOOT TESTED.')
    return 0
if __name__=='__main__':
    raise SystemExit(main())