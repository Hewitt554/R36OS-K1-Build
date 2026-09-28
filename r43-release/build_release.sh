#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
R41="${1:?verified Alpha5R41 .r36upd required}"
FSCK_DIR="${2:?validated R43 fsck directory required}"
OUT="${3:?output directory required}"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r43'
NAME='00-R36OS-Alpha5R43-FATRepairCompatibility-FromR42.r36upd'
EXPECTED_R41='ac3e350a7332ee3da4624952a15cfdc83cb04c767038e0c0d1015a078a237567'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r43-release"

rm -rf "$WORK" "$OUT"
mkdir -p \
  "$WORK/base" \
  "$WORK/update/payload/root/etc/r36os" \
  "$WORK/update/payload/root/usr/local/bin" \
  "$WORK/update/payload/root/usr/local/libexec/r36os" \
  "$WORK/update/payload/root/etc/systemd/system" \
  "$WORK/update/payload/root/etc/systemd/system-generators" \
  "$WORK/update/payload/root/lib/systemd/system-generators" \
  "$WORK/update/payload/root/opt/r36os/features" \
  "$OUT"

[[ "$(sha256sum "$R41" | awk '{print $1}')" == "$EXPECTED_R41" ]] || { echo 'R41 source package SHA-256 mismatch' >&2; exit 10; }
tar -xzf "$R41" -C "$WORK/base"
(cd "$WORK/base" && sha256sum -c checksums.sha256 >/dev/null)
[[ "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.41.0' ]] || { echo 'R41 base version mismatch' >&2; exit 11; }

FSCK="$FSCK_DIR/fsck.fat-static"
FSCK_SUM="$FSCK_DIR/fsck.fat-static.sha256"
[ -x "$FSCK" ] && [ -s "$FSCK_SUM" ] || { echo 'validated fsck artifact missing' >&2; exit 12; }
(cd "$FSCK_DIR" && sha256sum -c fsck.fat-static.sha256 >/dev/null)
cp "$FSCK" "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static"
cp "$FSCK_SUM" "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static.sha256"
chmod 0755 "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static"
chmod 0644 "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static.sha256"

# Carry the release-bound K1 userspace helpers forward from the exact R41 package,
# changing release identity only. K1 binaries themselves remain untouched.
python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
if src.count('0.5.41.0') != 1:
    raise SystemExit('unexpected R41 prepare version-guard count')
out=src.replace('0.5.41.0','0.5.43.0')
for stale in ('0.5.41.0','0.5.42.0'):
    if stale in out: raise SystemExit(f'stale prepare identity: {stale}')
Path(sys.argv[2]).write_text(out)
PY
python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-slot" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
checks={'0.5.41.0':1,'Alpha 5R41':1,'r41-runtime-lock':1}
for needle,count in checks.items():
    if src.count(needle) != count: raise SystemExit(f'unexpected R41 slot identity count: {needle}')
out=(src.replace('0.5.41.0','0.5.43.0')
        .replace('Alpha 5R41','Alpha 5R43')
        .replace('r41-runtime-lock','r43-runtime-lock'))
for stale in ('0.5.41.0','0.5.42.0','Alpha 5R41','Alpha 5R42','r41-runtime-lock','r42-runtime-lock'):
    if stale in out: raise SystemExit(f'stale slot identity: {stale}')
Path(sys.argv[2]).write_text(out)
PY
chmod 0755 "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"

# R41 generator/service layout is physically proven on the user's systemd 242 device.
cp "$WORK/base/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator" \
  "$WORK/update/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator"
cp "$WORK/base/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator" \
  "$WORK/update/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator"
cp "$WORK/base/payload/root/etc/systemd/system/r36os-firstboot-update-repair.service" \
  "$WORK/update/payload/root/etc/systemd/system/r36os-firstboot-update-repair.service"
chmod 0755 "$WORK/update/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator" \
  "$WORK/update/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator"
chmod 0644 "$WORK/update/payload/root/etc/systemd/system/r36os-firstboot-update-repair.service"

for f in r36os-r36update-repair r36os-firstboot-update-repair r36os-diagnostic-snapshot r36os-export-current-logs; do
  bash -n "$HERE/$f"
  cp "$HERE/$f" "$WORK/update/payload/root/usr/local/bin/$f"
  chmod 0755 "$WORK/update/payload/root/usr/local/bin/$f"
done

cat >"$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf" <<'EOF_MARK'
format=R36OS_R36UPDATE_REPAIR_ONCE_V1
release=0.5.43.0
reason=retry-with-target-validated-fsck
EOF_MARK
chmod 0644 "$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf"

cat >"$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R43"
R36OS_PACKAGE_VERSION="0.5.43.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-28"
R36OS_COMPATIBILITY="Target-validated R36UPDATE FAT repair compatibility retry"
R36OS_NOTES="Alpha 5R43 replaces only the userspace FAT checker/repair path proven to abort on Alpha 5R42. The K1 candidate $CID and Linux $KREL binaries are unchanged. Private diagnostics authentication already stored on R36STATE is preserved and is not included in this public package."
EOF_RELEASE

cat >"$WORK/update/payload/root/opt/r36os/features/alpha5r43" <<EOF_FEATURE
R36OS Alpha 5R43
- Replaces the R40 FAT checker with an AArch64 static dosfstools 4.2 build made on Ubuntu 20.04 with iconv disabled.
- CI executes the actual target binary under qemu on a deliberately dirty FAT32 image.
- Removes the redundant fsck -V internal verification pass; repair is -a followed by a separate -n verification.
- Re-arms one first-boot repair retry and preserves the physically proven systemd 242 generator/service wiring.
- Adds the newest full repair log and checker fingerprint to remote diagnostics.
- Preserves R42 private-log upload behavior without shipping any credential.
- K1 binaries unchanged: candidate $CID / Linux $KREL.
EOF_FEATURE
chmod 0644 "$WORK/update/payload/root/etc/r36os-release" "$WORK/update/payload/root/opt/r36os/features/alpha5r43"

python3 - "$WORK/base/payload/root/etc/r36os-core-manifest.sha256" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}
for line in base.read_text().splitlines():
    if not line.strip(): continue
    sha,path=line.split(None,1)
    entries[path.strip()]=sha
for path in [
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-r36update-repair',
'/usr/local/bin/r36os-firstboot-update-repair',
'/usr/local/bin/r36os-diagnostic-snapshot',
'/usr/local/bin/r36os-export-current-logs',
'/usr/local/libexec/r36os/fsck.fat-static',
'/usr/local/libexec/r36os/fsck.fat-static.sha256',
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
version=0.5.43.0
hardware=R36XX-RK3326
base_version=0.5.42.0
channel=system-core
requires_reboot=true
description=Alpha 5R43 replaces the userspace FAT checker that aborted on the physical R36S, genuinely target-tests the replacement path, re-arms one safe R36UPDATE repair retry, and improves repair diagnostics. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r36update_repair=target-validated-static-noiconv-explicit-repair-then-readonly-verify
remote_diagnostics=preserve-r42-device-local-auth-no-secret-in-package
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

if find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'; then
  echo 'active boot/module payload forbidden' >&2; exit 20
fi
if find "$WORK/update/payload/root" -type l -print -quit | grep -q .; then
  echo 'symlink payload forbidden' >&2; exit 21
fi
if find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'; then
  echo 'R43 unexpectedly carries K1 binary' >&2; exit 22
fi
if find "$WORK/update/payload/root" -type f | grep -Eq '/r36state/(secrets|config)/'; then
  echo 'R43 public package must not carry device-local diagnostics auth/config' >&2; exit 23
fi
if grep -R -n -E 'github_pat_|ghp_|github-diagnostics\.token' "$WORK/update/payload/root" 2>/dev/null; then
  echo 'credential material/reference unexpectedly present in public R43 payload' >&2; exit 24
fi
if grep -R -n -E '0\.5\.(41|42)\.0|Alpha[[:space:]]*5R4[12]|r4[12]-runtime-lock' \
  "$WORK/update/payload/root/usr/local/bin" 2>/dev/null; then
  echo 'stale R41/R42 runtime identity found in R43 payload' >&2; exit 25
fi

grep -q '"$FSCK" -a "$EXPECTED_DEV"' "$WORK/update/payload/root/usr/local/bin/r36os-r36update-repair"
! grep -q '"$FSCK" -a -V' "$WORK/update/payload/root/usr/local/bin/r36os-r36update-repair"
grep -q 'r36update-repair-full-log' "$WORK/update/payload/root/usr/local/bin/r36os-diagnostic-snapshot"

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
version=0.5.43.0
base_version=0.5.42.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R43 release build PASS
base_version=0.5.42.0
version=0.5.43.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
source_r41_sha256=$EXPECTED_R41
fsck_sha256=$(awk '{print $1}' "$FSCK_SUM")
fsck_build=dosfstools-4.2-static-aarch64-ubuntu20.04-without-iconv
repair_flow=backup-normal-unmount-fsck-a-readonly-fsck-n-readonly-candidate-check-final-unmount
private_diagnostics_credential_in_package=no
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R43_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
