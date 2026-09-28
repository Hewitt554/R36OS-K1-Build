#!/usr/bin/env bash
set -euo pipefail
OUT="${1:?output directory required}"
rm -rf "$OUT"
mkdir -p "$OUT"
IMG="$OUT/fsck-selftest.img"
truncate -s 64M "$IMG"
mkfs.fat -F 32 -n R36TEST -i 52343354 "$IMG" >/dev/null
printf 'R36OS-R43-FSCK-SELFTEST\n' >"$OUT/fixture-note.txt"
gzip -9 -n "$IMG"
sha256sum "$OUT/fsck-selftest.img.gz" | sed 's#  .*/#  #' >"$OUT/fsck-selftest.img.gz.sha256"
