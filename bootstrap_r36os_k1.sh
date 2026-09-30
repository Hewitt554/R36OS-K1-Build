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
# CLOUD9 Wi-Fi delta: keep the exact successful Run-11 kernel config/Image/DTB
# and add only an ABI-matched external 8188eu module to the staged K1 module tree.
# Physical R58 evidence identifies USB 0bda:0179, and the working legacy kernel
# binds the Realtek 8188EU family driver. Arch-R's RK3326 reference also ships
# the pinned 8188eu driver for RTL8188EUS instead of relying on rtl8xxxu.
_r36os_builder = root / "BUILD_K1_CHECKPOINT04.sh"
_r36os_b = _r36os_builder.read_text()
_r36os_lines = _r36os_b.splitlines(keepends=True)

_r36os_make_hits = [
    i for i,line in enumerate(_r36os_lines)
    if "Image rockchip/rk3326-r36os-k1.dtb modules" in line and "MAKE" in line
]
if len(_r36os_make_hits) != 1:
    raise SystemExit(f"ERROR: CLOUD9 kernel make anchor count != 1: {len(_r36os_make_hits)}")

_r36os_external_build = "DRIVER_COMMIT=af3bf004458f76b7aec33e9ba552cd382ed1f5c3\nDRIVER_WORK=\"$(dirname \"$OBJ\")/rtl8188eus-r36os\"\nrm -rf \"$DRIVER_WORK\"\ngit init -q \"$DRIVER_WORK\"\ngit -C \"$DRIVER_WORK\" remote add origin https://github.com/aircrack-ng/rtl8188eus.git\ngit -C \"$DRIVER_WORK\" fetch -q --depth 1 origin \"$DRIVER_COMMIT\"\ngit -C \"$DRIVER_WORK\" checkout -q --detach FETCH_HEAD\n[[ \"$(git -C \"$DRIVER_WORK\" rev-parse HEAD)\" == \"$DRIVER_COMMIT\" ]] || fail \"8188eu source commit mismatch\"\n\nCC_BIN=\"$(find \"$(dirname \"$OBJ\")\" -type f -perm -u+x \\( -name 'aarch64-linux-gnu-gcc' -o -name 'aarch64-none-linux-gnu-gcc' \\) -print -quit)\"\nif [[ -z \"$CC_BIN\" ]]; then\n  CC_BIN=\"$(command -v aarch64-linux-gnu-gcc 2>/dev/null || true)\"\nfi\n[[ -n \"$CC_BIN\" && -x \"$CC_BIN\" ]] || fail \"AArch64 cross compiler not found for 8188eu\"\nDRIVER_CROSS=\"${CC_BIN%gcc}\"\necho \"CLOUD9=INFO building pinned 8188eu commit=$DRIVER_COMMIT compiler=$CC_BIN\"\nmake -C \"$DRIVER_WORK\" -j\"$JOBS\" ARCH=arm64 CROSS_COMPILE=\"$DRIVER_CROSS\" KSRC=\"$OBJ\" CONFIG_POWER_SAVING=y\nDRIVER_KO=\"$DRIVER_WORK/8188eu.ko\"\n[[ -f \"$DRIVER_KO\" ]] || fail \"8188eu.ko was not built\"\nfile \"$DRIVER_KO\" | grep -Eq 'ARM aarch64|ARM64' || fail \"8188eu.ko is not ARM64\"\nKREL_NOW=\"$(cat \"$OBJ/include/config/kernel.release\")\"\nmodinfo \"$DRIVER_KO\" | grep -Fq \"vermagic:       $KREL_NOW \" || fail \"8188eu vermagic mismatch\"\nmodinfo \"$DRIVER_KO\" | grep -Eq '^alias:[[:space:]]+usb:v0BDAp0179' || fail \"8188eu missing USB alias 0bda:0179\"\necho \"CLOUD9=PASS pinned 8188eu module built for $KREL_NOW with 0bda:0179 alias\"\n"
_r36os_lines.insert(_r36os_make_hits[0] + 1, _r36os_external_build)

_r36os_modinst_hits = [
    i for i,line in enumerate(_r36os_lines)
    if "modules_install" in line and "INSTALL_MOD_PATH" in line
]
if len(_r36os_modinst_hits) != 1:
    raise SystemExit(f"ERROR: CLOUD9 modules_install anchor count != 1: {len(_r36os_modinst_hits)}")

_r36os_external_install = "KREL_NOW=\"$(cat \"$OBJ/include/config/kernel.release\")\"\nMODROOT=\"$(find \"$(dirname \"$OBJ\")\" -type d -path \"*/modules/lib/modules/$KREL_NOW\" -print -quit)\"\n[[ -n \"$MODROOT\" && -d \"$MODROOT\" ]] || fail \"staged K1 module root not found\"\nDRIVER_DEST=\"$MODROOT/kernel/drivers/net/wireless/realtek/r8188eu/8188eu.ko\"\nmkdir -p \"$(dirname \"$DRIVER_DEST\")\"\ncp -f \"$DRIVER_KO\" \"$DRIVER_DEST\"\nSTAGE_ROOT=\"${MODROOT%/lib/modules/$KREL_NOW}\"\ndepmod -b \"$STAGE_ROOT\" \"$KREL_NOW\"\n[[ -f \"$DRIVER_DEST\" ]] || fail \"8188eu.ko missing after module-tree injection\"\ngrep -Fq 'kernel/drivers/net/wireless/realtek/r8188eu/8188eu.ko' \"$MODROOT/modules.dep\" || fail \"8188eu missing from modules.dep\"\nmodinfo \"$DRIVER_DEST\" | grep -Eq '^alias:[[:space:]]+usb:v0BDAp0179' || fail \"staged 8188eu alias check failed\"\necho \"CLOUD9=PASS 8188eu injected into staged K1 module tree and depmod refreshed\"\n"
_r36os_lines.insert(_r36os_modinst_hits[0] + 1, _r36os_external_install)

_r36os_builder.write_text("".join(_r36os_lines))
print("CLOUD9=PASS injected pinned RTL8188EU external-module build and staging")
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
