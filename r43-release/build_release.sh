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
EXPECTED_SOURCE='64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527'
EXPECTED_R42_EXPORT='ef3330f91db693f8278952b67453fe096e70b48bcbce07d029681ff90894cd40'
EXPECTED_R42_PREPARE='0336d0f6d389641ddd4305a4d3f87ea85702fdeb5b750815397369e5160d3815'
EXPECTED_R42_SLOT='8ac6a7ec87d218c468fc1b4330ba61ad786eb6a728a5da7425b06379ce487805'
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

# Reconstruct the non-secret R42 core state from the exact R41 scripts. This
# intentionally does not need, contain, or inspect the private R42 credential.
python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/r42/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if s.count("0.5.41.0") != 1: raise SystemExit("unexpected R41 prepare identity")
Path(sys.argv[2]).write_text(s.replace("0.5.41.0","0.5.42.0"))
PY
python3 - "$WORK/base/payload/root/usr/local/bin/r36os-kernel-slot" "$WORK/r42/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
for n in ("0.5.41.0","Alpha 5R41","r41-runtime-lock"):
    if s.count(n) != 1: raise SystemExit("unexpected R41 slot identity: "+n)
s=s.replace("0.5.41.0","0.5.42.0").replace("Alpha 5R41","Alpha 5R42").replace("r41-runtime-lock","r42-runtime-lock")
Path(sys.argv[2]).write_text(s)
PY
cp "$HERE/r36os-export-current-logs" "$WORK/r42/r36os-export-current-logs"
[[ "$(sha256sum "$WORK/r42/r36os-export-current-logs"|awk '{print $1}')" == "$EXPECTED_R42_EXPORT" ]] || exit 14
[[ "$(sha256sum "$WORK/r42/r36os-kernel-next-prepare"|awk '{print $1}')" == "$EXPECTED_R42_PREPARE" ]] || exit 15
[[ "$(sha256sum "$WORK/r42/r36os-kernel-slot"|awk '{print $1}')" == "$EXPECTED_R42_SLOT" ]] || exit 16

# Advance only the release-bound guards from the proven R42 runtime to R43.
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
reason=retry-with-old-runtime-fat-checker-after-r42-rc134
EOF_MARK
chmod 0644 "$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf"

cat >"$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R43"
R36OS_PACKAGE_VERSION="0.5.43.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-28"
R36OS_COMPATIBILITY="R36UPDATE FAT checker runtime compatibility fix and complete repair diagnostics"
R36OS_NOTES="Alpha 5R43 replaces the R40 static FAT checker after the physical R42 repair aborted with rc 134. The checker is rebuilt with an older AArch64 glibc runtime, repair uses an explicit read-only preflight plus independent post-repair verification, and full fsck output is included in diagnostics. K1 candidate $CID and Linux $KREL are unchanged."
EOF_RELEASE
cat >"$WORK/update/payload/root/opt/r36os/features/alpha5r43" <<EOF_FEATURE
R36OS Alpha 5R43
- Replaces the static FAT checker that aborted with rc 134 on the physical R36S.
- Uses an older AArch64 glibc toolchain and rejects the newer SME runtime symbol in validation.
- Runs a read-only checker preflight before any repair write.
- Uses fsck.fat -a without redundant -V, then a separate fsck.fat -n verification.
- Preserves complete latest fsck output in GitHub diagnostics.
- Re-arms one-time R36UPDATE repair.
- K1 candidate and kernel binaries unchanged.
EOF_FEATURE

python3 - "$WORK/base/payload/root/etc/r36os-core-manifest.sha256" "$WORK/r42" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); r42=Path(sys.argv[2]); root=Path(sys.argv[3]); out=Path(sys.argv[4])
entries={}
for line in base.read_text().splitlines():
    if not line.strip(): continue
    sha,path=line.split(None,1); entries[path.strip()]=sha
# Exact non-secret R42 core delta.
for path,name in [
('/usr/local/bin/r36os-export-current-logs','r36os-export-current-logs'),
('/usr/local/bin/r36os-kernel-next-prepare','r36os-kernel-next-prepare'),
('/usr/local/bin/r36os-kernel-slot','r36os-kernel-slot')]:
    entries[path]=hashlib.sha256((r42/name).read_bytes()).hexdigest()
# R43 core delta.
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
description=Alpha 5R43 fixes the real-device FAT checker rc 134 failure, adds read-only preflight and complete repair diagnostics, and re-arms the one-time R36UPDATE repair. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r36update_repair=old-runtime-fsck-readonly-preflight-explicit-verify
remote_diagnostics=preserve-full-latest-fsck-log
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

if find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'; then echo 'active boot/module payload forbidden' >&2; exit 20; fi
if find "$WORK/update/payload/root" -type l -print -quit | grep -q .; then echo 'symlink payload forbidden' >&2; exit 21; fi
if find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'; then echo 'R43 unexpectedly carries K1 binary' >&2; exit 22; fi
if find "$WORK/update/payload/root" -type f | grep -q '^.*/r36state/secrets/'; then echo 'R43 must not ship device credentials' >&2; exit 23; fi
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
The fsck.fat binary was built using an older AArch64 GNU libc cross-toolchain to avoid the newer runtime involved in the physical-device rc 134 failure investigation.
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
dosfstools_source_sha256=$EXPECTED_SOURCE
fsck_sha256=$FSCK_SHA
repair_change=old-runtime-readonly-preflight-no-redundant-V-explicit-verify
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R43_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA fsck_sha256=$FSCK_SHA"
