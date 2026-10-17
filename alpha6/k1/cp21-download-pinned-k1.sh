#!/usr/bin/env bash
# CP21: CI-only verified K1 download; FAIL CLOSED if no exact pin.
set -euo pipefail
REPO='Hewitt554/R36OS-K1-Build'
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIN="$BASE/k1-candidate-pin.json"
TOOL="$BASE/cp21_pinned_artifact.py"
: "${GH_TOKEN:?GitHub read-only Actions token is required}"
: "${RUNNER_TEMP:?Only a GitHub CI scratch directory may be used}"
for exe in python3 gh find; do command -v "$exe" >/dev/null || exit 3; done
# No automatic newest run discovery: only the explicitly approved ID works.
RUN_ID="$(python3 "$TOOL" "$PIN" --get run-id)"
ARTIFACT="$(python3 "$TOOL" "$PIN" --get artifact-name)"
STAGE="$(mktemp -d "$RUNNER_TEMP/r36os-cp21-pinned-k1-XXXXXXXX")"
trap 'rm -rf -- "$STAGE"' EXIT
# Verify the API response is a successful run on the exact intended branch/ref.
gh api "repos/$REPO/actions/runs/$RUN_ID" > "$STAGE/run.json"
python3 "$TOOL" "$PIN" --validate-run "$STAGE/run.json"
mkdir "$STAGE/download"
gh run download "$RUN_ID" -R "$REPO" -n "$ARTIFACT" -D "$STAGE/download"
mapfile -t ARCHIVES < <(find "$STAGE/download" -type f -name 'R36OS_K1_CP04_CP05_RESULT_*.tar.gz' | sort)
[ "${#ARCHIVES[@]}" -eq 1 ] || { echo 'CP21 expected exactly one pinned K1 archive' >&2; exit 4; }
python3 "$TOOL" "$PIN" --verify-archive "${ARCHIVES[0]}"
# Caller specifies a new, non-existing regular output filename under RUNNER_TEMP.
: "${1:?Provide NEW output archive path under RUNNER_TEMP}"
TARGET="$1"
case "$TARGET" in "$RUNNER_TEMP"/*) ;; *) echo 'CP21 refused non-scratch output location' >&2; exit 4;; esac
[ ! -e "$TARGET" ] && [ ! -L "$TARGET" ] || { echo 'CP21 refuses overwrite' >&2; exit 4; }
cp -n -- "${ARCHIVES[0]}" "$TARGET"
python3 "$TOOL" "$PIN" --verify-archive "$TARGET"
echo 'CP21 verified new K1 candidate archived to scratch location; not boot tested; DO NOT FLASH'