#!/usr/bin/env bash
set -euo pipefail

# R36OS K1 CP04P-CLOUD8
#
# Run #9 proved the Linux 6.12.94 kernel, Panel-4 DTB and module tree build.
# Run #10 proved the previous BUILD.log manifest-race fix was inserted at the
# correct point, but assumed the manifest was named artifacts/MANIFEST.sha256.
# That filename was wrong. CLOUD8 discovers the real checksum manifest by its
# BUILD.log entry, requires exactly one candidate and one BUILD.log entry,
# refreshes only that digest after tee has closed, verifies it, then runs the
# original CP04 validator and normal CP05 path unchanged.

BASE_COMMIT="89719bd08a8a8b32fb0448b58e0e55df20acd0f4"
BASE_BLOB_SHA1="7afd3b5032f78371f687e3bab0a38fc076a6c966"
BASE_URL="https://raw.githubusercontent.com/Hewitt554/R36OS-K1-Build/${BASE_COMMIT}/bootstrap_r36os_k1.sh"

WRAP_ROOT="${RUNNER_TEMP:-/tmp}/r36os-k1-cloud8-wrapper"
BASE_BOOTSTRAP="$WRAP_ROOT/bootstrap_run9.sh"
PATCHED_BOOTSTRAP="$WRAP_ROOT/bootstrap_cloud8.sh"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

for cmd in curl git python3 bash; do
  command -v "$cmd" >/dev/null 2>&1 || fail "required wrapper command missing: $cmd"
done

rm -rf "$WRAP_ROOT"
mkdir -p "$WRAP_ROOT"

echo "CLOUD8=INFO fetching immutable Run #9 bootstrap"
curl --fail --location --silent --show-error \
  --retry 4 --retry-delay 2 --retry-all-errors \
  "$BASE_URL" -o "$BASE_BOOTSTRAP"

actual_blob="$(git hash-object "$BASE_BOOTSTRAP")"
[[ "$actual_blob" == "$BASE_BLOB_SHA1" ]] || \
  fail "Run #9 bootstrap Git blob mismatch: expected=$BASE_BLOB_SHA1 actual=$actual_blob"

echo "CLOUD8=PASS Run #9 bootstrap Git blob verified"

python3 - "$BASE_BOOTSTRAP" "$PATCHED_BOOTSTRAP" <<'R36OS_CLOUD8_PATCH_BOOTSTRAP'
from pathlib import Path
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text()

anchor = '(root / "CLOUD_PATCHSET.txt").write_text('
if text.count(anchor) != 1:
    raise SystemExit(
        f"ERROR: CLOUD8 bootstrap insertion anchor count != 1: {text.count(anchor)}"
    )

injection = r"""
# 11) Run #9's only real CP04 validation failure was a stale BUILD.log digest.
#     Run #10 confirmed this hook executes after the build/tee has closed, but
#     also proved the checksum manifest is not named MANIFEST.sha256.
#     Discover the real manifest by its checksum entry instead of its filename.
_r36os_external = root / "external_cp04_builder/build_cp04_external.sh"
_r36os_text = _r36os_external.read_text()
_r36os_lines = _r36os_text.splitlines(keepends=True)
_r36os_validator_lines = [
    i for i, line in enumerate(_r36os_lines)
    if "validate_cp04_artifacts.py" in line and not line.lstrip().startswith("#")
]
if len(_r36os_validator_lines) != 1:
    raise SystemExit(
        "ERROR: cp04-buildlog-manifest-refresh-v2: expected exactly one "
        f"real validate_cp04_artifacts.py invocation, found {len(_r36os_validator_lines)}"
    )

_r36os_idx = _r36os_validator_lines[0]
_r36os_refresh = r'''# CLOUD8: discover the actual CP04 checksum manifest by its BUILD.log entry.
# This runs after the checkpoint build + tee have completed and before the
# existing CP04 artifact validator. No validator is disabled or bypassed.
R36OS_CP04_ART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/artifacts"
R36OS_CP04_BUILDLOG="$R36OS_CP04_ART_DIR/BUILD.log"

[[ -d "$R36OS_CP04_ART_DIR" ]] || {
  echo "CP04 manifest refresh v2: artifact directory missing: $R36OS_CP04_ART_DIR" >&2
  exit 1
}
[[ -f "$R36OS_CP04_BUILDLOG" ]] || {
  echo "CP04 manifest refresh v2: BUILD.log missing: $R36OS_CP04_BUILDLOG" >&2
  exit 1
}

python3 - "$R36OS_CP04_ART_DIR" "$R36OS_CP04_BUILDLOG" <<'R36OS_REFRESH_DISCOVERED_BUILDLOG_MANIFEST'
from pathlib import Path
import hashlib
import re
import sys

artifact_dir = Path(sys.argv[1]).resolve()
buildlog = Path(sys.argv[2]).resolve()

if not buildlog.is_file():
    raise SystemExit(f"BUILD.log is not a file: {buildlog}")

actual = hashlib.sha256(buildlog.read_bytes()).hexdigest()
checksum_line = re.compile(r"^([0-9A-Fa-f]{64})([ \t]+)(\*?)(.+)$")
candidates = []

for p in sorted(artifact_dir.rglob("*")):
    if not p.is_file() or p.resolve() == buildlog:
        continue
    try:
        size = p.stat().st_size
    except OSError:
        continue
    if size > 2 * 1024 * 1024:
        continue
    try:
        data = p.read_text()
    except (UnicodeDecodeError, OSError):
        continue

    matches = []
    for i, line in enumerate(data.splitlines()):
        m = checksum_line.match(line)
        if not m:
            continue
        entry = m.group(4)
        if entry in ("BUILD.log", "./BUILD.log"):
            matches.append((i, m))

    if matches:
        candidates.append((p, data, matches))

if len(candidates) != 1:
    shown = ", ".join(str(p.relative_to(artifact_dir)) for p, _, _ in candidates) or "<none>"
    raise SystemExit(
        "expected exactly one CP04 checksum manifest containing BUILD.log; "
        f"found {len(candidates)}: {shown}"
    )

manifest, data, matches = candidates[0]
if len(matches) != 1:
    raise SystemExit(
        f"expected exactly one BUILD.log entry in {manifest.name}; found {len(matches)}"
    )

lines = data.splitlines()
idx, m = matches[0]
old = m.group(1).lower()
lines[idx] = actual + m.group(2) + m.group(3) + m.group(4)
manifest.write_text("\n".join(lines) + "\n")

verified = []
for line in manifest.read_text().splitlines():
    m2 = checksum_line.match(line)
    if m2 and m2.group(4) in ("BUILD.log", "./BUILD.log"):
        verified.append(m2.group(1).lower())

if verified != [actual]:
    raise SystemExit(
        f"BUILD.log manifest refresh verification failed: entries={verified} actual={actual}"
    )

print(
    "CLOUD8=PASS refreshed final BUILD.log digest "
    f"manifest={manifest.relative_to(artifact_dir)} old={old} new={actual}"
)
R36OS_REFRESH_DISCOVERED_BUILDLOG_MANIFEST
'''
_r36os_lines.insert(_r36os_idx, _r36os_refresh)
_r36os_external.write_text("".join(_r36os_lines))
print(
    "CLOUD_PATCH=PASS cp04-buildlog-manifest-refresh-v2 "
    "file=external_cp04_builder/build_cp04_external.sh"
)
"""

text = text.replace(anchor, injection + "\n" + anchor, 1)

replacements = [
    (
        "R36OS K1 CP04N GitHub cloud compatibility overlay",
        "R36OS K1 CP04P GitHub cloud compatibility overlay",
        "overlay title",
    ),
    (
        "overlay_id=CP04N-CLOUD6",
        "overlay_id=CP04P-CLOUD8",
        "overlay id",
    ),
    (
        "STATUS=PASS CP04N-CLOUD6 compatibility overlay applied",
        "STATUS=PASS CP04P-CLOUD8 compatibility overlay applied",
        "overlay status",
    ),
    (
        "changes=fetch local set-u declaration; timeconst checksum formatting; pipefail-safe self-tests and metadata; explicit module-tree selection; complete CP04/CP05 dependency checks; INPUT_JOYSTICK parent correction; aggregate required-Kconfig reporting; Rockchip-qualified DTB build target; authoritative Panel-4 DTB identity validation; result provenance",
        "changes=fetch local set-u declaration; timeconst checksum formatting; pipefail-safe self-tests and metadata; explicit module-tree selection; complete CP04/CP05 dependency checks; INPUT_JOYSTICK parent correction; aggregate required-Kconfig reporting; Rockchip-qualified DTB build target; authoritative Panel-4 DTB identity validation; result provenance; discovered post-tee BUILD.log checksum-manifest refresh",
        "overlay change list",
    ),
]

for old, new, label in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"ERROR: CLOUD8 {label}: expected exactly one match, found {count}"
        )
    text = text.replace(old, new, 1)

if "cp04-buildlog-manifest-refresh-v2" not in text:
    raise SystemExit("ERROR: CLOUD8 manifest-refresh-v2 injection missing after patch")

dst.write_text(text)
R36OS_CLOUD8_PATCH_BOOTSTRAP

chmod +x "$PATCHED_BOOTSTRAP"
bash -n "$PATCHED_BOOTSTRAP"

echo "CLOUD8=PASS patched bootstrap syntax verified"
echo "CLOUD8=INFO executing CP04P-CLOUD8"
exec bash "$PATCHED_BOOTSTRAP"
