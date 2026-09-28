#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
R41="${1:?verified Alpha5R41 .r36upd required}"
FSCK="${2:?validated old-runtime AArch64 fsck.fat required}"
SOURCE_TAR="${3:?dosfstools-4.2 source tarball required}"
OUT="${4:?output directory required}"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r43'
NAME='00-R36OS-Alpha5R43-FATRuntimeFix-FromR42.r36upd'
EXPECTED_R41='ac3e350a7332ee3da4624952a15cfdc83cb04c767038e0c0d1015a078a237567'
PRIVATE_R42_PACKAGE_SHA='cbdfa3e3fc37e2c66b3233d17ee1385e3d9deedf8b093855150ced9c218ddc44'
EXPECTED_R42_CORE_MANIFEST='c15ab3d6da735f1a9db034a3a2c12b2150afb7a07defd9d888ccbfb63c95c898'
EXPECTED_SOURCE='64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r43-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/base" "$WORK/r42"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/etc/systemd/system"   "$WORK/update/payload/root/etc/systemd/system-generators"   "$WORK/update/payload/root/lib/systemd/system-generators"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/usr/local/libexec/r36os"   "$WORK/update/payload/root/opt/r36os/features" "$OUT"

[[ "$(sha256sum "$R41" | awk '{print $1}')" == "$EXPECTED_R41" ]] || { echo 'R41 source package SHA-256 mismatch' >&2; exit 10; }
[[ "$(sha256sum "$SOURCE_TAR" | awk '{print $1}')" == "$EXPECTED_SOURCE" ]] || { echo 'dosfstools source SHA mismatch' >&2; exit 11; }
tar -xzf "$R41" -C "$WORK/base"
(cd "$WORK/base" && sha256sum -c checksums.sha256 >/dev/null)
[[ "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.41.0' ]] || exit 12
[[ "$(awk -F= '$1=="base_version"{print $2}' "$WORK/base/manifest.conf")" == '0.5.40.0' ]] || exit 13

python3 "$HERE/verify_r42_baseline.py" "$WORK/base" "$HERE/r36os-export-current-logs" "$WORK/r42"
[[ "$(sha256sum "$WORK/r42/r36os-core-manifest.sha256" | awk '{print $1}')" == "$EXPECTED_R42_CORE_MANIFEST" ]] || exit 14

# Advance only the release-bound K1 userspace guards from exact reconstructed
# R42 non-secret state. K1 candidate binaries themselves remain untouched.
python3 - "$WORK/r42/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if s.count("0.5.42.0") != 1: raise SystemExit("unexpected R42 prepare identity")
Path(sys.argv[2]).write_text(s.replace("0.5.42.0","0.5.43.0"))
PY
python3 - "$WORK/r42/r36os-kernel-slot" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
for n in ("0.5.42.0","Alpha 5R42","r42-runtime-lock"):
    if s.count(n) != 1: raise SystemExit("unexpected R42 slot identity: "+n)
s=s.replace("0.5.42.0","0.5.43.0").replace("Alpha 5R42","Alpha 5R43").replace("r42-runtime-lock","r43-runtime-lock")
Path(sys.argv[2]).write_text(s)
PY

for f in r36os-r36update-repair r36os-firstboot-update-repair r36os-diagnostic-snapshot r36os-export-current-logs r36os-firstboot-update-repair-generator; do
  bash -n "$HERE/$f"
done
python3 -m py_compile "$HERE/verify_r42_baseline.py"

cp "$HERE/r36os-r36update-repair" "$WORK/update/payload/root/usr/local/bin/r36os-r36update-repair"
cp "$HERE/r36os-firstboot-update-repair" "$WORK/update/payload/root/usr/local/bin/r36os-firstboot-update-repair"
cp "$HERE/r36os-diagnostic-snapshot" "$WORK/update/payload/root/usr/local/bin/r36os-diagnostic-snapshot"
cp "$HERE/r36os-export-current-logs" "$WORK/update/payload/root/usr/local/bin/r36os-export-current-logs"
cp "$HERE/r36os-firstboot-update-repair-generator" "$WORK/update/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator"
cp "$HERE/r36os-firstboot-update-repair-generator" "$WORK/update/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator"
cp "$HERE/r36os-firstboot-update-repair.service" "$WORK/update/payload/root/etc/systemd/system/r36os-firstboot-update-repair.service"
cp "$FSCK" "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static"

chmod 0755 "$WORK/update/payload/root/usr/local/bin/"*   "$WORK/update/payload/root/usr/local/libexec/r36os/fsck.fat-static"   "$WORK/update/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator"   "$WORK/update/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator"
chmod 0644 "$WORK/update/payload/root/etc/systemd/system/r36os-firstboot-update-repair.service"

cat >"$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf" <<'EOF_MARK'
format=R36OS_R36UPDATE_REPAIR_ONCE_V1
release=0.5.43.0
reason=retry-after-r42-fsck-abort-with-readonly-preflight
EOF_MARK
chmod 0644 "$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf"

cat >"$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R43"
R36OS_PACKAGE_VERSION="0.5.43.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-28"
R36OS_COMPATIBILITY="R36UPDATE FAT checker compatibility fix with fail-before-write preflight and complete repair diagnostics"
R36OS_NOTES="Alpha 5R43 replaces the R40 static FAT checker after the physical R42 repair aborted with rc 134. The checker uses an older AArch64 glibc runtime, runs help and read-only preflight before any repair write, repairs without same-process -V verification, then verifies in a fresh read-only process. K1 candidate $CID and Linux $KREL are unchanged."
EOF_RELEASE

cat >"$WORK/update/payload/root/opt/r36os/features/alpha5r43" <<EOF_FEATURE
R36OS Alpha 5R43
- Exact non-secret R42 baseline reconstruction is hash-verified before build.
- Replaces the static FAT checker that aborted with rc 134 on the physical R36S.
- Uses an older AArch64 glibc 2.31-era cross-toolchain targeted at ARMv8-A/Cortex-A35.
- Runs fsck --help and a real-volume fsck -n preflight before any repair write.
- Uses fsck -a without same-process -V, then an independent fsck -n verification.
- Clears stale repair result files before each attempt.
- Preserves the complete latest fsck output in privacy-redacted diagnostics.
- Removes stale version-labelled diagnostic snapshot files before capture.
- Re-arms the one-time R36UPDATE repair.
- K1 candidate and kernel binaries unchanged.
EOF_FEATURE

python3 - "$WORK/r42/r36os-core-manifest.sha256" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}
for line in base.read_text().splitlines():
    if not line.strip(): continue
    digest,path=line.split(None,1); entries[path.strip()]=digest
for path in [
'/usr/local/bin/r36os-export-current-logs',
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-r36update-repair',
'/usr/local/libexec/r36os/fsck.fat-static',
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
version=0.5.43.0
hardware=R36XX-RK3326
base_version=0.5.42.0
channel=system-core
requires_reboot=true
description=Alpha 5R43 fixes the real-device FAT checker rc 134 path using an older runtime plus fail-before-write read-only preflight, independent verification and complete diagnostics. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r36update_repair=old-runtime-help-preflight-readonly-preflight-separate-verify
remote_diagnostics=complete-latest-fsck-log-no-stale-versioned-snapshot
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

if find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'; then echo 'active boot/module payload forbidden' >&2; exit 20; fi
if find "$WORK/update/payload/root" -type l -print -quit | grep -q .; then echo 'symlink payload forbidden' >&2; exit 21; fi
if find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'; then echo 'R43 unexpectedly carries K1 binary' >&2; exit 22; fi
if find "$WORK/update/payload/root" -type f | grep -q '/r36state/secrets/'; then echo 'R43 must not ship device credentials' >&2; exit 23; fi
if grep -R -a -n -E 'github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}' "$WORK/update" >/dev/null 2>&1; then echo 'credential-like token found in public R43 package source' >&2; exit 24; fi
if grep -R -n -E '0\.5\.42\.0|Alpha[[:space:]]*5R42|r42-runtime-lock' "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"; then
  echo 'stale R42 release identity in R43 K1 runtime' >&2; exit 25
fi

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-28 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

AUD="$WORK/audit"; mkdir -p "$AUD"; tar -xzf "$OUT/$NAME" -C "$AUD"; (cd "$AUD" && sha256sum -c checksums.sha256 >/dev/null)
for f in "$AUD"/payload/root/usr/local/bin/r36os-* "$AUD"/payload/root/etc/systemd/system-generators/r36os-firstboot-update-repair-generator "$AUD"/payload/root/lib/systemd/system-generators/r36os-firstboot-update-repair-generator; do bash -n "$f"; done

cp "$SOURCE_TAR" "$OUT/dosfstools-4.2.tar.gz"
cat >"$OUT/THIRD_PARTY_NOTICES.txt" <<EOF_NOTICE
R36OS Alpha 5R43 includes a statically linked fsck.fat from dosfstools 4.2.
Upstream: https://github.com/dosfstools/dosfstools
Source archive SHA-256: $EXPECTED_SOURCE
The corresponding unmodified source archive is included with the R43 release.
The fsck.fat binary is built using a pinned older AArch64 GNU libc 2.31-era cross-toolchain and targeted at ARMv8-A/Cortex-A35.
EOF_NOTICE

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

FSCK_SHA="$(sha256sum "$FSCK"|awk '{print $1}')"
cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R43 release build PASS
base_version=0.5.42.0
version=0.5.43.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
source_r41_sha256=$EXPECTED_R41
private_r42_package_sha256=$PRIVATE_R42_PACKAGE_SHA
r42_nonsecret_core_manifest_sha256=$EXPECTED_R42_CORE_MANIFEST
dosfstools_source_sha256=$EXPECTED_SOURCE
fsck_sha256=$FSCK_SHA
repair_change=old-runtime-help-preflight-readonly-preflight-separate-verify
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R43_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA fsck_sha256=$FSCK_SHA"
