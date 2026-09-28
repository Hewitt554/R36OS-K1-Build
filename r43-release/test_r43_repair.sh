#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HELPER="$HERE/r36os-r36update-repair"
QEMU_WRAPPER="$HERE/qemu-fsck-wrapper.sh"
TARGET_FSCK="${TARGET_FSCK:?TARGET_FSCK must point to built AArch64 fsck.fat}"
CID='e551eb6598d6da7a8e8320e9'

make_k1_fixture(){
  local mnt="$1"
  sudo mkdir -p "$mnt/R36OS-KernelNext/K1"
  for f in Image uInitrd rk3326-r36s-k1.dtb modules.tar.xz BUILD_INFO.txt; do
    printf 'fixture-%s\n' "$f" | sudo tee "$mnt/R36OS-KernelNext/K1/$f" >/dev/null
  done
  printf 'format=R36OS_K1_CANDIDATE_V1\ncandidate_id=%s\n' "$CID" | sudo tee "$mnt/R36OS-KernelNext/K1/K1.conf" >/dev/null
  (cd "$mnt/R36OS-KernelNext/K1" && sudo sha256sum Image uInitrd rk3326-r36s-k1.dtb modules.tar.xz K1.conf BUILD_INFO.txt | sudo tee MANIFEST.sha256 >/dev/null)
}

new_loop_fixture(){
  local prefix="$1"
  MNT="/tmp/${prefix}-mnt"
  STATE="/tmp/${prefix}-state"
  IMG="/tmp/${prefix}.img"
  sudo rm -rf "$MNT" "$STATE" "$IMG"
  sudo mkdir -p "$MNT" "$STATE"
  sudo mount -t tmpfs -o size=3G tmpfs "$STATE"
  truncate -s 64M "$IMG"
  mkfs.fat -F 32 -n R36UPDATE "$IMG" >/dev/null
  LOOP="$(sudo losetup --find --show "$IMG")"
  UUID="$(sudo blkid -s UUID -o value "$LOOP")"
  sudo mount -t vfat "$LOOP" "$MNT"
  make_k1_fixture "$MNT"
}

cleanup_loop_fixture(){
  sudo umount "$MNT" 2>/dev/null || true
  sudo umount "$STATE" 2>/dev/null || true
  sudo losetup -d "$LOOP" 2>/dev/null || true
  sudo rm -rf "$MNT" "$STATE" "$IMG" 2>/dev/null || true
}

run_target_checker_full_helper(){
  (
    new_loop_fixture r43-target-helper
    trap cleanup_loop_fixture EXIT
    sudo env \
      R36OS_R36UPDATE_MOUNT="$MNT" \
      R36OS_R36UPDATE_DEV="$LOOP" \
      R36OS_R36UPDATE_UUID="$UUID" \
      R36OS_STATE_ROOT="$STATE" \
      R36OS_FSCK_FAT="$QEMU_WRAPPER" \
      R36OS_FSCK_QEMU_BIN="$TARGET_FSCK" \
      bash "$HELPER" repair | tee /tmp/r43-target-helper.out
    grep -q 'status=PASS_REBOOT_REQUIRED' /tmp/r43-target-helper.out
    ! mountpoint -q "$MNT"
    grep -q '^precheck_rc=0$' "$STATE/logs/r36update-repair/LAST.conf"
    grep -q '^repair_rc=not-needed$' "$STATE/logs/r36update-repair/LAST.conf"
    grep -q '^verify_rc=0$' "$STATE/logs/r36update-repair/LAST.conf"
    grep -Fq "checker=$QEMU_WRAPPER" "$STATE/logs/r36update-repair/LAST.conf"
    test -s "$STATE"/recovery/r36update/R36UPDATE-pre-fsck-*.tar
  )
  echo R43_FULL_TARGET_HELPER=PASS
}

run_readonly_fallback(){
  (
    new_loop_fixture r43-fallback
    trap cleanup_loop_fixture EXIT
    BAD=/tmp/r43-fallback-bad
    GOOD=/tmp/r43-fallback-good
    cat >"$BAD" <<'BAD_EOF'
#!/bin/sh
exit 134
BAD_EOF
    cat >"$GOOD" <<'GOOD_EOF'
#!/bin/sh
exec /usr/sbin/fsck.fat "$@"
GOOD_EOF
    chmod 0755 "$BAD" "$GOOD"
    sudo env \
      R36OS_R36UPDATE_MOUNT="$MNT" \
      R36OS_R36UPDATE_DEV="$LOOP" \
      R36OS_R36UPDATE_UUID="$UUID" \
      R36OS_STATE_ROOT="$STATE" \
      "R36OS_FSCK_NATIVE_CANDIDATES=$BAD $GOOD" \
      bash "$HELPER" repair | tee /tmp/r43-fallback.out
    grep -q 'status=PASS_REBOOT_REQUIRED' /tmp/r43-fallback.out
    grep -Fq "checker=$GOOD" "$STATE/logs/r36update-repair/LAST.conf"
    grep -Fq "checker_precheck_rc=134 checker=$BAD" "$STATE"/logs/r36update-repair/repair-*.log
    ! mountpoint -q "$MNT"
  )
  echo R43_READONLY_FALLBACK=PASS
}

run_no_switch_after_write(){
  (
    new_loop_fixture r43-no-switch
    trap cleanup_loop_fixture EXIT
    FIRST=/tmp/r43-no-switch-first
    SECOND=/tmp/r43-no-switch-second
    SENTINEL=/tmp/r43-no-switch-second-used
    rm -f "$SENTINEL"
    cat >"$FIRST" <<'FIRST_EOF'
#!/bin/sh
case "${1:-}" in
  -n) exit 1 ;;
  -a) kill -ABRT $$ ;;
  *) exit 2 ;;
esac
FIRST_EOF
    cat >"$SECOND" <<SECOND_EOF
#!/bin/sh
touch "$SENTINEL"
exec /usr/sbin/fsck.fat "\$@"
SECOND_EOF
    chmod 0755 "$FIRST" "$SECOND"
    set +e
    sudo env \
      R36OS_R36UPDATE_MOUNT="$MNT" \
      R36OS_R36UPDATE_DEV="$LOOP" \
      R36OS_R36UPDATE_UUID="$UUID" \
      R36OS_STATE_ROOT="$STATE" \
      "R36OS_FSCK_NATIVE_CANDIDATES=$FIRST $SECOND" \
      bash "$HELPER" repair >/tmp/r43-no-switch.out 2>&1
    RC=$?
    set -e
    test "$RC" -eq 58
    grep -q 'fat-repair-failed-rc-134' /tmp/r43-no-switch.out
    grep -q '^precheck_rc=1$' "$STATE/logs/r36update-repair/LAST.conf"
    grep -q '^repair_rc=134$' "$STATE/logs/r36update-repair/LAST.conf"
    grep -Fq "checker=$FIRST" "$STATE/logs/r36update-repair/LAST.conf"
    test ! -e "$SENTINEL"
    mountpoint -q "$MNT"
    findmnt -rn -o OPTIONS --target "$MNT" | grep -Eq '(^|,)ro(,|$)'
  )
  echo R43_NO_SWITCH_AFTER_WRITE=PASS
}

run_no_compatible_checker(){
  (
    new_loop_fixture r43-no-checker
    trap cleanup_loop_fixture EXIT
    BAD=/tmp/r43-no-checker-bad
    printf '#!/bin/sh\nexit 134\n' >"$BAD"
    chmod 0755 "$BAD"
    set +e
    sudo env \
      R36OS_R36UPDATE_MOUNT="$MNT" \
      R36OS_R36UPDATE_DEV="$LOOP" \
      R36OS_R36UPDATE_UUID="$UUID" \
      R36OS_STATE_ROOT="$STATE" \
      "R36OS_FSCK_NATIVE_CANDIDATES=$BAD" \
      bash "$HELPER" repair >/tmp/r43-no-checker.out 2>&1
    RC=$?
    set -e
    test "$RC" -eq 57
    grep -q 'no-compatible-fat-checker' /tmp/r43-no-checker.out
    mountpoint -q "$MNT"
    findmnt -rn -o OPTIONS --target "$MNT" | grep -Eq '(^|,)ro(,|$)'
  )
  echo R43_NO_COMPATIBLE_CHECKER_FAIL_CLOSED=PASS
}

run_armed_marker_refusal(){
  (
    new_loop_fixture r43-armed
    trap cleanup_loop_fixture EXIT
    printf 'armed\n' | sudo tee "$MNT/R36OS-KernelNext/boot-next.$CID.once" >/dev/null
    set +e
    sudo env \
      R36OS_R36UPDATE_MOUNT="$MNT" \
      R36OS_R36UPDATE_DEV="$LOOP" \
      R36OS_R36UPDATE_UUID="$UUID" \
      R36OS_STATE_ROOT="$STATE" \
      bash "$HELPER" repair >/tmp/r43-armed.out 2>&1
    RC=$?
    set -e
    test "$RC" -eq 45
    grep -q 'k1-one-shot-marker-present' /tmp/r43-armed.out
    mountpoint -q "$MNT"
  )
  echo R43_ARMED_MARKER_REFUSAL=PASS
}

run_target_checker_full_helper
run_readonly_fallback
run_no_switch_after_write
run_no_compatible_checker
run_armed_marker_refusal
echo R43_REPAIR_MATRIX=PASS
