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
# CLOUD9 Wi-Fi delta: physical R58 evidence proves K1 enumerates USB 0bda:0179
# (RTL8188EU) but has no WLAN driver. Linux 6.12.94's maintained rtl8xxxu
# driver explicitly supports RTL8188EU. Modify the frozen K1 config fragment
# using splitlines()/chr(10) so multi-layer bootstrap quoting cannot turn
# newlines into literal "\\n" text.
_r36os_frag = root / "k1_source/k1.config.fragment"
_r36os_lines = _r36os_frag.read_text().splitlines()
_r36os_wifi = [
    ("WLAN", "y"),
    ("USB", "y"),
    ("CFG80211", "m"),
    ("MAC80211", "m"),
    ("WLAN_VENDOR_REALTEK", "y"),
    ("NEW_LEDS", "y"),
    ("LEDS_CLASS", "y"),
    ("RTL8XXXU", "m"),
]
_r36os_names = {name for name,_ in _r36os_wifi}
_r36os_clean = []
for _line in _r36os_lines:
    _drop = False
    for _name in _r36os_names:
        if _line.startswith("CONFIG_" + _name + "=") or _line == "# CONFIG_" + _name + " is not set":
            _drop = True
            break
    if _line.startswith("CONFIG_RTL8XXXU_UNTESTED=") or _line == "# CONFIG_RTL8XXXU_UNTESTED is not set":
        _drop = True
    if not _drop:
        _r36os_clean.append(_line)
_r36os_clean.extend("CONFIG_" + name + "=" + value for name,value in _r36os_wifi)
_r36os_clean.append("# CONFIG_RTL8XXXU_UNTESTED is not set")
_r36os_frag.write_text(chr(10).join(_r36os_clean) + chr(10))

_r36os_builder = root / "BUILD_K1_CHECKPOINT04.sh"
_r36os_b = _r36os_builder.read_text()
_r36os_bl = _r36os_b.splitlines(keepends=True)
_r36os_check_hits = [
    i for i,line in enumerate(_r36os_bl)
    if "required config lost after olddefconfig:" in line and "missing_required" in line
]
if len(_r36os_check_hits) != 1:
    raise SystemExit(f"ERROR: CLOUD9 olddefconfig validation anchor count != 1: {len(_r36os_check_hits)}")
_r36os_diag = (
    'echo "CLOUD9_WIFI_CONFIG_BEGIN"' + chr(10)
    + "grep -E '^(CONFIG_(NET|WIRELESS|WLAN|USB|MODULES|CFG80211|MAC80211|WLAN_VENDOR_REALTEK|NEW_LEDS|LEDS_CLASS|RTL8XXXU)=|# CONFIG_(NET|WIRELESS|WLAN|USB|MODULES|CFG80211|MAC80211|WLAN_VENDOR_REALTEK|NEW_LEDS|LEDS_CLASS|RTL8XXXU|RTL8XXXU_UNTESTED) is not set)' \"$OBJ/.config\" || true" + chr(10)
    + 'echo "CLOUD9_WIFI_CONFIG_END"' + chr(10)
)
_r36os_check = (
    'for spec in WLAN=y USB=y CFG80211=m MAC80211=m WLAN_VENDOR_REALTEK=y NEW_LEDS=y LEDS_CLASS=y RTL8XXXU=m; do' + chr(10)
    + '  sym="\${spec%%=*}"; val="\${spec#*=}"' + chr(10)
    + '  grep -q "^CONFIG_\${sym}=\${val}$" "$OBJ/.config" || fail "required Wi-Fi config lost after olddefconfig: CONFIG_\${sym}=\${val}"' + chr(10)
    + 'done' + chr(10)
    + "grep -q '^# CONFIG_RTL8XXXU_UNTESTED is not set$' \"$OBJ/.config\" || fail \"RTL8XXXU_UNTESTED unexpectedly enabled\"" + chr(10)
)
_r36os_bl.insert(_r36os_check_hits[0] + 1, _r36os_diag)
_r36os_bl.insert(_r36os_check_hits[0] + 2, _r36os_check)

_r36os_make_hits = [
    i for i,line in enumerate(_r36os_bl)
    if "Image rockchip/rk3326-r36os-k1.dtb modules" in line and "MAKE" in line
]
if len(_r36os_make_hits) != 1:
    raise SystemExit(f"ERROR: CLOUD9 kernel make anchor count != 1: {len(_r36os_make_hits)}")
_r36os_postmake = (
    'RTL8XXXU_KO="$(find "$OBJ/drivers/net/wireless/realtek/rtl8xxxu" -type f -name "rtl8xxxu.ko" -print -quit)"' + chr(10)
    + '[[ -n "$RTL8XXXU_KO" && -f "$RTL8XXXU_KO" ]] || fail "rtl8xxxu.ko was not built"' + chr(10)
    + 'RTL8XXXU_INFO="$(modinfo "$RTL8XXXU_KO")" || fail "modinfo failed for rtl8xxxu.ko"' + chr(10)
    + 'grep -Eq "^alias:[[:space:]]+usb:v0BDAp0179" <<<"$RTL8XXXU_INFO" || fail "rtl8xxxu.ko missing RTL8188EU 0bda:0179 alias"' + chr(10)
    + 'grep -Fq "firmware:       rtlwifi/rtl8188eufw.bin" <<<"$RTL8XXXU_INFO" || fail "rtl8xxxu.ko missing RTL8188EU firmware declaration"' + chr(10)
    + 'echo "STATUS=PASS rtl8xxxu module built with 0bda:0179 alias and firmware declaration"' + chr(10)
)
_r36os_bl.insert(_r36os_make_hits[0] + 1, _r36os_postmake)
_r36os_builder.write_text("".join(_r36os_bl))
print("CLOUD9=PASS injected maintained in-tree RTL8188EU/rtl8xxxu config and validation")
'''

s=s.replace(anchor,injection+'\n'+anchor,1)
p.write_text(s)
R36OS_CLOUD9_WIFI_PATCH
chmod +x "$PATCHED_BOOTSTRAP"
bash -n "$PATCHED_BOOTSTRAP"
echo "CLOUD9=PASS Wi-Fi-patched bootstrap syntax verified"
echo "CLOUD9=INFO executing Run-11 lineage with maintained rtl8xxxu RTL8188EU delta"
exec bash "$PATCHED_BOOTSTRAP"
"""
text=text.replace(old,new,1)
dst.write_text(text)
R36OS_CLOUD9_OUTER_PATCH

chmod +x "$PATCHED_BOOTSTRAP"
bash -n "$PATCHED_BOOTSTRAP"
echo "CLOUD9=PASS outer wrapper syntax verified"
exec bash "$PATCHED_BOOTSTRAP"
