#!/usr/bin/env bash
set -euo pipefail

PKG="${1:?r49 package required}"
WORK="${2:-${RUNNER_TEMP:-/tmp}/r49-integration}"
rm -rf "$WORK"
mkdir -p "$WORK/audit"
tar -xzf "$PKG" -C "$WORK/audit"
ROOT="$WORK/audit/payload/root"

POLICY="$ROOT/usr/local/bin/r36os-r36update-policy"
MAINT="$ROOT/usr/local/bin/r36os-r36update-maint"
SLOT="$ROOT/usr/local/bin/r36os-kernel-slot"

T="$WORK/runtime"
PUB="$T/r36update"
STATE="$T/state"
PKGROOT="$T/pkg"
BOOT="$T/boot.ini"
PREFLIGHT="$T/preflight"
VERSION="$T/version"
CHECKER="$T/fake-fsck"
MODE="$T/checker-mode"
REPAIRED="$T/repaired"
IMG="$T/r36update.img"
PRIVATE=/run/r36os-r36update-rw
GUARD=/run/r36os-r36update-guard
CID=e551eb6598d6da7a8e8320e9

rm -rf "$T"
mkdir -p "$PUB" "$STATE" "$PKGROOT/K1"
sudo rm -rf "$PRIVATE" "$GUARD" 2>/dev/null || true
sudo mkdir -p /usr/local/libexec/r36os
sudo cp "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz" /usr/local/libexec/r36os/
sudo cp "$ROOT/usr/local/libexec/r36os/fsck-selftest.img.gz.sha256" /usr/local/libexec/r36os/

cat >"$BOOT" <<EOF
# R36OS-K1-BOOT-ONCE-HOOK
# candidate_id=$CID
EOF
BOOTSHA="$(sha256sum "$BOOT" | awk '{print $1}')"

for x in Image uInitrd rk3326-r36s-k1.dtb modules.tar.xz BUILD_INFO.txt; do
  printf '%s\n' "$x-r49-test" >"$PKGROOT/K1/$x"
done
cat >"$PKGROOT/K1/K1.conf" <<EOF
hardware=R36XX-RK3326
panel=PANEL4_NV3051D_640X480
root_uuid=e139ce78-9841-40fe-8823-96a304a09859
state_uuid=a25488c6-742d-4555-82d1-e28ffc848af3
boot_mode=R36OS_K1_BOOT_ONCE
modules_storage=R36STATE_BIND
kernel_release=6.12.94-r36os-k1
candidate_id=$CID
EOF
(
  cd "$PKGROOT/K1"
  sha256sum Image uInitrd rk3326-r36s-k1.dtb modules.tar.xz K1.conf BUILD_INFO.txt >MANIFEST.sha256
)
cat >"$PKGROOT/hook.conf" <<EOF
candidate_id=$CID
hooked_boot_sha256=$BOOTSHA
EOF

cat >"$PREFLIGHT" <<'EOF'
#!/bin/sh
case "${R49_PREFLIGHT_FAIL_STAGE:-0}:$1" in
  1:*'.K1.r49-stage.'*) exit 88;;
esac
exit 0
EOF
cat >"$VERSION" <<'EOF'
#!/bin/sh
if [ "$1" = version ]; then
  echo 0.5.49.0
  exit 0
fi
exit 1
EOF
chmod +x "$PREFLIGHT" "$VERSION"

truncate -s 96M "$IMG"
LOOP="$(sudo losetup --find --show "$IMG")"
cleanup(){
  set +e
  if [ -n "${HOLDER:-}" ]; then sudo kill "$HOLDER" 2>/dev/null || true; fi
  sudo umount "$PRIVATE" 2>/dev/null || true
  sudo umount "$PUB" 2>/dev/null || true
  sudo losetup -d "$LOOP" 2>/dev/null || true
  sudo rm -rf "$PRIVATE" "$GUARD" 2>/dev/null || true
}
trap cleanup EXIT

sudo mkfs.vfat -F 32 -i C49E0225 -n R36UPDATE "$LOOP" >/dev/null
sudo mount -t vfat "$LOOP" "$PUB"
sudo mkdir -p "$PUB/R36OS-Cache" "$PUB/R36OS-Logs" "$PUB/R36OS-KernelLab" "$PUB/update"

cat >"$CHECKER" <<EOF
#!/bin/bash
mode="\$(cat "$MODE" 2>/dev/null || echo clean)"
last="\${!#}"
auto=no
for a in "\$@"; do [ "\$a" = -a ] && auto=yes; done
if [ "\$last" != "$LOOP" ]; then
  exit 0
fi
case "\$mode" in
  clean) exit 0;;
  dirty)
    if [ "\$auto" = yes ]; then touch "$REPAIRED"; exit 0; fi
    [ -f "$REPAIRED" ] && exit 0 || exit 1
    ;;
  fail) exit 8;;
  *) exit 9;;
esac
EOF
chmod +x "$CHECKER"
sha256sum "$CHECKER" >"$CHECKER.sha256"
echo clean >"$MODE"

ENVV=(
  "R36OS_UPDATE_MOUNT=$PUB"
  "R36OS_UPDATE_DEV=$LOOP"
  "R36OS_EXPECTED_UPDATE_UUID=C49E-0225"
  "R36OS_STATE_ROOT=$STATE"
  "R36OS_R36UPDATE_POLICY=$POLICY"
  "R36OS_K1_PACKAGED_ROOT=$PKGROOT"
  "R36OS_K1_PREFLIGHT=$PREFLIGHT"
  "R36OS_VERSION_HELPER=$VERSION"
  "R36OS_FSCK_FAT=$CHECKER"
  "R36OS_R36UPDATE_POLICY_STATUS=$T/policy-status"
  "R36OS_R36UPDATE_MAINT_RESULT=$T/maint-result"
  "R36OS_K1_PROGRESS_FILE=$T/progress"
)

run_root(){
  sudo -E env "${ENVV[@]}" "$@"
}
assert_public_ro(){
  mountpoint -q "$PUB"
  opts="$(findmnt -n -o OPTIONS "$PUB" | head -1)"
  case ",$opts," in *,ro,*) ;; *) echo "ASSERT: public R36UPDATE not RO: $opts" >&2; exit 200;; esac
}
assert_private_absent(){
  ! mountpoint -q "$PRIVATE"
}

echo "=== normal policy ==="
run_root "$POLICY" normal
assert_public_ro
sudo touch "$PUB/R36OS-Logs/compat-write-test"
test -f "$STATE/compat/r36update/logs/compat-write-test"

set +e
run_root "$POLICY" prepare-write >"$T/public-rw-command.out" 2>&1
rc=$?
set -e
test "$rc" -eq 2

echo "=== clean maintenance ==="
run_root "$MAINT" prepare-stage
grep -q '^status=PASS_RO_STAGED$' "$T/maint-result"
grep -q '^verify_rc=0$' "$T/maint-result"
test -s "$PUB/R36OS-KernelNext/K1/K1.conf"
assert_public_ro
assert_private_absent

echo "=== direct slot arm must fail on public RO ==="
set +e
sudo -E env"p(HÌÙ=M}-I91}9aQ}I==PôAU½HÌÙ=Lµ-É¹±9áÐÀ¢#3dõ5õUDDUôÔõTåCÒ"ET"" WÍÔ×ÓQÐPÖWÐÓÕHÓÕ\
  R36OS_VERSION_HELPER="$VERSION""p(HÌÙ=M},Å}AI1%!PôAI1%!PÀ¢"E4ÄõB"&ÒÖöæ6Râ"EBöF&V7B×&òÖ&Òæ÷WB"#âc§&3ÒCð§6WBÖP§FW7B"G&2"ÖWcp¦w&W×v6öçG&öÆÆVB×w&FR×væF÷r×&WV&VBr"EBöF&V7B×&òÖ&Òæ÷WB  ¦V6ò#ÓÓÒ6×VÆFVBF'GdB&W"FÓÓÒ ¦V6òF'Gâ"DÔôDR §&ÒÖb"E$U$TB §'Vå÷&ö÷B"DÔåB"&W&R×7FvP¦w&W×uç&W%÷&3ÓBr"EBöÖçB×&W7VÇB ¦w&W×uçfW&g÷&3ÓBr"EBöÖçB×&W7VÇB §FW7BÖb"E$U$TB ¦76W'E÷V&Æ5÷&ð¦76W'E÷&fFUö'6Vç@ ¦V6ò#ÓÓÒ6V6¶W"&BfÇW&R&W7F÷&W2$òÓÓÒ ¦V6òfÂâ"DÔôDR §6WB¶P§'Vå÷&ö÷B"DÔåB"&W&R×7FvRâ"EBö6V6¶W"ÖfÂæ÷WB"#âc§&3ÒCð§6WBÖP§FW7B"G&2"ÖWc¦76W'E÷V&Æ5÷&ð¦76W'E÷&fFUö'6Vç@ ¦V6ò#ÓÓÒ7FværfÇW&R&W7F÷&W2$òÓÓÒ §'Vå÷&ö÷B"EôÄ5"ÆVfR×VæÖ÷VçFVBâöFWböçVÆÀ§7VFòÖ¶g2çffBÔb3"Ö3CS##RÖâ#3eUDDR"DÄôõ"âöFWböçVÆÀ§7VFòÖ÷VçB×BffB"DÄôõ""ET" §7VFòÖ¶F"×"ET"õ#3dõ2Ô66R""ET"õ#3dõ2ÔÆöw2""ET"õ#3dõ2Ô¶W&æVÄÆ"""ET"÷WFFR ¦V6ò6ÆVââ"DÔôDR §6WB¶P§7VFòÔRVçb"G´Tåee´×Ò"#Cõ$TdÄtEôdÅõ5DtSÓ"DÔåB"&W&R×7FvRâ"EB÷7FvRÖfÂæ÷WB"#âc§&3ÒCð§6WBÖP§FW7B"G&2"ÖWsP¦76W'E÷V&Æ5÷&ð¦76W'E÷&fFUö'6Vç@ ¦V6ò#ÓÓÒ&V6÷fW"7Fværf÷"Ö&¶W"FW7G2ÓÓÒ §'Vå÷&ö÷B"DÔåB"&W&R×7FvRâöFWböçVÆÀ¦76W'E÷V&Æ5÷&ð ¦V6ò#ÓÓÒÖ&¶W"væF÷r2&fFR²wV&FVBÓÓÒ §'Vå÷&ö÷B"DÔåB"Ö&¶W"Ö÷Vââ"EBöÖ&¶W"Ö÷Vâæ÷WB §FW7B"B&VFÆæ²Öb"BfæFÖçBÖâÖò4õU$4R"E$dDR"ÂVBÓ""Ò"B&VFÆæ²Öb"DÄôõ" §÷G3Ò"BfæFÖçBÖâÖòõDôå2"E$dDR"ÂVBÓ ¦66R"ÂG÷G2Â"â¢Ç'rÂ¢³²¢V6ò'&fFRæ÷B%r"âc#²WB#³²W60¦w7&3Ò"BfæFÖçBÖâÖò4õU$4R"ET""ÂVBÓ ¦V6ò"Fw7&2"Âw&W×w#3f÷2×#3gWFFRÖwV&Bp¦v÷G3Ò"BfæFÖçBÖâÖòõDôå2"ET""ÂVBÓ ¦66R"ÂFv÷G2Â"â¢Ç&òÂ¢³²¢V6ò&wV&Bæ÷B$ò"âc#²WB##³²W60 ¦V6ò#ÓÓÒ&fFR6Æ÷B&ÒöF6&ÒÓÓÒ §7VFòÔRVçb WÍÔ×ÒÑTSÓVÔÓÕHUUKÔÍÔËRÙ\[^ÍÔ×ÕTUWÓSÕSHUUHÍÔ×ÓQÐPÖWÐÓÕHÓÕÍÔ×ÕTÒSÓÒSTHTÒSÓÍÔ×ÒÌWÔQQÒHQQÒÓÕ\K[ÛÙHÜ]]KX\KÝ]Ü\\H	×Ý]\ÏTTÔÉÈÜ]]KX\KÝ]\Ý\ÈUUKÔÍÔËRÙ\[^ØÛÝ[^ÒQÛÙHÝYÈQH[ÍÔ×ÒÑTSÓVÔÓÕHUUKÔÍÔËRÙ\[^ÍÔ×ÕTUWÓSÕSHUUHÍÔ×ÓQÐPÖWÐÓÕHÓÕÍÔ×ÕTÒSÓÒSTHTÒSÓÍÔ×ÒÌWÔQQÒHQQÒÓÕ\Ø\HÙ]Û[\ÝHYHUUKÔÍÔËRÙ\[^ØÛÝ[^ÒQÛÙHXÚÈOOHX\Ù\Ü]HZ[\H]OOHÝYÈ[Ý[[È[[Ý[ÈUUHÙ]
ÙBÝYÈQH[ÍÔ×ÒÑTSÓVÔÓÕHUUKÔÍÔËRÙ\[^ÍÔ×ÕTUWÓSÕSHUUHÍÔ×ÓQÐPÖWÐÓÕHÓÕÍÔ×ÕTÒSÓÒSTHTÒSÓÍÔ×ÒÌWÔQQÒHQQÒÓÕ\K[ÛÙHÜ]]K\ËX\KÝ]BÏIÂÙ]YB\ÝÈY\HÂÝYÈ[Ý[[È[[Ý[ÈUUH[ÜÛÝPRSX\Ù\XXÜ\ÈÙ]Û[\ÜÙ\ÜXX×ÜÂ\ÜÙ\Ü]]WØXÙ[XÚÈOOH\ÞH[[]]H[[Ý[Z[ÈÛÜÙYOOH[ÜÛÝPRSX\Ù\[Ü[Ù]Û[ÝYÈ\ÚXÈÙ	ÉUUIÎÈ^XÈÛY\Ì	ÓTIBÛY\BÙ]
ÙB[ÜÛÝPRSX\Ù\XÛÜÙK][[Ý[YØ\ÞKXÛÜÙKÝ]BÏIÂÙ]YB\ÝÈY\HMÂÝYÈÚ[ÓTÙ]Û[YBØZ]ÓTÙ]Û[YBÓTH[ÜÛÝPRSX\Ù\XXÜ\ÈÙ]Û[\ÜÙ\ÜXX×ÜÂ\ÜÙ\Ü]]WØXÙ[XÚÈOOHÝXØÙ\ÜÙ[ÛÜÙHX]\ÈU[[Ý[YOOH[ÜÛÝPRSX\Ù\[Ü[Ù]Û[[ÜÛÝPRSX\Ù\XÛÜÙK][[Ý[YÙ]Û[H[Ý[Ú[\HPH[Ý[Ú[\HUUH[ÜÛÝÓPÖHÜX[Ù]Û[\ÜÙ\ÜXX×ÜÂXÚÈWÒSQÔUSÓÕTÕTTÔÈÿÿ