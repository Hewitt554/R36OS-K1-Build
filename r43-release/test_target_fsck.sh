#!/usr/bin/env bash
set -euo pipefail
TARGET_FSCK="${TARGET_FSCK:?TARGET_FSCK required}"
FIXTURE_GZ="${FIXTURE_GZ:?FIXTURE_GZ required}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${RUNNER_TEMP:-/tmp}/r43-target-fsck-test"
rm -rf "$WORK"; mkdir -p "$WORK"
gzip -dc "$FIXTURE_GZ" >"$WORK/clean.img"
LC_ALL=C LANG=C /usr/bin/qemu-aarch64-static "$TARGET_FSCK" --help >"$WORK/help.txt" 2>&1
grep -q 'Check FAT filesystem' "$WORK/help.txt"
LC_ALL=C LANG=C /usr/bin/qemu-aarch64-static "$TARGET_FSCK" -n "$WORK/clean.img" >"$WORK/clean-n.txt" 2>&1
cp "$WORK/clean.img" "$WORK/dirty.img"
python3 "$HERE/fat_fixture_tool.py" dirty "$WORK/dirty.img"
set +e
LC_ALL=C LANG=C /usr/bin/qemu-aarch64-static "$TARGET_FSCK" -n "$WORK/dirty.img" >"$WORK/dirty-precheck.txt" 2>&1
PRE=$?
set -e
test "$PRE" -eq 1
cp "$WORK/dirty.img" "$WORK/repaired.img"
set +e
LC_ALL=C LANG=C /usr/bin/qemu-aarch64-static "$TARGET_FSCK" -a "$WORK/repaired.img" >"$WORK/repair.txt" 2>&1
REPAIR=$?
set -e
case "$REPAIR" in 0|1) ;; *) cat "$WORK/repair.txt" >&2; exit 20;; esac
LC_ALL=C LANG=C /usr/bin/qemu-aarch64-static "$TARGET_FSCK" -n "$WORK/repaired.img" >"$WORK/verify.txt" 2>&1
python3 "$HERE/fat_fixture_tool.py" assert-clean "$WORK/repaired.img"
printf 'precheck_rc=%s\nrepair_rc=%s\nverify_rc=0\n' "$PRE" "$REPAIR" >"$WORK/result.txt"
echo R43_TARGET_FSCK_MATRIX=PASS
