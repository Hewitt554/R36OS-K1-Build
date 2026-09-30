#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r54.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R54="$1"; OUT="$2"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r55'
NAME='00-R36OS-Alpha5R55-ModuleReuseRebind-FromR54.r36upd'
EXPECTED_R54='ed3b331fe1fb6cb23bf60aa997d2bd1fc6634039f2ec176d93d0dd2561ce166e'
CID='4c70486f70ba16acf7437403'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r55-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r54"   "$WORK/update/payload/root/etc"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha256sum "$R54" | awk '{print $1}')" = "$EXPECTED_R54" || { echo r54-sha-mismatch >&2; exit 10; }
tar -xzf "$R54" -C "$WORK/r54"
(cd "$WORK/r54" && sha256sum -c checksums.sha256 >/dev/null)

R54ROOT="$WORK/r54/payload/root"
ROOT="$WORK/update/payload/root"
CORE="$R54ROOT/etc/r36os-core-manifest.sha256"
test -s "$CORE"

python3 "$HERE/transform_prepare.py"   "$R54ROOT/usr/local/bin/r36os-kernel-next-prepare"   "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_identity.py"   "$R54ROOT/usr/local/bin/r36os-kernel-slot"   "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_identity.py"   "$R54ROOT/usr/local/bin/r36os-r36update-maint"   "$ROOT/usr/local/bin/r36os-r36update-maint"
chmod 0755 "$ROOT/usr/local/bin/"*

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R55"
R36OS_PACKAGE_VERSION="0.5.55.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-30"
R36OS_COMPATIBILITY="K1 module-tree reuse keyed by kernel release and exact module archive contents"
R36OS_NOTES="Alpha 5R55 fixes physical R54 Boot Next code 67 existing-modules-invalid. R54 changed only the K1 uInitrd/candidate ID while Image, kernel release and modules archive were unchanged. R55 validates an existing R36STATE module tree by kernel release, exact modules archive SHA-256, exact file count, exact byte count, modules.dep and no symlinks; when content is unchanged it atomically rebinds only the module metadata to the current candidate ID. No K1 binary, U-Boot hook, DTB, Image, uInitrd or modules payload changes are included."
EOF_RELEASE

cat >"$ROOT/opt/r36os/features/alpha5r55" <<'EOF_FEATURE'
R36OS Alpha 5R55
- Fixes physical R54 Boot Next failure code 67: existing-modules-invalid.
- Root cause: module metadata was bound to the whole K1 candidate ID, even though the candidate ID changed only because uInitrd changed.
- Existing module tree reuse now requires:
  * exact kernel_release match
  * exact modules.tar.xz SHA-256 match
  * exact module file count
  * exact uncompressed byte count
  * modules.dep present
  * no symlinks in the staged module tree
- If those content checks pass and only candidate_id differs, metadata is atomically rewritten and read back.
- Existing 1.09 GB module tree is reused; no unnecessary re-extraction is required.
- K1 candidate remains 4c70486f70ba16acf7437403.
- Linux Image, DTB, uInitrd, modules archive and U-Boot hook are unchanged from R54.
- Legacy normal-boot startup path remains unchanged.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r55"

python3 - "$CORE" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip(); entries[p]=h; order.append(p)
for p in [
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
'/usr/local/bin/r36os-r36update-maint',
]:
    fp=root/p.lstrip('/')
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.55.0
hardware=R36XX-RK3326
base_version=0.5.54.0
channel=system-core
requires_reboot=true
description=Alpha 5R55 fixes candidate-only module metadata invalidation while preserving exact module-content verification.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
candidate_id_change=no
module_payload_change=no
module_reuse_rebind=yes
legacy_ui_startup_change=no
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

# Safety/audit.
test ! -e "$ROOT/r36state"
! find "$ROOT" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$ROOT" -type f | grep -Eq '/opt/r36os/kernel-next/(hooked-boot.ini|hook.conf|K1/)'
! find "$ROOT" -type l | grep -q .
for p in "$ROOT"/usr/local/bin/*; do bash -n "$p"; done
python3 -m py_compile "$HERE/"*.py

grep -Fq 'write_module_meta(){' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq 'Rebinding K1 module metadata' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq 'verify_modules || fail 67 existing-modules-invalid' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
! grep -F 'verify_modules(){' -A12 "$ROOT/usr/local/bin/r36os-kernel-next-prepare" | grep -Fq '"$(val "$MODMETA" candidate_id)" = "$CID"'
grep -Fq '0.5.55.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
grep -Fq '0.5.55.0' "$ROOT/usr/local/bin/r36os-kernel-slot"
grep -Fq '0.5.55.0' "$ROOT/usr/local/bin/r36os-r36update-maint"

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-30 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.55.0
base_version=0.5.54.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R55 audited release build PASS
base_version=0.5.54.0
version=0.5.55.0
candidate_id=$CID
kernel_release=$KREL
r54_source_sha256=$EXPECTED_R54
k1_binary_change=no
candidate_id_change=no
module_payload_change=no
module_reuse_rebind=yes
legacy_ui_startup_change=no
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R55_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
