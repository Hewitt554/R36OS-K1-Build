#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
R39="${1:?verified Alpha5R39 .r36upd required}"
FSCK_STATIC="${2:?verified static ARM64 fsck.fat required}"
OUT="${3:?output directory required}"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r40'
NAME='00-R36OS-Alpha5R40-LogsAndFATRepair-FromR39.r36upd'
EXPECTED_R39='406aa63aedf893b39fdff16f6131f605d99883aa759286228c1cf607dce74ebd'
EXPECTED_FSCK='fe165b0784dd3c301cdf422691b1e5630bd5fab11bca15b8419906b10900d665'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r40-release"

rm -rf "$WORK" "$OUT"
mkdir -p   "$WORK/base"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/usr/local/libexec/r36os"   "$WORK/update/payload/root/usr/lib/systemd/system-generators"   "$WORK/update/payload/root/etc/systemd/system"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

[[ "$(sha256sum "$R39" | awk '{print $1}')" == "$EXPECTED_R39" ]] || { echo 'R39 source package SHA-256 mismatch' >&2; exit 10; }
[[ "$(sha256sum "$FSCK_STATIC" | awk '{print $1}')" == "$EXPECTED_FSCK" ]] || { echo 'static fsck.fat SHA-256 mismatch' >&2; exit 11; }

tar -xzf "$R39" -C "$WORK/base"   manifest.conf   payload/root/etc/r36os-core-manifest.sha256   payload/root/usr/local/bin/r36os-kernel-next-prepare   payload/root/usr/local/bin/r36os-kernel-slot

[[ "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.39.0' ]] || { echo 'R39 base version mismatch' >&2; exit 12; }
[[ "$(awk -F= '$1=="base_version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.38.0' ]] || { echo 'R39 source base mismatch' >&2; exit 13; }

# Carry the verified R39 K1 helpers forward. Only the userspace release guard changes.
python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
if src.count("0.5.39.0") != 1:
    raise SystemExit("unexpected R39 prepare version-guard count")
out=src.replace("0.5.39.0","0.5.40.0")
Path(sys.argv[2]).write_text(out)
PY
python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-slot" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
if src.count("0.5.39.0") != 1:
    raise SystemExit("unexpected R39 slot version-guard count")
out=src.replace("0.5.39.0","0.5.40.0")
Path(sys.argv[2]).write_text(out)
PY

for f in   r36os-github-diagnostics   r36os-export-current-logs   r36os-r36update-repair   r36os-r40-firstboot-repair; do
  bash -n "$HERE/$f"
  cp "$HERE/$f" "$WORK/update/payload/root/usr/local/bin/$f"
  chmod 0755 "$WORK/update/payload/root/usr/local/bin/$f"
done

cp "$HERE/r36os-r40-repair-generator" "$WORK/update/payload/root/usr/lib/systemd/system-generators/r36os-r40-repair-generator"
chmod 0755 "$WORK/update/payload/root/usr/lib/systemd/system-generators/r36os-r40-repair-generator"
cp "$HERE/r36os-r40-firstboot-repair.service" "$WORK/update/payload/root/etc/systemd/system/r36os-r40-firstboot-repair.service"
chmod 0644 "$WORK/update/payload/root/etc/systemd/system/r36os-r40-firstboot-repair.service"

cp "$FSCK_STATIC" "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static"
chmod 0755 "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static"
file "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static" | grep -q 'ARM aarch64'
file "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static" | grep -q 'statically linked'

# One-shot marker. It is deliberately excluded from the persistent core manifest.
printf '%s\n' 'R40 one-time R36UPDATE repair gate' > "$WORK/update/payload/root/etc/r36os/r40-r36update-repair-once"
chmod 0644 "$WORK/update/payload/root/etc/r36os/r40-r36update-repair-once"

cat > "$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R40"
R36OS_PACKAGE_VERSION="0.5.40.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-28"
R36OS_COMPATIBILITY="General private diagnostics upload plus verified R36UPDATE FAT repair"
R36OS_NOTES="Alpha 5R40 keeps candidate $CID and Linux $KREL unchanged. Diagnostics exports include bounded privacy-redacted game/OS/kernel evidence and target the dedicated private GitHub inbox when a device-local token is present. A one-time first-boot gate safely repairs the confirmed dirty R36UPDATE FAT filesystem only when the exact mmcblk0p3 warning is present."
EOF_RELEASE

cat > "$WORK/update/payload/root/opt/r36os/features/alpha5r40" <<EOF_FEATURE
R36OS Alpha 5R40
- Diagnostics A(bottom) export now queues/uploads privacy-redacted game, OS and kernel evidence.
- Default private diagnostics destination: Hewitt554/R36OS-Device-Logs.
- Full manual archive remains local.
- One-time exact-device R36UPDATE FAT repair gate with verified pre-repair backup.
- K1 candidate and kernel binaries unchanged.
EOF_FEATURE
chmod 0644 "$WORK/update/payload/root/etc/r36os-release" "$WORK/update/payload/root/opt/r36os/features/alpha5r40"

"$HERE/r36os-github-diagnostics" selftest | grep -q 'PASS'

# Patch the inherited full core manifest with R40's persistent files.
python3 - "$WORK/base/payload/root/etc/r36os-core-manifest.sha256" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}
for line in base.read_text().splitlines():
    if not line.strip(): continue
    sha,path=line.split(None,1)
    entries[path.strip()]=sha
paths=[
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-github-diagnostics',
'/usr/local/bin/r36os-export-current-logs',
'/usr/local/bin/r36os-r36update-repair',
'/usr/local/bin/r36os-r40-firstboot-repair',
'/usr/local/libexec/r36os/fsck.fat-static',
'/usr/lib/systemd/system-generators/r36os-r40-repair-generator',
'/etc/systemd/system/r36os-r40-firstboot-repair.service',
]
for path in paths:
    p=root/path.lstrip('/')
    entries[path]=hashlib.sha256(p.read_bytes()).hexdigest()
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in entries))
PY

cat > "$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.40.0
hardware=R36XX-RK3326
base_version=0.5.39.0
channel=system-core
requires_reboot=true
description=Alpha 5R40 adds bounded privacy-redacted game/OS/kernel GitHub diagnostics and a fail-closed one-time repair path for the confirmed dirty R36UPDATE FAT filesystem. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
remote_diagnostics=private-inbox-game-os-kernel
r36update_repair=one-time-exact-device-backed-up-offline-verified
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > checksums.sha256)

if find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'; then
  echo 'active boot/module payload forbidden' >&2; exit 20
fi
if find "$WORK/update/payload/root" -type l -print -quit | grep -q .; then
  echo 'symlink payload forbidden' >&2; exit 21
fi
if find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'; then
  echo 'R40 unexpectedly carries K1 binary' >&2; exit 22
fi

grep -q '0.5.40.0' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
grep -q '0.5.40.0' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"
! grep -q '0.5.39.0' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
! grep -q '0.5.39.0' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"

grep -q 'Hewitt554/R36OS-Device-Logs' "$WORK/update/payload/root/usr/local/bin/r36os-github-diagnostics"
grep -q 'latest-game-session' "$WORK/update/payload/root/usr/local/bin/r36os-github-diagnostics"
grep -q 'find "$tmp" -type f -print0' "$WORK/update/payload/root/usr/local/bin/r36os-github-diagnostics"
grep -q 'r36os-github-diagnostics upload-queued' "$WORK/update/payload/root/usr/local/bin/r36os-export-current-logs"

grep -q 'EXPECTED_DEV="${R36OS_R36UPDATE_DEV:-/dev/mmcblk0p3}"' "$WORK/update/payload/root/usr/local/bin/r36os-r36update-repair"
grep -q 'EXPECTED_UUID="${R36OS_R36UPDATE_UUID:-C49E-0225}"' "$WORK/update/payload/root/usr/local/bin/r36os-r36update-repair"
grep -q 'umount "$MOUNT"' "$WORK/update/payload/root/usr/local/bin/r36os-r36update-repair"
! grep -Eq 'umount[[:space:]]+-(f|l)|umount[[:space:]]+--force|umount[[:space:]]+--lazy' "$WORK/update/payload/root/usr/local/bin/r36os-r36update-repair"

( cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-28 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n > "$OUT/$NAME" )
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" > "$OUT/$NAME.sha256"

AUD="$WORK/audit"
mkdir -p "$AUD"
tar -xzf "$OUT/$NAME" -C "$AUD"
(cd "$AUD" && sha256sum -c checksums.sha256 >/dev/null)
for f in "$AUD"/payload/root/usr/local/bin/r36os-* "$AUD"/payload/root/usr/lib/systemd/system-generators/r36os-r40-repair-generator; do
  bash -n "$f"
done
"$AUD/payload/root/usr/local/bin/r36os-github-diagnostics" selftest | grep -q PASS
[[ "$(sha256sum "$AUD/payload/root/usr/local/libexec/r36os/fsck.fat-static" | awk '{print $1}')" == "$EXPECTED_FSCK" ]]

cat > "$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.40.0
base_version=0.5.39.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat > "$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R40 release build PASS
base_version=0.5.39.0
version=0.5.40.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
source_r39_sha256=$EXPECTED_R39
static_fsck_sha256=$EXPECTED_FSCK
remote_diagnostics=private-inbox-game-os-kernel
r36update_repair=exact-device-backed-up-offline-verified-firstboot
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R40_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
