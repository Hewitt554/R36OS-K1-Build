#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 3 ] || { echo "usage: build_release.sh <exact-r52.r36upd> <exact-r38.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R52="$1"; R38="$2"; OUT="$3"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r53'
NAME='00-R36OS-Alpha5R53-K1SystemdHandoffHeader-FromR52.r36upd'
EXPECTED_R52='0ef468b19eddc77a3d8ccb8016238082c4fea23ef0d884135a7f48bd26baf0cb'
EXPECTED_R38='68db42212fc0e13a9bad777daf68f4634bb86f58aa2347a923dde8cd71db30c0'
EXPECTED_IMAGE='a7a388d5ca21b276bddcc0e3892b0c965b73d92f2c0238cb9c25a210dba7c97e'
EXPECTED_DTB='e2145905b1beb8d0f5b9dee6c5a21d31c29474be8762c893e81506fc40e627f4'
EXPECTED_OLD_UINITRD='6d44f435bd88b54e91af569fd6445db460b9ab80313062b8136796f27b888f6e'
OLD_CID='e551eb6598d6da7a8e8320e9'
ROOT_UUID='e139ce78-9841-40fe-8823-96a304a09859'
STATE_UUID='a25488c6-742d-4555-82d1-e28ffc848af3'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r53-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r52" "$WORK/r38" "$WORK/full-k1"   "$WORK/update/payload/root/etc/systemd/system/r36os.service.d"   "$WORK/update/payload/root/etc/systemd/system"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$WORK/update/payload/root/opt/r36os/kernel-next/K1"   "$WORK/update/payload/root/opt/r36os/kernel-next"   "$WORK/update/payload/root/opt" "$OUT"

check(){ local f="$1" want="$2"; local got; got="$(sha256sum "$f"|awk '{print $1}')"; [ "$got" = "$want" ] || { echo "sha mismatch: $f want=$want got=$got" >&2; exit 10; }; }
check "$R52" "$EXPECTED_R52"
check "$R38" "$EXPECTED_R38"

tar -xzf "$R52" -C "$WORK/r52"
tar -xzf "$R38" -C "$WORK/r38"
(cd "$WORK/r52" && sha256sum -c checksums.sha256 >/dev/null)
(cd "$WORK/r38" && sha256sum -c checksums.sha256 >/dev/null)

R52ROOT="$WORK/r52/payload/root"
R38ROOT="$WORK/r38/payload/root"
OLDK1="$R38ROOT/opt/r36os/kernel-next/K1"
ROOT="$WORK/update/payload/root"
CORE="$R52ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"
test -d "$OLDK1"
(cd "$OLDK1" && sha256sum -c MANIFEST.sha256 >/dev/null)
check "$OLDK1/Image" "$EXPECTED_IMAGE"
check "$OLDK1/rk3326-r36s-k1.dtb" "$EXPECTED_DTB"
check "$OLDK1/uInitrd" "$EXPECTED_OLD_UINITRD"
test "$(awk -F= '$1=="candidate_id"{print $2}' "$OLDK1/K1.conf")" = "$OLD_CID"

command -v clang >/dev/null
command -v ld.lld >/dev/null || command -v lld >/dev/null
clang --target=aarch64-linux-gnu -nostdlib -static -fuse-ld=lld -O2   -fno-builtin -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables   -Wl,-e,_start "$HERE/r36i.c" "$HERE/start_aarch64.S" -o "$WORK/r36i"
chmod 0755 "$WORK/r36i"
file "$WORK/r36i" | grep -q 'ARM aarch64'
readelf -h "$WORK/r36i" | grep -q 'AArch64'
! readelf -d "$WORK/r36i" 2>/dev/null | grep -q NEEDED
strings "$WORK/r36i" | grep -Fxq '/lib/systemd/systemd'
strings "$WORK/r36i" | grep -Fxq '/usr/lib/systemd/systemd'

python3 "$HERE/patch_uinitrd.py" "$OLDK1/uInitrd" "$WORK/uInitrd" | tee "$WORK/uinitrd-patch.log"
test "$(sha256sum "$WORK/uInitrd"|awk '{print $1}')" != "$EXPECTED_OLD_UINITRD"

cp -a "$OLDK1/." "$WORK/full-k1/"
cp "$WORK/uInitrd" "$WORK/full-k1/uInitrd"
KREL="$(awk -F= '$1=="kernel_release"{print $2}' "$WORK/full-k1/K1.conf")"
MODBASE="$(awk -F= '$1=="modules_archive_root"{print $2}' "$WORK/full-k1/K1.conf")"
test "$KREL" = '6.12.94-r36os-k1'
CID="$(cd "$WORK/full-k1"; { sha256sum Image; sha256sum uInitrd; sha256sum rk3326-r36s-k1.dtb; sha256sum modules.tar.xz; printf 'kernel_release=%s\n' "$KREL"; } | sha256sum | awk '{print substr($1,1,24)}')"
[[ "$CID" =~ ^[0-9a-f]{24}$ ]]
test "$CID" != "$OLD_CID"

python3 - "$WORK/full-k1/K1.conf" "$CID" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); cid=sys.argv[2]
lines=[]; seen=False
for line in p.read_text().splitlines():
    if line.startswith('candidate_id='):
        line='candidate_id='+cid; seen=True
    if not line.startswith('uinitrd_handoff='):
        lines.append(line)
    else:
        pass
if not seen: raise SystemExit('candidate_id missing')
lines.append('uinitrd_handoff=opt-r36i-systemd-probe')
lines.append('uinitrd_handoff_wrapper=/opt/r36i')
p.write_text('\n'.join(lines)+'\n')
PY
cat >>"$WORK/full-k1/BUILD_INFO.txt" <<EOF_INFO

R53 handoff update:
- candidate_id=$CID
- Linux Image unchanged SHA256 $EXPECTED_IMAGE
- Panel-4 DTB unchanged SHA256 $EXPECTED_DTB
- modules archive unchanged
- uInitrd changed only to hand off through /opt/r36i instead of requiring /sbin/init
- /opt/r36i probes standard systemd/init locations and is not used by legacy 4.4
EOF_INFO
(cd "$WORK/full-k1" && find . -maxdepth 1 -type f ! -name MANIFEST.sha256 -printf '%f\0' | LC_ALL=C sort -z | xargs -0 sha256sum >MANIFEST.sha256)
"$R38ROOT/usr/local/bin/r36os-k1-preflight" "$WORK/full-k1" >/dev/null

# Only K1 files that actually changed are included in the update overlay.
for f in uInitrd K1.conf BUILD_INFO.txt MANIFEST.sha256; do
  cp "$WORK/full-k1/$f" "$ROOT/opt/r36os/kernel-next/K1/$f"
  chmod 0644 "$ROOT/opt/r36os/kernel-next/K1/$f"
done
cp "$WORK/r36i" "$ROOT/opt/r36i"; chmod 0755 "$ROOT/opt/r36i"

# Advance release-gated K1 userspace helpers.
for f in r36os-kernel-next-prepare r36os-kernel-slot r36os-r36update-maint; do
  python3 "$HERE/transform_identity.py" "$R52ROOT/usr/local/bin/$f" "$ROOT/usr/local/bin/$f"
  chmod 0755 "$ROOT/usr/local/bin/$f"
done

python3 "$HERE/transform_hook_candidate.py"   "$R52ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$R52ROOT/opt/r36os/kernel-next/hook.conf"   "$CID"   "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$ROOT/opt/r36os/kernel-next/hook.conf"
chmod 0644 "$ROOT/opt/r36os/kernel-next/hooked-boot.ini" "$ROOT/opt/r36os/kernel-next/hook.conf"

python3 "$HERE/transform_installer.py"   "$R52ROOT/usr/local/bin/r36os-k1-install-hook"   "$R52ROOT/opt/r36os/kernel-next/hook.conf"   "$ROOT/usr/local/bin/r36os-k1-install-hook"
chmod 0755 "$ROOT/usr/local/bin/r36os-k1-install-hook"

# UI header label without modifying canonical host release metadata.
cp "$HERE/r36os-ui-kernel-label" "$ROOT/usr/local/bin/r36os-ui-kernel-label"
cp "$HERE/r36os-version" "$ROOT/usr/local/bin/r36os-version"
cp "$HERE/r36os-ui-kernel-label.service" "$ROOT/etc/systemd/system/r36os-ui-kernel-label.service"
cp "$HERE/99-ui-kernel-label.conf" "$ROOT/etc/systemd/system/r36os.service.d/99-ui-kernel-label.conf"
chmod 0755 "$ROOT/usr/local/bin/r36os-ui-kernel-label" "$ROOT/usr/local/bin/r36os-version"
chmod 0644 "$ROOT/etc/systemd/system/r36os-ui-kernel-label.service" "$ROOT/etc/systemd/system/r36os.service.d/99-ui-kernel-label.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R53"
R36OS_PACKAGE_VERSION="0.5.53.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="K1 Linux 6.12 userspace handoff via K1-only systemd probe; UI header shows LEGACY/K1"
R36OS_NOTES="Alpha 5R53 is based on physical R52 proof that Image, initramfs, Panel-4 DTB, root, R36STATE and modules all succeed. It changes only the K1 uInitrd handoff so /opt/r36i probes standard systemd PID-1 paths instead of requiring missing /sbin/init. Linux Image, DTB and modules remain unchanged. The UI gets a private read-only release view so the existing top header displays LEGACY or K1 while canonical system release metadata remains Alpha 5R53 / 0.5.53.0."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r53" <<EOF_FEATURE
R36OS Alpha 5R53
- Physical R52 result: K1 reached root-mounted, state-mounted and modules-bound.
- R52 failed only because the K1 initramfs hard-coded /newroot/sbin/init.
- New K1 candidate: $CID
- Linux Image unchanged.
- Panel-4 DTB unchanged.
- modules.tar.xz unchanged.
- uInitrd patched to validate and exec /opt/r36i after switch_root.
- /opt/r36i tries /lib/systemd/systemd, /usr/lib/systemd/systemd, /bin/systemd, /usr/bin/systemd, /usr/sbin/init, then /bin/init.
- /opt/r36i prints each handoff attempt on the K1 diagnostic console.
- Legacy 4.4 never uses /opt/r36i.
- R52 visible U-Boot trace and persistent breadcrumbs remain enabled for the new candidate.
- Existing UI header receives a UI-private R36OS_VERSION suffix: LEGACY on 4.4.189, K1 on 6.12.94-r36os-k1.
- The host /etc/r36os-release remains canonical; r36os-version strips any UI-only suffix inside the UI namespace.
EOF_FEATURE

python3 - "$CORE" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip(); entries[p]=h; order.append(p)
paths=[
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-r36update-maint',
'/usr/local/bin/r36os-k1-install-hook',
'/usr/local/bin/r36os-ui-kernel-label',
'/usr/local/bin/r36os-version',
'/etc/systemd/system/r36os-ui-kernel-label.service',
'/etc/systemd/system/r36os.service.d/99-ui-kernel-label.conf',
'/opt/r36i',
'/opt/r36os/kernel-next/hooked-boot.ini',
'/opt/r36os/kernel-next/hook.conf',
'/opt/r36os/kernel-next/K1/MANIFEST.sha256',
]
for p in paths:
    fp=root/p.lstrip('/')
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.53.0
hardware=R36XX-RK3326
base_version=0.5.52.0
channel=system-core
requires_reboot=true
description=Alpha 5R53 fixes the physically observed K1 initramfs /sbin/init handoff failure using a K1-only systemd probe wrapper and adds LEGACY/K1 to the existing UI version header.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=yes
k1_image_change=no
k1_dtb_change=no
k1_modules_change=no
k1_uinitrd_change=yes
legacy_default_boot=true
ui_kernel_track_header=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

# Package safety.
test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type l | grep -q .
for p in "$ROOT"/usr/local/bin/*; do bash -n "$p"; done
python3 -m py_compile "$HERE/"*.py
R36OS_RELEASE_FILE="$ROOT/etc/r36os-release" "$ROOT/usr/local/bin/r36os-version" version | grep -Fxq '0.5.53.0'

# Test UI-private label generation without changing the host.
mkdir -p "$WORK/ui-test"
cp "$ROOT/etc/r36os-release" "$WORK/ui-test/release"
R36OS_RELEASE_FILE="$WORK/ui-test/release" R36OS_UI_RELEASE_OUT="$WORK/ui-test/ui-release" R36OS_UNAME_R=4.4.189 "$ROOT/usr/local/bin/r36os-ui-kernel-label"
grep -Fxq 'R36OS_VERSION="Alpha 5R53 LEGACY"' "$WORK/ui-test/ui-release"
R36OS_RELEASE_FILE="$WORK/ui-test/ui-release" "$ROOT/usr/local/bin/r36os-version" tag | grep -Fxq 'Alpha5R53'
R36OS_RELEASE_FILE="$WORK/ui-test/release" R36OS_UI_RELEASE_OUT="$WORK/ui-test/ui-release" R36OS_UNAME_R=6.12.94-r36os-k1 "$ROOT/usr/local/bin/r36os-ui-kernel-label"
grep -Fxq 'R36OS_VERSION="Alpha 5R53 K1"' "$WORK/ui-test/ui-release"
R36OS_RELEASE_FILE="$WORK/ui-test/ui-release" "$ROOT/usr/local/bin/r36os-version" version | grep -Fxq '0.5.53.0'

# Validate the full merged K1 tree exactly as it will exist after overlay.
AUDK="$WORK/audit-k1"; cp -a "$OLDK1" "$AUDK"
for f in uInitrd K1.conf BUILD_INFO.txt MANIFEST.sha256; do cp "$ROOT/opt/r36os/kernel-next/K1/$f" "$AUDK/$f"; done
"$R38ROOT/usr/local/bin/r36os-k1-preflight" "$AUDK" >/dev/null
test "$(awk -F= '$1=="candidate_id"{print $2}' "$AUDK/K1.conf")" = "$CID"
test "$(sha256sum "$AUDK/Image"|awk '{print $1}')" = "$EXPECTED_IMAGE"
test "$(sha256sum "$AUDK/rk3326-r36s-k1.dtb"|awk '{print $1}')" = "$EXPECTED_DTB"
test "$(sha256sum "$AUDK/modules.tar.xz"|awk '{print $1}')" = "$(sha256sum "$OLDK1/modules.tar.xz"|awk '{print $1}')"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME"|awk '{print $1}')"; SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.53.0
base_version=0.5.52.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R53 audited release build PASS
base_version=0.5.52.0
version=0.5.53.0
old_candidate_id=$OLD_CID
candidate_id=$CID
kernel_release=$KREL
k1_image_change=no
k1_dtb_change=no
k1_modules_change=no
k1_uinitrd_change=yes
systemd_handoff_wrapper=/opt/r36i
ui_kernel_track_header=yes
r52_source_sha256=$EXPECTED_R52
r38_source_sha256=$EXPECTED_R38
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT
echo "R53_RELEASE_BUILD=PASS candidate_id=$CID size=$SIZE sha256=$SHA"
