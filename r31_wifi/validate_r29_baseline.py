#!/usr/bin/env python3
"""Validate raw exported R36OS K1 /proc/config.gz options; NEVER installs or changes a kernel."""
import sys,gzip
from pathlib import Path
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('WIFI_KERNEL_CONFIG_R29.gz')
try:
    data=gzip.decompress(p.read_bytes()).decode('utf-8')
except Exception as ex:
    raise SystemExit('Could not read config: '+str(ex))
checks=['CONFIG_MODULES','CONFIG_MODVERSIONS','CONFIG_USB','CONFIG_LEDS_CLASS','CONFIG_FW_LOADER','CONFIG_CFG80211','CONFIG_MAC80211','CONFIG_RFKILL','CONFIG_CRYPTO_LIB_ARC4','CONFIG_RTL8XXXU','CONFIG_RTL8XXXU_UNTESTED']
settings={}
for line in data.splitlines():
    if line.startswith('CONFIG_') and '=' in line:
        k,v=line.split('=',1);settings[k]=v
    elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
        settings[line.split()[1]]='n'
for k in checks:
    print(f'{k}={settings.get(k,"not-present")}')
assert settings.get('CONFIG_RTL8XXXU')=='n','This is not the captured R29 baseline configuration'
assert settings.get('CONFIG_CFG80211')=='m' and settings.get('CONFIG_MAC80211')=='m'
print('PASS: R29 baseline identified, rtl8xxxu disabled. THIS IS NOT A DRIVER BUILD.')
