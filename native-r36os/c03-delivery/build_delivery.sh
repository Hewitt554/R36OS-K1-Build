#!/bin/bash
set -euo pipefail

[ "$#" -eq 4 ] || {
  echo "usage: build_delivery.sh <exact-r60.r36upd> <c03-bundle-dir> <exact-r58-source.c> <out-dir>" >&2
  exit 2
}

HERE="$(cd "$(dirname "$0")" && pwd)"
R60="$1"
C03SRC="$2"
R58SRC="$3"
OUT="$(readlink -m "$4")"
WORK="${RUNNER_TEMP:-/tmp}/r36os-c03dev-delivery"
ROOT="$WORK/update/payload/root"
NAME='00-R36OS-Alpha5R60-C03Dev1-FromR60.r36upd'
R60_SHA='0f17ef90423984f163a5a25a306c9bee346c24a958c921b03a1bda3ba01c05c2'
R58_SOURCE_SHA='657803bb2b4f60414d85775f86dae8d01d3cb46d631cfe2309e682dffd93289a'
C03_NID='8f8eaa3bae6ad4352b4e01ef'
C03_ROOT_SHA='08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4'
C03_UINITRD_SHA='be567cd71bc95c35cfdaf7100ee0846517df5cd78538e4f3da6157a7fa61d694'
C03_PREP_SHA='a214a3fb799103cb7286b9e7b3b9fca1c93cbbccb057444aa0cdadaa8dd1273c'
K1_CID='9d7bd2334f315d98b482f850'
KREL='6.12.94-r36os-k1'

sha(){ sha256sum "$1" | awk '{print $1}'; }
fail(){ echo "C03DEV_DELIVERY_BUILD=FAIL $*" >&2; exit 1; }

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/base" "$ROOT/usr/local/bin" "$ROOT/etc" "$ROOT/opt/r36os/native-next/C03" "$ROOT/opt/r36os/features" "$OUT"

test "$(sha "$R60")" = "$R60_SHA" || fail r60-sha
test "$(sha "$R58SRC")" = "$R58_SOURCE_SHA" || fail r58-source-sha
tar -xzf "$R60" -C "$WORK/base"
(cd "$WORK/base" && sha256sum -c checksums.sha256 >/dev/null)
test "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" = 0.5.60.0 || fail r60-version
test "$(awk -F= '$1=="base_version"{print $2}' "$WORK/base/manifest.conf")" = 0.5.59.0 || fail r60-base-version

BASE="$WORK/base/payload/root"
test -s "$BASE/etc/r36os-core-manifest.sha256" || fail missing-r60-core-manifest
for f in r36os-kernel-next-prepare r36os-kernel-slot r36os-r36update-maint; do
  test -s "$BASE/usr/local/bin/$f" || fail "missing-r60-helper-$f"
  python3 "$HERE/transform_r60_dev.py" "$BASE/usr/local/bin/$f" "$ROOT/usr/local/bin/$f"
  chmod 0755 "$ROOT/usr/local/bin/$f"
  bash -n "$ROOT/usr/local/bin/$f"
done

# Rebuild the exact R58/R60 UI source with C03 developer controls.
python3 "$HERE/transform_ui_c03dev.py" "$R58SRC" "$WORK/r60-c03dev.c"
CC="${CC:-clang}"
for n in a b; do
  "$CC" --target=aarch64-linux-gnu -nostdlib -static -fuse-ld=lld -O2 \
    -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables \
    -Wl,-e,_start "$WORK/r60-c03dev.c" -o "$WORK/r36os-alpha5.$n"
done
cmp "$WORK/r36os-alpha5.a" "$WORK/r36os-alpha5.b" || fail ui-nondeterministic
cp "$WORK/r36os-alpha5.a" "$ROOT/usr/local/bin/r36os-alpha5"
chmod 0755 "$ROOT/usr/local/bin/r36os-alpha5"
file "$ROOT/usr/local/bin/r36os-alpha5" | grep -Eq 'ARM aarch64|ARM64' || fail ui-arch
file "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'statically linked' || fail ui-static
strings "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'Native C03 developer controls' || fail ui-native-menu
strings "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'Arm Native Boot Once' || fail ui-native-arm
strings "$ROOT/usr/local/bin/r36os-alpha5" | grep -Fq 'K1 split input: gpio-keys event' || fail ui-r58-input-regression

# Install the explicit control wrapper.
cp "$HERE/r36os-native-c03-control" "$ROOT/usr/local/bin/r36os-native-c03-control"
chmod 0755 "$ROOT/usr/local/bin/r36os-native-c03-control"
bash -n "$ROOT/usr/local/bin/r36os-native-c03-control"

# Copy the exact validated C03 bundle and change only its host-version gate.
test -d "$C03SRC" || fail c03-bundle-missing
cp -a "$C03SRC/." "$ROOT/opt/r36os/native-next/C03/"
C03="$ROOT/opt/r36os/native-next/C03"
(cd "$C03SRC" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail c03-source-manifest
test "$(sha "$C03/rootfs.tar.zst")" = "$C03_ROOT_SHA" || fail c03-rootfs-sha
test "$(sha "$C03/uInitrd")" = "$C03_UINITRD_SHA" || fail c03-uinitrd-sha
test "$(sha "$C03/r36os-native-c03-prepare")" = "$C03_PREP_SHA" || fail c03-prepare-preimage

python3 - "$C03/r36os-native-c03-prepare" "$C03/C03_READY.conf" <<'PY'
from pathlib import Path
import hashlib,sys
prep=Path(sys.argv[1]); ready=Path(sys.argv[2])
s=prep.read_text()
if s.count('EXPECTED_VERSION=0.5.60.0') != 1:
    raise SystemExit('C03 prepare expected-version anchor mismatch')
s=s.replace('EXPECTED_VERSION=0.5.60.0','EXPECTED_VERSION=0.5.60.1')
prep.write_text(s)
psha=hashlib.sha256(prep.read_bytes()).hexdigest()
lines=[]
seen=0
for line in ready.read_text().splitlines():
    if line.startswith('prepare_sha256='):
        line='prepare_sha256='+psha
        seen+=1
    lines.append(line)
if seen!=1:
    raise SystemExit('C03_READY prepare hash anchor mismatch')
ready.write_text('\n'.join(lines)+'\n')
print('C03DEV_PREPARE_SHA='+psha)
PY
chmod 0755 "$C03/r36os-native-c03-prepare"
bash -n "$C03/r36os-native-c03-prepare"

# Rebuild C03 bundle manifest after the one allowed delivery transform.
(
  cd "$C03"
  sha256sum rootfs.tar.zst rootfs-files.sha256 uInitrd hooked-boot.ini previous-hooked-boot.ini hook.conf C03_READY.conf r36os-native-c03-install-hook r36os-native-c03-prepare >MANIFEST.sha256
  sha256sum -c MANIFEST.sha256 >/dev/null
)
test "$(awk -F= '$1=="native_candidate"{print $2}' "$C03/C03_READY.conf")" = "$C03_NID" || fail c03-candidate
test "$(awk -F= '$1=="k1_candidate"{print $2}' "$C03/C03_READY.conf")" = "$K1_CID" || fail c03-k1-candidate
test "$(awk -F= '$1=="kernel_release"{print $2}' "$C03/C03_READY.conf")" = "$KREL" || fail c03-krel
test "$(awk -F= '$1=="rootfs_sha256"{print $2}' "$C03/C03_READY.conf")" = "$C03_ROOT_SHA" || fail c03-ready-root
grep -Fxq 'EXPECTED_VERSION=0.5.60.1' "$C03/r36os-native-c03-prepare" || fail c03-version-gate
! grep -Fq 'EXPECTED_VERSION=0.5.60.0' "$C03/r36os-native-c03-prepare" || fail c03-stale-version-gate

# Developer-only R60.1 identity. Public latest.conf is deliberately not produced.
cat >"$ROOT/etc/r36os-release" <<EOF
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R60 C03Dev1"
R36OS_PACKAGE_VERSION="0.5.60.1"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="developer"
R36OS_BUILD_DATE="2026-10-01"
R36OS_COMPATIBILITY="R60 + validated Native C03 developer delivery"
R36OS_NOTES="Private developer build. Installs the frozen C03 candidate and explicit Status/Stage Only/Arm Once/Disarm controls. It does not auto-stage, auto-arm or auto-boot native R36OS. Public update channel remains Alpha 5R60."
EOF

cat >"$ROOT/opt/r36os/features/native-c03-dev1" <<EOF
R36OS Alpha 5R60 C03Dev1

Private developer delivery for Native R36OS Chapter 3.

Diagnostics:
- R1 opens Native C03 developer controls.
- Status / refresh
- Stage native root only
- Arm Native Boot Once (second confirmation required)
- Disarm native request

No action is automatic.
Existing legacy 4.4 fallback remains unchanged.
Existing K1 Image, Panel-4 DTB and K1 modules remain unchanged.
Native candidate: $C03_NID
K1 candidate: $K1_CID
Kernel: $KREL
EOF

# Advance the R60 cumulative core manifest for changed/critical delivery files.
python3 - "$BASE/etc/r36os-core-manifest.sha256" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip()
    entries[p]=h; order.append(p)
changed=[
 '/usr/local/bin/r36os-alpha5',
 '/usr/local/bin/r36os-kernel-next-prepare',
 '/usr/local/bin/r36os-kernel-slot',
 '/usr/local/bin/r36os-r36update-maint',
 '/usr/local/bin/r36os-native-c03-control',
 '/opt/r36os/native-next/C03/MANIFEST.sha256',
 '/opt/r36os/native-next/C03/C03_READY.conf',
 '/opt/r36os/native-next/C03/r36os-native-c03-prepare',
 '/opt/r36os/native-next/C03/r36os-native-c03-install-hook',
]
for p in changed:
    fp=root/p.lstrip('/')
    if not fp.is_file():
        raise SystemExit('missing core delivery file '+p)
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF
format=R36UPD2
version=0.5.60.1
hardware=R36XX-RK3326
base_version=0.5.60.0
channel=developer
requires_reboot=true
description=Private Native C03 developer delivery; installs validated C03 bundle and explicit manual controls without auto-arming.
developer_only=yes
public_channel_change=no
native_candidate=$C03_NID
k1_candidate=$K1_CID
kernel_release=$KREL
auto_stage=no
auto_arm=no
auto_boot=no
legacy_kernel_change=no
k1_image_change=no
k1_dtb_change=no
k1_modules_change=no
EOF

# The normal R36UPD2 updater forbids payload symlinks and boot/module files.
test "$(find "$ROOT" -type l -print -quit)" = "" || fail payload-symlink
test ! -e "$ROOT/boot" || fail boot-payload
test ! -e "$ROOT/lib/modules" || fail lib-modules-payload
test ! -e "$ROOT/usr/lib/modules" || fail usr-lib-modules-payload
grep -Fq 'R36OS_PACKAGE_VERSION="0.5.60.1"' "$ROOT/etc/r36os-release"
for f in r36os-kernel-next-prepare r36os-kernel-slot r36os-r36update-maint; do
  grep -Fq '0.5.60.1' "$ROOT/usr/local/bin/$f" || fail "$f-new-version"
  ! grep -Fq '0.5.60.0' "$ROOT/usr/local/bin/$f" || fail "$f-stale-version"
done

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

(
 cd "$WORK/update"
 tar --sort=name --mtime='UTC 2026-10-01 00:00:00' --owner=0 --group=0 --numeric-owner \
   -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME"
)
PKG_SHA="$(sha "$OUT/$NAME")"
PKG_SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$PKG_SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/C03DEV_DELIVERY_REPORT.txt" <<EOF
format=R36OS_NATIVE_C03_DEV_DELIVERY_V1
status=PASS
version=0.5.60.1
base_version=0.5.60.0
package=$NAME
size_bytes=$PKG_SIZE
sha256=$PKG_SHA
native_candidate=$C03_NID
rootfs_sha256=$C03_ROOT_SHA
uinitrd_sha256=$C03_UINITRD_SHA
k1_candidate=$K1_CID
kernel_release=$KREL
auto_stage=no
auto_arm=no
auto_boot=no
public_channel_change=no
EOF

# Re-open final package.
rm -rf "$WORK/audit"; mkdir -p "$WORK/audit"
tar -xzf "$OUT/$NAME" -C "$WORK/audit"
(cd "$WORK/audit" && sha256sum -c checksums.sha256 >/dev/null)
test "$(awk -F= '$1=="version"{print $2}' "$WORK/audit/manifest.conf")" = 0.5.60.1
test "$(awk -F= '$1=="base_version"{print $2}' "$WORK/audit/manifest.conf")" = 0.5.60.0
test "$(awk -F= '$1=="auto_arm"{print $2}' "$WORK/audit/manifest.conf")" = no
test "$(awk -F= '$1=="auto_boot"{print $2}' "$WORK/audit/manifest.conf")" = no

echo "C03DEV_DELIVERY_BUILD=PASS package=$NAME size=$PKG_SIZE sha256=$PKG_SHA ui_sha256=$(sha "$ROOT/usr/local/bin/r36os-alpha5")"
