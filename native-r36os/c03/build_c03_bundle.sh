#!/bin/bash
set -euo pipefail
[ "$#" -eq 4 ] || { echo "usage: build_c03_bundle.sh <C02-rootfs.tar.zst> <R54-uInitrd> <R59-hooked-boot.ini> <out-dir>" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "build_c03_bundle.sh must run as root because the rootfs contains device nodes" >&2; exit 3; }
HERE="$(cd "$(dirname "$0")" && pwd)"
C02="$1"
BASE_UINITRD="$2"
CURRENT_HOOK="$3"
OUT="$(readlink -m "$4")"
WORK="$OUT/work"
ROOT="$WORK/rootfs"
BUNDLE="$OUT/bundle"
EPOCH=1790812800
C02_SHA_EXPECTED=42eec8dc524fcd821d0919bb3d185a3a0894f5bbf48fa0bf36d0a3834b454fac
R54_UINITRD_SHA=023a0d2adc113b2d1fea6826387ab6e03e4d479cf5fa36c9b9ff86cf41fd1925
CURRENT_HOOK_SHA=e389b843ca85cbed59e9227247b2735356f5f551351e8e274e2731fbb15e3c9c
K1_CID=9d7bd2334f315d98b482f850
KREL=6.12.94-r36os-k1
STATE_UUID=a25488c6-742d-4555-82d1-e28ffc848af3

sha(){ sha256sum "$1" | awk '{print $1}'; }
[ "$(sha "$C02")" = "$C02_SHA_EXPECTED" ] || { echo C02-rootfs-sha-mismatch >&2; exit 10; }
[ "$(sha "$BASE_UINITRD")" = "$R54_UINITRD_SHA" ] || { echo R54-uInitrd-sha-mismatch >&2; exit 11; }
[ "$(sha "$CURRENT_HOOK")" = "$CURRENT_HOOK_SHA" ] || { echo current-hook-sha-mismatch >&2; exit 12; }

rm -rf "$OUT"
mkdir -p "$ROOT" "$BUNDLE"

# Build the tiny native initramfs twice and require exact identity.
bash "$HERE/build_initramfs.sh" "$BASE_UINITRD" "$WORK/init-a"
bash "$HERE/build_initramfs.sh" "$BASE_UINITRD" "$WORK/init-b"
cmp "$WORK/init-a/uInitrd" "$WORK/init-b/uInitrd"
UINITRD_SHA="$(sha "$WORK/init-a/uInitrd")"
INIT_SHA="$(sha "$WORK/init-a/initramfs-root/init")"

# Candidate identity is independent of mutable timestamps/archive path names.
NATIVE_ID="$(printf '%s\n' \
  'R36OS_NATIVE_C03_V1' \
  "$C02_SHA_EXPECTED" \
  "$UINITRD_SHA" \
  "$INIT_SHA" \
  "$(sha "$HERE/overlay/usr/local/bin/r36os-native-c03-health")" \
  "$(sha "$HERE/overlay/etc/systemd/system/r36os-native-c03-health.service")" \
  "$K1_CID" "$KREL" "$STATE_UUID" \
  | sha256sum | awk '{print substr($1,1,24)}')"
echo "$NATIVE_ID" | grep -Eq '^[0-9a-f]{24}$'

# Extend the exact C02 root with C03 health-only overlay.
tar --zstd -xf "$C02" -C "$ROOT"
install -D -m 0755 "$HERE/overlay/usr/local/bin/r36os-native-c03-health" "$ROOT/usr/local/bin/r36os-native-c03-health"
install -D -m 0644 "$HERE/overlay/etc/systemd/system/r36os-native-c03-health.service" "$ROOT/etc/systemd/system/r36os-native-c03-health.service"
mkdir -p "$ROOT/etc/systemd/system/multi-user.target.wants"
ln -s ../r36os-native-c03-health.service "$ROOT/etc/systemd/system/multi-user.target.wants/r36os-native-c03-health.service"

python3 - "$ROOT/etc/r36os-release" "$NATIVE_ID" "$C02_SHA_EXPECTED" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); nid=sys.argv[2]; base=sys.argv[3]
s=p.read_text()
s=s.replace('R36OS_VERSION="Native Prototype C02"','R36OS_VERSION="Native Prototype C03"')
s=s.replace('R36OS_PACKAGE_VERSION="native-c02"','R36OS_PACKAGE_VERSION="native-c03"')
s += f'R36OS_NATIVE_CANDIDATE="{nid}"\nR36OS_C02_ROOTFS_SHA256="{base}"\n'
p.write_text(s)
PY
cat >"$ROOT/etc/r36os-native-c03.conf" <<EOF
format=R36OS_NATIVE_C03_ROOT_V1
native_candidate=$NATIVE_ID
k1_candidate=$K1_CID
kernel_release=$KREL
state_uuid=$STATE_UUID
base_c02_rootfs_sha256=$C02_SHA_EXPECTED
native_uinitrd_sha256=$UINITRD_SHA
EOF

# Runtime bind target for the externally authenticated C03_READY.conf.
# /init bind-mounts the staged marker over this regular file before systemd.
printf '%s\n' '# R36OS Native C03 runtime ready-marker bind target' >"$ROOT/etc/r36os-c03-staged-ready.conf"

# Normalize C03 overlay mtimes too.
find "$ROOT" -xdev -exec touch -h -d "@$EPOCH" {} +

# Regular-file manifest used again after device extraction.
(
  cd "$ROOT"
  find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
) >"$BUNDLE/rootfs-files.sha256"

# Deterministic C03 rootfs archive.
tar --sort=name --mtime="@$EPOCH" --owner=0 --group=0 --numeric-owner \
  --pax-option=delete=atime,delete=ctime -C "$ROOT" -cf - . \
  | zstd -19 -T1 --no-progress -o "$BUNDLE/rootfs.tar.zst"
ROOTFS_SHA="$(sha "$BUNDLE/rootfs.tar.zst")"
ROOTFS_BYTES="$(stat -c %s "$BUNDLE/rootfs.tar.zst")"
# Logical regular-file bytes are deterministic. Filesystem allocation from
# du(1) is not, and C03 already adds a fixed 512 MiB staging headroom.
ROOTFS_LOGICAL_BYTES="$(find "$ROOT" -xdev -type f -printf '%s\\n' | awk '{s+=$1} END{printf "%.0f",s+0}')"
echo "$ROOTFS_LOGICAL_BYTES" | grep -Eq '^[0-9]+$' || { echo rootfs-logical-bytes-invalid >&2; exit 26; }
ROOTFS_KB=$(((ROOTFS_LOGICAL_BYTES + 1023) / 1024))

cp "$WORK/init-a/uInitrd" "$BUNDLE/uInitrd"
cp "$CURRENT_HOOK" "$BUNDLE/previous-hooked-boot.ini"
cp "$HERE/r36os-native-c03-install-hook" "$BUNDLE/r36os-native-c03-install-hook"
cp "$HERE/r36os-native-c03-prepare" "$BUNDLE/r36os-native-c03-prepare"
chmod 0755 "$BUNDLE/r36os-native-c03-install-hook" "$BUNDLE/r36os-native-c03-prepare"
python3 "$HERE/transform_hook.py" "$CURRENT_HOOK" "$NATIVE_ID" "$ROOTFS_SHA" \
  "$BUNDLE/hooked-boot.ini" "$BUNDLE/hook.conf"

cat >"$BUNDLE/C03_READY.conf" <<EOF
format=R36OS_NATIVE_C03_READY_V1
native_candidate=$NATIVE_ID
k1_candidate=$K1_CID
kernel_release=$KREL
state_uuid=$STATE_UUID
base_c02_rootfs_sha256=$C02_SHA_EXPECTED
rootfs_sha256=$ROOTFS_SHA
rootfs_bytes=$ROOTFS_BYTES
rootfs_unpacked_kb=$ROOTFS_KB
rootfs_files_sha256=$(sha "$BUNDLE/rootfs-files.sha256")
uinitrd_sha256=$UINITRD_SHA
hooked_boot_sha256=$(sha "$BUNDLE/hooked-boot.ini")
previous_hook_sha256=$CURRENT_HOOK_SHA
previous_hook_file_sha256=$(sha "$BUNDLE/previous-hooked-boot.ini")
prepare_sha256=$(sha "$BUNDLE/r36os-native-c03-prepare")
install_hook_sha256=$(sha "$BUNDLE/r36os-native-c03-install-hook")
native_request=R36OS-NativeNext/C03/boot-native.$NATIVE_ID.once
native_consumed=R36N3.CNS
EOF

# Bundle manifest covers every production input.
(
  cd "$BUNDLE"
  sha256sum rootfs.tar.zst rootfs-files.sha256 uInitrd hooked-boot.ini previous-hooked-boot.ini hook.conf C03_READY.conf r36os-native-c03-install-hook r36os-native-c03-prepare
) >"$BUNDLE/MANIFEST.sha256"

# Re-open and verify the root identity and health enablement.
mkdir "$WORK/verify"
tar --zstd -xf "$BUNDLE/rootfs.tar.zst" -C "$WORK/verify"
grep -Fq 'R36OS_VERSION="Native Prototype C03"' "$WORK/verify/etc/r36os-release"
grep -Fxq "native_candidate=$NATIVE_ID" "$WORK/verify/etc/r36os-native-c03.conf"
test -L "$WORK/verify/etc/systemd/system/multi-user.target.wants/r36os-native-c03-health.service"
bash -n "$WORK/verify/usr/local/bin/r36os-native-c03-health"
bash -n "$BUNDLE/r36os-native-c03-install-hook"
bash -n "$BUNDLE/r36os-native-c03-prepare"
test "$(sha "$BUNDLE/previous-hooked-boot.ini")" = "$CURRENT_HOOK_SHA"
(cd "$WORK/verify" && sha256sum -c "$BUNDLE/rootfs-files.sha256" >/dev/null)
(cd "$BUNDLE" && sha256sum -c MANIFEST.sha256 >/dev/null)

cat >"$OUT/C03_BUILD.conf" <<EOF
format=R36OS_NATIVE_C03_BUILD_V1
status=PASS
native_candidate=$NATIVE_ID
base_c02_rootfs_sha256=$C02_SHA_EXPECTED
rootfs_sha256=$ROOTFS_SHA
rootfs_bytes=$ROOTFS_BYTES
uinitrd_sha256=$UINITRD_SHA
init_sha256=$INIT_SHA
hooked_boot_sha256=$(sha "$BUNDLE/hooked-boot.ini")
previous_hook_sha256=$CURRENT_HOOK_SHA
k1_candidate=$K1_CID
kernel_release=$KREL
state_uuid=$STATE_UUID
EOF

rm -rf "$WORK"
echo "R36OS_NATIVE_C03_BUILD=PASS native_candidate=$NATIVE_ID rootfs_sha256=$ROOTFS_SHA uinitrd_sha256=$UINITRD_SHA"
 || { echo rootfs-logical-bytes-invalid >&2; exit 26; }
ROOTFS_KB=$(((ROOTFS_LOGICAL_BYTES + 1023) / 1024))

cp "$WORK/init-a/uInitrd" "$BUNDLE/uInitrd"
cp "$CURRENT_HOOK" "$BUNDLE/previous-hooked-boot.ini"
cp "$HERE/r36os-native-c03-install-hook" "$BUNDLE/r36os-native-c03-install-hook"
cp "$HERE/r36os-native-c03-prepare" "$BUNDLE/r36os-native-c03-prepare"
chmod 0755 "$BUNDLE/r36os-native-c03-install-hook" "$BUNDLE/r36os-native-c03-prepare"
python3 "$HERE/transform_hook.py" "$CURRENT_HOOK" "$NATIVE_ID" "$ROOTFS_SHA" \
  "$BUNDLE/hooked-boot.ini" "$BUNDLE/hook.conf"

cat >"$BUNDLE/C03_READY.conf" <<EOF
format=R36OS_NATIVE_C03_READY_V1
native_candidate=$NATIVE_ID
k1_candidate=$K1_CID
kernel_release=$KREL
state_uuid=$STATE_UUID
base_c02_rootfs_sha256=$C02_SHA_EXPECTED
rootfs_sha256=$ROOTFS_SHA
rootfs_bytes=$ROOTFS_BYTES
rootfs_unpacked_kb=$ROOTFS_KB
rootfs_files_sha256=$(sha "$BUNDLE/rootfs-files.sha256")
uinitrd_sha256=$UINITRD_SHA
hooked_boot_sha256=$(sha "$BUNDLE/hooked-boot.ini")
previous_hook_sha256=$CURRENT_HOOK_SHA
previous_hook_file_sha256=$(sha "$BUNDLE/previous-hooked-boot.ini")
prepare_sha256=$(sha "$BUNDLE/r36os-native-c03-prepare")
install_hook_sha256=$(sha "$BUNDLE/r36os-native-c03-install-hook")
native_request=R36OS-NativeNext/C03/boot-native.$NATIVE_ID.once
native_consumed=R36N3.CNS
EOF

# Bundle manifest covers every production input.
(
  cd "$BUNDLE"
  sha256sum rootfs.tar.zst rootfs-files.sha256 uInitrd hooked-boot.ini previous-hooked-boot.ini hook.conf C03_READY.conf r36os-native-c03-install-hook r36os-native-c03-prepare
) >"$BUNDLE/MANIFEST.sha256"

# Re-open and verify the root identity and health enablement.
mkdir "$WORK/verify"
tar --zstd -xf "$BUNDLE/rootfs.tar.zst" -C "$WORK/verify"
grep -Fq 'R36OS_VERSION="Native Prototype C03"' "$WORK/verify/etc/r36os-release"
grep -Fxq "native_candidate=$NATIVE_ID" "$WORK/verify/etc/r36os-native-c03.conf"
test -L "$WORK/verify/etc/systemd/system/multi-user.target.wants/r36os-native-c03-health.service"
bash -n "$WORK/verify/usr/local/bin/r36os-native-c03-health"
bash -n "$BUNDLE/r36os-native-c03-install-hook"
bash -n "$BUNDLE/r36os-native-c03-prepare"
test "$(sha "$BUNDLE/previous-hooked-boot.ini")" = "$CURRENT_HOOK_SHA"
(cd "$WORK/verify" && sha256sum -c "$BUNDLE/rootfs-files.sha256" >/dev/null)
(cd "$BUNDLE" && sha256sum -c MANIFEST.sha256 >/dev/null)

cat >"$OUT/C03_BUILD.conf" <<EOF
format=R36OS_NATIVE_C03_BUILD_V1
status=PASS
native_candidate=$NATIVE_ID
base_c02_rootfs_sha256=$C02_SHA_EXPECTED
rootfs_sha256=$ROOTFS_SHA
rootfs_bytes=$ROOTFS_BYTES
uinitrd_sha256=$UINITRD_SHA
init_sha256=$INIT_SHA
hooked_boot_sha256=$(sha "$BUNDLE/hooked-boot.ini")
previous_hook_sha256=$CURRENT_HOOK_SHA
k1_candidate=$K1_CID
kernel_release=$KREL
state_uuid=$STATE_UUID
EOF

rm -rf "$WORK"
echo "R36OS_NATIVE_C03_BUILD=PASS native_candidate=$NATIVE_ID rootfs_sha256=$ROOTFS_SHA uinitrd_sha256=$UINITRD_SHA"
