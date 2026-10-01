#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$PWD/out}"

SNAPSHOT=20260930T000000Z
SOURCE_DATE_EPOCH=1790726400
SUITE=trixie
ARCH=arm64
ROOTFS_NAME=r36os-native-c02-rootfs-arm64
KEYRING="${R36_DEBIAN_KEYRING:-/usr/share/keyrings/debian-archive-keyring.gpg}"
WORK="${RUNNER_TEMP:-/tmp}/r36os-native-c02-$$"
ROOT="$WORK/rootfs"
SOURCES="$WORK/sources.list"
PACKAGE_CSV="$WORK/packages.csv"

fail(){ echo "NATIVE_C02_BUILD=FAIL $*" >&2; exit 1; }

cleanup(){ sudo rm -rf "$WORK" 2>/dev/null || rm -rf "$WORK" 2>/dev/null || true; }
trap cleanup EXIT

rm -rf "$OUT"
mkdir -p "$OUT" "$WORK"

for c in mmdebstrap qemu-aarch64-static dpkg-query python3 tar zstd sha256sum file; do
  command -v "$c" >/dev/null 2>&1 || fail "missing-host-tool-$c"
done
test -r "$KEYRING" || fail debian-keyring-missing

grep -Ev '^[[:space:]]*(#|$)' "$HERE/packages-base.txt" | LC_ALL=C sort -u >"$WORK/packages.txt"
paste -sd, "$WORK/packages.txt" >"$PACKAGE_CSV"

cat >"$SOURCES" <<EOF
deb [arch=$ARCH check-valid-until=no] https://snapshot.debian.org/archive/debian/$SNAPSHOT/ $SUITE main
deb [arch=$ARCH check-valid-until=no] https://snapshot.debian.org/archive/debian/$SNAPSHOT/ $SUITE-updates main
deb [arch=$ARCH check-valid-until=no] https://snapshot.debian.org/archive/debian-security/$SNAPSHOT/ $SUITE-security main
EOF

export SOURCE_DATE_EPOCH
export TZ=UTC
export LC_ALL=C.UTF-8

sudo rm -rf "$ROOT"
sudo mkdir -p "$ROOT"

sudo -E mmdebstrap \
  --mode=root \
  --variant=apt \
  --architectures="$ARCH" \
  --include="$(cat "$PACKAGE_CSV")" \
  --aptopt='APT::Install-Recommends "false"' \
  --aptopt='APT::Install-Suggests "false"' \
  --aptopt='Acquire::Check-Valid-Until "false"' \
  --aptopt='Acquire::Languages "none"' \
  --keyring="$KEYRING" \
  "$SUITE" \
  "$ROOT" \
  "$SOURCES"

sudo rm -f "$ROOT/etc/machine-id" "$ROOT/var/lib/dbus/machine-id"
sudo install -m 0644 /dev/null "$ROOT/etc/machine-id"
sudo rm -f "$ROOT/var/lib/systemd/random-seed"
sudo rm -rf "$ROOT/var/cache/apt/archives/"*.deb "$ROOT/var/lib/apt/lists/"*
sudo find "$ROOT/var/log" -type f -exec truncate -s 0 {} + 2>/dev/null || true
sudo rm -f "$ROOT/etc/resolv.conf"
sudo ln -s /run/NetworkManager/resolv.conf "$ROOT/etc/resolv.conf"

sudo cp -a "$HERE/overlay/." "$ROOT/"

printf '%s\n' 'r36os-native' | sudo tee "$ROOT/etc/hostname" >/dev/null
cat <<'EOF' | sudo tee "$ROOT/etc/fstab" >/dev/null
# R36OS native C02 artifact.
# Hardware mounts are intentionally supplied by Chapter 3/4 platform policy.
EOF

sudo mkdir -p "$ROOT/etc/NetworkManager/conf.d"
cat <<'EOF' | sudo tee "$ROOT/etc/NetworkManager/conf.d/10-r36os-native.conf" >/dev/null
[main]
plugins=keyfile
rc-manager=symlink

[logging]
level=INFO
domains=DEFAULT
EOF

sudo mkdir -p "$ROOT/opt/r36os/native"
cat <<EOF | sudo tee "$ROOT/opt/r36os/native/C02_BUILD.conf" >/dev/null
format=R36OS_NATIVE_ROOTFS_V1
chapter=C02
distribution=Debian
suite=$SUITE
architecture=$ARCH
snapshot=$SNAPSHOT
source_date_epoch=$SOURCE_DATE_EPOCH
bootable_by_chapter=no
EOF

sudo mkdir -p "$ROOT/usr/local/libexec"
sudo install -m 0755 "$HERE/overlay/usr/local/libexec/r36os-native-inventory" \
  "$ROOT/usr/local/libexec/r36os-native-inventory"

test -x "$ROOT/lib/systemd/systemd" || fail systemd-binary
test -L "$ROOT/sbin/init" || test -x "$ROOT/sbin/init" || fail init-missing
test -x "$ROOT/usr/bin/journalctl" || fail journalctl-missing
test -x "$ROOT/usr/bin/udevadm" || fail udevadm-missing
test -x "$ROOT/usr/sbin/modprobe" || test -x "$ROOT/sbin/modprobe" || fail modprobe-missing
test -x "$ROOT/usr/bin/nmcli" || fail nmcli-missing
test -x "$ROOT/usr/sbin/NetworkManager" || fail networkmanager-missing
test -x "$ROOT/usr/bin/iw" || fail iw-missing
test -x "$ROOT/usr/sbin/rfkill" || test -x "$ROOT/usr/bin/rfkill" || fail rfkill-missing
test -x "$ROOT/usr/bin/lsusb" || fail lsusb-missing

file "$ROOT/lib/systemd/systemd" | grep -Eq 'ARM aarch64|ARM64' || fail systemd-not-arm64

if find "$ROOT/boot" -type f -print -quit 2>/dev/null | grep -q .; then fail boot-files-present; fi
if find "$ROOT" -type f \( -name 'Image' -o -name 'zImage' -o -name '*.dtb' -o -name 'uInitrd*' \) -print -quit | grep -q .; then
  fail kernel-or-dtb-present
fi

SCAN="$WORK/legacy-scan.txt"
: >"$SCAN"
for d in "$ROOT/etc" "$ROOT/opt" "$ROOT/usr/local" "$ROOT/usr/lib/systemd" "$ROOT/lib/systemd"; do
  [ -e "$d" ] || continue
  grep -RniE \
    'ArkOS|AeUX|PortMaster|weston_pkg\.squashfs|westonwrap\.sh|CrustyGBM|libcrusty|crusty_glx_gl4es|Bifrost-r13p0|GO-Super/Gamepad|networkwatchdaemon|play-video\.service|351mp\.service' \
    "$d" >>"$SCAN" 2>/dev/null || true
done
test ! -s "$SCAN" || { cat "$SCAN" >&2; fail forbidden-legacy-runtime; }

for p in \
  "$ROOT/opt/system/Tools/PortMaster" \
  "$ROOT/opt/tools/PortMaster" \
  "$ROOT/roms/ports/PortMaster"; do
  [ ! -e "$p" ] || fail "forbidden-path-$p"
done

cp "$WORK/packages.txt" "$OUT/requested-packages.txt"
sudo dpkg-query --admindir="$ROOT/var/lib/dpkg" \
  -W -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
  | LC_ALL=C sort >"$OUT/resolved-packages.tsv"

grep -Eq $'\tarm64\t' "$OUT/resolved-packages.tsv" || fail no-arm64-packages
if grep -Eq '^linux-image|^linux-headers|^grub|^emulationstation' "$OUT/resolved-packages.tsv"; then
  fail forbidden-package
fi

(
  cd "$HERE/overlay"
  find . -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum
) >"$OUT/overlay.sha256"

python3 "$HERE/make_rootfs_manifest.py" "$ROOT" >"$OUT/rootfs-manifest.tsv"

cp "$SOURCES" "$OUT/sources.list"
cat >"$OUT/BUILD_INFO.txt" <<EOF
format=R36OS_NATIVE_C02_BUILD_V1
suite=$SUITE
architecture=$ARCH
snapshot=$SNAPSHOT
source_date_epoch=$SOURCE_DATE_EPOCH
mmdebstrap=$(mmdebstrap --version 2>&1 | head -1)
qemu_aarch64=$(qemu-aarch64-static --version 2>&1 | head -1)
builder_sha256=$(sha256sum "$HERE/build_rootfs.sh" | awk '{print $1}')
package_list_sha256=$(sha256sum "$HERE/packages-base.txt" | awk '{print $1}')
overlay_manifest_sha256=$(sha256sum "$OUT/overlay.sha256" | awk '{print $1}')
resolved_packages_sha256=$(sha256sum "$OUT/resolved-packages.tsv" | awk '{print $1}')
rootfs_manifest_sha256=$(sha256sum "$OUT/rootfs-manifest.tsv" | awk '{print $1}')
EOF

sudo find "$ROOT" -xdev -print0 | sudo xargs -0 touch -h -d "@$SOURCE_DATE_EPOCH"

sudo tar \
  --sort=name \
  --mtime="@$SOURCE_DATE_EPOCH" \
  --clamp-mtime \
  --owner=0 --group=0 --numeric-owner \
  --acls --xattrs --xattrs-include='*' \
  -C "$ROOT" -cf "$WORK/rootfs.tar" .

zstd -q -19 -T1 --no-progress "$WORK/rootfs.tar" -o "$OUT/$ROOTFS_NAME.tar.zst"
sha256sum "$OUT/$ROOTFS_NAME.tar.zst" >"$OUT/$ROOTFS_NAME.tar.zst.sha256"

{
  echo "format=R36OS_NATIVE_C02_AUDIT_V1"
  echo "status=PASS"
  echo "legacy_scan_empty=yes"
  echo "kernel_payload_present=no"
  echo "architecture=arm64"
  echo "init=systemd"
  echo "snapshot=$SNAPSHOT"
  echo "archive_sha256=$(sha256sum "$OUT/$ROOTFS_NAME.tar.zst" | awk '{print $1}')"
  echo "archive_size=$(stat -c %s "$OUT/$ROOTFS_NAME.tar.zst")"
} >"$OUT/AUDIT.conf"

echo "NATIVE_C02_BUILD=PASS archive=$OUT/$ROOTFS_NAME.tar.zst sha256=$(sha256sum "$OUT/$ROOTFS_NAME.tar.zst" | awk '{print $1}')"
