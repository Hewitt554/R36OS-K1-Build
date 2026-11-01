#!/usr/bin/env python3
"""Document all Kconfig differences and flag unanticipated changes."""
from pathlib import Path
import sys

def load(filename):
    out={}
    for line in Path(filename).read_text().splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            k,v=line.split('=',1);out[k]=v
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            out[line.split(' ')[1]]='n'
    return out

old,new=map(load,sys.argv[1:3])
allowed={'CONFIG_RTL8XXXU','CONFIG_RTL8XXXU_UNTESTED','CONFIG_CFG80211',
         'CONFIG_MAC80211','CONFIG_RFKILL','CONFIG_CRYPTO_LIB_ARC4'}
changes=[]
for k in sorted(old.keys() | new.keys()):
    a,b=old.get(k,'absent'),new.get(k,'absent')
    if a != b:changes.append((k,a,b,k in allowed))
print('R36OS R31 kernel configuration delta (R29 device versus rebuilt modules)')
print('WARNING: Same kernelrelease/vermagic alone do NOT certify binary ABI compatibility')
for k,a,b,ok in changes:
    print(f'{"INTENDED" if ok else "REVIEW_REQUIRED"}: {k}: {a} -> {b}')
print(f'TOTAL_CHANGED={len(changes)} UNEXPECTED={sum(not x[3] for x in changes)}')
if any(not x[3] for x in changes):
    print('GATE=FAIL_UNEXPECTED_KERNEL_CONFIGURATION_CHANGE')
    sys.exit(4)
print('GATE=PASS_CONFIGURATION_CHANGE_ONLY — ABI STILL UNVERIFIED')
