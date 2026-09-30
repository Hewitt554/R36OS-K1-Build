#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r57.r36upd> <out-dir>" >&2; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
R57="$1"; OUT="$2"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r58'
NAME='00-R36OS-Alpha5R58-DirectK1SplitInputUI-FromR57.r36upd'
EXPECTED_R57='f059968b6f73acf52fe61527273fa74e34f4781ad96465ba9153b1d47d2460ee'
BASE_SOURCE_SHA='25e2de1b49b31033176e45f9106d4509d715c31371ac2dee1b95e6edbb6c71bd'
BASE_UI_SHA='173ee8f602cc08a76711bc90b24f382c6f47d46de5c90049d21b92caad95a7b3'
PATCHED_SOURCE_SHA='c88a4c29dcd4760f8e3edb48c6a313528abcee6dfabb02bb67f39cc9520e3687'
PATCHED_UI_SHA='7ff47b7c2ef16f4f5b83d1ac6215541c7ac8d350334c59ff8450a7962edc4f5a'
CID='4c70486f70ba16acf7437403'
KREL='6.12.94-r36os-k1'
CC="${CLANG:-clang}"
WORK="${RUNNER_TEMP:-/tmp}/r36os-r58-release"

rm -rf "$WORK" "$OUT"
mkdir -p   "$WORK/r57"   "$WORK/src"   "$WORK/update/payload/root/etc/systemd/system/r36os.service.d"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha256sum "$R57" | awk '{print $1}')" = "$EXPECTED_R57" || { echo r57-sha-mismatch >&2; exit 10; }
tar -xzf "$R57" -C "$WORK/r57"
(cd "$WORK/r57" && sha256sum -c checksums.sha256 >/dev/null)

R57ROOT="$WORK/r57/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R57ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"
command -v "$CC" >/dev/null 2>&1 || { echo "missing-clang:$CC" >&2; exit 11; }

# Recover the exact source which deterministically produces the current R57 UI.
# Keep it in fixed-size text chunks so GitHub transport cannot silently truncate
# the preserved source blob.
cat "$HERE/source/r36os_alpha5.c.gz.b64.part00"     "$HERE/source/r36os_alpha5.c.gz.b64.part01"     "$HERE/source/r36os_alpha5.c.gz.b64.part02"     "$HERE/source/r36os_alpha5.c.gz.b64.part03"     "$HERE/source/r36os_alpha5.c.gz.b64.part04"   | base64 -d >"$WORK/src/base.c.gz"
gzip -dc "$WORK/src/base.c.gz" >"$WORK/src/base.c"
ACTUAL_BASE_SOURCE_SHA="$(sha256sum "$WORK/src/base.c" | awk '{print $1}')"
echo "R58_DIAG base_source_sha=$ACTUAL_BASE_SOURCE_SHA expected=$BASE_SOURCE_SHA"
test "$ACTUAL_BASE_SOURCE_SHA" = "$BASE_SOURCE_SHA"

"$CC" --target=aarch64-linux-gnu -nostdlib -static -fuse-ld=lld -O2   -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables   -Wl,-e,_start "$WORK/src/base.c" -o "$WORK/src/base-ui"
chmod 0755 "$WORK/src/base-ui"
ACTUAL_BASE_UI_SHA="$(sha256sum "$WORK/src/base-ui" | awk '{print $1}')"
echo "R58_DIAG base_ui_sha=$ACTUAL_BASE_UI_SHA expected=$BASE_UI_SHA"
test "$ACTUAL_BASE_UI_SHA" = "$BASE_UI_SHA"

python3 "$HERE/transform_ui.py" "$WORK/src/base.c" "$WORK/src/r58.c"
ACTUAL_PATCHED_SOURCE_SHA="$(sha256sum "$WORK/src/r58.c" | awk '{print $1}')"
echo "R58_DIAG patched_source_sha=$ACTUAL_PATCHED_SOURCE_SHA expected=$PATCHED_SOURCE_SHA"
test "$ACTUAL_PATCHED_SOURCE_SHA" = "$PATCHED_SOURCE_SHA"

"$CC" --target=aarch64-linux-gnu -nostdlib -static -fuse-ld=lld -O2   -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables   -Wl,-e,_start "$WORK/src/r58.c" -o "$ROOT/usr/local/bin/r36os-alpha5"
chmod 0755 "$ROOT/usr/local/bin/r36os-alpha5"
ACTUAL_PATCHED_UI_SHA="$(sha256sum "$ROOT/usr/local/bin/r36os-alpha5" | awk '{print $1}')"
echo "R58_DIAG patched_ui_sha=$ACTUAL_PATCHED_UI_SHA expected=$PATCHED_UI_SHA"
test "$ACTUAL_PATCHED_UI_SHA" = "$PATCHED_UI_SHA"

# Advance release-gated K1 tooling without changing the K1 candidate.
python3 "$HERE/transform_identity.py"   "$R57ROOT/usr/local/bin/r36os-kernel-next-prepare"   "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_identity.py"   "$R57ROOT/usr/local/bin/r36os-kernel-slot"   "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_identity.py"   "$R57ROOT/usr/local/bin/r36os-r36update-maint"   "$ROOT/usr/local/bin/r36os-r36update-maint"
chmod 0755 "$ROOT/usr/local/bin/r36os-kernel-next-prepare"   "$ROOT/usr/local/bin/r36os-kernel-slot"   "$ROOT/usr/local/bin/r36os-r36update-maint"

# R57's uinput bridge cannot operate because this K1 kernel has no /dev/uinput.
# Overwrite the same drop-in and restore the original native session directly.
cp "$HERE/99-k1-input-wrapper.conf"   "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"
chmod 0644 "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R58"
R36OS_PACKAGE_VERSION="0.5.58.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-30"
R36OS_COMPATIBILITY="Direct K1 split evdev support in exact current native UI"
R36OS_NOTES="Alpha 5R58 is based on physical R57 evidence. K1 Linux 6.12.94 exposes adc-joystick on event2 and gpio-keys on event3, while uinput is unavailable, so the R57 virtual-gamepad bridge cannot create R36OS K1 Gamepad. R58 rebuilds the exact current native UI source and preserves the legacy GO-Super/Gamepad path first. Only if that path fails, the UI accepts gpio-keys as the primary button device, opens adc-joystick separately for analogue events, translates standard BTN_SELECT/START/MODE/THUMBL/THUMBR to R36OS 704-708 codes, and excludes the axis fd from auxiliary handling. The R57 uinput wrapper drop-in is overwritten to launch the original r36os-session directly. K1 Image, DTB, uInitrd, modules and U-Boot hook remain unchanged."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r58" <<'EOF_FEATURE'
R36OS Alpha 5R58
- Physical R57 logs prove K1 input topology:
  * event2 = adc-joystick, EV_ABS, ABS mask 0x1b
  * event3 = gpio-keys, EV_KEY
  * no R36OS K1 Gamepad was created
  * regression check: uinput=WARN
  * K1 kernel/module inspection contains no uinput.ko and live /dev/uinput is absent
- Removes the active R57 uinput dependency by restoring direct r36os-session startup.
- Rebuilds the exact current native UI from verified R37 source lineage:
  * verified source SHA = 25e2de1b49b31033176e45f9106d4509d715c31371ac2dee1b95e6edbb6c71bd
  * unmodified rebuild SHA = 173ee8f602cc08a76711bc90b24f382c6f47d46de5c90049d21b92caad95a7b3
  * patched UI SHA = 7ff47b7c2ef16f4f5b83d1ac6215541c7ac8d350334c59ff8450a7962edc4f5a
- Legacy input path remains first and unchanged:
  GO-Super / Gamepad / gamepad / odroid
- K1 fallback input path:
  gpio-keys -> primary button fd
  adc-joystick -> separate analogue fd
- K1-only key translations:
  BTN_SELECT 314 -> 704
  BTN_START 315 -> 705
  BTN_THUMBL 317 -> 706
  BTN_THUMBR 318 -> 707
  BTN_MODE 316 -> 708
- Face buttons, D-pad and shoulders remain unchanged.
- Controller Test reads analogue events from the K1 adc-joystick fd.
- K1 candidate remains 4c70486f70ba16acf7437403.
- K1 Image/DTB/uInitrd/modules/U-Boot are unchanged.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r58"

python3 - "$CORE" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip(); entries[p]=h; order.append(p)
for p in [
'/usr/local/bin/r36os-alpha5',
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-r36update-maint',
'/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf',
]:
    fp=root/p.lstrip('/')
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.58.0
hardware=R36XX-RK3326
base_version=0.5.57.0
channel=system-core
requires_reboot=true
description=Alpha 5R58 adds direct K1 gpio-keys plus adc-joystick support to the exact current native UI and removes the active uinput bridge dependency.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
candidate_id_change=no
native_ui_change=yes
native_ui_source_lineage_verified=yes
direct_k1_split_input=yes
uinput_required=no
original_session_change=no
legacy_input_path_preserved=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf
opt/r36os/features/alpha5r58
usr/local/bin/r36os-alpha5
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-maint
EOF_FILES
(cd "$ROOT" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

# Package safety/audit.
test ! -e "$ROOT/usr/local/bin/r36os-session"
test ! -e "$ROOT/usr/local/bin/r36os-k1-input-compat"
test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/(hooked-boot.ini|hook.conf|K1/)'
! find "$ROOT" -type l | grep -q .

for p in "$ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-r36update-maint"; do bash -n "$p"; done
python3 -m py_compile "$HERE/"*.py

file "$ROOT/usr/local/bin/r36os-alpha5" | grep -Eq 'ARM aarch64|ARM64'
file "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'statically linked'
strings "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'K1 split input: gpio-keys event'
strings "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'GAMEPAD NOT FOUND'
strings "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'Primary gamepad event'

grep -Fq 'contains(name,"GO-Super")' "$WORK/src/r58.c"
grep -Fq 'contains(name,"gpio-keys")' "$WORK/src/r58.c"
grep -Fq 'contains(name,"adc-joystick")' "$WORK/src/r58.c"
grep -Fq 'if(code==314)return KEY_SELECT' "$WORK/src/r58.c"
grep -Fq 'if(code==315)return KEY_START' "$WORK/src/r58.c"
grep -Fq 'if(code==316)return KEY_FN' "$WORK/src/r58.c"
grep -Fq 'if(code==317)return KEY_L3' "$WORK/src/r58.c"
grep -Fq 'if(code==318)return KEY_R3' "$WORK/src/r58.c"
grep -Fq 'if(k1_axisfd>=0)' "$WORK/src/r58.c"

grep -Fxq 'ExecStart=/usr/local/bin/r36os-session' "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"
! grep -Fq 'r36os-session-k1-wrapper' "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf"

grep -Fq '0.5.58.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq '0.5.58.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq '0.5.58.0' "$ROOT/usr/local/bin/r36os-r36update-maint"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-30 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.58.0
base_version=0.5.57.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R58 audited release build PASS
base_version=0.5.57.0
version=0.5.58.0
candidate_id=$CID
kernel_release=$KREL
r57_source_sha256=$EXPECTED_R57
base_ui_source_sha256=$BASE_SOURCE_SHA
base_ui_binary_sha256=$BASE_UI_SHA
patched_ui_source_sha256=$PATCHED_SOURCE_SHA
patched_ui_binary_sha256=$PATCHED_UI_SHA
k1_binary_change=no
candidate_id_change=no
native_ui_change=yes
native_ui_source_lineage_verified=yes
direct_k1_split_input=yes
uinput_required=no
original_session_change=no
legacy_input_path_preserved=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R58_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
