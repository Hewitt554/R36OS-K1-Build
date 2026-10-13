#!/usr/bin/env bash
set -euo pipefail
test "$(uname -m)" = aarch64 || { echo 'Require ARM64 CI' >&2; exit 2; }
BASE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$BASE/.rescue-build/root"; OUT="$BASE/dist"
test ! -e "$BASE/.rescue-build" || { echo 'Refuse reused staging path' >&2; exit 2; }
for cmd in busybox mkimage cpio gzip readelf sha256sum python3; do command -v "$cmd" >/dev/null || exit 2; done
mkdir -p "$ROOT/bin" "$ROOT/sbin" "$ROOT/dev" "$ROOT/proc" "$ROOT/sys" "$ROOT/run" "$ROOT/etc" "$OUT"
BBOX="$(command -v busybox)"
if readelf -l "$BBOX" | grep -q INTERP; then echo 'BusyBox must be static' >&2; exit 3; fi
readelf -h "$BBOX" | grep -q AArch64 || exit 3
cp "$BBOX" "$ROOT/bin/busybox"
chmod 755 "$ROOT/bin/busybox"
for app in sh mount mkdir mknod mdev printf cat tr uname sleep; do
  busybox --list | grep -qx "$app" || { echo "Busybox missing applet $app" >&2; exit 3; }
  ln -s busybox "$ROOT/bin/$app"
done
install -m 0755 "$BASE/recovery/init" "$ROOT/init"
install -m 0755 "$BASE/recovery/r36os-rescue-status" "$ROOT/sbin/r36os-rescue-status"
printf 'NAME=R36OS-RESCUE\nVERSION=CP07\nWRITE_POLICY=DIAGNOSTIC_ONLY\nRESTORE=DISABLED\n' > "$ROOT/etc/r36os-rescue-release"
find "$ROOT" -exec touch -h -d '@1700000000' {} +
(cd "$ROOT" && find . -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --owner=0:0 --quiet) | gzip -n -9 > "$OUT/r36os-cp07-rescue.cpio.gz"
mkimage -A arm64 -O linux -T ramdisk -C gzip -n 'R36OS Rescue CP07' -d "$OUT/r36os-cp07-rescue.cpio.gz" "$OUT/r36os-cp07-rescue.uInitrd" >/dev/null
python3 "$BASE/recovery/verify-rescue.py" "$OUT/r36os-cp07-rescue.cpio.gz" "$OUT/r36os-cp07-rescue.uInitrd"
(cd "$OUT" && sha256sum r36os-cp07-rescue.cpio.gz r36os-cp07-rescue.uInitrd > r36os-cp07-rescue.sha256)
printf 'NOT FLASHABLE. No boot.ini hook or tested hardware rescue boot.\nDO NOT replace original uInitrd.\n' > "$OUT/RECOVERY_UNTESTED.txt"
du -h "$OUT/r36os-cp07-rescue.uInitrd"
