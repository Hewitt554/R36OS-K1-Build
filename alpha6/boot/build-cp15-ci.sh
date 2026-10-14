#!/usr/bin/env bash
# Run exclusively inside disposable ARM64 GitHub CI; no device/raw-image writes.
set -euo pipefail
[[ $(uname -m) == aarch64 && $(id -u) == 0 ]] || exit 2
BASE="$(cd "$(dirname "$0")/.." && pwd)"
[[ -s "$BASE/dist/cp14-k1-native-report.json" ]] || { echo 'CP14 native-root integration report is required' >&2; exit 3; }
for cmd in busybox python3 mkimage readelf; do command -v "$cmd" >/dev/null || exit 3; done
BUSYBOX=$(command -v busybox)
# Applet inventory varies across BusyBox distributions.
for applet in sh mount mdev mkdir sleep cat blkid grep uname switch_root; do
  busybox --list | grep -qx "$applet" || { echo "Missing static BusyBox applet: $applet" >&2; exit 3; }
done
WORK=$(mktemp -d /tmp/r36os-cp15-initrd-XXXXXXXX)
case "$WORK" in /tmp/r36os-cp15-initrd-*) ;; *) exit 3 ;; esac
trap 'case "$WORK" in /tmp/r36os-cp15-initrd-*) rm -rf -- "$WORK";; esac' EXIT
UUID=$(python3 - "$BASE/dist/cp14-k1-native-report.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
assert p['safe_to_flash'] is False and p['boot_tested'] is False
assert p['kernel_release']=='6.12.94-r36os-k1'
assert p['ext4_fsck']=='PASS_READONLY'
assert p['module_details']['module_files'] > 0
assert p['scratch_native_root_uuid'] != p['k1_root_uuid']
print(p['scratch_native_root_uuid'])
PY
)
python3 "$BASE/boot/build-cp15-initrd.py" \
  --busybox "$BUSYBOX" \
  --init-script "$BASE/boot/cp15-init" \
  --output-dir "$WORK" \
  --native-root-uuid "$UUID"
mkimage -l "$WORK/CP15-ARM-UNTESTED.uInitrd"
mkimage -l "$WORK/CP15-ARM64-UNTESTED.uInitrd"
# Both headers must be valid but their compatibility with physical U-Boot is NOT proved.
python3 - "$WORK" "$BASE/dist/cp14-k1-native-report.json" <<'PY'
import json,sys
from pathlib import Path
x=json.loads((Path(sys.argv[1])/'cp15-initrd-report.json').read_text())
cp14=json.loads(Path(sys.argv[2]).read_text())
assert x['native_root_uuid']==cp14['scratch_native_root_uuid']
assert x['kernel_release']==cp14['kernel_release']
assert set(x['initrd_files'])=={'2','22'}
assert x['safe_to_flash'] is False and x['boot_tested'] is False
print('CP15 K1/native-root UUID binding and both U-Boot header formats PASS (offline only)')
PY
install -m 0644 "$WORK/cp15-initrd-report.json" "$BASE/dist/cp15-initrd-report.json"
# NOT an installation: upload only development assets for further analysis.
install -m 0644 "$WORK/CP15-ARM-UNTESTED.uInitrd" "$BASE/dist/CP15-ARM-UNTESTED.uInitrd"
install -m 0644 "$WORK/CP15-ARM64-UNTESTED.uInitrd" "$BASE/dist/CP15-ARM64-UNTESTED.uInitrd"
install -m 0644 "$WORK/CP15-BOOTARGS-SAMPLE-NOT-INSTALL.txt" "$BASE/dist/CP15-BOOTARGS-SAMPLE-NOT-INSTALL.txt"