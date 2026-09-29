#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r43.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R43="$1"
OUT="$2"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r44'
NAME='00-R36OS-Alpha5R44-K1FATStaging-FromR43.r36upd'
EXPECTED_R43='cd4e66c08de18c0dbdd4ec3ff3babd5efcf6cc876113f1bd0f57aa1fc3ee421a'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r44-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/base"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha256sum "$R43" | awk '{print $1}')" = "$EXPECTED_R43" || { echo r43-sha-mismatch >&2; exit 10; }
tar -xzf "$R43" -C "$WORK/base"
(cd "$WORK/base" && sha256sum -c checksums.sha256 >/dev/null)
test "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" = 0.5.43.0 || { echo r43-version-mismatch >&2; exit 11; }
test "$(awk -F= '$1=="base_version"{print $2}' "$WORK/base/manifest.conf")" = 0.5.42.0 || { echo r43-base-mismatch >&2; exit 12; }

BASE="$WORK/base/payload/root"
for f in "$BASE/usr/local/bin/r36os-kernel-next-prepare" "$BASE/usr/local/bin/r36os-kernel-slot" "$BASE/etc/r36os-core-manifest.sha256"; do
  test -s "$f" || { echo "missing R43 base file: $f" >&2; exit 13; }
done

# Guard the exact physical failure lineage before replacing it.
test "$(grep -c '0.5.43.0' "$BASE/usr/local/bin/r36os-kernel-next-prepare")" -eq 1
test "$(grep -Fc '  cp -a "$SRC/." "$TMP/" || { rm -rf "$TMP"; fail 33 stage-copy; }' "$BASE/usr/local/bin/r36os-kernel-next-prepare")" -eq 1
bash -n "$HERE/r36os-kernel-next-prepare"
test "$(grep -c '0.5.44.0' "$HERE/r36os-kernel-next-prepare")" -eq 1
! grep -Eq '^[[:space:]]*cp[[:space:]]+-a([[:space:]]|$)' "$HERE/r36os-kernel-next-prepare"
grep -q 'cp -R "$SRC/." "$TMP/"' "$HERE/r36os-kernel-next-prepare"
grep -q 'candidate_tree_digest' "$HERE/r36os-kernel-next-prepare"

cp "$HERE/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"

python3 - "$BASE/usr/local/bin/r36os-kernel-slot" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
checks={'0.5.43.0':1,'Alpha 5R43':1,'r43-runtime-lock':1}
for needle,count in checks.items():
    if s.count(needle) != count:
        raise SystemExit(f'unexpected R43 slot identity: {needle} count={s.count(needle)}')
s=s.replace('0.5.43.0','0.5.44.0').replace('Alpha 5R43','Alpha 5R44').replace('r43-runtime-lock','r44-runtime-lock')
Path(sys.argv[2]).write_text(s)
PY

chmod 0755 "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"

cat >"$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R44"
R36OS_PACKAGE_VERSION="0.5.44.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="FAT-safe K1 Boot Next Once staging from Alpha 5R43"
R36OS_NOTES="Alpha 5R44 fixes physical code 33 stage-copy by replacing cp -a on R36UPDATE FAT with data-only staging plus exact tree/preflight/readback verification. K1 binaries are unchanged."
EOF_RELEASE

cat >"$WORK/update/payload/root/opt/r36os/features/alpha5r44" <<EOF_FEATURE
R36OS Alpha 5R44
- Fixes physical K1 Boot Next Once code 33 (stage-copy).
- Does not preserve unsupported Unix ownership metadata on R36UPDATE FAT.
- Uses a fresh candidate-bound sibling staging directory.
- Verifies the entire regular-file tree before and after activation.
- Runs existing K1 preflight before copy, on staged FAT data and after activation.
- Removes stale candidate-bound staging directories.
- Keeps the candidate size plus 64 MiB FAT headroom check.
- Does not re-run the R43 FAT repair.
- K1 candidate $CID / Linux $KREL binaries are unchanged.
EOF_FEATURE
chmod 0644 "$WORK/update/payload/root/etc/r36os-release" "$WORK/update/payload/root/opt/r36os/features/alpha5r44"

python3 - "$BASE/etc/r36os-core-manifest.sha256" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip():
        continue
    sha,path=line.split(None,1); path=path.strip()
    entries[path]=sha; order.append(path)
for path in ['/usr/local/bin/r36os-kernel-next-prepare','/usr/local/bin/r36os-kernel-slot']:
    p=root/path.lstrip('/')
    entries[path]=hashlib.sha256(p.read_bytes()).hexdigest()
    if path not in order:
        order.append(path)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.44.0
hardware=R36XX-RK3326
base_version=0.5.43.0
channel=system-core
requires_reboot=true
description=Alpha 5R44 fixes K1 stage-copy code 33 with FAT-safe candidate staging and exact staged-tree verification. K1 binaries are unchanged.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
k1_staging=fat-safe-data-copy-tree-digest-preflight-atomic-rename
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
opt/r36os/features/alpha5r44
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
EOF_FILES
(cd "$WORK/update/payload/root" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

test ! -e "$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf"
test ! -e "$WORK/update/payload/root/r36state"
! find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'
if grep -R -n -E 'github_pat_[A-Za-z0-9]|gh[pousr]_[A-Za-z0-9]' "$WORK/update/payload/root"; then
  echo credential-pattern-forbidden >&2; exit 25
fi

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

AUD="$WORK/audit"
mkdir -p "$AUD"
tar -xzf "$OUT/$NAME" -C "$AUD"
(cd "$AUD" && sha256sum -c checksums.sha256 >/dev/null)
bash -n "$AUD/payload/root/usr/local/bin/r36os-kernel-next-prepare"
bash -n "$AUD/payload/root/usr/local/bin/r36os-kernel-slot"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.44.0
base_version=0.5.43.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R44 audited release build PASS
base_version=0.5.43.0
version=0.5.44.0
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r43_source_sha256=$EXPECTED_R43
r43_prepare_sha256=$(sha256sum "$BASE/usr/local/bin/r36os-kernel-next-prepare" | awk '{print $1}')
r44_prepare_sha256=$(sha256sum "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" | awk '{print $1}')
staging=fat-safe-data-copy-tree-digest-preflight-atomic-rename
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R44_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
