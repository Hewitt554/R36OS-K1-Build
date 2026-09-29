#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 4 ] || { echo "usage: build_release.sh <exact-r51.r36upd> <exact-r50.r36upd> <exact-r39.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R51="$1"; R50="$2"; R39="$3"; OUT="$4"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r52'
NAME='00-R36OS-Alpha5R52-VisibleK1BootTrace-FromR51.r36upd'
EXPECTED_R51='11e1bdfd6378f96607dbc608412c17fefd729ceef71cb1ed633073b99cfc4f82'
EXPECTED_R50='5a41efe1b5019bfb2c8b9166bffd48c663997121e90a8a58f59b1e901f7072f0'
EXPECTED_R39='406aa63aedf893b39fdff16f6131f605d99883aa759286228c1cf607dce74ebd'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r52-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r51" "$WORK/r50" "$WORK/r39"   "$WORK/update/payload/root/etc"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$WORK/update/payload/root/opt/r36os/kernel-next"   "$OUT"

check(){ f="$1"; want="$2"; got="$(sha256sum "$f"|awk '{print $1}')"; [ "$got" = "$want" ] || { echo "sha mismatch $f" >&2; exit 10; }; }
check "$R51" "$EXPECTED_R51"
check "$R50" "$EXPECTED_R50"
check "$R39" "$EXPECTED_R39"

tar -xzf "$R51" -C "$WORK/r51"
tar -xzf "$R50" -C "$WORK/r50"
tar -xzf "$R39" -C "$WORK/r39"
(cd "$WORK/r51" && sha256sum -c checksums.sha256 >/dev/null)
(cd "$WORK/r50" && sha256sum -c checksums.sha256 >/dev/null)
(cd "$WORK/r39" && sha256sum -c checksums.sha256 >/dev/null)

R51ROOT="$WORK/r51/payload/root"
R50ROOT="$WORK/r50/payload/root"
R39ROOT="$WORK/r39/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R51ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

python3 "$HERE/transform_identity.py" "$R51ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_identity.py" "$R51ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_identity.py" "$R51ROOT/usr/local/bin/r36os-r36update-maint" "$ROOT/usr/local/bin/r36os-r36update-maint"

python3 "$HERE/transform_hook.py"   "$R51ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$R51ROOT/opt/r36os/kernel-next/hook.conf"   "$ROOT/opt/r36os/kernel-next/hooked-boot.ini"   "$ROOT/opt/r36os/kernel-next/hook.conf"

python3 "$HERE/transform_installer.py"   "$R51ROOT/usr/local/bin/r36os-k1-install-hook"   "$R51ROOT/opt/r36os/kernel-next/hook.conf"   "$ROOT/usr/local/bin/r36os-k1-install-hook"

python3 "$HERE/transform_health.py"   "$R50ROOT/usr/local/bin/r36os-kernel-next-health"   "$ROOT/usr/local/bin/r36os-kernel-next-health"

python3 "$HERE/transform_github_diagnostics.py"   "$R39ROOT/usr/local/bin/r36os-github-diagnostics"   "$ROOT/usr/local/bin/r36os-github-diagnostics"

chmod 0755 "$ROOT/usr/local/bin/"*
chmod 0644 "$ROOT/opt/r36os/kernel-next/hooked-boot.ini" "$ROOT/opt/r36os/kernel-next/hook.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R52"
R36OS_PACKAGE_VERSION="0.5.52.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="Visible K1 boot trace plus persistent breadcrumb export"
R36OS_NOTES="Alpha 5R52 preserves the R49 isolation architecture, R50 root consumed marker and R51 persistent breadcrumbs. It adds visible U-Boot stage text, verbose K1 console arguments, records deepest persistent breadcrumb in the automatic fallback record, and exports K1 attempt/root marker evidence. K1 Image, uInitrd, DTB and modules are unchanged."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r52" <<'EOF_FEATURE'
R36OS Alpha 5R52
- Visible K1 diagnostic trace during Boot Next Once:
  [1/5] One-shot guard verified
  [2/5] Linux Image loaded
  [3/5] initramfs loaded
  [4/5] Panel-4 DTB loaded
  [5/5] Starting Linux 6.12.94-r36os-k1
- Visible [FAIL] messages for Image/initramfs/DTB/consumed-marker failures.
- K1 diagnostic boot appends console=tty1 loglevel=8 ignore_loglevel earlycon plymouth.enable=0 systemd.show_status=1.
- Existing R51 K1CON/K1IMG/K1INI/K1DTB/K1BOT/K1RET persistent breadcrumbs remain authoritative.
- Automatic K1 fallback record now includes every breadcrumb and deepest_uboot_stage.
- GitHub diagnostics now explicitly export live kernel-slot status, K1 attempt status, R36STATE attempt record and root breadcrumb presence.
- K1 Image, uInitrd, DTB and modules are unchanged.
- Legacy 4.4 fallback remains intact.
EOF_FEATURE

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
'/usr/local/bin/r36os-kernel-next-health',
'/usr/local/bin/r36os-github-diagnostics',
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
version=0.5.52.0
hardware=R36XX-RK3326
base_version=0.5.51.0
channel=system-core
requires_reboot=true
description=Alpha 5R52 adds visible K1 boot stages and guarantees breadcrumb evidence is included in automatic fallback diagnostics.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
initramfs_binary_change=no
dtb_binary_change=no
visible_k1_trace=yes
persistent_breadcrumbs=yes
fallback_breadcrumb_capture=yes
diagnostics_breadcrumb_export=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
opt/r36os/features/alpha5r52
opt/r36os/kernel-next/hook.conf
opt/r36os/kernel-next/hooked-boot.ini
usr/local/bin/r36os-github-diagnostics
usr/local/bin/r36os-k1-install-hook
usr/local/bin/r36os-kernel-next-health
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-maint
EOF_FILES
(cd "$ROOT" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'
! find "$ROOT" -type l | grep -q .
for p in "$ROOT"/usr/local/bin/*; do bash -n "$p"; done
python3 -m py_compile "$HERE/"*.py

"$ROOT/usr/local/bin/r36os-github-diagnostics" selftest | grep -q 'R36OS_GITHUB_DIAGNOSTICS_SELFTEST=PASS'

HOOK="$ROOT/opt/r36os/kernel-next/hooked-boot.ini"
META="$ROOT/opt/r36os/kernel-next/hook.conf"
for msg in   '[1/5] One-shot guard verified'   '[2/5] Linux Image loaded'   '[3/5] initramfs loaded'   '[4/5] Panel-4 DTB loaded'   '[5/5] Starting Linux 6.12.94-r36os-k1'; do
  grep -Fq "$msg" "$HOOK"
done
grep -Fq 'console=tty1 loglevel=8 ignore_loglevel earlycon plymouth.enable=0 systemd.show_status=1' "$HOOK"
grep -Fxq 'visible_trace=yes' "$META"
grep -Fxq 'format=R36OS_K1_BOOT_HOOK_V5' "$META"

# All FAT writes remain root-level filenames only.
if grep 'fatwrite mmc 1:3' "$HOOK" | sed -n 's/.*"\([^"]*\)".*/\1/p' | grep -q '/'; then
  echo subdirectory-fatwrite-found >&2
  exit 30
fi

grep -Fq 'deepest_uboot_stage=' "$ROOT/usr/local/bin/r36os-kernel-next-health"
grep -Fq 'R36OS_DIAG_FAILURE_DETAIL="pstore_files=$COPIED deepest=$BREADCRUMB_DEEPEST"' "$ROOT/usr/local/bin/r36os-kernel-next-health"
grep -Fq 'k1-root-breadcrumbs.txt' "$ROOT/usr/local/bin/r36os-github-diagnostics"
grep -Fq 'k1-attempt-status.txt' "$ROOT/usr/local/bin/r36os-github-diagnostics"
grep -Fq 'kernel-slot-live.txt' "$ROOT/usr/local/bin/r36os-github-diagnostics"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME"|awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.52.0
base_version=0.5.51.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R52 audited release build PASS
base_version=0.5.51.0
version=0.5.52.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
initramfs_binary_change=no
dtb_binary_change=no
r51_source_sha256=$EXPECTED_R51
r50_health_source_sha256=$EXPECTED_R50
r39_diagnostics_source_sha256=$EXPECTED_R39
visible_k1_trace=yes
persistent_breadcrumbs=yes
fallback_breadcrumb_capture=yes
diagnostics_breadcrumb_export=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT
echo "R52_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
