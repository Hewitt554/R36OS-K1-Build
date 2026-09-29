#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 3 ] || { echo "usage: build_release.sh <exact-r47.r36upd> <exact-r43.r36upd> <out-dir>" >&2; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
R47="$1"; R43="$2"; OUT="$3"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r48'
NAME='00-R36OS-Alpha5R48-StaleK1DisarmBeforeFATRepair-FromR47.r36upd'
EXPECTED_R47='0f012501b0f8bebb0bd377f62dde554901f1584ab85c49e77cfad5e73b750808'
EXPECTED_R43='cd4e66c08de18c0dbdd4ec3ff3babd5efcf6cc876113f1bd0f57aa1fc3ee421a'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r48-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r47" "$WORK/r43" "$WORK/update/payload/root/etc/r36os" "$WORK/update/payload/root/usr/local/bin" "$WORK/update/payload/root/usr/local/libexec/r36os" "$WORK/update/payload/root/opt/r36os/features" "$OUT"

test "$(sha256sum "$R47" | awk '{print $1}')" = "$EXPECTED_R47" || { echo r47-sha-mismatch >&2; exit 10; }
test "$(sha256sum "$R43" | awk '{print $1}')" = "$EXPECTED_R43" || { echo r43-sha-mismatch >&2; exit 11; }

tar -xzf "$R47" -C "$WORK/r47"
tar -xzf "$R43" -C "$WORK/r43"
(cd "$WORK/r47" && sha256sum -c checksums.sha256 >/dev/null)
(cd "$WORK/r43" && sha256sum -c checksums.sha256 >/dev/null)

R47ROOT="$WORK/r47/payload/root"
R43ROOT="$WORK/r43/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R47ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

python3 - "$R47ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if s.count('0.5.47.0') != 1:
    raise SystemExit(f'unexpected R47 prepare identity count: {s.count("0.5.47.0")}')
Path(sys.argv[2]).write_text(s.replace('0.5.47.0','0.5.48.0',1))
PY

cp "$HERE/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-kernel-slot"
cp "$HERE/r36os-firstboot-update-repair" "$ROOT/usr/local/bin/r36os-firstboot-update-repair"

for p in   usr/local/bin/r36os-r36update-repair   usr/local/libexec/r36os/fsck.fat-static   usr/local/libexec/r36os/fsck.fat-static.sha256   usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt   usr/local/libexec/r36os/fsck-selftest.img.gz   usr/local/libexec/r36os/fsck-selftest.img.gz.sha256; do
  test -e "$R43ROOT/$p" || { echo "missing R43 repair payload: $p" >&2; exit 12; }
  mkdir -p "$ROOT/$(dirname "$p")"
  cp -a "$R43ROOT/$p" "$ROOT/$p"
done

chmod 0755 "$ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-firstboot-update-repair" "$ROOT/usr/local/bin/r36os-r36update-repair" "$ROOT/usr/local/libexec/r36os/fsck.fat-static"
chmod 0644 "$ROOT/usr/local/libexec/r36os/fsck.fat-static.sha256" "$ROOT/usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt" "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz" "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz.sha256"

cat >"$ROOT/etc/r36os/r36update-repair-once.conf" <<'EOF_MARK'
format=R36OS_R36UPDATE_REPAIR_ONCE_V1
release=0.5.48.0
reason=stale-k1-armed-unconsumed-marker-blocked-r47-fat-repair
EOF_MARK
chmod 0644 "$ROOT/etc/r36os/r36update-repair-once.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R48"
R36OS_PACKAGE_VERSION="0.5.48.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="Defer FAT repair until update marked good; safely clear stale armed/unconsumed K1 request first"
R36OS_NOTES="Alpha 5R48 fixes the R47 repair ordering discovered from physical logs. It leaves the repair marker intact during transactional activation, then on the next ordinary boot verifies and disarms only an armed=yes/consumed=no K1 request before running the exact R43 FAT repair. K1 binaries are unchanged."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r48" <<EOF_FEATURE
R36OS Alpha 5R48
- Direct corrective update from Alpha 5R47.
- R47 physical logs proved FAT repair stopped safely at code 45 because the old K1 one-shot request was still armed and unconsumed.
- During the transactional activation boot, repair is deferred while /r36state/update/pending.conf exists.
- On the next ordinary boot, only armed=yes + consumed=no is eligible for automatic stale-request cleanup.
- Candidate and hook quick identity must pass before cleanup.
- r36os-kernel-slot disarm now performs full candidate verification, fails closed if verification fails, and verifies the marker is actually gone.
- After stale-request cleanup, the unchanged exact R43 FAT repair runs.
- R48 emits bounded R36OS_R48 breadcrumbs to /dev/kmsg for remote diagnostics.
- Preserves R47 rollback R36UPDATE clean-unmount hardening and R46 120-second health window.
- K1 Image, DTB, uInitrd and modules are unchanged.
- The observed flashing blue top-left underscore is tracked separately as a boot/TTY cursor cosmetic issue and is intentionally not changed here.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r48"

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
'/usr/local/bin/r36os-firstboot-update-repair',
'/usr/local/bin/r36os-r36update-repair',
'/usr/local/libexec/r36os/fsck.fat-static',
'/usr/local/libexec/r36os/fsck.fat-static.sha256',
'/usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt',
'/usr/local/libexec/r36os/fsck-selftest.img.gz',
'/usr/local/libexec/r36os/fsck-selftest.img.gz.sha256',
]
for p in paths:
    fp=root/p.lstrip('/')
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.48.0
hardware=R36XX-RK3326
base_version=0.5.47.0
channel=system-core
requires_reboot=true
description=Alpha 5R48 defers the one-time FAT repair until R48 is marked good, then safely clears only a verified stale armed/unconsumed K1 request before running the unchanged R43 repair. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
repair_activation=defer-while-transaction-pending
stale_k1_cleanup=armed-yes-consumed-no-only-full-verify-fail-closed
r36update_repair=exact-final-r43-target-validated-one-shot
post_install_repair_restart_required=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/r36os/r36update-repair-once.conf
opt/r36os/features/alpha5r48
usr/local/bin/r36os-firstboot-update-repair
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-repair
usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt
usr/local/libexec/r36os/fsck-selftest.img.gz
usr/local/libexec/r36os/fsck-selftest.img.gz.sha256
usr/local/libexec/r36os/fsck.fat-static
usr/local/libexec/r36os/fsck.fat-static.sha256
EOF_FILES
(cd "$ROOT" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'
! find "$ROOT" -type l | grep -q .
HITS="$(grep -R -n -E 'github_pat_[A-Za-z0-9]|gh[pousr]_[A-Za-z0-9]' "$ROOT" || true)"
test -z "$HITS"

for p in "$ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-firstboot-update-repair" "$ROOT/usr/local/bin/r36os-r36update-repair"; do bash -n "$p"; done

grep -q '0.5.48.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -q '0.5.48.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q 'Alpha 5R48' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q 'r48-runtime-lock' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq 'status=FAIL code=$V detail=verification' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq 'code=66 detail=marker-clear-failed' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq 'if [ -s "$PENDING" ]' "$ROOT/usr/local/bin/r36os-firstboot-update-repair"
grep -Fq 'yes:no)' "$ROOT/usr/local/bin/r36os-firstboot-update-repair"
grep -Fq 'STALE_K1_DISARM_PASS' "$ROOT/usr/local/bin/r36os-firstboot-update-repair"
grep -Fq 'FAT_REPAIR_PASS' "$ROOT/usr/local/bin/r36os-firstboot-update-repair"

cmp "$R43ROOT/usr/local/bin/r36os-r36update-repair" "$ROOT/usr/local/bin/r36os-r36update-repair"
for p in fsck.fat-static fsck.fat-static.sha256 fsck-fat-BUILD_INFO.txt fsck-selftest.img.gz fsck-selftest.img.gz.sha256; do
  cmp "$R43ROOT/usr/local/libexec/r36os/$p" "$ROOT/usr/local/libexec/r36os/$p"
done
(cd "$ROOT/usr/local/libexec/r36os" && sha256sum -c fsck.fat-static.sha256 >/dev/null && sha256sum -c fsck-selftest.img.gz.sha256 >/dev/null)

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.48.0
base_version=0.5.47.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R48 audited release build PASS
base_version=0.5.47.0
version=0.5.48.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r47_source_sha256=$EXPECTED_R47
r43_repair_source_sha256=$EXPECTED_R43
repair_deferred_during_transaction=yes
stale_cleanup_only_armed_yes_consumed_no=yes
disarm_full_candidate_verify=yes
disarm_marker_clear_readback=yes
r43_repair_reused_exactly=yes
post_install_repair_restart_required=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R48_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
