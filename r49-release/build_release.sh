#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 5 ] || { echo "usage: build_release.sh <r48.r36upd> <r47.r36upd> <r43.r36upd> <r39.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R48="$1"; R47="$2"; R43="$3"; R39="$4"; OUT="$5"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r49'
NAME='00-R36OS-Alpha5R49-R36UpdateIsolationMaintenance-FromR48.r36upd'
EXPECTED_R48='37ba7053807b1c331176b74963640f4ee6b982c19d533e7febebb29d16d17a98'
EXPECTED_R47='0f012501b0f8bebb0bd377f62dde554901f1584ab85c49e77cfad5e73b750808'
EXPECTED_R43='cd4e66c08de18c0dbdd4ec3ff3babd5efcf6cc876113f1bd0f57aa1fc3ee421a'
EXPECTED_R39='406aa63aedf893b39fdff16f6131f605d99883aa759286228c1cf607dce74ebd'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r49-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r48" "$WORK/r47" "$WORK/r43" "$WORK/r39"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/etc/systemd/system/r36update.mount.d"   "$WORK/update/payload/root/etc/systemd/system/r36os.service.d"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/usr/local/libexec/r36os"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

check_input(){ f="$1"; want="$2"; got="$(sha256sum "$f" | awk '{print $1}')"; [ "$got" = "$want" ] || { echo "input-sha-mismatch file=$f want=$want got=$got" >&2; exit 10; }; }
check_input "$R48" "$EXPECTED_R48"
check_input "$R47" "$EXPECTED_R47"
check_input "$R43" "$EXPECTED_R43"
check_input "$R39" "$EXPECTED_R39"

tar -xzf "$R48" -C "$WORK/r48"
tar -xzf "$R47" -C "$WORK/r47"
tar -xzf "$R43" -C "$WORK/r43"
tar -xzf "$R39" -C "$WORK/r39"
for d in r48 r47 r43 r39; do (cd "$WORK/$d" && sha256sum -c checksums.sha256 >/dev/null); done

R48ROOT="$WORK/r48/payload/root"
R47ROOT="$WORK/r47/payload/root"
R43ROOT="$WORK/r43/payload/root"
R39ROOT="$WORK/r39/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R48ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

python3 "$HERE/transform_prepare.py" "$R48ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_slot.py" "$R48ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-kernel-slot"

cp "$HERE/r36os-r36update-policy" "$ROOT/usr/local/bin/r36os-r36update-policy"
cp "$HERE/r36os-r36update-maint" "$ROOT/usr/local/bin/r36os-r36update-maint"
cp "$HERE/r36os-firstboot-update-repair" "$ROOT/usr/local/bin/r36os-firstboot-update-repair"
cp "$HERE/r36os-r36update-repair" "$ROOT/usr/local/bin/r36os-r36update-repair"
cp "$HERE/r36os-kernel-next-health" "$ROOT/usr/local/bin/r36os-kernel-next-health"
cp "$HERE/r36os-update-rollback" "$ROOT/usr/local/bin/r36os-update-rollback"
cp "$HERE/90-r36os-readonly.conf" "$ROOT/etc/systemd/system/r36update.mount.d/90-r36os-readonly.conf"
cp "$HERE/95-r36update-policy.conf" "$ROOT/etc/systemd/system/r36os.service.d/95-r36update-policy.conf"

# Proven checker/fixture are retained exactly from published R43.
for p in   usr/local/libexec/r36os/fsck.fat-static   usr/local/libexec/r36os/fsck.fat-static.sha256   usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt   usr/local/libexec/r36os/fsck-selftest.img.gz   usr/local/libexec/r36os/fsck-selftest.img.gz.sha256; do
  test -e "$R43ROOT/$p"
  cp -a "$R43ROOT/$p" "$ROOT/$p"
done

# Prove the branch copies used for modified long-lived helpers were derived from
# the correct installed lineage.
test "$(sha256sum "$R39ROOT/usr/local/bin/r36os-kernel-next-health" | awk '{print $1}')" = '43d93da3988e739912d6ad82791cefe9218d40dd4ae00761dbcc4487ced1d4d7'
grep -q 'R36OS Alpha 5R49 K1 health' "$ROOT/usr/local/bin/r36os-kernel-next-health"
test -s "$R47ROOT/usr/local/bin/r36os-update-rollback"
grep -q 'R49: isolate/unmount R36UPDATE BEFORE' "$ROOT/usr/local/bin/r36os-update-rollback"

chmod 0755   "$ROOT/usr/local/bin/r36os-kernel-next-prepare"   "$ROOT/usr/local/bin/r36os-kernel-slot"   "$ROOT/usr/local/bin/r36os-r36update-policy"   "$ROOT/usr/local/bin/r36os-r36update-maint"   "$ROOT/usr/local/bin/r36os-firstboot-update-repair"   "$ROOT/usr/local/bin/r36os-r36update-repair"   "$ROOT/usr/local/bin/r36os-kernel-next-health"   "$ROOT/usr/local/bin/r36os-update-rollback"   "$ROOT/usr/local/libexec/r36os/fsck.fat-static"
chmod 0644   "$ROOT/etc/systemd/system/r36update.mount.d/90-r36os-readonly.conf"   "$ROOT/etc/systemd/system/r36os.service.d/95-r36update-policy.conf"   "$ROOT/usr/local/libexec/r36os/fsck.fat-static.sha256"   "$ROOT/usr/local/libexec/r36os/fsck-fat-BUILD_INFO.txt"   "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz"   "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz.sha256"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R49"
R36OS_PACKAGE_VERSION="0.5.49.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="R36UPDATE isolated read-only handoff storage with private K1 maintenance windows"
R36OS_NOTES="Alpha 5R49 retires the R43-R48 boot-time full-partition FAT repair model. R36UPDATE is read-only during normal userspace, legacy writable subpaths bind to R36STATE, and Boot Next Once performs fsck/staging/marker writes through private guarded maintenance mounts. K1 binaries remain unchanged."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r49" <<'EOF_FEATURE'
R36OS Alpha 5R49
- R36UPDATE is boot-handoff storage, not general writable storage.
- /dev/mmcblk0p3 mounts read-only in normal userspace.
- Legacy R36OS-Cache, R36OS-Logs, R36OS-KernelLab and update paths attempt best-effort R36STATE bind overlays when their FAT directories exist; unsupported overlays never make FAT writable or block boot.
- The R43-R48 automatic first-boot full-partition backup/repair path is retired.
- Boot Next Once owns the controlled maintenance transaction:
  verify authoritative /opt K1 -> unmount FAT -> fsck read-only -> repair if needed -> verify clean -> private guarded RW mount -> reuse/restage exact K1 -> return read-only -> install/verify hook -> private guarded marker window -> clean final unmount.
- Long K1 staging and tiny request-marker writes both occur on a private /run mount while /r36update is a read-only guard.
- Failed preparation restores read-only policy.
- Transaction rollback isolates/unmounts R36UPDATE before restoring/removing R49 files.
- K1 success/fallback marker cleanup uses the private guarded FAT window.
- Exact R43 target-validated fsck.fat checker and fixture are retained.
- K1 Image, DTB, uInitrd and modules are unchanged.
- Legacy Linux 4.4 remains the fallback.
- The flashing top-left blue underscore remains tracked separately as a boot/TTY visual issue.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r49"

# Update the cumulative core manifest from exact R48.
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
'/usr/local/bin/r36os-r36update-policy',
'/usr/local/bin/r36os-r36update-maint',
'/usr/local/bin/r36os-firstboot-update-repair',
'/usr/local/bin/r36os-r36update-repair',
'/usr/local/bin/r36os-kernel-next-health',
'/usr/local/bin/r36os-update-rollback',
'/etc/systemd/system/r36update.mount.d/90-r36os-readonly.conf',
'/etc/systemd/system/r36os.service.d/95-r36update-policy.conf',
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
version=0.5.49.0
hardware=R36XX-RK3326
base_version=0.5.48.0
channel=system-core
requires_reboot=true
description=Alpha 5R49 isolates R36UPDATE as read-only boot-handoff storage and replaces the failed full-partition backup repair flow with a guarded private maintenance/staging transaction.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r36update_normal_mode=read-only
r36update_compat_writes=best-effort-r36state-bind-or-safe-ro-failure
full_partition_tar_backup=retired
k1_maintenance=unmounted-fsck-private-rw-stage-private-rw-marker
final_arm_state=r36update-unmounted
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
etc/systemd/system/r36os.service.d/95-r36update-policy.conf
etc/systemd/system/r36update.mount.d/90-r36os-readonly.conf
opt/r36os/features/alpha5r49
usr/local/bin/r36os-firstboot-update-repair
usr/local/bin/r36os-kernel-next-health
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
usr/local/bin/r36os-r36update-maint
usr/local/bin/r36os-r36update-policy
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

test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'
! find "$ROOT" -type l | grep -q .
HITS="$(grep -R -n -E 'github_pat_[A-Za-z0-9]|gh[pousr]_[A-Za-z0-9]' "$ROOT" || true)"
test -z "$HITS"

for p in "$ROOT"/usr/local/bin/*; do bash -n "$p"; done
grep -q '0.5.49.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -q '0.5.49.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q 'Alpha 5R49' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -q 'r49-runtime-lock' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq 'marker-open' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq 'ARMED_ONCE_PRIVATE_WINDOW_R36UPDATE_UNMOUNTED' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq 'private_mount=' "$ROOT/usr/local/bin/r36os-r36update-maint"
grep -Fq 'full_partition_tar_backup=no' "$ROOT/usr/local/bin/r36os-r36update-maint"
grep -Fxq 'Options=ro' "$ROOT/etc/systemd/system/r36update.mount.d/90-r36os-readonly.conf"
grep -Fq 'ExecStartPre=/usr/local/bin/r36os-r36update-policy normal' "$ROOT/etc/systemd/system/r36os.service.d/95-r36update-policy.conf"
! grep -Eq 'umount[[:space:]]+(-f|-l|--force|--lazy)' "$ROOT/usr/local/bin/r36os-update-rollback"
! grep -Eq 'reboot[[:space:]]+-f|poweroff[[:space:]]+-f' "$ROOT/usr/local/bin/r36os-update-rollback"

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
version=0.5.49.0
base_version=0.5.48.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R49 audited release build PASS
base_version=0.5.48.0
version=0.5.49.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r48_source_sha256=$EXPECTED_R48
r47_source_sha256=$EXPECTED_R47
r43_source_sha256=$EXPECTED_R43
r39_source_sha256=$EXPECTED_R39
r36update_normal_readonly=yes
compat_writes_best_effort_r36state_or_safe_ro_failure=yes
full_partition_tar_backup=retired
long_stage_private_guarded_mount=yes
marker_write_private_guarded_mount=yes
rollback_unmount_before_restore=yes
post_attempt_marker_cleanup_private=yes
final_arm_r36update_unmounted=yes
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R49_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
