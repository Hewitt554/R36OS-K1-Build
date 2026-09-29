#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 2 ] || { echo "usage: build_release.sh <exact-r44.r36upd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
R44="$1"
OUT="$2"

REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r45'
NAME='00-R36OS-Alpha5R45-K1HandoffDiagnostics-FromR44.r36upd'
EXPECTED_R44='2a6b872c3e7b81a88272c03f8c1484d9d4ae582dfe9172796ebff4e8e396a4fa'
CID='e551eb6598d6da7a8e8320e9'
KREL='6.12.94-r36os-k1'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r45-release"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/base"   "$WORK/update/payload/root/etc/r36os"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$OUT"

test "$(sha256sum "$R44" | awk '{print $1}')" = "$EXPECTED_R44" || { echo r44-sha-mismatch >&2; exit 10; }
tar -xzf "$R44" -C "$WORK/base"
(cd "$WORK/base" && sha256sum -c checksums.sha256 >/dev/null)
test "$(awk -F= '$1=="version"{print $2}' "$WORK/base/manifest.conf")" = 0.5.44.0 || { echo r44-version-mismatch >&2; exit 11; }
test "$(awk -F= '$1=="base_version"{print $2}' "$WORK/base/manifest.conf")" = 0.5.43.0 || { echo r44-base-mismatch >&2; exit 12; }

BASE="$WORK/base/payload/root"
CORE="$BASE/etc/r36os-core-manifest.sha256"
test -s "$CORE" || { echo r44-core-manifest-missing >&2; exit 13; }

core_sha(){
  awk -v p="$1" '$2==p{print $1;exit}' "$CORE"
}

# Verify that the public audited base sources are exactly the files installed
# according to the R44 authoritative core manifest before deriving R45.
BASE_UPLOADER="$ROOT/r39-release/r36os-github-diagnostics"
BASE_SNAPSHOT="$ROOT/r43-release/r36os-diagnostic-snapshot"
test -s "$BASE_UPLOADER" && test -s "$BASE_SNAPSHOT"
test "$(sha256sum "$BASE_UPLOADER" | awk '{print $1}')" = "$(core_sha /usr/local/bin/r36os-github-diagnostics)" || { echo uploader-lineage-mismatch >&2; exit 14; }
test "$(sha256sum "$BASE_SNAPSHOT" | awk '{print $1}')" = "$(core_sha /usr/local/bin/r36os-diagnostic-snapshot)" || { echo snapshot-lineage-mismatch >&2; exit 15; }

python3 - "$BASE_UPLOADER" "$HERE/r36os-github-diagnostics" <<'PY'
from pathlib import Path
import sys
base=Path(sys.argv[1]).read_text()
committed=Path(sys.argv[2]).read_text()
a='  ensure_device_id || { write_status ERROR device-id; return 21; }\n'
b=a+'  if command -v r36os-k1-boot-audit >/dev/null 2>&1; then\n    r36os-k1-boot-audit >/dev/null 2>&1 || true\n  fi\n'
if base.count(a)!=1:
    raise SystemExit(f'unexpected uploader anchor count={base.count(a)}')
derived=base.replace(a,b,1)
if derived != committed:
    raise SystemExit('committed R45 uploader does not match audited base plus passive-audit insertion')
PY

python3 - "$BASE_SNAPSHOT" "$HERE/r36os-diagnostic-snapshot" <<'PY'
from pathlib import Path
import sys
base=Path(sys.argv[1]).read_text()
committed=Path(sys.argv[2]).read_text()
a='} >>"$TMP"\n\nGSDIR='
b='} >>"$TMP"\n\nif command -v r36os-k1-boot-audit >/dev/null 2>&1; then\n  r36os-k1-boot-audit >/dev/null 2>&1 || true\nfi\nsection k1-boot-handoff "$STATE/logs/kernel-next/boot-handoff-current.conf" 131072\n\nGSDIR='
if base.count(a)!=1:
    raise SystemExit(f'unexpected snapshot anchor count={base.count(a)}')
derived=base.replace(a,b,1)
if derived != committed:
    raise SystemExit('committed R45 snapshot does not match audited base plus passive-audit insertion')
PY

for f in r36os-github-diagnostics r36os-diagnostic-snapshot r36os-k1-boot-audit; do
  cp "$HERE/$f" "$WORK/update/payload/root/usr/local/bin/$f"
  chmod 0755 "$WORK/update/payload/root/usr/local/bin/$f"
  bash -n "$WORK/update/payload/root/usr/local/bin/$f"
done

python3 - "$BASE/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if s.count('0.5.44.0') != 1:
    raise SystemExit('unexpected R44 prepare release identity')
Path(sys.argv[2]).write_text(s.replace('0.5.44.0','0.5.45.0'))
PY

python3 - "$BASE/usr/local/bin/r36os-kernel-slot" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
checks={'0.5.44.0':1,'Alpha 5R44':1,'r44-runtime-lock':1}
for needle,count in checks.items():
    if s.count(needle) != count:
        raise SystemExit(f'unexpected R44 slot identity {needle}: {s.count(needle)}')
s=s.replace('0.5.44.0','0.5.45.0').replace('Alpha 5R44','Alpha 5R45').replace('r44-runtime-lock','r45-runtime-lock')
Path(sys.argv[2]).write_text(s)
PY
chmod 0755 "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare" "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-kernel-next-prepare"
bash -n "$WORK/update/payload/root/usr/local/bin/r36os-kernel-slot"

cat >"$WORK/update/payload/root/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R45"
R36OS_PACKAGE_VERSION="0.5.45.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-29"
R36OS_COMPATIBILITY="Passive K1 boot-handoff diagnostics from Alpha 5R44"
R36OS_NOTES="Alpha 5R45 records K1 request/consumed marker state, boot-hook identity, K1 preflight, cmdline, pstore and health-service state before every diagnostic capture. It does not alter K1 boot state or binaries."
EOF_RELEASE

cat >"$WORK/update/payload/root/opt/r36os/features/alpha5r45" <<EOF_FEATURE
R36OS Alpha 5R45
- Adds passive K1 boot-handoff evidence recording.
- Every remote diagnostic capture refreshes the handoff record first.
- Distinguishes NONE / ARMED_PENDING / CONSUMED_WITH_REQUEST / ORPHAN_CONSUMED.
- Records K1 candidate preflight and boot-hook identity/readback.
- Records relevant kernel cmdline, pstore and health-service state.
- Never arms, disarms, consumes or clears K1 markers.
- No K1 Image, DTB, uInitrd or module changes.
- No reboot is required for this diagnostics-only update.
EOF_FEATURE
chmod 0644 "$WORK/update/payload/root/etc/r36os-release" "$WORK/update/payload/root/opt/r36os/features/alpha5r45"

python3 - "$CORE" "$WORK/update/payload/root" "$WORK/update/payload/root/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3])
entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    sha,path=line.split(None,1); path=path.strip()
    entries[path]=sha; order.append(path)
paths=[
'/usr/local/bin/r36os-github-diagnostics',
'/usr/local/bin/r36os-diagnostic-snapshot',
'/usr/local/bin/r36os-k1-boot-audit',
'/usr/local/bin/r36os-kernel-next-prepare',
'/usr/local/bin/r36os-kernel-slot',
]
for path in paths:
    p=root/path.lstrip('/')
    entries[path]=hashlib.sha256(p.read_bytes()).hexdigest()
    if path not in order: order.append(path)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.45.0
hardware=R36XX-RK3326
base_version=0.5.44.0
channel=system-core
requires_reboot=false
description=Alpha 5R45 adds passive K1 boot-handoff diagnostics without modifying K1 boot state or binaries.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
boot_handoff_diagnostics=passive-marker-hook-preflight-cmdline-pstore
EOF_MAN

(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >checksums.sha256)

cat >"$WORK/expected-files.txt" <<'EOF_FILES'
etc/r36os-core-manifest.sha256
etc/r36os-release
opt/r36os/features/alpha5r45
usr/local/bin/r36os-diagnostic-snapshot
usr/local/bin/r36os-github-diagnostics
usr/local/bin/r36os-k1-boot-audit
usr/local/bin/r36os-kernel-next-prepare
usr/local/bin/r36os-kernel-slot
EOF_FILES
(cd "$WORK/update/payload/root" && find . -type f -printf '%P\n' | LC_ALL=C sort) >"$WORK/actual-files.txt"
cmp "$WORK/expected-files.txt" "$WORK/actual-files.txt"

test ! -e "$WORK/update/payload/root/etc/r36os/r36update-repair-once.conf"
test ! -e "$WORK/update/payload/root/r36state"
! find "$WORK/update/payload/root" -type f | grep -Eq '/(boot/|lib/modules/|usr/lib/modules/)'
! find "$WORK/update/payload/root" -type f | grep -Eq '/opt/r36os/kernel-next/K1/(Image|uInitrd|rk3326-r36s-k1.dtb|modules.tar.xz)$'

# Only the two long-standing fake token strings in the uploader self-test are allowed.
HITS="$(grep -R -n -E 'github_pat_[A-Za-z0-9]|gh[pousr]_[A-Za-z0-9]' "$WORK/update/payload/root" || true)"
HITS="$(printf '%s\n' "$HITS" | grep -v -F 'raw_github=github_pat_11AAABBBCCCDDDEEE' | grep -v -F 'legacy_token=ghp_1234567890abcdefghijk' || true)"
[ -z "$HITS" ] || { printf '%s\n' "$HITS" >&2; echo credential-pattern-forbidden >&2; exit 25; }

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-29 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha256sum "$OUT/$NAME" | awk '{print $1}')"
SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"

AUD="$WORK/audit"
mkdir -p "$AUD"
tar -xzf "$OUT/$NAME" -C "$AUD"
(cd "$AUD" && sha256sum -c checksums.sha256 >/dev/null)

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.45.0
base_version=0.5.44.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST

cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R45 audited release build PASS
base_version=0.5.44.0
version=0.5.45.0
requires_reboot=false
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=no
r44_source_sha256=$EXPECTED_R44
boot_handoff_diagnostics=passive
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT

echo "R45_RELEASE_BUILD=PASS size=$SIZE sha256=$SHA"
