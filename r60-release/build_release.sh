#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r59.r36upd> <out-dir>" >&2; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT_REPO="$(cd "$HERE/.." && pwd)"
R59="$1"
OUT="$2"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r48'
NAME='00-R36OS-Alpha5R60-K1WiFiGraphicsLab-FromR59.r36upd'
EXPECTED_R59='cfd4daa7185ec40fdb42bf7e62736e714f98d5fbd16e0a683085015beb48b624'
CID='9d7bd2334f315d98b482f850'
KREL='6.12.94-r36os-k1'
GRAPHICS_SHA='9830642ae3b67397d74358718cae260fc228f497b9ae9aacec0ec452ac695291'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r60-release"

fail(){ echo "R60_RELEASE_BUILD=FAIL $*" >&2; exit 1; }
sha(){ sha256sum "$1" | awk '{print $1}'; }

rm -rf "$WORK" "$OUT"
mkdir -p   "$WORK/base"   "$WORK/update/payload/root/etc/systemd/system/NetworkManager.service.d"   "$WORK/update/payload/root/etc/systemd/system"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha "$R59")" = "$EXPECTED_R59" || fail r59-sha
tar -xzf "$R59" -C "$WORK/base"
(cd "$WORK/base" && sha256sum -c checksums.sha256 >/dev/null)
test "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" = 0.5.59.0 || fail r59-version
test "$(awk -F= '$1=="candidate_id"{print $2}' "$WORK/base/manifest.conf")" = "$CID" || fail r59-candidate
test "$(awk -F= '$1=="kernel_release"{print $2}' "$WORK/base/manifest.conf")" = "$KREL" || fail r59-krel

BASEROOT="$WORK/base/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$BASEROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE" || fail r59-core-manifest

# CP02.3 Wi-Fi runtime binder and activation path.
cp "$ROOT_REPO/r60-cp02-wifi/r36os-k1-wifi-bind" "$ROOT/usr/local/bin/r36os-k1-wifi-bind"
cp "$ROOT_REPO/r60-cp02-wifi/r36os-k1-wifi-bind.service" "$ROOT/etc/systemd/system/r36os-k1-wifi-bind.service"
cp "$ROOT_REPO/r60-cp02-wifi/20-r36os-k1-wifi-bind.conf" "$ROOT/etc/systemd/system/NetworkManager.service.d/20-r36os-k1-wifi-bind.conf"
chmod 0755 "$ROOT/usr/local/bin/r36os-k1-wifi-bind"
chmod 0644 "$ROOT/etc/systemd/system/r36os-k1-wifi-bind.service"   "$ROOT/etc/systemd/system/NetworkManager.service.d/20-r36os-k1-wifi-bind.conf"

# CP03 exact Graphics Lab payload.
cat "$ROOT_REPO"/r60-cp03-graphics/payload/r36os-graphics-test-session.b64.part{00,01,02,03}   | base64 -d >"$ROOT/usr/local/bin/r36os-graphics-test-session"
chmod 0755 "$ROOT/usr/local/bin/r36os-graphics-test-session"
test "$(sha "$ROOT/usr/local/bin/r36os-graphics-test-session")" = "$GRAPHICS_SHA" || fail graphics-sha
bash -n "$ROOT/usr/local/bin/r36os-graphics-test-session" || fail graphics-syntax

# Advance only the three R59 release-gated safety helpers.
for f in r36os-kernel-next-prepare r36os-kernel-slot r36os-r36update-maint; do
  python3 "$HERE/transform_identity.py"     "$BASEROOT/usr/local/bin/$f"     "$ROOT/usr/local/bin/$f"
  chmod 0755 "$ROOT/usr/local/bin/$f"
  bash -n "$ROOT/usr/local/bin/$f"
done

cat >"$ROOT/etc/r36os-release" <<'EOF_RELEASE'
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R60"
R36OS_PACKAGE_VERSION="0.5.60.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-10-01"
R36OS_COMPATIBILITY="K1 RTL8188EU runtime bind + K1 Graphics Lab no-input external session"
R36OS_NOTES="Alpha 5R60 is a userspace-only corrective update over R59. K1 candidate 9d7bd2334f315d98b482f850, Linux Image, Panel-4 DTB, R54 uInitrd, module archive, boot hook, legacy 4.4 kernel and R58 split-input UI are unchanged. CP02.3 explicitly loads/binds the validated rtl8xxxu stack for USB 0bda:0179 before NetworkManager, with an ordered direct insmod fallback and privacy-safe status on R36STATE. CP03 lets the autonomous Graphics Lab use a K1 no-input external-session path because the legacy game-input supervisor requires a single GO-Super gamepad plus uinput; legacy/non-K1 Graphics Lab behavior remains unchanged."
EOF_RELEASE
chmod 0644 "$ROOT/etc/r36os-release"

cat >"$ROOT/opt/r36os/features/alpha5r60" <<'EOF_FEATURE'
R36OS Alpha 5R60

CP02.3 — K1 Wi-Fi runtime bind
- Exact target USB device: Realtek 0bda:0179.
- Normal modprobe path remains preferred.
- R36STATE-backed /usr module-root lookup is supported.
- Ordered direct fallback:
  rfkill -> libarc4 -> cfg80211 -> mac80211 -> rtl8xxxu.
- Verifies firmware, module metadata, driver binding and wireless netdev.
- Runs before NetworkManager through a plain systemd drop-in.
- Legacy/non-K1 kernel path is a strict no-op.
- No SSID, MAC, password, PSK or profile data is logged.
- No Wi-Fi reconnect action reboots R36OS.
- Privacy-safe result is mirrored to:
  /r36state/logs/kernel-next/K1-WIFI-BIND.conf

CP03 — K1 Graphics Lab
- Physical R59 evidence proved Panfrost and /dev/dri exist.
- Exact failure was the old game-input supervisor:
  physical_gamepad_fd=-1
  FATAL gamepad not found
  input_supervisor ready=no
- The autonomous Graphics Lab does not require controller forwarding.
- Exact K1 uses a no-input external-session path.
- Legacy/non-K1 still requires the original r36_external_begin path.
- Kernel Oops detection, D-state guard and 42-second timeout remain.

Unchanged:
- K1 candidate 9d7bd2334f315d98b482f850.
- Linux 6.12.94-r36os-k1 Image/modules.
- Panel-4 DTB.
- R54 /opt/r36i uInitrd.
- Boot Next Once safety/fallback.
- Legacy Linux 4.4.
- R58 split-input R36OS UI.
EOF_FEATURE
chmod 0644 "$ROOT/opt/r36os/features/alpha5r60"

# Advance the cumulative core-integrity manifest from the exact R59 manifest.
python3 - "$CORE" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib, sys

base=Path(sys.argv[1])
root=Path(sys.argv[2])
out=Path(sys.argv[3])
entries={}
order=[]
for line in base.read_text().splitlines():
    if not line.strip():
        continue
    h,p=line.split(None,1)
    p=p.strip()
    entries[p]=h
    order.append(p)

changed=[
    '/usr/local/bin/r36os-kernel-next-prepare',
    '/usr/local/bin/r36os-kernel-slot',
    '/usr/local/bin/r36os-r36update-maint',
    '/usr/local/bin/r36os-k1-wifi-bind',
    '/etc/systemd/system/r36os-k1-wifi-bind.service',
    '/etc/systemd/system/NetworkManager.service.d/20-r36os-k1-wifi-bind.conf',
    '/usr/local/bin/r36os-graphics-test-session',
]
for p in changed:
    fp=root/p.lstrip('/')
    if not fp.is_file():
        raise SystemExit('missing changed core file: '+p)
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order:
        order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.60.0
hardware=R36XX-RK3326
base_version=0.5.59.0
channel=system-core
requires_reboot=true
description=Alpha 5R60 fixes K1 RTL8188EU runtime binding and lets the automated Graphics Lab run without the legacy uinput game supervisor.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
candidate_id_change=no
k1_image_change=no
k1_dtb_change=no
k1_uinitrd_change=no
module_payload_change=no
legacy_kernel_change=no
native_ui_change=no
wifi_runtime_bind_fix=yes
wifi_driver=rtl8xxxu
wifi_usb_id=0bda:0179
wifi_direct_module_fallback=yes
wifi_networkmanager_activation=yes
graphics_lab_change=yes
graphics_lab_k1_noinput=yes
legacy_graphics_behavior_preserved=yes
r1_singleflight_preserved=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/systemd/system/NetworkManager.service.d/20-r36os-k1-wifi-bind.conf
etc/systemd/system/r36os-k1-wifi-bind.service
opt/r36os/features/alpha5r60
usr/local/bin/r36os-graphics-test-session
usr/local/bin/r36os-k1-wifi-bind
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-maint
EOF_FILES
(cd "$ROOT" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt" || fail payload-file-set

# Scope and safety audit.
test ! -e "$ROOT/boot" || fail boot-payload
test ! -e "$ROOT/lib/modules" || fail lib-modules-payload
test ! -e "$ROOT/usr/lib/modules" || fail usr-lib-modules-payload
test ! -e "$ROOT/opt/r36os/kernel-next/K1" || fail k1-binary-payload
test ! -e "$ROOT/opt/r36os/kernel-next/hook.conf" || fail hook-conf-payload
test ! -e "$ROOT/opt/r36os/kernel-next/hooked-boot.ini" || fail hooked-boot-payload
test ! -e "$ROOT/usr/local/bin/r36os-alpha5" || fail ui-binary-payload
test "$(find "$ROOT" -type l -print -quit)" = "" || fail symlink-payload

dash -n "$ROOT/usr/local/bin/r36os-k1-wifi-bind"
bash -n "$ROOT/usr/local/bin/r36os-graphics-test-session"
for f in r36os-kernel-next-prepare r36os-kernel-slot r36os-r36update-maint; do
  bash -n "$ROOT/usr/local/bin/$f"
  grep -Fq '0.5.60.0' "$ROOT/usr/local/bin/$f" || fail "$f-version"
  ! grep -Fq '0.5.59.0' "$ROOT/usr/local/bin/$f" || fail "$f-stale-version"
done

grep -Fq 'ConditionKernelCommandLine=r36os.kernel_attempt=K1' "$ROOT/etc/systemd/system/r36os-k1-wifi-bind.service"
grep -Fxq 'Wants=r36os-k1-wifi-bind.service' "$ROOT/etc/systemd/system/NetworkManager.service.d/20-r36os-k1-wifi-bind.conf"
grep -Fxq 'After=r36os-k1-wifi-bind.service' "$ROOT/etc/systemd/system/NetworkManager.service.d/20-r36os-k1-wifi-bind.conf"
grep -Fq 'for m in rfkill libarc4 cfg80211 mac80211 rtl8xxxu; do' "$ROOT/usr/local/bin/r36os-k1-wifi-bind"
grep -Fq 'insmod "$path"' "$ROOT/usr/local/bin/r36os-k1-wifi-bind"
! grep -Eqi 'ssid|psk|password|802-11-wireless\.ssid' "$ROOT/usr/local/bin/r36os-k1-wifi-bind"
! grep -Eqi 'reboot|shutdown|systemctl restart.*NetworkManager|systemctl restart.*r36os' "$ROOT/usr/local/bin/r36os-k1-wifi-bind"

grep -Fq 'r36_graphics_external_begin_k1_noinput(){' "$ROOT/usr/local/bin/r36os-graphics-test-session"
grep -Fq 'ready=SKIPPED_K1_GRAPHICS_NO_UINPUT' "$ROOT/usr/local/bin/r36os-graphics-test-session"
grep -Fq 'r36_external_begin "$LOG" "graphics-lab-$TS"' "$ROOT/usr/local/bin/r36os-graphics-test-session"
test "$(grep -Fc 'r36_external_begin "$LOG" "graphics-lab-$TS"' "$ROOT/usr/local/bin/r36os-graphics-test-session")" -eq 1
grep -Fq 'KERNEL_DRIVER_FAULT' "$ROOT/usr/local/bin/r36os-graphics-test-session"
grep -Fq 'd_state_graphics_process=1' "$ROOT/usr/local/bin/r36os-graphics-test-session"

# Verify the cumulative manifest contains exact changed-file hashes.
python3 - "$ROOT/etc/r36os-core-manifest.sha256" "$ROOT" <<'PY'
from pathlib import Path
import hashlib,sys
manifest=Path(sys.argv[1]).read_text().splitlines()
root=Path(sys.argv[2])
entries={}
for line in manifest:
    if line.strip():
        h,p=line.split(None,1)
        entries[p.strip()]=h
changed=[
    '/usr/local/bin/r36os-kernel-next-prepare',
    '/usr/local/bin/r36os-kernel-slot',
    '/usr/local/bin/r36os-r36update-maint',
    '/usr/local/bin/r36os-k1-wifi-bind',
    '/etc/systemd/system/r36os-k1-wifi-bind.service',
    '/etc/systemd/system/NetworkManager.service.d/20-r36os-k1-wifi-bind.conf',
    '/usr/local/bin/r36os-graphics-test-session',
]
for p in changed:
    actual=hashlib.sha256((root/p.lstrip('/')).read_bytes()).hexdigest()
    if entries.get(p) != actual:
        raise SystemExit(f'core manifest mismatch {p}: {entries.get(p)} != {actual}')
print('R60_CORE_MANIFEST=PASS')
PY

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-10-01 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha "$OUT/$NAME")"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.60.0
base_version=0.5.59.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R60 audited integration build PASS
base_version=0.5.59.0
version=0.5.60.0
candidate_id=$CID
kernel_release=$KREL
r59_source_sha256=$EXPECTED_R59
k1_binary_change=no
candidate_id_change=no
k1_image_change=no
k1_dtb_change=no
k1_uinitrd_change=no
module_payload_change=no
legacy_kernel_change=no
native_ui_change=no
wifi_runtime_bind_fix=yes
wifi_direct_module_fallback=yes
wifi_networkmanager_activation=yes
wifi_status_persistent_conf=yes
graphics_lab_change=yes
graphics_lab_k1_noinput=yes
graphics_payload_sha256=$GRAPHICS_SHA
legacy_graphics_behavior_preserved=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R60_RELEASE_BUILD=PASS candidate_id=$CID size=$SIZE sha256=$SHA"
