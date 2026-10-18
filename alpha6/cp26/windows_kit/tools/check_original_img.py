#!/usr/bin/env python3
"""Stream-verify original R3 IMG from existing PC disk; NEVER copy or write it."""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys
EXPECTED_NAME='R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img'
EXPECTED_BYTES=18375245824
EXPECTED_SHA256='5cdec71b14a94845efe696ea73aacb4f629d0925a3c5c484439738b755cc2219'

def check(p:Path):
    if not p.is_file() or p.is_symlink():raise ValueError('source must be a regular file, not a device')
    if p.name!=EXPECTED_NAME or p.stat().st_size!=EXPECTED_BYTES:
        raise ValueError('wrong original R3 image filename or length')
    h=hashlib.sha256(); count=0
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):
            h.update(block);count+=len(block)
    if count!=EXPECTED_BYTES or h.hexdigest()!=EXPECTED_SHA256:
        raise ValueError('original R3 image SHA256 differs from previously verified reference')
    return 'PASS: Verified original R3 .img SHA256 (read-only), bytes '+str(count)

if __name__=='__main__':
    path=Path(sys.argv[1].strip('"') if len(sys.argv)>1 else input('Original R3 .img path [F:\\r36\\...]: ').strip('"'))
    try:print(check(path))
    except (OSError,ValueError) as e:print('FAIL: ',e,file=sys.stderr);sys.exit(1)