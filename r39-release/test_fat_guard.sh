#!/usr/bin/env bash
set -euo pipefail
PREP="$(cd "$(dirname "$0")" && pwd)/r36os-kernel-next-prepare"
T="${TMPDIR:-/tmp}/r36os-r39-fat-test.$$"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/pkg/K1" "$T/update" "$T/state"
touch "$T/mmcblk0p3"
cat > "$T/pkg/K1/K1.conf" <<'C'
candidate_id=e551eb6598d6da7a8e8320e9
kernel_release=6.12.94-r36os-k1
C
printf 'dummy\n' > "$T/pkg/K1/MANIFEST.sha256"
printf '# hook\n' > "$T/pkg/hooked-boot.ini"
printf 'candidate_id=e551eb6598d6da7a8e8320e9\n' > "$T/pkg/hook.conf"
cat > "$T/bin/version" <<'S'
#!/bin/sh
[ "${1:-}" = version ] && echo 0.5.39.0
S
cat > "$T/bin/preflight" <<'S'
#!/bin/sh
exit 0
S
cat > "$T/bin/mountpoint" <<'S'
#!/bin/sh
exit 0
S
cat > "$T/bin/findmnt" <<S
#!/bin/sh
case "\$*" in
  *SOURCE*) echo "$T/mmcblk0p3";;
  *FSTYPE*) echo vfat;;
  *OPTIONS*) echo rw,nosuid,nodev;;
  *) exit 1;;
esac
S
cat > "$T/bin/blkid" <<'S'
#!/bin/sh
echo C49E-0225
S
cat > "$T/bin/df" <<'S'
#!/bin/sh
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/mock 2000000 1000 1999000 1%% /mock\n'
S
chmod +x "$T/bin/"*
run_case(){
  name="$1"; msg="$2"; expect="$3"
  rm -rf "$T/update/R36OS-KernelNext"
  cat > "$T/bin/dmesg" <<S
#!/bin/sh
printf '%s\n' '$msg'
S
  chmod +x "$T/bin/dmesg"
  set +e
  out="$(PATH="$T/bin:/usr/bin:/bin" \
    R36OS_K1_PACKAGED_ROOT="$T/pkg" \
    R36OS_UPDATE_MOUNT="$T/update" \
    R36OS_KERNEL_NEXT_ROOT="$T/update/R36OS-KernelNext" \
    R36OS_STATE_ROOT="$T/state" \
    R36OS_VERSION_HELPER="$T/bin/version" \
    R36OS_K1_PREFLIGHT="$T/bin/preflight" \
    "$PREP" stage-only 2>&1)"
  rc=$?
  set -e
  printf '%s rc=%s out=%s\n' "$name" "$rc" "$out"
  if [ "$expect" = pass ]; then
    [ "$rc" -eq 0 ]
    echo "$out" | grep -q 'result=STAGED'
  else
    [ "$rc" -eq 25 ]
    echo "$out" | grep -q 'detail=r36update-fat-health-mmcblk0p3'
  fi
}
run_case unrelated 'FAT-fs (mmcblk0p1): Volume was not properly unmounted. Some data may be corrupt.' pass
run_case actual 'FAT-fs (mmcblk0p3): Volume was not properly unmounted. Some data may be corrupt.' fail
printf 'R39_FAT_GUARD_TEST=PASS\n'
