#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r56.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R56="$1"; OUT="$2"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r57'
NAME='00-R36OS-Alpha5R57-K1InputCompat-FromR56.r36upd'
EXPECTED_R56='f96d11043eb989f5ba22c5ea54d46e9ef4ac9d11f1f3f14d0101fb33306c5818'
CID='4c70486f70ba16acf7437403'
KREL='6.12.94-r36os-k1'
CC="${AARCH64_CC:-aarch64-linux-gnu-gcc}"
WORK="${RUNNER_TEMP:-/tmp}/r36os-r57-release"

rm -rf "$WORK" "$OUT"
mkdir -p   "$WORK/r56"   "$WORK/update/payload/root/etc/systemd/system/r36os.service.d"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha256sum "$R56" | awk '{print $1}')" = "$EXPECTED_R56" || { echo r56-sha-mismatch >&2; exit 10; }
tar -xzf "$R56" -C "$WORK/r56"
(cd "$WORK/r56" && sha256sum -c checksums.sha256 >/dev/null)

R56ROOT="$WORK/r56/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R56ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"
command -v "$CC" >/dev/null 2>&1 || { echo "missing-cross-compiler:$CC" >&2; exit 11; }

python3 "$HERE/transform_identity.py"   "$R56ROOT/usr/local/bin/r36os-kernel-next-prepare"   "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_identity.py"   "$R56ROOT/usr/local/bin/r36os-kernel-slot"   "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_identity.py"   "$R56ROOT/usr/local/bin/r36os-r36update-maint"   "$ROOT/usr/local/bin/r36os-r36update-maint"

"$CC" -O2 -static -s -Wl,--build-id=none   "$HERE/r36os-k1-input-compat.c"   -o "$ROOT/usr/local/bin/r36os-k1-input-compat"

cp "$HERE/r36os-session-k1-wrapper" "$ROOT/usr/local/bin/r36os-session-k1-wrapper"
cp "$HERE/99-k1-input-wrapper.conf" "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"

chmod 0755 "$ROOT/usr/local/bin/"*
chmod 0644 "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R57"
R36OS_PACKAGE_VERSION="0.5.57.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-30"
R36OS_COMPATIBILITY="K1 evdev capability bridge for split/renamed R36S controls"
R36OS_NOTES="Alpha 5R57 keeps K1 candidate 4c70486f70ba16acf7437403 unchanged. Physical R56 evidence proved Linux 6.12.94 reached K1 HEALTHY but the existing UI stopped at GAMEPAD NOT FOUND. R57 leaves the native UI and original r36os-session unchanged. On K1 only, a wrapper snapshots input topology, discovers evdev sources by capabilities, merges split axis/button devices when needed, translates standard Select/Start/Mode/L3/R3 codes to the legacy R36OS 704-708 codes, creates a stable R36OS K1 Gamepad through uinput, then launches the existing session. Legacy 4.4 immediately execs the original session. R56 R1 single-flight and battery-LED K1 guard are preserved."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r57" <<'EOF_FEATURE'
R36OS Alpha 5R57
- Physical R56 test proved K1 Linux 6.12.94 reaches HEALTHY/systemd userspace.
- Current blocker is input topology compatibility before the existing UI gets its first healthy frame.
- Exact shipped Panel-4 DTB describes:
  * adc-joystick axes: ABS_X, ABS_Y, ABS_RX, ABS_RY
  * gpio-keys face/shoulder/D-pad controls
  * standard Linux BTN_SELECT/BTN_START/BTN_MODE/BTN_THUMBL/BTN_THUMBR
- K1-only compatibility bridge:
  * discovers input sources by evdev capabilities, not device name
  * supports one combined source, split axis/key sources, or key-only degraded mode
  * creates a stable virtual device named R36OS K1 Gamepad
  * translates 314->704 Select, 315->705 Start, 317->706 L3, 318->707 R3, 316->708 FN
  * forwards D-pad/face/shoulder codes unchanged because the K1 DTB already matches R36OS
  * persists scan/results in R36STATE
- K1 wrapper snapshots hardware both before and after bridge creation.
- If K1 UI still fails, tty1 stays on an evidence screen instead of dropping to a white underscore.
- Legacy 4.4 immediately execs the original r36os-session.
- Original r36os-session binary and native r36os-alpha5 UI binary are not replaced.
- K1 candidate/Image/DTB/uInitrd/modules/U-Boot hook are unchanged.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r57"

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
'/usr/local/bin/r36os-k1-input-compat',
'/usr/local/bin/r36os-session-k1-wrapper',
'/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf',
]:
    fp=root/p.lstrip('/')
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.57.0
hardware=R36XX-RK3326
base_version=0.5.56.0
channel=system-core
requires_reboot=true
description=Alpha 5R57 adds a K1-only evdev capability/uinput compatibility bridge while preserving the existing UI and legacy session.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
candidate_id_change=no
native_ui_change=no
original_session_change=no
k1_input_compat=yes
k1_key_translation=yes
legacy_direct_exec=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf
opt/r36os/features/alpha5r57
usr/local/bin/r36os-k1-input-compat
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-maint
usr/local/bin/r36os-session-k1-wrapper
EOF_FILES
(cd "$ROOT" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

# Safety/audit.
test ! -e "$ROOT/r36state"
test ! -e "$ROOT/usr/local/bin/r36os-session"
test ! -e "$ROOT/usr/local/bin/r36os-alpha5"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/(hooked-boot.ini|hook.conf|K1/)'
! find "$ROOT" -type l | grep -q .
bash -n "$ROOT/usr/local/bin/r36os-session-k1-wrapper"
for p in "$ROOT"/usr/local/bin/r36os-kernel-next-prepare "$ROOT"/usr/local/bin/r36os-kernel-slot "$ROOT"/usr/local/bin/r36os-r36update-maint; do bash -n "$p"; done
python3 -m py_compile "$HERE/"*.py

file "$ROOT/usr/local/bin/r36os-k1-input-compat" | grep -Eq 'ARM aarch64|ARM64'
file "$ROOT/usr/local/bin/r36os-k1-input-compat" | grep -Fq 'statically linked'
grep -Fq 'R36OS K1 Gamepad' "$HERE/r36os-k1-input-compat.c"
grep -Fq 'map_key_code' "$HERE/r36os-k1-input-compat.c"
grep -Fq 'BTN_SELECT)return 704' "$HERE/r36os-k1-input-compat.c"
grep -Fq 'BTN_START)return 705' "$HERE/r36os-k1-input-compat.c"
grep -Fq 'BTN_MODE)return 708' "$HERE/r36os-k1-input-compat.c"
grep -Fq 'CMDLINE_FILE=' "$ROOT/usr/local/bin/r36os-session-k1-wrapper"
grep -Fq 'exec "$SESSION_BIN" "$@"' "$ROOT/usr/local/bin/r36os-session-k1-wrapper"
grep -Fxq 'ExecStart=/usr/local/bin/r36os-session-k1-wrapper' "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"
! grep -Eq 'Requires=|Bind(ReadOnly)?Paths=' "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"

grep -Fq '0.5.57.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq '0.5.57.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq '0.5.57.0' "$ROOT/usr/local/bin/r36os-r36update-maint"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-30 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.57.0
base_version=0.5.56.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R57 audited release build PASS
base_version=0.5.56.0
version=0.5.57.0
candidate_id=$CID
kernel_release=$KREL
r56_source_sha256=$EXPECTED_R56
k1_binary_change=no
candidate_id_change=no
native_ui_change=no
original_session_change=no
k1_input_compat=yes
k1_key_translation=yes
legacy_direct_exec=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R57_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
