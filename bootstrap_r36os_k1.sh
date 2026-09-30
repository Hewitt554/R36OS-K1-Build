#!/usr/bin/env bash
set -euo pipefail

# R36OS K1 CLOUD9 — RTL8188EU/rtl8xxxu Wi-Fi enablement
# Physical Alpha 5R58 evidence proves the K1 USB host sees 0bda:0179 but
# Linux 6.12 has no wireless driver bound. Preserve the exact successful
# CLOUD8/Run-11 kernel lineage and change only the wireless Kconfig contract.

BASE_COMMIT="39c64b87a2dd9cd9f323fb01db2fc450f9431244"
BASE_BLOB_SHA1="05a38d9b4526beb657db98399a9b1a8003703a76"
BASE_URL="https://raw.githubusercontent.com/Hewitt554/R36OS-K1-Build/${BASE_COMMIT}/bootstrap_r36os_k1.sh"
WRAP_ROOT="${RUNNER_TEMP:-/tmp}/r36os-k1-cloud9-wrapper"
BASE_BOOTSTRAP="$WRAP_ROOT/bootstrap_cloud8.sh"
PATCHED_BOOTSTRAP="$WRAP_ROOT/bootstrap_cloud9.sh"

fail(){ echo "ERROR: $*" >&2; exit 1; }
for cmd in curl git python3 bash; do command -v "$cmd" >/dev/null 2>&1 || fail "required wrapper command missing: $cmd"; done
rm -rf "$WRAP_ROOT"; mkdir -p "$WRAP_ROOT"

echo "CLOUD9=INFO fetching immutable successful CLOUD8 bootstrap"
curl --fail --location --silent --show-error --retry 4 --retry-delay 2 --retry-all-errors "$BASE_URL" -o "$BASE_BOOTSTRAP"
actual_blob="$(git hash-object "$BASE_BOOTSTRAP")"
[[ "$actual_blob" == "$BASE_BLOB_SHA1" ]] || fail "CLOUD8 bootstrap Git blob mismatch: expected=$BASE_BLOB_SHA1 actual=$actual_blob"
echo "CLOUD9=PASS CLOUD8 bootstrap Git blob verified"

python3 - "$BASE_BOOTSTRAP" "$PATCHED_BOOTSTRAP" <<'R36OS_CLOUD9_OUTER_PATCH'
from pathlib import Path
import sys
src=Path(sys.argv[1]); dst=Path(sys.argv[2]); text=src.read_text()
old='''echo "CLOUD8=PASS patched bootstrap syntax verified"\necho "CLOUD8=INFO executing CP04P-CLOUD8"\nexec bash "$PATCHED_BOOTSTRAP"\n'''
if text.count(old)!=1:
    raise SystemExit(f"ERROR: CLOUD9 outer exec anchor count != 1: {text.count(old)}")
new=r"""echo "CLOUD8=PASS patched bootstrap syntax verified"

# CLOUD9 patches the already-verified CLOUD8-generated bootstrap.  The patch is
# deliberately limited to Kconfig and post-olddefconfig validation; source,
# Panel-4 DTS, toolchain, initramfs logic and CP04/CP05 safety checks remain the
# exact successful Run-11 lineage.
python3 - "$PATCHED_BOOTSTRAP" <<'R36OS_CLOUD9_WIFI_PATCH'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
anchor='(root / "CLOUD_PATCHSET.txt").write_text('
if s.count(anchor)!=1:
    raise SystemExit(f"ERROR: CLOUD9 nested patch anchor count != 1: {s.count(anchor)}")

injection=r'''
# CLOUD9 Wi-Fi delta: physical R58 logs show USB 0bda:0179 (RTL8188EU) is
# enumerated under K1 but NetworkManager reports WIFI-HW=missing. Linux 6.12's
# rtl8xxxu supports this USB ID. Build the wireless stack as modules so firmware
# loading happens after the real root filesystem is available.
import re as _r36os_re
_r36os_frag = root / "k1_source/k1.config.fragment"
_r36os_cfg = _r36os_frag.read_text()
_r36os_wifi = {
    "WLAN": "y",
    "CFG80211": "m",
    "MAC80211": "m",
    "WLAN_VENDOR_REALTEK": "y",
    "RTL8XXXU": "m",
    "RTL8XXXU_UNTESTED": "n",
}
for _sym,_val in _r36os_wifi.items():
    _r36os_cfg = _r36os_re.sub(rf"^CONFIG_{_sym}=.*$\\n?", "", _r36os_cfg, flags=_r36os_re.M)
    _r36os_cfg = _r36os_re.sub(rf"^# CONFIG_{_sym} is not set$\\n?", "", _r36os_cfg, flags=_r36os_re.M)
_r36os_cfg = _r36os_cfg.rstrip()+"\\n"+"".join(f"CONFIG_{k}={v}\\n" for k,v in _r36os_wifi.items())
_r36os_frag.write_text(_r36os_cfg)

_r36os_builder = root / "BUILD_K1_CHECKPOINT04.sh"
_r36os_b = _r36os_builder.read_text()
_r36os_check_anchor = '(( ${#missing_required[@]} == 0 )) || fail "required config lost after olddefconfig: ${missing_required[*]}"\\n'
if _r36os_b.count(_r36os_check_anchor) != 1:
    raise SystemExit("ERROR: CLOUD9 olddefconfig validation anchor mismatch")
_r36os_check = _r36os_check_anchor + (
    'for spec in CFG80211=m MAC80211=m WLAN_VENDOR_REALTEK=y RTL8XXXU=m; do\n'
    '  sym="${spec%%=*}"; val="${spec#*=}"\n'
    '  grep -q "^CONFIG_${sym}=${val}$" "$OBJ/.config" || fail "required Wi-Fi config lost after olddefconfig: CONFIG_${sym}=${val}"\n'
    'done\n'
    "grep -q '^# CONFIG_RTL8XXXU_UNTESTED is not set$' \"$OBJ/.config\" || fail \"RTL8XXXU_UNTESTED unexpectedly enabled\"\n"
)
_r36os_b = _r36os_b.replace(_r36os_check_anchor, _r36os_check, 1)

_r36os_make_anchor='"${MAKE[@]}" -j"$JOBS" Image rockchip/rk3326-r36os-k1.dtb modules\\n'
if _r36os_b.count(_r36os_make_anchor) != 1:
    raise SystemExit("ERROR: CLOUD9 kernel make anchor mismatch")
_r36os_postmake = _r36os_make_anchor + (
    "RTL8XXXU_KO=\"$(find \"$OBJ/drivers/net/wireless/realtek/rtl8xxxu\" -type f -name 'rtl8xxxu.ko' -print -quit)\"\n"
    '[[ -n "$RTL8XXXU_KO" && -f "$RTL8XXXU_KO" ]] || fail "rtl8xxxu.ko was not built"\n'
    "modinfo \"$RTL8XXXU_KO\" | grep -Fq 'alias:          usb:v0BDAp0179' || fail \"rtl8xxxu.ko missing RTL8188EU 0bda:0179 alias\"\n"
    'echo "STATUS=PASS rtl8xxxu module built with RTL8188EU USB alias"\n'
)
_r36os_b = _r36os_b.replace(_r36os_make_anchor, _r36os_postmake, 1)
_r36os_builder.write_text(_r36os_b)
print("CLOUD9=PASS injected RTL8188EU/rtl8xxxu Kconfig and build validation")
'''

s=s.replace(anchor,injection+'\n'+anchor,1)
p.write_text(s)
R36OS_CLOUD9_WIFI_PATCH
chmod +x "$PATCHED_BOOTSTRAP"
bash -n "$PATCHED_BOOTSTRAP"
echo "CLOUD9=PASS Wi-Fi-patched bootstrap syntax verified"
echo "CLOUD9=INFO executing Run-11 lineage with RTL8188EU Wi-Fi delta"
exec bash "$PATCHED_BOOTSTRAP"
"""
text=text.replace(old,new,1)
dst.write_text(text)
R36OS_CLOUD9_OUTER_PATCH

chmod +x "$PATCHED_BOOTSTRAP"
bash -n "$PATCHED_BOOTSTRAP"
echo "CLOUD9=PASS outer wrapper syntax verified"
exec bash "$PATCHED_BOOTSTRAP"
