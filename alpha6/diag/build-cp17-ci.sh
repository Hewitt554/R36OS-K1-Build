#!/usr/bin/env bash
# ARM64 GitHub disposable build only. No raw disk/BOOT files or partition writes.
set -euo pipefail
[[ $(uname -m) == aarch64 ]] || { echo 'Native AArch64 runner required' >&2; exit 2; }
BASE="$(cd "$(dirname "$0")/.." && pwd)"
for cmd in busybox gcc readelf python3 mkimage sha256sum; do command -v "$cmd" >/dev/null || exit 3; done
for app in sh mount mdev mkdir cat tr uname sleep; do
  busybox --list | grep -qx "$app" || { echo "Missing required BusyBox applet: $app" >&2; exit 3; }
done
WORK="$(mktemp -d /tmp/r36os-cp17-diag-XXXXXXXX)"
case "$WORK" in /tmp/r36os-cp17-diag-*) ;; *) exit 4;; esac
trap 'case "$WORK" in /tmp/r36os-cp17-diag-*) rm -rf -- "$WORK";; esac' EXIT
# stdlib C/Linux framebuffer header comes from Ubuntu-native cross-compatible glibc on ARM64.
gcc -std=c11 -Os -Wall -Wextra -Werror -static -o "$WORK/fbdiag" "$BASE/diag/cp17-fbdiag.c"
if readelf -l "$WORK/fbdiag" | grep -q INTERP; then echo 'Framebuffer helper is not static' >&2; exit 3; fi
readelf -h "$WORK/fbdiag" | grep -q AArch64 || exit 3
python3 "$BASE/diag/build-cp17-diag.py" \
  --busybox "$(command -v busybox)" \
  --framebuffer-tool "$WORK/fbdiag" \
  --init-script "$BASE/diag/cp17-init" \
  --output-dir "$WORK"
for u in "$WORK"/*.uInitrd; do mkimage -l "$u"; done
python3 - "$WORK" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);report=json.loads((root/'cp17-diagnostic-report.json').read_text())
assert report['safe_to_flash'] is False and report['boot_tested'] is False
assert report['writes_persistent_storage'] is False
assert report['automatic_recovery'] is False
for item in report['variants'].values():
    name=item['name']
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==item['sha256']
print('CP17 two diagnostic-only U-Boot ramdisks verified. Hardware NOT TESTED')
PY
mkdir -p "$BASE/dist/cp17-uninstalled-diagnostic"
install -m 0644 "$WORK"/*.uInitrd "$BASE/dist/cp17-uninstalled-diagnostic/"
install -m 0644 "$WORK"/cp17-diagnostic-report.json "$BASE/dist/cp17-uninstalled-diagnostic/"
install -m 0644 "$WORK"/DO_NOT_FLASH.txt "$BASE/dist/cp17-uninstalled-diagnostic/"