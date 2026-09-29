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
sudo -E env \
  R36OS_KERNEL_NEXT_ROOT="$PUB/R36OS-KernelNext" \
  R36OS_UPDATE_MOUNT="$PUB" \
  R36OS_LEGACY_BOOT="$BOOT" \
  R36OS_VERSION_HELPER="$VERSION" \
  R36OS_K1_PREFLIGHT="$PREFLIGHT" \
  "$SLOT" arm-once >"$T/direct-ro-arm.out" 2>&1
rc=$?
set -e
test "$rc" -eq 67
grep -q 'controlled-write-window-required' "$T/direct-ro-arm.out"

echo "=== simulated dirty FAT repair path ==="
echo dirty >"$MODE"
rm -f "$REPAIRED"
run_root "$MAINT" prepare-stage
grep -q '^repair_rc=0$' "$T/maint-result"
grep -q '^verify_rc=0$' "$T/maint-result"
test -f "$REPAIRED"
assert_public_ro
assert_private_absent

echo "=== checker hard failure restores RO ==="
echo fail >"$MODE"
set +e
run_root "$MAINT" prepare-stage >"$T/checker-fail.out" 2>&1
rc=$?
set -e
test "$rc" -eq 61
assert_public_ro
assert_private_absent

echo "=== staging failure restores RO ==="
run_root "$POLICY" leave-unmounted >/dev/null
sudo mkfs.vfat -F 32 -i C49E0225 -n R36UPDATE "$LOOP" >/dev/null
sudo mount -t vfat "$LOOP" "$PUB"
sudo mkdir -p "$PUB/R36OS-Cache" "$PUB/R36OS-Logs" "$PUB/R36OS-KernelLab" "$PUB/update"
echo clean >"$MODE"
set +e
sudo -E env "${ENVV[@]}" R49_PREFLIGHT_FAIL_STAGE=1 "$MAINT" prepare-stage >"$T/stage-fail.out" 2>&1
rc=$?
set -e
test "$rc" -eq 75
assert_public_ro
assert_private_absent

echo "=== recover staging for marker tests ==="
run_root "$MAINT" prepare-stage >/dev/null
assert_public_ro

echo "==== marker window is private + guarded ==="
run_root "$MAINT" marker-open >"$T/marker-open.out"
test "$(readlink -f "$(findmnt -n -o SOURCE "$PRIVATE" | head -1)")" = "$(readlink -f "$LOOP")"
popts="$(findmnt -n -o OPTIONS "$PRIVATE" | head -1)"
case ",$popts," in *,rw,*) ;; *) echo "private not RW" >&2; exit 201;; esac
gsrc="$(findmnt -n -o SOURCE "$PUB" | head -1)"
echo "$gsrc" | grep -q 'r36os-r36update-guard'
gopts="$(findmnt -n -o OPTIONS "$PUB"ÂVBÓ ¦66R"ÂFv÷G2Â"â¢Ç&òÂ¢³²¢V6ò&wV&Bæ÷B$ò"âc#²WB##³²W60 ¦V6ò#ÓÓÒ&fFR6Æ÷B&ÒöF6&ÒÓÓÒ §7VFòÔRVçbÀ¢#3dõ5ô´U$äTÅôäUEõ$ôõCÒ"E$dDRõ#3dõ2Ô¶W&æVÄæWB"À¢#3dõ5õUDDUôÔõTåCÒ"E$dDR"À¢#3dõ5ôÄTt5ô$ôõCÒ"D$ôõB"À¢#3dõ5õdU%4ôåôTÅU#Ò"EdU%4ôâ"À¢#3dõ5ô³õ$TdÄtCÒ"E$TdÄtB"À¢"E4ÄõB"&ÒÖöæ6Râ"EB÷&fFRÖ&Òæ÷WB ¦w&W×uç7FGW3Õ52r"EB÷&fFRÖ&Òæ÷WB §FW7B×2"E$dDRõ#3dõ2Ô¶W&æVÄæWBö&ö÷BÖæWBâD4Bæöæ6R §7VFòÔRVçb PKÿÿ