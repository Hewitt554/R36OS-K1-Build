#!/usr/bin/env python3
"""Collect recursive module dependency closure without shipping kernel Image."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path

def run(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT).strip()

p=argparse.ArgumentParser()
p.add_argument('--build',required=True,type=Path)
p.add_argument('--out',required=True,type=Path)
p.add_argument('--release',required=True)
a=p.parse_args()
modules={}
for mod in a.build.rglob('*.ko'):
    if mod.is_symlink():continue
    if mod.stem in modules:
        raise SystemExit(f'ERROR duplicate module basename: {mod.stem}')
    modules[mod.stem]=mod
required=['rtl8xxxu','cfg80211','mac80211','rfkill','libarc4']
for mod in required:
    if mod not in modules:raise SystemExit(f'ERROR missing configured wifi module: {mod}')
closure={}
def collect(name):
    name=name.replace('-','_')
    if name in closure:return
    path=modules.get(name)
    if path is None:raise SystemExit(f'ERROR missing dependent module: {name}')
    closure[name]=path
    for dep in run('modinfo','-F','depends',str(path)).split(','):
        if dep.strip():collect(dep.strip())
for name in required:collect(name)
a.out.mkdir(parents=True,exist_ok=False)
dstmod=a.out/'lib/modules'/a.release
entries=[]
for name,path in sorted(closure.items()):
    # Retain Kbuild relative tree layout, avoid repackaging other unrelated modules.
    rel=path.relative_to(a.build)
    dest=dstmod/'kernel'/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,dest)
    vermagic=run('modinfo','-F','vermagic',str(dest))
    if not vermagic.startswith(a.release+' '):
        raise SystemExit(f'ERROR vermagic mismatch: {name}: {vermagic}')
    entries.append({'name':name,'path':str(dest.relative_to(a.out)),
                    'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
                    'vermagic':vermagic,'depends':run('modinfo','-F','depends',str(dest))})
# Prove the exact USB alias will bind to this driver.
rtl=closure['rtl8xxxu']
aliases=run('modinfo','-F','alias',str(rtl)).splitlines()
if not any(re.search(r'v0bdap0179',t.lower()) for t in aliases):
    raise SystemExit('ERROR missing usb:v0BDAp0179 RTL8188ETV device alias')
run('depmod','-b',str(a.out),'-a',a.release)
# Validate modalias resolution without insmod, requires depmod data.
lines=run('modprobe','-d',str(a.out),'-S',a.release,'--show-depends','rtl8xxxu')
if 'rtl8xxxu.ko' not in lines:
    raise SystemExit('ERROR modprobe cannot resolve rtl8xxxu dependencies')
manifest={
    'format':'R36OS_R31_K1_WIFI_MODULE_CANDIDATE_V1',
    'target_usb_id':'0bda:0179',
    'expected_running_kernel':a.release,
    'status':'HOST_BUILT_ABI_UNVERIFIED_NOT_INSTALLABLE',
    'boot_kernel_modified':False,
    'kernel_image_shipped':False,
    'requires_in_device_export_and_symbol_compatibility_check':True,
    'requires_firmware_and_network_services':True,
    'driver_alias_present':True,
    'modules':entries,
}
(a.out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
(a.out/'README_NOT_INSTALLABLE.txt').write_text(
    'R36OS R31: Candidate modules only. DO NOT copy to R36XX or load them yet.\n'
    'The original kernel source/patch and ABI identity must be verified.\n'
    'No firmware, WPA or DHCP services are present in this candidate.\n')
print('PASS staged module dependency closure:',', '.join(sorted(closure)))
