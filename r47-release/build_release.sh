#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 3 ] || { echo "usage: build_release.sh <exact-r46.r36upd> <exact-r43.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R46="$1"
R43="$2"
OUT="$3"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r47'
NAME='00-R36OS-Alpha5R47-R36UpdateRepairRollbackFix-FromR46.r36upd'
EXPECTED_R46='9fd037fd79f78420c6f1b6e8df67db2280ed4339df714ef2aeadb225f4e95815'
EXPECTED_R43='cd4e66c08de18c0dbdd4ec3ff3babd5efcf6cc876113f1bd0f57aa1fc3ee421a'
BASE_ROLLBACK_SHA='ea6636224705dfe06f4abd56aad853a2a17bb0d08b413d0d568900c13c2a9423'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r47-release"

rm -rf "$WORK" "$OUT"
mkdir -p   "$WORK/r46" "$WORK/r43"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/etc/systemd/system"   "$WORK/update/payload/root/etc/systemd/system-generators"   "$WORK/update/payload/root/lib/systemd/system-generators"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/usr/local/libexec/r36os"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha256sum "$R46" | awk '{print $1}')" = "$EXPECTED_R46" || { echo r46-sha-mismatch >&2; exit 10; }
test "$(sha256sum "$R43" | awk '{print $1}')" = "$EXPECTED_R43" || { echo r43-sha-mismatch >&2; exit 11; }

tar -xzf "$R46" -C "$WORK/r46"
tar -xzf "$R43" -C "$WORK/r43"
(cd "$WORK/r46" && sha256sum -c checksums.sha256 >/dev/null)
(cd "$WORK/r43" && sha256sum -c checksums.sha256 >/dev/null)

R46ROOT="$WORK/r46/payload/root"
R43ROOT="$WORK/r43/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R46ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

# Preserve R46 K1 behavior while updating only the release identity to R47.
python3 - "$R46ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if s.count('0.5.46.0') != 1:
    raise SystemExit('unexpected R46 prepare identity count')
s=s.replace('0.5.46.0','0.5.47.0',1)
Path(sys.argv[2]).write_text(s)
PY

python3 - "$R46ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
checks=[('0.5.46.0','0.5.47.0',2),('Alpha 5R46','Alpha 5R47',1),('r46-runtime-lock','r47-runtime-lock',1)]
for a,b,count in checks:
    if s.count(a) != count:
        raise SystemExit(f'unexpected R46 slot identity count for {a}: {s.count(a)} expected {count}')
    s=s.replace(a,b)
Path(sys.argv[2]).write_text(s)
PY

# Reuse the exact physically proven R43 repair engine and checker.
for p in   usr/local/bin/r36os-r36update-repair   usr/local/libexec/r36os/fsck.fat-static   usr/local/libexec/r36os/fsck.fat-static.sha256   etc/systemd/system-generators/r36os-firstboot-update-repair-generator   lib/systemd/system-generators/r36os-firstboot-update-repair-generator   etc/systemd/system/r36os-firstboot-update-repair.service; do
  test -e "$R43ROOT/$p" || { echo "missing R43 repair payload: $p" >&2; exit 12; }
  mkdir -p "$ROOT/$(dirname "$p")"
  cp -a "$R43ROOT/$p" "$ROOT/$p"
done

# Reuse the proven first-boot repair runner, changing only its release-bound marker.
python3 - "$R43ROOT/usr/local/bin/r36os-firstboot-update-repair" "$ROOT/usr/local/bin/r36os-firstboot-update-repair" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if s.count('0.5.43.0') != 1:
    raise SystemExit('unexpected R43 firstboot identity count')
s=s.replace('0.5.43.0','0.5.47.0',1)
Path(sys.argv[2]).write_text(s)
PY

# Install the audited R47 rollback helper.
cp "$HERE/r36os-update-rollback" "$ROOT/usr/local/bin/r36os-update-rollback"

chmod 0755   "$ROOT/usr/local/bin/r36os-kernel-next-prepare"   "$ROOT/usr/local/bin/r36os-kernel-slot"   "$ROOT/usr/local/bin/r36os-r36update-repair"   "$ROOT/usr/local/bin/r36os-firstboot-update-repair"   "$ROOT/usr/local/bin/r36os-update-rollback"   "$ROOT/usr/local/libexec/r36os/fsck.fat-static"   "$ROOT/etc/systemd/system-generators/r36os-firstboot-update-repair-generator"   "$ROOT/lib/systemd/system-generators/r36os-firstboot-update-repair-generator"
chmod 0644   "$ROOT/usr/local/libexec/r36os/fsck.fat-static.sha256"   "$ROOT/etc/systemd/system/r36os-firstboot-update-repair.service"

cat >"$ROOT/etc/r36os/r36update-repair-once.conf" <<'EOF_MARK'
format=R36OS_R36UPDATE_REPAIR_ONCE_V1
release=0.5.47.0
reason=repair-dirty-r36update-after-r45-rollback-cycle
EOF_MARK
chmod 0644 "$ROOT/etc/r36os/r36update-repair-once.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R47"
R36OS_PACKAGE_VERSION="0.5.47.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="R36UPDATE one-time audited FAT repair plus clean transactional rollback unmount"
R36OS_NOTES="Alpha 5R47 preserves R46 K1 binaries and handoff probes. It re-arms the physically proven R43 FAT repair for the current dirty R36UPDATE partition and hardens transactional rollback so /r36update is normally unmounted before the caller reboots."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r47" <<EOF_FEATURE
R36OS Alpha 5R47
- Direct corrective update from Alpha 5R46.
- Reuses the exact R43 target-validated AArch64 FAT checker and repair engine.
- Re-arms one R36UPDATE repair because physical logs prove mmcblk0p3 became dirty after the failed R45 transactional rollback cycle.
- Transactional rollback now syncs and retries a normal /r36update unmount before reboot; forced/lazy unmount is forbidden.
- If normal unmount cannot complete, rollback records evidence and attempts a read-only remount before reboot.
- Preserves R46 120-second update-health window and quick non-hashing kernel status.
- K1 Image, DTB, uInitrd and modules are unchanged.
- Legacy Linux 4.4 remains the fallback.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r47"

# Update the R46 full core manifest only for files R47 changes/reinstalls.
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
'/usr/local/bin/r36os-r36update-repair',
'/usr/local/bin/r36os-firstboot-update-repair',
'/usr/local/bin/r36os-update-rollback',
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
version=0.5.47.0
hardware=R36XX-RK3326
base_version=0.5.46.0
channel=system-core
requires_reboot=true
description=Alpha 5R47 repairs the physically confirmed dirty R36UPDATE partition using the proven R43 checker and prevents transactional rollback from rebooting while R36UPDATE is still mounted read/write. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r36update_repair=exact-r43-target-validated-one-shot
rollback_r36update_cleanup=sync-normal-unmount-retry-no-force-no-lazy
post_install_repair_restart_required=yes
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/r36os/r36update-repair-once.conf
opt/r36os/features/alpha5r47
usr/local/bin/r36os-firstboot-update-repair
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-repair
usr/local/bin/r36os-update-rollback
usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt
usr/local/libexec/r36os/fsck-selftest.img.gz
usr/local/libexec/r36os/fsck-selftest.img.gz.sha256
usr/local/libexec/r36os/fsck.fat-static
usr/local/libexec/r36os/fsck.fat-static.sha256
EOF_FILES
(cd "$ROOT" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

# Scope and safety gates.
test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'
! find "$ROOT" -type l | grep -q .
! grep -R -n -E 'github_pat_[A-Za-z0-9]|gh[pousr]_[A-Za-z0-9]' "$ROOT" >/dev/null 2>&1

bash -n "$ROOT/usr/local/bin/r36os-update-rollback"
bash -n "$ROOT/usr/local/bin/r36os-r36update-repair"
bash -n "$ROOT/usr/local/bin/r36os-firstboot-update-repair"
bash -n "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
bash -n "$ROOT/usr/local/bin/r36os-kernel-slot"

# The rollback fix must use a normal unmount and must never force/lazy-unmount.
grep -Fq 'umount "$UPDATE_MOUNT"' "$ROOT/usr/local/bin/r36os-update-rollback"
! grep -Eq 'umount[[:space:]]+(-f|-l|--force|--lazy)' "$ROOT/usr/local/bin/r36os-update-rollback"
! grep -Eq 'reboot[[:space:]]+-f|poweroff[[:space:]]+-f' "$ROOT/usr/local/bin/r36os-update-rollback"

# Prove exact R43 repair artifacts are retained.
cmp "$R43ROOT/usr/local/bin/r36os-r36update-repair" "$ROOT/usr/local/bin/r36os-r36update-repair"
cmp "$R43ROOT/usr/local/libexec/r36os/fsck.fat-static" "$ROOT/usr/local/libexec/r36os/fsck.fat-static"
cmp "$R43ROOT/usr/local/libexec/r36os/fsck.fat-static.sha256" "$ROOT/usr/local/libexec/r36os/fsck.fat-static.sha256"
cmp "$R43ROOT/usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt" "$ROOT/usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt"
cmp "$R43ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz" "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz"
cmp "$R43ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz.sha256" "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz.sha256"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.47.0
base_version=0.5.46.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R47 audited release build PASS
base_version=0.5.46.0
version=0.5.47.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r46_source_sha256=$EXPECTED_R46
r43_repair_source_sha256=$EXPECTED_R43
baseline_rollback_sha256=$BASE_ROLLBACK_SHA
r43_repair_reused_exactly=yes
rollback_normal_r36update_unmount=yes
rollback_forced_or_lazy_unmount=no
post_install_repair_restart_required=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R47_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
