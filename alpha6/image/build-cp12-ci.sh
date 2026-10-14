#!/usr/bin/env bash
# Build *disposable* whole-disk partition integration fixture on ARM64 CI ONLY.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run via sudo in disposable CI only' >&2; exit 2; }
[[ $(uname -m) == aarch64 ]] || { echo 'CP12 rootfs fixture requires ARM64 CI' >&2; exit 2; }
BASE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d /tmp/r36os-cp12-image-XXXXXXXX)"
[[ "$WORK" == /tmp/r36os-cp12-image-* ]] || exit 3
printf 'R36OS_CP12_NONBOOTABLE_DISK_FIXTURE_V1\n' > "$WORK/.cp12-fixture-id"
for tool in mkfs.fat mkfs.ext4 e2fsck fsck.fat truncate mmd mcopy python3 tar; do
  command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 3; }
done
[[ -s "$BASE/dist/r36os-native-rootfs-arm64-cp06.tar.zst" ]] || { echo 'CP06 rootfs missing' >&2; exit 3; }
[[ -s "$BASE/dist/r36os-cp07-rescue.uInitrd" ]] || { echo 'CP07 rescue ramdisk missing' >&2; exit 3; }
mkdir -p "$WORK/rootfs"
tar --use-compress-program=zstd -xf "$BASE/dist/r36os-native-rootfs-arm64-cp06.tar.zst" -C "$WORK/rootfs" --numeric-owner
[[ -f "$WORK/rootfs/etc/r36os-release" ]] || { echo 'Native root identity missing' >&2; exit 4; }
[[ -f "$WORK/rootfs/etc/r36os/firstboot-policy.conf" ]] || exit 4
grep -qx 'flash_image_ready=false' "$WORK/rootfs/etc/r36os/firstboot-policy.conf"
truncate -s 128M "$WORK/boot.fat"
mkfs.fat -F 32 -n R36BOOT "$WORK/boot.fat" > /dev/null
mmd -i "$WORK/boot.fat" ::R36OS
printf 'NONBOOTABLE CP12 CI fixture. U-Boot, kernel and boot.ini deliberately absent. DO NOT FLASH.\r\n' > "$WORK/DO-NOT-FLASH.TXT"
mcopy -i "$WORK/boot.fat" "$WORK/DO-NOT-FLASH.TXT" ::/DO-NOT-FLASH.TXT
mcopy -i "$WORK/boot.fat" "$BASE/dist/r36os-cp07-rescue.uInitrd" ::R36OS/rescue.uInitrd
truncate -s 1024M "$WORK/root.ext4"
mkfs.ext4 -F -q -m 0 -L R36SYS -d "$WORK/rootfs" "$WORK/root.ext4"
truncate -s 64M "$WORK/update.fat"
mkfs.fat -F 32 -n R36UPDATE "$WORK/update.fat" > /dev/null
truncate -s 128M "$WORK/state.ext4"
mkfs.ext4 -F -q -m 0 -L R36STATE "$WORK/state.ext4"
for x in "$WORK/root.ext4" "$WORK/state.ext4"; do e2fsck -fn "$x" >/dev/null; done
for x in "$WORK/boot.fat" "$WORK/update.fat"; do fsck.fat -n "$x" >/dev/null; done
python3 "$BASE/image/assemble-disk-fixture.py" "$WORK"
# Never upload the generated entire disk fixture; only the small manifest.
cp "$WORK/cp12-image-report.json" "$BASE/dist/cp12-image-report.json"
python3 - "$WORK" <<'PY'
import json,sys
from pathlib import Path
base=Path(sys.argv[1]); data=json.loads((base/'cp12-image-report.json').read_text())
assert not data['safe_to_flash']
assert 'ABSENT' in data['bootloader'] and 'ABSENT' in data['kernel']
print('CP12 integration verified: actual MBR/4 filesystems/CP06 root/CP07 rescue')
print('CP12 image size:', data['total_bytes'])
print('CP12 image SHA-256:', data['sha256'])
print('CP12 report:',base/'cp12-image-report.json')
PY
# Delete only this exact fixture directory to save hosted storage; no external paths.
case "$WORK" in /tmp/r36os-cp12-image-*) rm -rf -- "$WORK";; *) exit 4;; esac
printf 'CI fixture deleted; no flashable image or bootloader artifact created.\n'