#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 3 ] || { echo "usage: build_release.sh <exact-r49.r36upd> <exact-r46.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R49="$1"; R46="$2"; OUT="$3"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r50'
NAME='00-R36OS-Alpha5R50-RootConsumedKernelStatus-FromR49.r36upd'
EXPECTED_R49='6a65fe9a952140ee0f380e9ef053d1ea7b658976ead496eda7bd30f9a83502cb'
EXPECTED_R46='9fd037fd79f78420c6f1b6e8df67db2280ed4339df714ef2aeadb225f4e95815'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r50-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r49" "$WORK/r46"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/etc/systemd/system/r36os.service.d"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$WORK/update/payload/root/opt/r36os/kernel-next"   "$OUT"

check_input(){ f="$1"; want="$2"; got="$(sha256sum "$f" | awk '{print $1}')"; [ "$got" = "$want" ] || { echo "input-sha-mismatch file=$f want=$want got=$got" >&2; exit 10; }; }
check_input "$R49" "$EXPECTED_R49"
check_input "$R46" "$EXPECTED_R46"
tar -xzf "$R49" -C "$WORK/r49"
tar -xzf "$R46" -C "$WORK/r46"
(cd "$WORK/r49" && sha256sum -c checksums.sha256 >/dev/null)
(cd "$WORK/r46" && sha256sum -c checksums.sha256 >/dev/null)

R49ROOT="$WORK/r49/payload/root"
R46ROOT="$WORK/r46/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R49ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

python3 "$HERE/transform_prepare.py" "$R49ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_slot.py" "$R49ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_maint.py" "$R49ROOT/usr/local/bin/r36os-r36update-maint" "$ROOT/usr/local/bin/r36os-r36update-maint"
python3 "$HERE/transform_health.py" "$R49ROOT/usr/local/bin/r36os-kernel-next-health" "$ROOT/usr/local/bin/r36os-kernel-next-health"

python3 "$HERE/generate_hook.py"   "$R46ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$R46ROOT/opt/r36os/kernel-next/hook.conf"   "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$ROOT/opt/r36os/kernel-next/hook.conf"

python3 "$HERE/transform_installer.py"   "$R46ROOT/usr/local/bin/r36os-k1-install-hook"   "$R46ROOT/opt/r36os/kernel-next/hook.conf"   "$ROOT/usr/local/bin/r36os-k1-install-hook"

cp "$HERE/r36os-running-kernel-status" "$ROOT/usr/local/bin/r36os-running-kernel-status"
cp "$HERE/97-running-kernel-status.conf" "$ROOT/etc/systemd/system/r36os.service.d/97-running-kernel-status.conf"

chmod 0755 "$ROOT/usr/local/bin/"*
chmod 0644 "$ROOT/etc/systemd/system/r36os.service.d/97-running-kernel-status.conf"   "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$ROOT/opt/r36os/kernel-next/hook.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R50"
R36OS_PACKAGE_VERSION="0.5.50.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="Root-level 8.3 U-Boot consumed marker plus live kernel identity in Diagnostics"
R36OS_NOTES="Alpha 5R50 preserves the R49 isolated R36UPDATE architecture and all K1 binaries. Physical R49 evidence reached U-Boot probe consumed_readback_failed. R50 moves only the U-Boot-written consumed marker to root-level R36K1.CNS for old fatwrite compatibility, retains the candidate-bound request in R36OS-KernelNext, and makes the Diagnostics Kernel Lab status show the live kernel identity."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r50" <<'EOF_FEATURE'
R36OS Alpha 5R50
- Direct corrective update from Alpha 5R49.
- Physical R49 test reached r36os.k1_probe=consumed_readback_failed on legacy Linux 4.4.189.
- Linux-created candidate-bound request remains R36OS-KernelNext/boot-next.<candidate>.once.
- U-Boot-written consumed marker is now root-level FAT 8.3-safe R36K1.CNS.
- U-Boot reads back R36K1.CNS and verifies its size before any K1 payload load.
- Existing breadcrumb stages and legacy fallthrough remain intact.
- Linux slot, maintenance, health and cleanup paths all understand the root consumed marker.
- Obsolete subdirectory consumed markers are cleaned during explicit new arm/disarm operations.
- R36UPDATE remains read-only in normal userspace and private/guarded for writes as introduced by R49.
- Diagnostics Kernel Lab row now reports the live uname release as "4.4.189 Legacy" or "6.12.94-r36os-k1 K1" at UI startup.
- K1 Image, uInitrd, DTB and modules are unchanged.
- Legacy Linux 4.4 fallback remains intact.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r50"

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
'/usr/local/bin/r36os-kernel-next-health',
'/usr/local/bin/r36os-k1-install-hook',
'/usr/local/bin/r36os-running-kernel-status',
'/etc/systemd/system/r36os.service.d/97-running-kernel-status.conf',
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
version=0.5.50.0
hardware=R36XX-RK3326
base_version=0.5.49.0
channel=system-core
requires_reboot=true
description=Alpha 5R50 fixes the physically observed U-Boot consumed-marker readback failure with a root-level 8.3 marker and exposes the live kernel identity in Diagnostics. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
consumed_marker=R36K1.CNS
consumed_marker_mode=root-8.3
request_marker_mode=candidate-bound-subdirectory
r36update_architecture=R49-isolated-readonly-private-write
diagnostics_live_kernel=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/systemd/system/r36os.service.d/97-running-kernel-status.conf
opt/r36os/features/alpha5r50
opt/r36os/kernel-next/hook.conf
opt/r36os/kernel-next/hooked-boot.ini
usr/local/bin/r36os-k1-install-hook
usr/local/bin/r36os-kernel-next-health
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

grep -q '0.5.50.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -q '0.5.50.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q '0.5.50.0' "$ROOT/usr/local/bin/r36os-r36update-maint"
grep -q 'Alpha 5R50' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q 'r50-runtime-lock' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq 'CONSUMED="$UPDATE_MOUNT/R36K1.CNS"' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq 'CONSUMED="${R36OS_UPDATE_MOUNT:-/r36update}/R36K1.CNS"' "$ROOT/usr/local/bin/r36os-kernel-next-health"
grep -Fq 'consumed=R36K1.CNS' "$ROOT/opt/r36os/kernel-next/hook.conf"
grep -Fq 'consumed_marker_mode=root-8.3' "$ROOT/opt/r36os/kernel-next/hook.conf"
grep -Fq 'fatwrite mmc 1:3 ${loadaddr} "R36K1.CNS" ${r36os_req_size}' "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"
! grep -F 'fatwrite mmc 1:3' "$ROOT/opt/r36os/kernel-next/hooked-boot.ini" | grep -q '/'
grep -Fq 'baseline_status=$DISPLAY' "$ROOT/usr/local/bin/r36os-running-kernel-status"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.50.0
base_version=0.5.49.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R50 audited release build PASS
base_version=0.5.49.0
version=0.5.50.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r49_source_sha256=$EXPECTED_R49
r46_hook_source_sha256=$EXPECTED_R46
consumed_marker=R36K1.CNS
consumed_marker_mode=root-8.3
public_r36update_write_model=unchanged-from-r49
diagnostics_live_kernel=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R50_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
