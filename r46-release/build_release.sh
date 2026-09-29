#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 3 ] || { echo "usage: build_release.sh <exact-r44.r36upd> <exact-r38.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R44="$1"
R38="$2"
OUT="$3"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r46'
NAME='00-R36OS-Alpha5R46-K1HandoffProbe-FromR44.r36upd'
EXPECTED_R44='2a6b872c3e7b81a88272c03f8c1484d9d4ae582dfe9172796ebff4e8e396a4fa'
EXPECTED_R38='68db42212fc0e13a9bad777daf68f4634bb86f58aa2347a923dde8cd71db30c0'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
LEGACY_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
OLD_HOOK_SHA='c5fddc8c36ece7ddc3b542a7baa96167a08587062327aa45bf8c2c39400587b1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r46-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r44" "$WORK/r38"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$WORK/update/payload/root/opt/r36os/kernel-next"   "$OUT"

test "$(sha256sum "$R44" | awk '{print $1}')" = "$EXPECTED_R44" || { echo r44-sha-mismatch >&2; exit 10; }
test "$(sha256sum "$R38" | awk '{print $1}')" = "$EXPECTED_R38" || { echo r38-sha-mismatch >&2; exit 11; }
tar -xzf "$R44" -C "$WORK/r44"
tar -xzf "$R38" -C "$WORK/r38"
(cd "$WORK/r44" && sha256sum -c checksums.sha256 >/dev/null)
(cd "$WORK/r38" && sha256sum -c checksums.sha256 >/dev/null)

R44ROOT="$WORK/r44/payload/root"
R38ROOT="$WORK/r38/payload/root"
CORE="$R44ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

# Derive R46 prepare from exact published R44.
python3 - "$R44ROOT/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if s.count('0.5.44.0') != 1:
    raise SystemExit('unexpected R44 prepare identity')
s=s.replace('0.5.44.0','0.5.46.0')
Path(sys.argv[2]).write_text(s)
PY

# Derive R46 slot manager from exact published R44. Full verification is still
# mandatory for arm-once; ordinary status uses only small structural/hash checks.
python3 - "$R44ROOT/usr/local/bin/r36os-kernel-slot" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
for a,b in [('0.5.44.0','0.5.46.0'),('Alpha 5R44','Alpha 5R46'),('r44-runtime-lock','r46-runtime-lock')]:
    if s.count(a)!=1: raise SystemExit(f'unexpected slot identity {a}: {s.count(a)}')
    s=s.replace(a,b,1)
anchor='''status(){
  verify_candidate; V=$?; verify_hook; H=$?
  echo "candidate_verify_code=$V"; echo "hook_verify_code=$H"
  if [ -n "$REQ" ]; then
    echo "request_path=$REQ"; echo "consumed_path=$CONSUMED"
    echo "armed=$([ -s "$REQ" ]&&echo yes||echo no)"; echo "consumed=$([ -s "$CONSUMED" ]&&echo yes||echo no)"
  else
    echo "armed=no"; echo "consumed=no"
  fi
}
'''
replacement='''quick_candidate(){
  [ "$("$VERSION_HELPER" version 2>/dev/null)" = 0.5.46.0 ] || return 19
  [ -d "$K1" ] || return 20
  for f in Image uInitrd rk3326-r36s-k1.dtb modules.tar.xz K1.conf BUILD_INFO.txt MANIFEST.sha256; do [ -s "$K1/$f" ] || return 21; done
  [ "$(val "$K1/K1.conf" hardware)" = R36XX-RK3326 ] || return 23
  [ "$(val "$K1/K1.conf" panel)" = PANEL4_NV3051D_640X480 ] || return 24
  [ "$(val "$K1/K1.conf" root_uuid)" = e139ce78-9841-40fe-8823-96a304a09859 ] || return 25
  [ "$(val "$K1/K1.conf" boot_mode)" = R36OS_K1_BOOT_ONCE ] || return 26
  CID="$(val "$K1/K1.conf" candidate_id)"; echo "$CID" | grep -Eq '^[0-9a-f]{24}$' || return 29
  marker_paths || return 30
  return 0
}
quick_hook(){
  [ -s "$META" ] && [ -s "$BOOT" ] || return 40
  quick_candidate || return $?
  [ "$(val "$META" candidate_id)" = "$CID" ] || return 41
  H="$(val "$META" hooked_boot_sha256)"; [ -n "$H" ] || return 42
  [ "$(sha "$BOOT")" = "$H" ] || return 43
  grep -qF '# R36OS-K1-BOOT-ONCE-HOOK' "$BOOT" || return 44
  grep -qF "# candidate_id=$CID" "$BOOT" || return 45
  return 0
}
status(){
  quick_candidate; V=$?
  if [ "$V" -eq 0 ]; then quick_hook; H=$?; else H=$V; fi
  echo "candidate_verify_mode=quick-identity-no-payload-hash"
  echo "candidate_verify_code=$V"; echo "hook_verify_code=$H"
  if [ -n "$REQ" ]; then
    echo "request_path=$REQ"; echo "consumed_path=$CONSUMED"
    echo "armed=$([ -s "$REQ" ]&&echo yes||echo no)"; echo "consumed=$([ -s "$CONSUMED" ]&&echo yes||echo no)"
  else
    echo "armed=no"; echo "consumed=no"
  fi
  echo "full_payload_verification=required-on-arm-once"
}
'''
if s.count(anchor)!=1: raise SystemExit('R44 slot status anchor mismatch')
s=s.replace(anchor,replacement,1)
Path(sys.argv[2]).write_text(s)
PY

# Derive a migration-safe hook installer from the exact R38 installer. R44 still
# uses this installer hash; the new version accepts only frozen legacy, the exact
# old audited K1 hook, or the exact new hook.
python3 - "$R38ROOT/usr/local/bin/r36os-k1-install-hook" "$WORK/update/payload/root/usr/local/bin/r36os-k1-install-hook" "$OLD_HOOK_SHA" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
oldsha=sys.argv[3]
needle="LEGACY_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'\n"
if s.count(needle)!=1: raise SystemExit('legacy hash anchor mismatch')
s=s.replace(needle,needle+f"PREV_HOOK_SHA='{oldsha}'\n",1)
old='''CUR="$(sha "$BOOT")"
if [ "$CUR" = "$NEW_SHA" ]; then echo 'status=ALREADY_INSTALLED'; exit 0; fi
[ "$CUR" = "$LEGACY_SHA" ] || fail "active boot.ini is neither frozen legacy nor this exact hook: $CUR"
mkdir -p "$REC"
BACK="$REC/boot.ini.legacy.$LEGACY_SHA"
if [ ! -e "$BACK" ]; then cp -f "$BOOT" "$BACK"; sync; fi
[ "$(sha "$BACK")" = "$LEGACY_SHA" ] || fail 'recovery backup verification failed'
'''
new='''CUR="$(sha "$BOOT")"
if [ "$CUR" = "$NEW_SHA" ]; then echo 'status=ALREADY_INSTALLED'; exit 0; fi
mkdir -p "$REC"
BACK="$REC/boot.ini.legacy.$LEGACY_SHA"
if [ "$CUR" = "$LEGACY_SHA" ]; then
  if [ ! -e "$BACK" ]; then cp -f "$BOOT" "$BACK"; sync; fi
elif [ "$CUR" = "$PREV_HOOK_SHA" ]; then
  [ -f "$BACK" ] || fail 'previous audited hook is active but frozen legacy recovery copy is missing'
else
  fail "active boot.ini is neither frozen legacy, previous audited hook, nor this exact hook: $CUR"
fi
[ "$(sha "$BACK")" = "$LEGACY_SHA" ] || fail 'recovery backup verification failed'
'''
if s.count(old)!=1: raise SystemExit('installer migration anchor mismatch')
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
PY

# Recover the exact frozen legacy boot.ini from the old audited hook, then
# generate a probe-bearing hook. The probe is carried in kernel cmdline on every
# legacy fallthrough, so no U-Boot filesystem write is needed just for diagnosis.
python3 - "$R38ROOT/opt/r36os/kernel-next/hooked-boot.ini" "$R38ROOT/opt/r36os/kernel-next/hook.conf"   "$WORK/update/payload/root/opt/r36os/kernel-next/hooked-boot.ini"   "$WORK/update/payload/root/opt/r36os/kernel-next/hook.conf" <<'PY'
from pathlib import Path
import hashlib,sys,re
old=Path(sys.argv[1]); oldmeta=Path(sys.argv[2]); out=Path(sys.argv[3]); meta=Path(sys.argv[4])
CID='e551eb6598d6da7a8e8320e9'
LEGACY_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
OLD_HOOK_SHA='c5fddc8c36ece7ddc3b542a7baa96167a08587062327aa45bf8c2c39400587b1'
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(old)!=OLD_HOOK_SHA: raise SystemExit('old hook SHA mismatch')
m=dict(line.split('=',1) for line in oldmeta.read_text().splitlines() if '=' in line)
if m.get('hooked_boot_sha256')!=OLD_HOOK_SHA or m.get('candidate_id')!=CID:
    raise SystemExit('old hook metadata mismatch')
text=old.read_text()
start=text.index('# R36OS-K1-BOOT-ONCE-HOOK\n')
end=text.index('# R36OS-K1-BOOT-ONCE-HOOK-END\n',start)+len('# R36OS-K1-BOOT-ONCE-HOOK-END\n')
while end < len(text) and text[end]=='\n': end+=1
legacy=text[:start]+text[end:]
if hashlib.sha256(legacy.encode()).hexdigest()!=LEGACY_SHA:
    raise SystemExit('stripped hook did not recover frozen legacy boot.ini')
anchor='if env exists PanelNum '
if legacy.count(anchor)!=1: raise SystemExit('legacy hook anchor mismatch')
req=f'R36OS-KernelNext/boot-next.{CID}.once'
cons=f'R36OS-KernelNext/boot-next.{CID}.consumed'
hook=f'''# R36OS-K1-BOOT-ONCE-HOOK
# candidate_id={CID}
# R46 probe: encode exactly how far U-Boot gets into the one-shot handoff.
# Every failure still falls through to the untouched legacy load path below.
setenv r36os_k1_probe "hook_seen"
if load mmc 1:3 ${loadaddr} "{req}"
then
    setenv r36os_k1_probe "request_visible"
    setenv r36os_req_size ${filesize}
    if load mmc 1:3 ${loadaddr} "{cons}"
    then
        setenv r36os_k1_probe "already_consumed"
        echo "R36OS K1 attempt already consumed - booting legacy kernel"
    else
        if fatwrite mmc 1:3 ${loadaddr} "{cons}" ${r36os_req_size}
        then
            setenv r36os_k1_probe "consumed_written"
            if load mmc 1:3 ${loadaddr} "{cons}"
            then
                setenv r36os_k1_probe "consumed_readback"
                if test ${filesize} = ${r36os_req_size}
                then
                    setenv r36os_k1_probe "guard_verified"
                    if load mmc 1:3 ${loadaddr} "R36OS-KernelNext/K1/Image"
                    then
                        setenv r36os_k1_probe "image_loaded"
                        if load mmc 1:3 ${initrd_loadaddr} "R36OS-KernelNext/K1/uInitrd"
                        then
                            setenv r36os_k1_probe "initrd_loaded"
                            if load mmc 1:3 ${dtb_loadaddr} "R36OS-KernelNext/K1/rk3326-r36s-k1.dtb"
                            then
                                setenv r36os_k1_probe "payloads_loaded"
                                setenv r36os_legacy_bootargs "${bootargs}"
                                setenv bootargs "${bootargs} r36os.kernel_slot=next r36os.kernel_attempt=K1 r36os.kernel_candidate={CID} r36os.k1_probe=${r36os_k1_probe}"
                                booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}
                                setenv bootargs "${r36os_legacy_bootargs}"
                                setenv r36os_k1_probe "booti_return"
                            else
                                setenv r36os_k1_probe "dtb_load_failed"
                            fi
                        else
                            setenv r36os_k1_probe "initrd_load_failed"
                        fi
                    else
                        setenv r36os_k1_probe "image_load_failed"
                    fi
                else
                    setenv r36os_k1_probe "consumed_size_mismatch"
                fi
            else
                setenv r36os_k1_probe "consumed_readback_failed"
            fi
        else
            setenv r36os_k1_probe "consumed_write_failed"
        fi
    fi
else
    if load mmc 1:3 ${loadaddr} "R36OS-KernelNext/K1/K1.conf"
    then
        setenv r36os_k1_probe "candidate_visible_request_missing"
    else
        setenv r36os_k1_probe "r36update_unreadable"
    fi
fi
setenv bootargs "${bootargs} r36os.k1_probe=${r36os_k1_probe}"
# R36OS-K1-BOOT-ONCE-HOOK-END

'''
newtext=legacy.replace(anchor,hook+anchor,1)
out.write_text(newtext)
newsha=sha(out)
meta.write_text('\n'.join([
 'format=R36OS_K1_BOOT_HOOK_V2',
 f'candidate_id={CID}',
 f'legacy_boot_sha256={LEGACY_SHA}',
 f'hooked_boot_sha256={newsha}',
 'previous_hook_sha256='+OLD_HOOK_SHA,
 'update_partition=mmc_1_3',
 'candidate_dtb=rk3326-r36s-k1.dtb',
 f'request={req}',
 f'consumed={cons}',
 'legacy_fallthrough=yes',
 'probe_cmdline_key=r36os.k1_probe',
])+'\n')
PY

cp "$HERE/r36os-health-watchdog" "$WORK/update/payload/root/usr/local/bin/r36os-health-watchdog"
chmod 0755 "$WORK/update/payload/root/usr/local/bin/"r36os-*
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-health-watchdog"
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-k1-install-hook"

cat >"$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R46"
R36OS_PACKAGE_VERSION="0.5.46.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="K1 U-Boot handoff probe and update-health timing fix from Alpha 5R44"
R36OS_NOTES="Alpha 5R46 keeps K1 binaries unchanged, extends transactional update first-frame health to 120 seconds, makes ordinary kernel-slot status non-hashing, and instruments the one-shot U-Boot path through r36os.k1_probe."
EOF_RELEASE

cat >"$WORK/update/payload/root/opt/r36os/features/alpha5r46" <<EOF_FEATURE
R36OS Alpha 5R46
- Based directly on Alpha 5R44; Alpha 5R45 was withdrawn after rollback.
- Extends update boot-health first-frame timeout from 25 to 120 seconds.
- Ordinary kernel-slot status no longer re-hashes the full K1 payload.
- Full K1 payload verification remains mandatory before arm-once.
- Adds U-Boot handoff breadcrumbs via r36os.k1_probe in kernel cmdline.
- Safely migrates from the exact prior audited K1 boot hook.
- Does not replace K1 Image, uInitrd, DTB or modules.
EOF_FEATURE

python3 - "$CORE" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip(); entries[p]=h; order.append(p)
paths=[
'/usr/local/bin/r36os-health-watchdog',
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-k1-install-hook',
'/opt/r36os/kernel-next/hooked-boot.ini',
'/opt/r36os/kernel-next/hook.conf',
]
for p in paths:
    fp=root/p.lstrip('/')
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.46.0
hardware=R36XX-RK3326
base_version=0.5.44.0
channel=system-core
requires_reboot=true
description=Alpha 5R46 fixes slow-K1 update health timing and instruments the one-shot U-Boot handoff. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
boot_handoff_probe=r36os.k1_probe
update_health_timeout_seconds=120
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
opt/r36os/features/alpha5r46
opt/r36os/kernel-next/hook.conf
opt/r36os/kernel-next/hooked-boot.ini
usr/local/bin/r36os-health-watchdog
usr/local/bin/r36os-k1-install-hook
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
EOF_FILES
(cd "$WORK/update/payload/root" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

test ! -e "$WORK/update/payload/root/r36state"
! find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.46.0
base_version=0.5.44.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R46 audited release build PASS
base_version=0.5.44.0
version=0.5.46.0
requires_reboot=true
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r44_source_sha256=$EXPECTED_R44
r38_k1_source_sha256=$EXPECTED_R38
legacy_boot_sha256=$LEGACY_SHA
previous_hook_sha256=$OLD_HOOK_SHA
new_hook_sha256=$(sha256sum "$WORK/update/payload/root/opt/r36os/kernel-next/hooked-boot.ini" | awk '{print $1}')
update_health_timeout_seconds=120
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R46_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
