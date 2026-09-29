#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r50.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R50="$1"; OUT="$2"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r51'
NAME='00-R36OS-Alpha5R51-PersistentK1Breadcrumbs-FromR50.r36upd'
EXPECTED_R50='5a41efe1b5019bfb2c8b9166bffd48c663997121e90a8a58f59b1e901f7072f0'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r51-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r50"   "$WORK/update/payload/root/etc/systemd/system/r36os.service.d"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$WORK/update/payload/root/opt/r36os/kernel-next"   "$OUT"

test "$(sha256sum "$R50" | awk '{print $1}')" = "$EXPECTED_R50" || { echo r50-sha-mismatch >&2; exit 10; }
tar -xzf "$R50" -C "$WORK/r50"
(cd "$WORK/r50" && sha256sum -c checksums.sha256 >/dev/null)

R50ROOT="$WORK/r50/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R50ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

python3 "$HERE/transform_prepare.py" "$R50ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_slot.py" "$R50ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_maint.py" "$R50ROOT/usr/local/bin/r36os-r36update-maint" "$ROOT/usr/local/bin/r36os-r36update-maint"

python3 "$HERE/generate_hook.py"   "$R50ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$R50ROOT/opt/r36os/kernel-next/hook.conf"   "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$ROOT/opt/r36os/kernel-next/hook.conf"

python3 "$HERE/transform_installer.py"   "$R50ROOT/usr/local/bin/r36os-k1-install-hook"   "$R50ROOT/opt/r36os/kernel-next/hook.conf"   "$ROOT/usr/local/bin/r36os-k1-install-hook"

cp "$HERE/r36os-k1-attempt-capture" "$ROOT/usr/local/bin/r36os-k1-attempt-capture"
cp "$HERE/r36os-running-kernel-status" "$ROOT/usr/local/bin/r36os-running-kernel-status"
cp "$HERE/98-k1-diagnostics.conf" "$ROOT/etc/systemd/system/r36os.service.d/98-k1-diagnostics.conf"

chmod 0755 "$ROOT/usr/local/bin/"*
chmod 0644   "$ROOT/etc/systemd/system/r36os.service.d/98-k1-diagnostics.conf"   "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$ROOT/opt/r36os/kernel-next/hook.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R51"
R36OS_PACKAGE_VERSION="0.5.51.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="Persistent U-Boot K1 stage breadcrumbs plus post-recovery capture"
R36OS_NOTES="Alpha 5R51 preserves R50 root consumed marker and the R49 isolated R36UPDATE architecture. It adds best-effort root-level 8.3 U-Boot stage markers that survive hard reset, exposes the deepest surviving stage in kernel-slot diagnostics, captures attempt state to R36STATE after recovery, and refreshes the live kernel display after the UI starts. K1 binaries are unchanged."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r51" <<'EOF_FEATURE'
R36OS Alpha 5R51
- Persistent K1 U-Boot breadcrumbs survive a hard reset:
  K1CON.OK = one-shot consumed guard verified
  K1IMG.OK = Linux Image loaded
  K1INI.OK = uInitrd loaded
  K1DTB.OK = DTB loaded
  K1BOT.OK = immediately before booti
  K1RET.OK = booti returned to U-Boot
- Breadcrumb writes are best-effort root-level 8.3 FAT files and do not gate boot.
- Every explicit new arm clears the previous breadcrumb set first.
- kernel-slot status reports each breadcrumb and the deepest surviving U-Boot stage.
- Recovered legacy boot captures breadcrumb/probe state to /run and /r36state/logs/k1-attempts.
- Diagnostics kernel status refresh now runs after the UI process starts so a later Kernel Lab status refresh cannot erase the live uname before the screen appears.
- Preserved R38 uInitrd already contains initramfs stage instrumentation; it is not rebuilt in R51.
- K1 Image, uInitrd, DTB and modules are unchanged.
- Legacy Linux 4.4 remains the fallback.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r51"

python3 - "$CORE" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip()
    entries[p]=h; order.append(p)
paths=[
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-r36update-maint',
'/usr/local/bin/r36os-k1-install-hook',
'/usr/local/bin/r36os-k1-attempt-capture',
'/usr/local/bin/r36os-running-kernel-status',
'/etc/systemd/system/r36os.service.d/98-k1-diagnostics.conf',
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
version=0.5.51.0
hardware=R36XX-RK3326
base_version=0.5.50.0
channel=system-core
requires_reboot=true
description=Alpha 5R51 adds persistent root-level K1 U-Boot stage breadcrumbs and recovery capture without changing any K1 binary payload.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
consumed_marker=R36K1.CNS
breadcrumbs=K1CON.OK,K1IMG.OK,K1INI.OK,K1DTB.OK,K1BOT.OK,K1RET.OK
breadcrumbs_persistent_across_hard_reset=yes
initramfs_binary_change=no
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/systemd/system/r36os.service.d/98-k1-diagnostics.conf
opt/r36os/features/alpha5r51
opt/r36os/kernel-next/hook.conf
opt/r36os/kernel-next/hooked-boot.ini
usr/local/bin/r36os-k1-attempt-capture
usr/local/bin/r36os-k1-install-hook
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-maint
usr/local/bin/r36os-running-kernel-status
EOF_FILES
(cd "$ROOT" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'
! find "$ROOT" -type l | grep -q .
HITS="$(grep -R -n -E 'github_pat_[A-Za-z0-9]|gh[pousr]_[A-Za-z0-9]' "$ROOT" || true)"
test -z "$HITS"

for p in "$ROOT"/usr/local/bin/*; do bash -n "$p"; done
python3 -m py_compile "$HERE/"*.py

grep -q '0.5.51.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -q '0.5.51.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q '0.5.51.0' "$ROOT/usr/local/bin/r36os-r36update-maint"
grep -q 'Alpha 5R51' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q 'r51-runtime-lock' "$ROOT/usr/local/bin/r36os-kernel-slot"
for f in K1CON.OK K1IMG.OK K1INI.OK K1DTB.OK K1BOT.OK K1RET.OK; do
  grep -Fq "$f" "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"
  grep -Fq "$f" "$ROOT/usr/local/bin/r36os-kernel-slot"
done
grep -Fq 'breadcrumbs_mode=root-8.3-best-effort' "$ROOT/opt/r36os/kernel-next/hook.conf"
grep -Fq 'breadcrumb_deepest=' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq 'ExecStartPost=/usr/local/bin/r36os-k1-attempt-capture' "$ROOT/etc/systemd/system/r36os.service.d/98-k1-diagnostics.conf"
grep -Fq 'ExecStartPost=/usr/local/bin/r36os-running-kernel-status' "$ROOT/etc/systemd/system/r36os.service.d/98-k1-diagnostics.conf"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.51.0
base_version=0.5.50.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R51 audited release build PASS
base_version=0.5.50.0
version=0.5.51.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r50_source_sha256=$EXPECTED_R50
breadcrumbs=K1CON.OK,K1IMG.OK,K1INI.OK,K1DTB.OK,K1BOT.OK,K1RET.OK
breadcrumbs_persistent_across_hard_reset=yes
initramfs_binary_change=no
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R51_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
