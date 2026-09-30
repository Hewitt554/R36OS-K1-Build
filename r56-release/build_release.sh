#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r55.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R55="$1"; OUT="$2"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r56'
NAME='00-R36OS-Alpha5R56-K1HardwareSnapshotR1SingleFlight-FromR55.r36upd'
EXPECTED_R55='09812b0f7a9e78f73fff42a6a1aafcacf16dbaebe0aa4e44d0a9d1f3b982ffad'
CID='4c70486f70ba16acf7437403'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r56-release"

rm -rf "$WORK" "$OUT"
mkdir -p   "$WORK/r55"   "$WORK/update/payload/root/etc/systemd/system/r36os.service.d"   "$WORK/update/payload/root/etc/systemd/system/batt_led.service.d"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha256sum "$R55" | awk '{print $1}')" = "$EXPECTED_R55" || { echo r55-sha-mismatch >&2; exit 10; }
tar -xzf "$R55" -C "$WORK/r55"
(cd "$WORK/r55" && sha256sum -c checksums.sha256 >/dev/null)

R55ROOT="$WORK/r55/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R55ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

python3 "$HERE/transform_prepare.py"   "$R55ROOT/usr/local/bin/r36os-kernel-next-prepare"   "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_identity.py"   "$R55ROOT/usr/local/bin/r36os-kernel-slot"   "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_identity.py"   "$R55ROOT/usr/local/bin/r36os-r36update-maint"   "$ROOT/usr/local/bin/r36os-r36update-maint"

cp "$HERE/r36os-k1-hardware-snapshot" "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot"
cp "$HERE/98-k1-hardware-snapshot.conf" "$ROOT/etc/systemd/system/r36os.service.d/98-k1-hardware-snapshot.conf"
cp "$HERE/90-r36os-k1-skip.conf" "$ROOT/etc/systemd/system/batt_led.service.d/90-r36os-k1-skip.conf"

chmod 0755 "$ROOT/usr/local/bin/"*
chmod 0644   "$ROOT/etc/systemd/system/r36os.service.d/98-k1-hardware-snapshot.conf"   "$ROOT/etc/systemd/system/batt_led.service.d/90-r36os-k1-skip.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R56"
R36OS_PACKAGE_VERSION="0.5.56.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-30"
R36OS_COMPATIBILITY="K1 hardware discovery snapshot plus idempotent Boot Next Once"
R36OS_NOTES="Alpha 5R56 keeps K1 candidate 4c70486f70ba16acf7437403 unchanged. It makes Boot Next Once single-flight/idempotent so duplicate buffered R1 presses cannot prepare or arm twice. On K1 only, it persists input, power-supply, LED, driver and relevant dmesg evidence before the native UI starts. The legacy batt_led.service is skipped only when r36os.kernel_slot=next to stop its Linux 6.12 restart loop. No K1 Image, DTB, uInitrd, modules or U-Boot hook change is included; the native UI/controller binary is also unchanged pending real K1 input evidence."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r56" <<'EOF_FEATURE'
R36OS Alpha 5R56
- Fixes buffered/duplicate R1 Boot Next Once actions:
  * atomic /run single-flight lock
  * duplicate concurrent request returns without running preparation again
  * a buffered request delivered after the first arm sees armed=yes and becomes a no-op
  * /run lock disappears automatically on reboot
- K1 hardware snapshot runs before the native UI and persists to:
  /r36state/logs/kernel-next/K1-HARDWARE-4c70486f70ba16acf7437403.conf
- Snapshot records:
  * /proc/bus/input/devices
  * each event device name/path/capability bitsets
  * /dev/input listing
  * power-supply interfaces/uevents
  * LED interfaces
  * likely input-driver bindings
  * loaded modules
  * journald unit/path evidence
  * batt_led service status
  * input/power-related dmesg
- batt_led.service is skipped only for K1 because the legacy helper restart-loops under 6.12.
- Legacy 4.4 battery LED behavior is unchanged.
- Native controller/UI binary is intentionally unchanged until the real K1 event capabilities are captured.
- K1 candidate, Image, DTB, uInitrd, modules and U-Boot hook are unchanged from R55.
EOF_FEATURE

python3 - "$CORE" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip(); entries[p]=h; order.append(p)
for p in [
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-r36update-maint',
'/usr/local/bin/r36os-k1-hardware-snapshot',
'/etc/systemd/system/r36os.service.d/98-k1-hardware-snapshot.conf',
'/etc/systemd/system/batt_led.service.d/90-r36os-k1-skip.conf',
]:
    fp=root/p.lstrip('/')
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.56.0
hardware=R36XX-RK3326
base_version=0.5.55.0
channel=system-core
requires_reboot=true
description=Alpha 5R56 makes Boot Next Once idempotent and captures exact K1 input/power interfaces before UI startup.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
candidate_id_change=no
r1_singleflight=yes
k1_hardware_snapshot=yes
k1_batt_led_legacy_skip=yes
native_ui_change=no
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

# Safety/audit.
test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/(hooked-boot.ini|hook.conf|K1/)'
! find "$ROOT" -type l | grep -q .
for p in "$ROOT"/usr/local/bin/*; do bash -n "$p"; done
python3 -m py_compile "$HERE/"*.py

grep -Fq 'LOCKDIR=/run/r36os-k1-prepare.lock' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq 'duplicate-request-ignored-in-progress' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq 'already-armed-duplicate-ignored' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq '0.5.56.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq '0.5.56.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq '0.5.56.0' "$ROOT/usr/local/bin/r36os-r36update-maint"
grep -Fxq 'ConditionKernelCommandLine=!r36os.kernel_slot=next' "$ROOT/etc/systemd/system/batt_led.service.d/90-r36os-k1-skip.conf"
grep -Fxq 'ExecStartPre=-/usr/local/bin/r36os-k1-hardware-snapshot' "$ROOT/etc/systemd/system/r36os.service.d/98-k1-hardware-snapshot.conf"
grep -Fq 'format=R36OS_K1_HARDWARE_SNAPSHOT_V1' "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-30 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.56.0
base_version=0.5.55.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R56 audited release build PASS
base_version=0.5.55.0
version=0.5.56.0
candidate_id=$CID
kernel_release=$KREL
r55_source_sha256=$EXPECTED_R55
k1_binary_change=no
candidate_id_change=no
r1_singleflight=yes
k1_hardware_snapshot=yes
k1_batt_led_legacy_skip=yes
native_ui_change=no
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R56_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
