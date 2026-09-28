#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
R38="${1:?verified Alpha5R38 .r36upd required}"
OUT="${2:?output directory required}"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r39'
NAME='00-R36OS-Alpha5R39-K1FATRemoteDiagnostics-FromR38.r36upd'
EXPECTED_R38='68db42212fc0e13a9bad777daf68f4634bb86f58aa2347a923dde8cd71db30c0'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r39-release"
rm -rf "$WORK" "$OUT"; mkdir -p "$WORK/base" "$WORK/update/payload/root/etc" "$WORK/update/payload/root/usr/local/bin" "$WORK/update/payload/root/opt/r36os/features" "$OUT"
[[ "$(sha256sum "$R38"|awk '{print $1}')" == "$EXPECTED_R38" ]] || { echo 'R38 source package SHA-256 mismatch' >&2; exit 10; }
tar -xzf "$R38" -C "$WORK/base" manifest.conf payload/root/etc/r36os-core-manifest.sha256
[[ "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.38.0' ]] || { echo 'R38 base version mismatch' >&2; exit 11; }
[[ "$(awk -F= '$1=="base_version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.37.0' ]] || { echo 'R38 source base mismatch' >&2; exit 12; }
for f in r36os-kernel-next-prepare r36os-kernel-slot r36os-kernel-next-health r36os-github-diagnostics r36os-export-current-logs; do
  bash -n "$HERE/$f"
  cp "$HERE/$f" "$WORK/update/payload/root/usr/local/bin/$f"
  chmod 0755 "$WORK/update/payload/root/usr/local/bin/$f"
done
"$HERE/r36os-github-diagnostics" selftest | grep -q 'PASS'
cat > "$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R39"
R36OS_PACKAGE_VERSION="0.5.39.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-28"
R36OS_COMPATIBILITY="K1 Boot Next Once FAT-device guard fix plus queue-first privacy-redacted GitHub diagnostics"
R36OS_NOTES="Alpha 5R39 keeps candidate $CID and Linux $KREL unchanged. R36UPDATE FAT warnings are matched only to the actual update device. K1 failures, fallbacks and manual log exports queue redacted diagnostics. Remote upload supports automatic/off only and requires a verified private GitHub logs repo plus fine-grained token."
EOF_RELEASE
printf '%s\n' 'R36OS Alpha 5R39: device-specific R36UPDATE FAT guard plus queue-first privacy-redacted GitHub diagnostics; automatic/off upload only; manual exports also queue a safe diagnostic bundle; K1 binaries remain unchanged.' > "$WORK/update/payload/root/opt/r36os/features/alpha5r39"
chmod 0644 "$WORK/update/payload/root/etc/r36os-release" "$WORK/update/payload/root/opt/r36os/features/alpha5r39"
python3 - "$WORK/base/payload/root/etc/r36os-core-manifest.sha256" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3]); entries={}
for line in base.read_text().splitlines():
    if not line.strip(): continue
    sha,path=line.split(None,1); entries[path.strip()]=sha
for path in [
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-kernel-next-health',
'/usr/local/bin/r36os-github-diagnostics',
'/usr/local/bin/r36os-export-current-logs']:
    p=root/path.lstrip('/')
    entries[path]=hashlib.sha256(p.read_bytes()).hexdigest()
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in entries))
PY
cat > "$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.39.0
hardware=R36XX-RK3326
base_version=0.5.38.0
channel=system-core
requires_reboot=true
description=Alpha 5R39 fixes the K1 Boot Next Once FAT-health guard so warnings are bound to the actual R36UPDATE device and adds queue-first privacy-redacted GitHub diagnostics. K1 Image, DTB, uInitrd and modules are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
remote_diagnostics=queue-first-manual-export-plus-k1-failure-private-repo-automatic-or-off
EOF_MAN
(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > checksums.sha256)
if find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'; then echo 'active boot/module payload forbidden' >&2; exit 20; fi
if find "$WORK/update/payload/root" -type l -print -quit | grep -q .; then echo 'symlink payload forbidden' >&2; exit 21; fi
# R39 must not carry/rewrite the K1 binaries themselves.
if find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'; then echo 'R39 unexpectedly carries K1 binary' >&2; exit 22; fi
# Verify release-bound K1 helpers are coherent with R39.
grep -q '0.5.39.0' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
grep -q '0.5.39.0' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"
# Verify the broad R38 FAT guard is gone and exact-device evidence is present.
! grep -Fq "dmesg 2>/dev/null | grep -Eiq 'FAT-fs.*" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
grep -q 'source_basename=' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
grep -q 'grep -F "FAT-fs ($DEV_BASE):"' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
# R39 exposes only automatic/off; ask-first is deliberately withheld until a real UI consent flow exists.
! grep -Eq 'automatic\|ask\|off|automatic\|ask|ask\|off' "$WORK/update/payload/root/usr/local/bin/r36os-github-diagnostics"
grep -q "public-build-repo-forbidden" "$WORK/update/payload/root/usr/local/bin/r36os-github-diagnostics"
grep -q "private-repo-required-or-inaccessible" "$WORK/update/payload/root/usr/local/bin/r36os-github-diagnostics"
# Manual exports queue the same small privacy-redacted diagnostic bundle; they do not upload the full manual archive.
grep -q 'r36os-github-diagnostics capture "export-\$WHY"' "$WORK/update/payload/root/usr/local/bin/r36os-export-current-logs"
( cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-28 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n > "$OUT/$NAME" )
SHA="$(sha256sum "$OUT/$NAME"|awk '{print $1}')"; SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" > "$OUT/$NAME.sha256"
AUD="$WORK/audit"; mkdir -p "$AUD"; tar -xzf "$OUT/$NAME" -C "$AUD"; (cd "$AUD" && sha256sum -c checksums.sha256 >/dev/null)
for f in "$AUD"/payload/root/usr/local/bin/r36os-*; do bash -n "$f"; done
"$AUD/payload/root/usr/local/bin/r36os-github-diagnostics" selftest | grep -q PASS
cat > "$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.39.0
base_version=0.5.38.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST
cat > "$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R39 GitHub release build PASS
base_version=0.5.38.0
version=0.5.39.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
fat_guard=device-specific-r36update
remote_diagnostics=queue-first-redacted-manual-export-plus-k1-failure-private-repo-auth-required
package=$NAME
size_bytes=$SIZE
sha256=$SHA
source_r38_sha256=$EXPECTED_R38
EOF_REPORT
echo "R39_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
