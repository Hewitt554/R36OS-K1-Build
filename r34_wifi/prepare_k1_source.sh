#!/usr/bin/env bash
# R34: reconstruct frozen original R36OS K1 kernel sources on the GitHub host.
# NO DEVICE WRITES; no kernel Image or DTB shipped.
set -Eeuo pipefail
SRC="${1:?source directory}"
ROOT="${2:?work directory}"
OUT="$ROOT/r34-original-k1"
mkdir -p "$OUT"
for x in git curl patch python3 tar sha256sum; do command -v "$x" >/dev/null || exit 1; done
BASE='https://raw.githubusercontent.com/Hewitt554/R36OS-K1-Build/89719bd08a8a8b32fb0448b58e0e55df20acd0f4/bootstrap_r36os_k1.sh'
curl -fsSL --retry 4 --retry-delay 2 "$BASE" -o "$OUT/authoritative_bootstrap.sh"
[[ "$(git hash-object "$OUT/authoritative_bootstrap.sh")" == 7afd3b5032f78371f687e3bab0a38fc076a6c966 ]] || { echo 'R34 bootstrap Git blob mismatch' >&2; exit 1; }
python3 - "$OUT/authoritative_bootstrap.sh" "$OUT" <<'PYEXTRACT'
from pathlib import Path
import base64,hashlib,sys,zipfile
s=Path(sys.argv[1]).read_text()
a=s.index("cat <<'R36OS_K1_KIT_BASE64' | base64 -d > \"$KIT_ZIP\"")
a=s.index('\n',a)+1;b=s.index('\nR36OS_K1_KIT_BASE64',a)
kit=base64.b64decode(s[a:b]);sha=hashlib.sha256(kit).hexdigest()
assert sha=='96c198d8e82c12c445901dbbee85a47a632a018bbc9dd304229d8e6212fa0eeb',sha
p=Path(sys.argv[2]);q=p/'k1-kit.zip';q.write_bytes(kit)
with zipfile.ZipFile(q) as z:
    assert z.testzip() is None
    z.extractall(p/'kit')
print('[R34] frozen original K1 project zip verified')
PYEXTRACT
KIT="$OUT/kit/R36OS_K1_CP04_CP05_WINDOWS_BUILD_KIT_2026-09-27"
[[ -f "$KIT/BUILD_K1_CHECKPOINT04.sh" ]] || exit 1
( cd "$KIT" && sha256sum -c SHA256SUMS.txt >/dev/null )
# Exact Cloud8 Linux-runner portability fix, without relaxing source hashes.
python3 - "$KIT/external_cp04_builder/fetch_exact_inputs.sh" <<'PYFIX'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
a='local rel="$1" expected="$2" out="$DEST/archr/$rel" cache="$CACHE/archr/$rel" tmp'
b='local rel="$1" expected="$2" tmp\n    local out="$DEST/archr/$rel" cache="$CACHE/archr/$rel"'
assert s.count(a)==1,'R34 frozen fetcher patch anchor mismatch'
p.write_text(s.replace(a,b))
PYFIX
bash "$KIT/external_cp04_builder/fetch_exact_inputs.sh" "$OUT/frozen-inputs"
P="$OUT/frozen-inputs/archr/projects/ArchR/devices/RK3326/patches/linux"
for file in 026-px30s-cpuinfo-soc-detection.patch 023-px30s-tsadc-support.patch 025-px30s-dsi-dphy-timing-table.patch; do
  patch -d "$SRC" -p1 --batch --forward --fuzz=0 < "$P/$file"
done
PANEL="$OUT/frozen-inputs/archr/projects/ArchR/packages/linux-drivers/generic-dsi/sources/panel-generic-dsi.c"
cp -- "$PANEL" "$SRC/drivers/gpu/drm/panel/panel-generic-dsi.c"
grep -Fq 'panel-generic-dsi.o' "$SRC/drivers/gpu/drm/panel/Makefile" || echo 'obj-y += panel-generic-dsi.o' >> "$SRC/drivers/gpu/drm/panel/Makefile"
cp "$KIT/k1_source/rk3326-r36os-k1-panel4.dts" "$SRC/arch/arm64/boot/dts/rockchip/rk3326-r36os-k1.dts"
grep -Fq 'rk3326-r36os-k1.dtb' "$SRC/arch/arm64/boot/dts/rockchip/Makefile" || echo 'dtb-$(CONFIG_ARCH_ROCKCHIP) += rk3326-r36os-k1.dtb' >> "$SRC/arch/arm64/boot/dts/rockchip/Makefile"
cat > "$ROOT/result/R34_K1_EXACT_SOURCE.txt" <<EOF
R34_SOURCE_RECREATED=1
ORIGINAL_K1_BOOTSTRAP_GIT_BLOB=7afd3b5032f78371f687e3bab0a38fc076a6c966
ORIGINAL_K1_KIT_SHA256=96c198d8e82c12c445901dbbee85a47a632a018bbc9dd304229d8e6212fa0eeb
LINUX_TARBALL_SHA256=e998a232b9418db3301cb58468e291a4f41d6ab8306029b30d991f56251dc8d2
ARCHR_COMMIT=dbd45d454f0fea1e61c0b35e429f6be18f3e997e
PATCHES=026,023,025
PANEL=EXACT_ORIGINAL_CP04_GENERIC_DSI
DTS=EXACT_ORIGINAL_CP04_PANEL4
NEVER_INSTALLED_TO_R36XX=1
EOF
echo '[R34] Frozen K1 source patches applied; still no device installation'
