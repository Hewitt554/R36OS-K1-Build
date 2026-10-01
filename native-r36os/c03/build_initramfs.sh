#!/bin/bash
set -euo pipefail
[ "$#" -eq 2 ] || { echo "usage: build_initramfs.sh <proven-r54-uInitrd> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
BASE="$1"
OUT="$(readlink -m "$2")"
B="$OUT/build"
R="$OUT/initramfs-root"
EPOCH=1790812800
rm -rf "$OUT"
mkdir -p "$B" "$R/dev" "$R/proc" "$R/sys" "$R/state" "$R/newroot"

clang --target=aarch64-linux-gnu -c -Os -Wall -Wextra -Werror -Wpedantic -Wconversion -Wshadow \
  -ffreestanding -fno-stack-protector -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -o "$B/start.o" "$HERE/src/start_aarch64.S"
clang --target=aarch64-linux-gnu -c -Os -Wall -Wextra -Werror -Wpedantic -Wconversion -Wshadow \
  -ffreestanding -fno-stack-protector -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -o "$B/init.o" "$HERE/src/native_init.c"
ld.lld -static -nostdlib --build-id=none -z noexecstack -e _start \
  -o "$R/init" "$B/start.o" "$B/init.o"
chmod 0755 "$R/init"
printf '%s\n' 'R36OS Native C03 one-shot initramfs' >"$R/R36OS-NATIVE-C03.txt"

find "$R" -xdev -exec touch -h -d "@$EPOCH" {} +
(
  cd "$R"
  find . -xdev -print0 | LC_ALL=C sort -z | cpio --null -o --format=newc --owner=0:0 --reproducible 2>"$B/cpio.log"
) >"$B/initramfs-native-c03.cpio"
gzip -n -9 -c "$B/initramfs-native-c03.cpio" >"$B/initramfs-native-c03.cpio.gz"
python3 "$HERE/wrap_uinitrd.py" "$BASE" "$B/initramfs-native-c03.cpio.gz" "$OUT/uInitrd"

file "$R/init" >"$OUT/VALIDATION.txt"
file "$B/initramfs-native-c03.cpio.gz" >>"$OUT/VALIDATION.txt"
file "$OUT/uInitrd" >>"$OUT/VALIDATION.txt"
readelf -h "$R/init" >>"$OUT/VALIDATION.txt"
sha256sum "$R/init" "$B/initramfs-native-c03.cpio" "$B/initramfs-native-c03.cpio.gz" "$OUT/uInitrd" >"$OUT/SHA256SUMS.txt"

grep -Eq 'ARM aarch64|ARM64' "$OUT/VALIDATION.txt"
echo C03_INITRAMFS_BUILD=PASS
