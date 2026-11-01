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
# Only for building a HOST-ONLY exploratory candidate. These changes indicate
# the source tree is NOT an exact match to the deployed R36OS K1 kernel.
known_source_drift={
    ('CONFIG_ROCKCHIP_CPUINFO','y','absent'),
    ('CONFIG_RUSTC_VERSION','109900','109901'),
}
changes=[]
for k in sorted(old.keys() | new.keys()):
    a,b=old.get(k,'absent'),new.get(k,'absent')
    if a != b:changes.append((k,a,b,k in allowed, (k,a,b) in known_source_drift))
print('R36OS R31 kernel configuration delta (R29 device versus rebuilt modules)')
print('WARNING: Same kernelrelease/vermagic alone do NOT certify binary ABI compatibility')
for k,a,b,ok,drift in changes:
    print(f'{"INTENDED" if ok else "KNOWN_K1_SOURCE_DRIFT" if drift else "REVIEW_REQUIRED"}: {k}: {a} -> {b}')
print(f'TOTAL_CHANGED={len(changes)} UNEXPECTED={sum(not x[3] and not x[4] for x in changes)}')
print(f'KNOWN_SOURCE_DRIFT={sum(x[4] for x in changes)}')
print('MODULES_ARE_NOT_VERIFIED_FOR_R36XX=1')
if any(not x[3] and not x[4] for x in changes):
    print('GATE=FAIL_UNEXPECTED_KERNEL_CONFIGURATION_CHANGE')
    sys.exit(4)
print('GATE=PASS_HOST_EXPLORATORY_BUILD_ONLY — SOURCE_DRIFT PRESENT; DEVICE INSTALL PROHIBITED')
