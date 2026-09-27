#!/usr/bin/env bash
set -euo pipefail

# R36OS K1 CP04O-CLOUD7
#
# Run #9 successfully built Linux 6.12.94, the Panel-4 DTB and the module
# tree, then failed CP04 validation because BUILD.log changed after its digest
# had already been written into MANIFEST.sha256. This wrapper starts from the
# exact immutable Run #9 bootstrap, verifies its Git blob identity, injects a
# fail-closed post-tee manifest refresh immediately before CP04 validation,
# then executes the normal pipeline.

BASE_COMMIT="89719bd08a8a8b32fb0448b58e0e55df20acd0f4"
BASE_BLOB_SHA1="7afd3b5032f78371f687e3bab0a38fc076a6c966"
BASE_URL="https://raw.githubusercontent.com/Hewitt554/R36OS-K1-Build/${BASE_COMMIT}/bootstrap_r36os_k1.sh"

WRAP_ROOT="${RUNNER_TEMP:-/tmp}/r36os-k1-cloud7-wrapper"
BASE_BOOTSTRAP="$WRAP_ROOT/bootstrap_run9.sh"
PATCHED_BOOTSTRAP="$WRAP_ROOT/bootstrap_cloud7.sh"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

for cmd in curl git python3 bash; do
  command -v "$cmd" >/dev/null 2>&1 || fail "required wrapper command missing: $cmd"
done

rm -rf "$WRAP_ROOT"
mkdir -p "$WRAP_ROOT"

echo "CLOUD7=INFO fetching immutable Run #9 bootstrap"
curl --fail --location --silent --show-error \
  --retry 4 --retry-delay 2 --retry-all-errors \
  "$BASE_URL" -o "$BASE_BOOTSTRAP"

actual_blob="$(git hash-object "$BASE_BOOTSTRAP")"
[[ "$actual_blob" == "$BASE_BLOB_SHA1" ]] || \
  fail "Run #9 bootstrap Git blob mismatch: expected=$BASE_BLOB_SHA1 actual=$actual_blob"

echo "CLOUD7=PASS Run #9 bootstrap Git blob verified"

python3 - "$BASE_BOOTSTRAP" "$PATCHED_BOOTSTRAP" <<'R36OS_CLOUD7_PATCH_BOOTSTRAP'
from pathlib import Path
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text()

anchor = '(root / "CLOUD_PATCHSET.txt").write_text('
if text.count(anchor) != 1:
    raise SystemExit(
        f"ERROR: CLOUD7 bootstrap insertion anchor count != 1: {text.count(anchor)}"
    )

injection = r"""
# 11) Run #9 completed the real kernel/DTB/modules build, then failed only
#     because BUILD.log's MANIFEST.sha256 entry was stale. BUILD.log is written
#     by the outer `tee`; the checkpoint script can therefore hash it before
#     tee has emitted its final bytes. Refresh exactly that one manifest entry
#     after the pipeline has closed and immediately before real CP04 validation.
_r36os_external = root / "external_cp04_builder/build_cp04_external.sh"
_r36os_text = _r36os_external.read_text()
_r36os_lines = _r36os_text.splitlines(keepends=True)
_r36os_validator_lines = [
    i for i, line in enumerate(_r36os_lines)
    if "validate_cp04_artifacts.py" in line and not line.lstrip().startswith("#")
]
if len(_r36os_validator_lines) != 1:
    raise SystemExit(
        "ERROR: cp04-buildlog-manifest-refresh: expected exactly one "
        f"real validate_cp04_artifacts.py invocation, found {len(_r36os_validator_lines)}"
    )

_r36os_idx = _r36os_validator_lines[0]
_r36os_refresh = r'''# CLOUD7: BUILD.log is produced by tee outside the checkpoint script.
# Refresh only its recorded checksum after tee has closed, preserving every
# other manifest entry and every existing artifact-integrity check.
R36OS_CP04_ART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/artifacts"
R36OS_CP04_MANIFEST="$R36OS_CP04_ART_DIR/MANIFEST.sha256"
R36OS_CP04_BUILDLOG="$R36OS_CP04_ART_DIR/BUILD.log"

[[ -f "$R36OS_CP04_MANIFEST" ]] || {
  echo "CP04 manifest refresh: missing $R36OS_CP04_MANIFEST" >&2
  exit 1
}
[[ -f "$R36OS_CP04_BUILDLOG" ]] || {
  echo "CP04 manifest refresh: missing $R36OS_CP04_BUILDLOG" >&2
  exit 1
}

R36OS_CP04_BUILDLOG_SHA="$(sha256sum "$R36OS_CP04_BUILDLOG" | awk '{print $1}')"
python3 - "$R36OS_CP04_MANIFEST" "$R36OS_CP04_BUILDLOG_SHA" <<'R36OS_REFRESH_BUILDLOG_MANIFEST'
from pathlib import Path
import re
import sys

manifest = Path(sys.argv[1])
digest = sys.argv[2].lower()

if not re.fullmatch(r"[0-9a-f]{64}", digest):
    raise SystemExit("invalid BUILD.log SHA-256")

lines = manifest.read_text().splitlines()
matches = []
parsed = {}
for i, line in enumerate(lines):
    m = re.match(r"^([0-9A-Fa-f]{64})([ \\t]+)(\\*?)(.+)$", line)
    if not m:
        continue
    path = m.group(4)
    if path in ("BUILD.log", "./BUILD.log"):
        matches.append(i)
        parsed[i] = m

if len(matches) != 1:
    raise SystemExit(
        f"expected exactly one BUILD.log entry in CP04 manifest, found {len(matches)}"
    )

i = matches[0]
m = parsed[i]
lines[i] = digest + m.group(2) + m.group(3) + m.group(4)
manifest.write_text("\\n".join(lines) + "\\n")
print("CLOUD7=PASS refreshed final BUILD.log SHA-256 in CP04 manifest")
R36OS_REFRESH_BUILDLOG_MANIFEST

python3 - "$R36OS_CP04_MANIFEST" "$R36OS_CP04_BUILDLOG" <<'R36OS_VERIFY_BUILDLOG_MANIFEST'
from pathlib import Path
import hashlib
import re
import sys

manifest = Path(sys.argv[1])
buildlog = Path(sys.argv[2])
actual = hashlib.sha256(buildlog.read_bytes()).hexdigest()

found = []
for line in manifest.read_text().splitlines():
    m = re.match(r"^([0-9A-Fa-f]{64})[ \\t]+\\*?(.+)$", line)
    if m and m.group(2) in ("BUILD.log", "./BUILD.log"):
        found.append(m.group(1).lower())

if found != [actual]:
    raise SystemExit(
        f"BUILD.log manifest refresh self-check failed: entries={found} actual={actual}"
    )

print("CLOUD7=PASS BUILD.log manifest refresh self-check")
R36OS_VERIFY_BUILDLOG_MANIFEST
'''
_r36os_lines.insert(_r36os_idx, _r36os_refresh)
_r36os_external.write_text("".join(_r36os_lines))
print(
    "CLOUD_PATCH=PASS cp04-buildlog-manifest-refresh "
    "file=external_cp04_builder/build_cp04_external.sh"
)
"""

text = text.replace(anchor, injection + "\n" + anchor, 1)

replacements = [
    (
        "R36OS K1 CP04N GitHub cloud compatibility overlay",
        "R36OS K1 CP04O GitHub cloud compatibility overlay",
        "overlay title",
    ),
    (
        "overlay_id=CP04N-CLOUD6",
        "overlay_id=CP04O-CLOUD7",
        "overlay id",
    ),
    (
        "STATUS=PASS CP04N-CLOUD6 compatibility overlay applied",
        "STATUS=PASS CP04O-CLOUD7 compatibility overlay applied",
        "overlay status",
    ),
    (
        "changes=fetch local set-u declaration; timeconst checksum formatting; pipefail-safe self-tests and metadata; explicit module-tree selection; complete CP04/CP05 dependency checks; INPUT_JOYSTICK parent correction; aggregate required-Kconfig reporting; Rockchip-qualified DTB build target; authoritative Panel-4 DTB identity validation; result provenance",
        "changes=fetch local set-u declaration; timeconst checksum formatting; pipefail-safe self-tests and metadata; explicit module-tree selection; complete CP04/CP05 dependency checks; INPUT_JOYSTICK parent correction; aggregate required-Kconfig reporting; Rockchip-qualified DTB build target; authoritative Panel-4 DTB identity validation; result provenance; post-tee BUILD.log manifest refresh",
        "overlay change list",
    ),
]

for old, new, label in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"ERROR: CLOUD7 {label}: expected exactly one match, found {count}"
        )
    text = text.replace(old, new, 1)

if "cp04-buildlog-manifest-refresh" not in text:
    raise SystemExit("ERROR: CLOUD7 manifest-refresh injection missing after patch")

dst.write_text(text)
R36OS_CLOUD7_PATCH_BOOTSTRAP

chmod +x "$PATCHED_BOOTSTRAP"
bash -n "$PATCHED_BOOTSTRAP"

echo "CLOUD7=PASS patched bootstrap syntax verified"
echo "CLOUD7=INFO executing CP04O-CLOUD7"
exec bash "$PATCHED_BOOTSTRAP"
