#!/bin/bash
set -euo pipefail

[ "$#" -eq 1 ] || { echo "usage: build_rootfs.sh <output-dir>" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "must run as root" >&2; exit 3; }

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(readlink -m "$1")"
CONF="$HERE/build.conf"
PKGS="$HERE/packages.txt"
SCAN="$HERE/forbidden_scan.py"
ROOT="$OUT/rootfs"
META="$OUT/meta"

val(){ awk -F= -v k="$1" '$1==k{print substr($0,index($0,"=")+1);exit}' "$CONF"; }
SNAPSHOT="$(val snapshot)"
SUITE="$(val suite)"
ARCH="$(val architecture)"
SNAPSHOT_URL="$(val snapshot_url)"
KREL="$(val kernel_release)"
EPOCH=1790812800

[ "$SNAPSHOT" = 20261001T082322Z ] || { echo bad-snapshot >&2; exit 10; }
[ "$SUITE" = trixie ] || { echo bad-suite >&2; exit 11; }
[ "$ARCH" = arm64 ] || { echo bad-arch >&2; exit 12; }
[ "$SNAPSHOT_URL" = "https://snapshot.debian.org/archive/debian/20261001T082322Z/" ] || { echo bad-snapshot-url >&2; exit 13; }

rm -rf "$OUT"
mkdir -p "$ROOT" "$META"

INCLUDE="$(awk 'NF && $1 !~ /^#/ {print $1}' "$PKGS" | paste -sd, -)"
[ -n "$INCLUDE" ] || { echo empty-package-list >&2; exit 14; }

MIRROR="deb [check-valid-until=no] $SNAPSHOT_URL $SUITE main"
printf '%s\n' "$MIRROR" >"$META/apt-source.txt"
cp "$CONF" "$META/build.conf"
awk 'NF && $1 !~ /^#/ {print $1}' "$PKGS" >"$META/requested-packages.txt"

export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C
export SOURCE_DATE_EPOCH="$EPOCH"

mmdebstrap \
  --mode=root \
  --variant=minbase \
  --architectures="$ARCH" \
  --components=main \
  --include="$INCLUDE" \
  --aptopt='APT::Install-Recommends "false"' \
  --aptopt='APT::Install-Suggests "false"' \
  --aptopt='Acquire::Check-Valid-Until "false"' \
  --keyring=/usr/share/keyrings/debian-archive-keyring.gpg \
  "$SUITE" "$ROOT" "$MIRROR"

install -d \
  "$ROOT/etc/systemd/journald.conf.d" \
  "$ROOT/etc/r36os" \
  "$ROOT/r36state" \
  "$ROOT/roms2" \
  "$ROOT/usr/lib/modules/$KREL" \
  "$ROOT/var/log"

cat >"$ROOT/etc/r36os-release" <<EOF
R36OS_NAME="R36OS"
R36OS_VERSION="Native Prototype C02"
R36OS_PACKAGE_VERSION="native-c02"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="native-prototype"
R36OS_USERSPACE="Debian 13 trixie arm64"
R36OS_DEBIAN_SNAPSHOT="$SNAPSHOT"
R36OS_KERNEL_RELEASE="$KREL"
EOF

printf 'r36os-native\n' >"$ROOT/etc/hostname"
cat >"$ROOT/etc/hosts" <<'EOF'
127.0.0.1 localhost
127.0.1.1 r36os-native
::1 localhost ip6-localhost ip6-loopback
EOF
printf 'LANG=C.UTF-8\n' >"$ROOT/etc/default/locale"
: >"$ROOT/etc/machine-id"
rm -f "$ROOT/etc/resolv.conf"
ln -s /run/NetworkManager/resolv.conf "$ROOT/etc/resolv.conf"

cat >"$ROOT/etc/systemd/journald.conf.d/10-r36os-native.conf" <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=16M
RuntimeKeepFree=32M
Compress=yes
ForwardToConsole=no
EOF

cat >"$ROOT/etc/fstab" <<'EOF'
# R36OS Native prototype.
# Root, R36STATE and K1 modules are mounted by the C03 initramfs.
# SD2/user-data mounting is intentionally deferred until later platform bring-up.
EOF

# Keep NetworkManager installed for later driver work but out of the C03 boot critical path.
rm -f \
  "$ROOT/etc/systemd/system/multi-user.target.wants/NetworkManager.service" \
  "$ROOT/etc/systemd/system/network-online.target.wants/NetworkManager-wait-online.service" \
  "$ROOT/etc/systemd/system/dbus-org.freedesktop.NetworkManager.service" \
  2>/dev/null || true

# Lock root login in the build artifact. C03 health is service-driven, not login-driven.
python3 - "$ROOT/etc/shadow" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
lines=[]
for line in p.read_text().splitlines():
    parts=line.split(':')
    if parts and parts[0]=='root':
        parts[1]='!'
        line=':'.join(parts)
    lines.append(line)
p.write_text('\n'.join(lines)+'\n')
PY

rm -rf \
  "$ROOT/var/lib/apt/lists/"* \
  "$ROOT/var/cache/apt/"* \
  "$ROOT/var/cache/debconf/"* \
  "$ROOT/var/log/"* \
  "$ROOT/tmp/"* \
  "$ROOT/var/tmp/"*
mkdir -p "$ROOT/var/lib/apt/lists/partial" "$ROOT/var/cache/apt/archives/partial" "$ROOT/tmp" "$ROOT/var/tmp" "$ROOT/var/log"
chmod 1777 "$ROOT/tmp" "$ROOT/var/tmp"
rm -f "$ROOT/var/lib/systemd/random-seed"

dpkg-query --admindir="$ROOT/var/lib/dpkg" -W -f='${binary:Package}\t${Version}\t${Architecture}\n' \
  | LC_ALL=C sort >"$META/packages.tsv"

[ -x "$ROOT/lib/systemd/systemd" ] || [ -x "$ROOT/usr/lib/systemd/systemd" ] || { echo missing-systemd >&2; exit 20; }
[ -e "$ROOT/sbin/init" ] || { echo missing-init >&2; exit 21; }
[ -x "$ROOT/usr/bin/systemctl" ] || [ -x "$ROOT/bin/systemctl" ] || { echo missing-systemctl >&2; exit 22; }
[ -x "$ROOT/usr/bin/journalctl" ] || [ -x "$ROOT/bin/journalctl" ] || { echo missing-journalctl >&2; exit 23; }
[ -x "$ROOT/usr/bin/udevadm" ] || [ -x "$ROOT/bin/udevadm" ] || { echo missing-udevadm >&2; exit 24; }
[ -x "$ROOT/usr/sbin/modprobe" ] || [ -x "$ROOT/sbin/modprobe" ] || { echo missing-modprobe >&2; exit 25; }

python3 "$SCAN" "$ROOT" --packages "$META/packages.tsv" --report "$META/forbidden-scan.txt"

python3 - "$ROOT" "$EPOCH" <<'PY'
from pathlib import Path
import os,sys
root=Path(sys.argv[1])
epoch=int(sys.argv[2])
for p in sorted(root.rglob('*'), key=lambda x: len(x.parts), reverse=True):
    try:
        os.utime(p,(epoch,epoch),follow_symlinks=False)
    except (FileNotFoundError,PermissionError,NotImplementedError):
        pass
os.utime(root,(epoch,epoch),follow_symlinks=False)
PY

python3 - "$ROOT" "$META/files.tsv" <<'PY'
from pathlib import Path
import hashlib,os,stat,sys
root=Path(sys.argv[1]); out=Path(sys.argv[2])
rows=[]
for p in sorted(root.rglob('*')):
    rel='/' + str(p.relative_to(root))
    st=p.lstat()
    mode=f'{stat.S_IMODE(st.st_mode):04o}'
    if p.is_symlink():
        rows.append(f'L\t{mode}\t{rel}\t{os.readlink(p)}')
    elif p.is_file():
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append(f'F\t{mode}\t{rel}\t{st.st_size}\t{h}')
    elif p.is_dir():
        rows.append(f'D\t{mode}\t{rel}')
out.write_text('\n'.join(rows)+'\n')
PY

{
  echo 'format=R36OS_NATIVE_C02_ROOTFS_V1'
  echo "suite=$SUITE"
  echo "architecture=$ARCH"
  echo "snapshot=$SNAPSHOT"
  echo "kernel_release=$KREL"
  echo "package_count=$(wc -l <"$META/packages.tsv" | tr -d ' ')"
  echo "file_manifest_sha256=$(sha256sum "$META/files.tsv" | awk '{print $1}')"
  echo "package_manifest_sha256=$(sha256sum "$META/packages.tsv" | awk '{print $1}')"
  echo "forbidden_scan=PASS"
} >"$META/ROOTFS.conf"

ARCHIVE="$OUT/r36os-native-c02-rootfs.tar.zst"
tar \
  --sort=name \
  --mtime="@$EPOCH" \
  --owner=0 --group=0 --numeric-owner \
  --pax-option=delete=atime,delete=ctime \
  -C "$ROOT" -cf - . \
  | zstd -19 -T1 --no-progress -o "$ARCHIVE"
sha256sum "$ARCHIVE" >"$ARCHIVE.sha256"

rm -rf "$ROOT"
echo "R36OS_NATIVE_C02_BUILD=PASS archive_sha256=$(awk '{print $1}' "$ARCHIVE.sha256")"
