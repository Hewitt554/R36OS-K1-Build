#!/bin/bash
# Native R36OS Chapter 1 read-only dependency capture.
# Writes evidence only under /r36state/logs/native-audit.
# It must not modify services, packages, networking, boot files or configuration.

set -u
umask 077

TS="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo unknown)"
BASE="${R36_NATIVE_AUDIT_ROOT:-/r36state/logs/native-audit}"
OUT="${1:-$BASE/native-c01-$TS}"
EXPORTS="$BASE/exports"

mkdir -p "$OUT" "$EXPORTS" || exit 20

note() {
  printf '%s\n' "$*" >>"$OUT/capture.log"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

capture_cmd() {
  name="$1"
  shift
  {
    printf '# command:'
    printf ' %q' "$@"
    printf '\n'
    "$@"
  } >"$OUT/$name" 2>&1 || true
}

copy_safe() {
  src="$1"
  dst="$2"
  if [ -r "$src" ]; then
    cp -f "$src" "$OUT/$dst" 2>/dev/null || true
  fi
}

note "format=R36OS_NATIVE_C01_CAPTURE_V1"
note "timestamp=$TS"
note "kernel=$(uname -r 2>/dev/null || true)"

capture_cmd uname.txt uname -a
copy_safe /etc/os-release os-release.txt
copy_safe /etc/debian_version debian-version.txt
copy_safe /etc/r36os-release r36os-release.txt
copy_safe /proc/cmdline cmdline.txt

if have systemctl; then
  capture_cmd systemd-version.txt systemctl --version
  capture_cmd systemd-failed.txt systemctl --failed --no-pager
  capture_cmd systemd-unit-files.txt systemctl list-unit-files --no-pager
  capture_cmd systemd-running-units.txt systemctl list-units --type=service --all --no-pager
  for u in \
    systemd-journald.service \
    systemd-udevd.service \
    NetworkManager.service \
    351mp.service \
    emulationstation.service \
    play-video.service \
    networkwatchdaemon.service \
    r36os.service \
    r36os-zram.service \
    r36os-usb-tune.service; do
      systemctl cat "$u" >"$OUT/unit-$u.txt" 2>&1 || true
  done
fi
if have udevadm; then capture_cmd udev-version.txt udevadm --version; fi
if have journalctl; then capture_cmd journal-status.txt journalctl --disk-usage; fi

if have dpkg-query; then
  dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' \
    >"$OUT/dpkg-packages.tsv" 2>"$OUT/dpkg-packages.err" || true
fi

copy_safe /etc/fstab fstab.txt
capture_cmd mounts-proc.txt cat /proc/mounts
if have findmnt; then capture_cmd findmnt.txt findmnt -R; fi
if have lsblk; then capture_cmd lsblk.txt lsblk -o NAME,PATH,TYPE,FSTYPE,LABEL,UUID,PARTUUID,SIZE,MOUNTPOINTS; fi
if have blkid; then capture_cmd blkid.txt blkid; fi
if have df; then capture_cmd df.txt df -hT; fi

if [ -d /boot ]; then
  (
    cd /boot || exit 0
    find . -maxdepth 2 -type f -printf '%P\t%s\n' 2>/dev/null | LC_ALL=C sort
  ) >"$OUT/boot-files.tsv" 2>/dev/null || true
  (
    cd /boot || exit 0
    find . -maxdepth 2 -type f \( \
      -name 'Image*' -o -name 'zImage*' -o -name 'uInitrd*' -o \
      -name '*.dtb' -o -name 'boot.ini' -o -name 'boot.scr' \
    \) -print0 2>/dev/null | LC_ALL=C sort -z | xargs -0 -r sha256sum
  ) >"$OUT/boot-critical.sha256" 2>/dev/null || true
fi

{
  for d in /etc/udev/rules.d /lib/udev/rules.d /usr/lib/udev/rules.d; do
    [ -d "$d" ] || continue
    find "$d" -maxdepth 1 -type f -name '*.rules' -print0 2>/dev/null
  done
} | sort -zu | while IFS= read -r -d '' f; do
  sha256sum "$f" 2>/dev/null || true
done >"$OUT/udev-rules.sha256"

{
  for d in /etc/udev/rules.d /lib/udev/rules.d /usr/lib/udev/rules.d; do
    [ -d "$d" ] || continue
    grep -HniE \
      'rk817|rk805|gpio|joystick|input|backlight|mmc|rtl|8188|wifi|wlan|bluetooth|alsa|sound|headphone|dri|mali|panfrost' \
      "$d"/*.rules 2>/dev/null || true
  done
} >"$OUT/udev-hardware-lines.txt"

copy_safe /proc/config.gz kernel-config.gz
if have lsmod; then capture_cmd lsmod.txt lsmod; fi
for m in panfrost drm rockchipdrm rtl8xxxu cfg80211 mac80211 rfkill libarc4; do
  if have modinfo; then modinfo "$m" >"$OUT/modinfo-$m.txt" 2>&1 || true; fi
done

if [ -d /lib/firmware ]; then
  find /lib/firmware -type f -printf '%p\t%s\n' 2>/dev/null | LC_ALL=C sort \
    >"$OUT/firmware-files.tsv" || true
  find /lib/firmware -type f \( \
      -iname '*rtl*' -o -iname '*8188*' -o -iname '*realtek*' -o \
      -iname '*rockchip*' -o -iname '*rk817*' -o -iname '*brcm*' \
    \) -print0 2>/dev/null | LC_ALL=C sort -z | xargs -0 -r sha256sum \
    >"$OUT/firmware-relevant.sha256" 2>/dev/null || true
fi

if have ldconfig; then
  ldconfig -p 2>/dev/null | grep -Ei \
    'lib(EGL|GLES|gbm|drm|X11|wayland|vulkan|Mali|panfrost)' \
    >"$OUT/graphics-ldconfig.txt" || true
fi
{
  find /lib /usr/lib /usr/local/lib -xdev \( -type f -o -type l \) \( \
    -name 'libEGL.so*' -o -name 'libGLESv2.so*' -o -name 'libgbm.so*' -o \
    -name 'libdrm.so*' -o -name 'libMali.so*' -o -name 'libvulkan*.so*' \
  \) -print 2>/dev/null
} | LC_ALL=C sort -u >"$OUT/graphics-library-paths.txt"

while IFS= read -r f; do
  [ -e "$f" ] || [ -L "$f" ] || continue
  printf '%s\t' "$f"
  if [ -L "$f" ]; then
    printf 'symlink->%s\n' "$(readlink "$f" 2>/dev/null || true)"
  else
    sha256sum "$f" 2>/dev/null | awk '{print $1}'
  fi
done <"$OUT/graphics-library-paths.txt" >"$OUT/graphics-library-identities.tsv"

if have dpkg-query; then
  while IFS= read -r f; do
    [ -e "$f" ] || [ -L "$f" ] || continue
    dpkg-query -S "$f" 2>/dev/null || true
  done <"$OUT/graphics-library-paths.txt" | LC_ALL=C sort -u \
    >"$OUT/graphics-library-packages.txt"
fi

if [ -d /sys/class/drm ]; then
  find /sys/class/drm -maxdepth 2 -type f \( \
    -name status -o -name enabled -o -name modes -o -name uevent \
  \) -print 2>/dev/null | LC_ALL=C sort >"$OUT/drm-sysfs-files.txt"
  while IFS= read -r f; do
    printf '### %s\n' "$f"
    cat "$f" 2>/dev/null || true
  done <"$OUT/drm-sysfs-files.txt" >"$OUT/drm-sysfs.txt"
fi
ls -l /dev/dri >"$OUT/dev-dri.txt" 2>&1 || true

copy_safe /proc/bus/input/devices input-devices.txt
if [ -d /sys/class/backlight ]; then
  find /sys/class/backlight -maxdepth 2 -type f \( \
    -name max_brightness -o -name brightness -o -name actual_brightness -o -name type \
  \) -print 2>/dev/null | LC_ALL=C sort | while read -r f; do
    printf '%s=' "$f"
    cat "$f" 2>/dev/null || true
  done >"$OUT/backlight.txt"
fi

for p in /sys/class/power_supply/*; do
  [ -d "$p" ] || continue
  n="$(basename "$p")"
  {
    echo "name=$n"
    for k in type status capacity capacity_level present online voltage_now current_now charge_now charge_full charge_full_design energy_now energy_full energy_full_design; do
      [ -r "$p/$k" ] || continue
      printf '%s=' "$k"
      cat "$p/$k" 2>/dev/null || true
    done
  } >"$OUT/power-$n.txt"
done

copy_safe /proc/asound/cards alsa-cards.txt
copy_safe /proc/asound/devices alsa-devices.txt
if have aplay; then capture_cmd alsa-aplay-list.txt aplay -l; fi
if have arecord; then capture_cmd alsa-arecord-list.txt arecord -l; fi
if have amixer; then
  capture_cmd alsa-amixer-info.txt amixer -c 0 info
  capture_cmd alsa-amixer-controls.txt amixer -c 0 controls
fi

if [ -d /proc/device-tree ]; then
  (
    cd /proc/device-tree || exit 0
    find . -type f -printf '%P\t%s\n' 2>/dev/null | LC_ALL=C sort
  ) >"$OUT/device-tree-files.tsv" || true
  tar -C /proc/device-tree -czf "$OUT/device-tree.tar.gz" . 2>"$OUT/device-tree-tar.err" || true
  for f in /proc/device-tree/model /proc/device-tree/compatible; do
    [ -r "$f" ] || continue
    printf '%s: ' "$f"
    tr '\0' '\n' <"$f" 2>/dev/null || true
  done >"$OUT/device-tree-root.txt"
fi

for c in \
  bash dash systemctl journalctl udevadm modprobe insmod depmod \
  nmcli NetworkManager iw rfkill lsusb \
  mount umount findmnt lsblk blkid \
  curl wget tar gzip xz lz4 zstd cpio \
  file readelf strings \
  amixer aplay arecord \
  plymouth chvt \
  box64 wine; do
  if have "$c"; then
    printf '%s\t%s\n' "$c" "$(command -v "$c")"
  else
    printf '%s\tMISSING\n' "$c"
  fi
done >"$OUT/tool-availability.tsv"

# Privacy guard: intentionally DO NOT copy NetworkManager profiles, SSH keys,
# GitHub secrets/tokens, shell histories, environment dumps, Wi-Fi scans,
# IP address output or MAC-address inventories.

(
  cd "$OUT" || exit 1
  find . -type f ! -name MANIFEST.sha256 -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
) >"$OUT/MANIFEST.sha256"

ARCHIVE="$EXPORTS/R36OS-native-c01-audit-$TS.tar.gz"
tar -C "$(dirname "$OUT")" -czf "$ARCHIVE" "$(basename "$OUT")" || exit 21
sha256sum "$ARCHIVE" >"$ARCHIVE.sha256"

printf 'status=PASS\narchive=%s\nsha256=%s\n' \
  "$ARCHIVE" \
  "$(sha256sum "$ARCHIVE" | awk '{print $1}')" \
  >"$OUT/RESULT.conf"

printf 'R36OS_NATIVE_C01_CAPTURE=PASS archive=%s\n' "$ARCHIVE"
