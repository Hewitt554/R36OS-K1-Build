#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
R40="${1:?verified Alpha5R40 .r36upd required}"
OUT="${2:?output directory required}"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r41'
NAME='00-R36OS-Alpha5R41-FirstBootRepairFix-FromR40.r36upd'
EXPECTED_R40='448c056d9b1eac99443d0fad1ff10be9c9b40c7a8ffc4be33015c52d44ecd1e2'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r41-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/base"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/etc/systemd/system"   "$WORK/update/payload/root/etc/systemd/system-generators"   "$WORK/update/payload/root/lib/systemd/system-generators"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

[[ "$(sha256sum "$R40" | awk '{print $1}')" == "$EXPECTED_R40" ]] || { echo 'R40 source package SHA-256 mismatch' >&2; exit 10; }
tar -xzf "$R40" -C "$WORK/base"
(cd "$WORK/base" && sha256sum -c checksums.sha256 >/dev/null)
[[ "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.40.0' ]] || { echo 'R40 base version mismatch' >&2; exit 11; }
[[ "$(awk -F= '$1=="base_version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.39.0' ]] || { echo 'R40 source base mismatch' >&2; exit 12; }

# Carry K1 userspace helpers forward; kernel candidate binaries remain untouched.
python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
if src.count("0.5.40.0") != 1:
    raise SystemExit("unexpected R40 prepare version-guard count")
out=src.replace("0.5.40.0","0.5.41.0")
if "0.5.40.0" in out:
    raise SystemExit("stale R40 prepare identity remains")
Path(sys.argv[2]).write_text(out)
PY

python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-slot" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
checks={"0.5.40.0":1,"Alpha 5R40":1,"r40-runtime-lock":1}
for needle,count in checks.items():
    if src.count(needle) != count:
        raise SystemExit(f"unexpected R40 slot identity count for {needle}")
out=(src.replace("0.5.40.0","0.5.41.0")
        .replace("Alpha 5R40","Alpha 5R41")
        .replace("r40-runtime-lock","r41-runtime-lock"))
for needle in checks:
    if needle in out:
        raise SystemExit(f"stale R40 slot identity remains: {needle}")
Path(sys.argv[2]).write_text(out)
PY
chmod 0755 "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"

for f in r36os-export-current-logs-wrapper r36os-diagnostic-snapshot r36os-firstboot-update-repair r36os-firstboot-update-repair-generator; do
  bash -n "$HERE/$f"
done
cp "$HERE/r36os-export-current-logs-wrapper" "$WORK/update/payload/root/usr/local/bin/r36os-export-current-logs"
cp "$HERE/r36os-diagnostic-snapshot" "$WORK/update/payload/root/usr/local/bin/r36os-diagnostic-snapshot"
cp "$HERE/r36os-firstboot-update-repair" "$WORK/update/payload/root/usr/local/bin/r36os-firstboot-update-repair"
cp "$HERE/r36os-firstboot-update-repair-generator" "$WORK/update/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator"
cp "$HERE/r36os-firstboot-update-repair-generator" "$WORK/update/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator"
cp "$HERE/r36os-firstboot-update-repair.service" "$WORK/update/payload/root/etc/systemd/system/r36os-firstboot-update-repair.service"
chmod 0755   "$WORK/update/payload/root/usr/local/bin/r36os-export-current-logs"   "$WORK/update/payload/root/usr/local/bin/r36os-diagnostic-snapshot"   "$WORK/update/payload/root/usr/local/bin/r36os-firstboot-update-repair"   "$WORK/update/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator"   "$WORK/update/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator"
chmod 0644 "$WORK/update/payload/root/etc/systemd/system/r36os-firstboot-update-repair.service"

cat >"$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf" <<'EOF_MARK'
format=R36OS_R36UPDATE_REPAIR_ONCE_V1
release=0.5.41.0
reason=confirmed-mmcblk0p3-dirty-volume
EOF_MARK
chmod 0644 "$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf"

cat >"$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R41"
R36OS_PACKAGE_VERSION="0.5.41.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-28"
R36OS_COMPATIBILITY="First-boot R36UPDATE repair activation fix plus diagnostics evidence"
R36OS_NOTES="Alpha 5R41 fixes first-boot repair activation on the device's systemd 242 userspace. The K1 candidate $CID and Linux $KREL are unchanged."
EOF_RELEASE

cat >"$WORK/update/payload/root/opt/r36os/features/alpha5r41" <<EOF_FEATURE
R36OS Alpha 5R41
- Fixes the first-boot R36UPDATE repair service activation path observed on systemd 242.
- Installs the repair generator in both /etc/systemd/system-generators and /lib/systemd/system-generators.
- Preserves the verified R40/R39 diagnostics uploader and FAT repair engine.
- Adds repair/generator evidence to local and remote diagnostic snapshots.
- K1 candidate and kernel binaries unchanged.
EOF_FEATURE
chmod 0644 "$WORK/update/payload/root/etc/r36os-release" "$WORK/update/payload/root/opt/r36os/features/alpha5r41"

python3 - "$WORK/base/payload/root/etc/r36os-core-manifest.sha256" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}
for line in base.read_text().splitlines():
    if not line.strip(): continue
    sha,path=line.split(None,1)
    entries[path.strip()]=sha
for obsolete in [
'/usr/local/bin/r36os-r40-github-snapshot',
'/usr/local/bin/r36os-r40-firstboot-repair',
'/usr/lib/systemd/system-generators/r36os-r40-repair-generator',
'/etc/systemd/system/r36os-r40-firstboot-repair.service',
]:
    entries.pop(obsolete,None)
for path in [
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-export-current-logs',
'/usr/local/bin/r36os-diagnostic-snapshot',
'/usr/local/bin/r36os-firstboot-update-repair',
'/etc/systemd/system-generators/r36os-firstboot-update-repair-generator',
'/lib/systemd/system-generators/r36os-firstboot-update-repair-generator',
'/etc/systemd/system/r36os-firstboot-update-repair.service',
]:
    p=root/path.lstrip('/')
    entries[path]=hashlib.sha256(p.read_bytes()).hexdigest()
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in entries))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.41.0
hardware=R36XX-RK3326
base_version=0.5.40.0
channel=system-core
requires_reboot=true
description=Alpha 5R41 fixes first-boot activation of the verified R36UPDATE FAT repair path on systemd 242 and improves repair evidence in diagnostics. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r36update_repair_activation=systemd242-generator-path-fix
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

if find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'; then
  echo 'active boot/module payload forbidden' >&2; exit 20
fi
if find "$WORK/update/payload/root" -type l -print -quit | grep -q .; then
  echo 'symlink payload forbidden' >&2; exit 21
fi
if find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'; then
  echo 'R41 unexpectedly carries K1 binary' >&2; exit 22
fi
if grep -R -n -E '0\.5\.40\.0|Alpha[[:space:]]*5R40|r40-runtime-lock'   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/etc/systemd/system-generators"   "$WORK/update/payload/root/lib/systemd/system-generators" 2>/dev/null; then
  echo 'stale R40 runtime identity found in R41 payload' >&2
  exit 23
fi

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-28 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

AUD="$WORK/audit"
mkdir -p "$AUD"
tar -xzf "$OUT/$NAME" -C "$AUD"
(cd "$AUD" && sha256sum -c checksums.sha256 >/dev/null)
for f in "$AUD"/payload/root/usr/local/bin/r36os-* "$AUD"/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator "$AUD"/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator; do
  bash -n "$f"
done

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.41.0
base_version=0.5.40.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R41 release build PASS
base_version=0.5.40.0
version=0.5.41.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
source_r40_sha256=$EXPECTED_R40
repair_activation=systemd242-generator-path-fix
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R41_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
