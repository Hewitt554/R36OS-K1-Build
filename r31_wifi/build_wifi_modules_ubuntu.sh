#!/usr/bin/env bash
# R36OS R31: compile standalone Wi-Fi module candidate, never install it.
set -Eeuo pipefail
export LC_ALL=C
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${R31_WORKDIR:-${RUNNER_TEMP:-/tmp}/r36os-r31-wifi}"
KERNEL_VERSION=6.12.94
KERNEL_RELEASE=6.12.94-r36os-k1
KERNEL_TARBALL_SHA=e998a232b9418db3301cb58468e291a4f41d6ab8306029b30d991f56251dc8d2
KERNEL_URL="https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${KERNEL_VERSION}.tar.xz"
JOBS="${R31_JOBS:-4}"
log(){ printf '[R31] %s\n' "$*"; }
fail(){ log "FAIL $*" >&2; exit 1; }
for bin in curl tar xz sha256sum clang-18 ld.lld-18 make python3 gzip depmod modinfo readelf; do
  command -v "$bin" >/dev/null 2>&1 || fail "required command missing: $bin";
done
[[ "${R31_ALLOW_OVERWRITE:-0}" == 1 || ! -e "$ROOT" ]] || fail "build output already exists: $ROOT. Choose a fresh R31_WORKDIR."
mkdir -p "$ROOT" "$ROOT/out" "$ROOT/work" "$ROOT/result"
SRC="$ROOT/work/linux-${KERNEL_VERSION}"
OUT="$ROOT/out"
mkdir -p "$ROOT/download"
if [[ -n "${R31_KERNEL_TARBALL:-}" ]]; then
  [[ -f "$R31_KERNEL_TARBALL" ]] || fail "R31_KERNEL_TARBALL is not a file"
  cp -- "$R31_KERNEL_TARBALL" "$ROOT/download/kernel.tar.xz"
else
  log "Downloading pinned Linux ${KERNEL_VERSION} source on build host"
  curl --fail --location --retry 4 --retry-delay 3 --connect-timeout 20 --max-time 900 \
    "$KERNEL_URL" -o "$ROOT/download/kernel.tar.xz"
fi
actual=$(sha256sum "$ROOT/download/kernel.tar.xz" | cut -d' ' -f1)
[[ "$actual" == "$KERNEL_TARBALL_SHA" ]] || fail "kernel tarball SHA256 mismatch: $actual"
log "Linux source checksum verified"
tar -xJf "$ROOT/download/kernel.tar.xz" -C "$ROOT/work"
[[ -f "$SRC/Makefile" && -x "$SRC/scripts/config" ]] || fail "source extraction missing Kbuild files"
gzip -cd "$HERE/WIFI_KERNEL_CONFIG_R29.gz" > "$OUT/.config"
python3 "$HERE/validate_r29_baseline.py" "$HERE/WIFI_KERNEL_CONFIG_R29.gz"
cp "$OUT/.config" "$ROOT/result/DEVICE_R29_BASELINE.config"
# Exact wireless feature flags requested. Keep every other kernel option from the
# device's authentic /proc/config.gz; olddefconfig resolves dependencies.
"$SRC/scripts/config" --file "$OUT/.config" \
 --enable WLAN --enable WLAN_VENDOR_REALTEK \
 --module CFG80211 --module MAC80211 --module RFKILL --module CRYPTO_LIB_ARC4 \
 --module RTL8XXXU --enable RTL8XXXU_UNTESTED
MAKE=(make -C "$SRC" O="$OUT" ARCH=arm64 LLVM=-18 LLVM_IAS=1)
"${MAKE[@]}" olddefconfig
expected=( 'CONFIG_CFG80211=m' 'CONFIG_MAC80211=m' 'CONFIG_RFKILL=m' \
 'CONFIG_CRYPTO_LIB_ARC4=m' 'CONFIG_RTL8XXXU=m' 'CONFIG_RTL8XXXU_UNTESTED=y' )
for line in "${expected[@]}"; do
  grep -qx "$line" "$OUT/.config" || fail "Kconfig olddefconfig rejected $line"
done
actual_rel=$("${MAKE[@]}" -s kernelrelease)
[[ "$actual_rel" == "$KERNEL_RELEASE" ]] || fail "kernelrelease not exact $KERNEL_RELEASE: $actual_rel"
cp "$OUT/.config" "$ROOT/result/RESOLVED_R31.config"
if ! python3 "$HERE/report_config_delta.py" "$ROOT/result/DEVICE_R29_BASELINE.config" \
 "$ROOT/result/RESOLVED_R31.config" > "$ROOT/result/CONFIG_DIFF.txt"; then
  log "Configuration drift detected; printing exact mismatch before stopping:"
  cat "$ROOT/result/CONFIG_DIFF.txt"
  fail "R31 kernel configuration changed unexpectedly; NO modules installed or packaged"
fi
cat "$ROOT/result/CONFIG_DIFF.txt"
log "Building full kernel symbols and configured modules; this is host-only"
"${MAKE[@]}" -j"$JOBS" Image modules 2>&1 | tee "$ROOT/result/BUILD.log"
[[ -s "$OUT/Module.symvers" ]] || fail "Module.symvers missing from kernel build"
[[ -s "$OUT/arch/arm64/boot/Image" ]] || fail "kernel Image was not produced on build host"
# Do not package or deploy this potentially ABI-different kernel Image!
# The closure collector selects only wifi modules and recursively needed modules.
python3 "$HERE/package_wifi_modules.py" --build "$OUT" --out "$ROOT/result/CANDIDATE" \
 --release "$KERNEL_RELEASE"
# The output intentionally lacks an SD installer and lacks the Linux Image.
[[ ! -e "$ROOT/result/CANDIDATE/Image" ]] || fail "kernel Image accidentally packaged"
( cd "$ROOT/result" && sha256sum CONFIG_DIFF.txt RESOLVED_R31.config \
  CANDIDATE/manifest.json > R31_SHA256SUMS.txt )
log "HOST_BUILD_COMPLETE: candidate modules only; still NOT cleared for R36XX installation"
log "RESULT=$ROOT/result"
