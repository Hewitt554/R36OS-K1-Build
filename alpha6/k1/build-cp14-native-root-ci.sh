#!/usr/bin/env bash
# CI-only: integrate pinned K1 modules with a disposable native root and test ext4 creation.
# Does NOT create bootable media or modify any device.
set -euo pipefail
[[ $(uname -m) == aarch64 ]] || { echo 'Native ARM64 runner required' >&2; exit 2; }
[[ $(id -u) == 0 ]] || { echo 'Run as root in disposable GitHub CI' >&2; exit 2; }
[[ $# -eq 1 && -f "$1" ]] || { echo 'Expected verified K1 source .tar.gz file' >&2; exit 2; }
K1_ARCHIVE="$(realpath "$1")"
BASE="$(cd "$(dirname "$0")/.." && pwd)"
[[ -s "$BASE/dist/r36os-native-rootfs-arm64-cp06.tar.zst" ]] || { echo 'CP06 rootfs archive missing' >&2; exit 2; }
for cmd in mkfs.ext4 e2fsck blkid zstd tar sha256sum python3; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 2; }
done
WORK="$(mktemp -d /tmp/r36os-cp14-integration-XXXXXXXX)"
case "$WORK" in /tmp/r36os-cp14-integration-*) ;; *) exit 3 ;; esac
cleanup() {
  case "$WORK" in /tmp/r36os-cp14-integration-*) rm -rf -- "$WORK" ;; esac
}
trap cleanup EXIT
printf 'R36OS_CP14_DISPOSABLE_NATIVE_ROOT_V1\n' > "$WORK/.cp14-fixture-id"
mkdir -p "$WORK/native-root" "$BASE/dist"
tar --use-compress-program=zstd -xf "$BASE/dist/r36os-native-rootfs-arm64-cp06.tar.zst" -C "$WORK/native-root" --numeric-owner
python3 "$BASE/k1/compose-k1-native-root.py" "$K1_ARCHIVE" "$WORK"
# A scratch partition image is created as a REGULAR FILE, not a loop/block device.
# Use only this named temp path. Its UUID is intentionally distinct from R3.
truncate -s 4096M "$WORK/cp14-root-NOT-BOOTABLE.ext4"
mkfs.ext4 -F -q -m 0 -L R36SYS -d "$WORK/native-root" "$WORK/cp14-root-NOT-BOOTABLE.ext4"
e2fsck -fn "$WORK/cp14-root-NOT-BOOTABLE.ext4" >/dev/null
CP14_UUID="$(blkid -s UUID -o value "$WORK/cp14-root-NOT-BOOTABLE.ext4")"
[[ -n "$CP14_UUID" && "$CP14_UUID" != 'e139ce78-9841-40fe-8823-96a304a09859' ]] || exit 3
python3 - "$WORK/cp14-compatibility-report.json" "$CP14_UUID" "$BASE/dist/cp14-k1-native-report.json" <<'PY'
import json,sys
from pathlib import Path
source, uuid, output = map(Path, (sys.argv[1], sys.argv[2], sys.argv[3]))
r=json.loads(source.read_text())
r['scratch_native_root_uuid']=str(uuid)
r['ext4_fsck']='PASS_READONLY'
r['ext4_test_size_mib']=4096
r['compatibility_gaps'].append('CP14 scratch root UUID differs from K1.conf root_uuid; old K1 initramfs cannot be assumed to mount this root')
assert r['safe_to_flash'] is False and r['boot_tested'] is False
assert r['kernel_release']=='6.12.94-r36os-k1'
assert r['module_details']['module_files']>0
assert r['scratch_native_root_uuid']!=r['k1_root_uuid']
output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
print('CP14 real ext4/native root integration PASS')
print('K1 module files:',r['module_details']['module_files'])
print('Compatibility gaps:',len(r['compatibility_gaps']))
print('Scratch native ext4 UUID:',r['scratch_native_root_uuid'])
print('NO flash image or bootloader generated.')
PY
# Scratch ext4 deleted by trap; only small report is an uploadable artifact.