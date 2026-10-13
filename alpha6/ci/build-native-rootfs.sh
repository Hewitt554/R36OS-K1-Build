#!/usr/bin/env bash
# DEVELOPMENT CI only. Never touches SD cards, raw block devices or current OS images.
set -euo pipefail
test "$(id -u)" = 0 || { echo "Build requires disposable root CI" >&2; exit 2; }
test "$(uname -m)" = aarch64 || { echo "Build requires native aarch64" >&2; exit 2; }
BASE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$BASE/.build/rootfs"
DIST="$BASE/dist"
test ! -e "$ROOT" || { echo "Refusing reused build directory" >&2; exit 2; }
for command_name in debootstrap chroot tar sha256sum zstd mount umount; do
  command -v "$command_name" >/dev/null || exit 2
done
mkdir -p "$ROOT" "$DIST"
debootstrap --arch=arm64 --variant=minbase bookworm "$ROOT" https://deb.debian.org/debian
cat > "$ROOT/etc/apt/sources.list" <<'END_APT'
deb https://deb.debian.org/debian bookworm main contrib non-free-firmware
deb https://deb.debian.org/debian bookworm-updates main contrib non-free-firmware
deb https://security.debian.org/debian-security bookworm-security main contrib non-free-firmware
END_APT
cat > "$ROOT/usr/sbin/policy-rc.d" <<'END_POLICY'
#!/bin/sh
exit 101
END_POLICY
chmod 755 "$ROOT/usr/sbin/policy-rc.d"
mounted=no
cleanup() {
  if [ "$mounted" = yes ]; then
    umount -R "$ROOT/dev" 2>/dev/null || true
    umount -R "$ROOT/sys" 2>/dev/null || true
    umount -R "$ROOT/proc" 2>/dev/null || true
  fi
}
trap cleanup EXIT
mount -t proc proc "$ROOT/proc"
mount --rbind /sys "$ROOT/sys"; mount --make-rslave "$ROOT/sys"
mount --rbind /dev "$ROOT/dev"; mount --make-rslave "$ROOT/dev"
mounted=yes
chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get -qq update
packages="$(grep -Ev '^[[:space:]]*(#|$)' "$BASE/manifest/core-arm64-packages.txt" | tr '\n' ' ')"
test "$(wc -w <<< "$packages")" -ge 10 || exit 3
# Intentional word splitting: manifest is whitespace-separated fixed Debian package names.
chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $packages
rm -f "$ROOT/usr/sbin/policy-rc.d" "$ROOT/etc/os-release"
install -d "$ROOT/etc/r36os" "$ROOT/usr/local/sbin" "$ROOT/r36state" "$ROOT/r36update" "$ROOT/roms2"
cat > "$ROOT/etc/os-release" <<'END_OS'
NAME="R36OS"
PRETTY_NAME="R36OS Alpha 6 Native Development Root"
ID=r36os
ID_LIKE=debian
VERSION_ID="0.6.0-cp06"
VERSION_CODENAME=bookworm
END_OS
cat > "$ROOT/etc/r36os-release" <<'END_R36'
NAME="R36OS"
ID=r36os
VERSION_ID="0.6.0-cp06"
R36OS_UPSTREAM="debian-bookworm-arm64"
R36OS_KERNEL_TARGET="6.12-k1-UNTESTED"
R36OS_RECOVERY_STATUS="NOT_IMPLEMENTED"
R36OS_IMAGE_STATUS="NOT_FLASHABLE"
END_R36
cat > "$ROOT/etc/r36os/firstboot-policy.conf" <<'END_SAFETY'
update_apply_enabled=false
boot_partition_update_enabled=false
kernel_update_enabled=false
recovery_snapshot_enabled=false
flash_image_ready=false
END_SAFETY
cat > "$ROOT/usr/local/sbin/r36os-update-preflight" <<'END_PREFLIGHT'
#!/bin/sh
set -eu
grep -q '^ID=r36os$' /etc/r36os-release
grep -q '^update_apply_enabled=false$' /etc/r36os/firstboot-policy.conf
grep -q '^flash_image_ready=false$' /etc/r36os/firstboot-policy.conf
echo 'Updater disabled: CP06 has no independent recovery or safe boot'
END_PREFLIGHT
cat > "$ROOT/usr/local/sbin/r36os-hardware-report" <<'END_HARDWARE'
#!/bin/sh
set -eu
mkdir -p /run/r36os
{
  echo 'R36OS CP06 hardware observation'
  uname -a
  if [ -r /proc/device-tree/model ]; then tr '\000' ' ' < /proc/device-tree/model; echo; fi
  for f in /sys/class/graphics/fb0/virtual_size /sys/class/power_supply/*/status; do
    if [ -r "$f" ]; then printf '%s: ' "$f"; head -c 100 "$f"; echo; fi
  done
} > /run/r36os/hardware-report.txt
END_HARDWARE
chmod 755 "$ROOT/usr/local/sbin/r36os-update-preflight" "$ROOT/usr/local/sbin/r36os-hardware-report"
install -d "$ROOT/etc/systemd/system/multi-user.target.wants"
cat > "$ROOT/etc/systemd/system/r36os-hardware-report.service" <<'END_SERVICE'
[Unit]
Description=R36OS native hardware report (read-only)
After=local-fs.target
ConditionPathExists=/sys/class
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/r36os-hardware-report
NoNewPrivileges=yes
ProtectSystem=strict
RuntimeDirectory=r36os
ReadWritePaths=/run/r36os
[Install]
WantedBy=multi-user.target
END_SERVICE
ln -s /etc/systemd/system/r36os-hardware-report.service "$ROOT/etc/systemd/system/multi-user.target.wants/r36os-hardware-report.service"
cat > "$ROOT/etc/fstab" <<'END_FSTAB'
# Root UUID and SD2 mapping require hardware validation, not yet configured.
LABEL=R36STATE /r36state ext4 defaults,noatime,nofail 0 2
LABEL=R36UPDATE /r36update vfat defaults,nofail,umask=0022 0 0
END_FSTAB
chroot "$ROOT" dpkg-query -W > "$DIST/r36os-native-packages.tsv"
chroot "$ROOT" /usr/local/sbin/r36os-update-preflight
if chroot "$ROOT" dpkg-query -W emulationstation-go2 >/dev/null 2>&1; then echo 'Unexpected ArkOS package' >&2; exit 3; fi
rm -f "$ROOT/etc/ssh/ssh_host_"* "$ROOT/etc/machine-id"
: > "$ROOT/etc/machine-id"
rm -rf "$ROOT/var/lib/apt/lists/"* "$ROOT/var/cache/apt/archives/"* "$ROOT/var/log/"*
mkdir -p "$ROOT/var/log"
cleanup
mounted=no
for path in "$ROOT/proc" "$ROOT/sys" "$ROOT/dev"; do
  if mountpoint -q "$path"; then echo "Refusing archive with live virtual mount: $path" >&2; exit 3; fi
done
{
  echo 'R36OS Alpha 6 CP06 native ARM64 development root'
  echo "UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Installed packages: $(wc -l < "$DIST/r36os-native-packages.tsv")"
  echo "Allocated root bytes: $(du -sb "$ROOT" | cut -f1)"
  echo 'Target kernel: K1 Linux 6.12 (NOT BOOT TESTED)'
  echo 'No boot chain, no independent recovery, NOT FLASHABLE'
} > "$DIST/r36os-native-build-metadata.txt"
for path in "$ROOT/proc" "$ROOT/sys" "$ROOT/dev"; do
  if mountpoint -q "$path"; then echo "Refusing archive with live virtual mount: $path" >&2; exit 3; fi
done
tar --numeric-owner --one-file-system -C "$ROOT" -cf - . | zstd -T0 -3 -o "$DIST/r36os-native-rootfs-arm64-cp06.tar.zst"
(cd "$DIST" && sha256sum r36os-native-rootfs-arm64-cp06.tar.zst > r36os-native-rootfs-arm64-cp06.sha256)
echo 'Clean R36OS native userspace created (NOT FLASHABLE)'
