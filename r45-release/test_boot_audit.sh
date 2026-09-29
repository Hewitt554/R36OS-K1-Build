#!/usr/bin/env bash
set -euo pipefail
H="${1:-r45-release/r36os-k1-boot-audit}"
W="${RUNNER_TEMP:-/tmp}/r45-audit-test"
rm -rf "$W"
mkdir -p "$W/state/logs/kernel-next" "$W/next/K1" "$W/pstore" "$W/run"
CID=e551eb6598d6da7a8e8320e9
KREL=6.12.94-r36os-k1

cat >"$W/next/K1/K1.conf" <<EOF
candidate_id=$CID
kernel_release=$KREL
EOF
printf 'dummy  K1.conf\n' >"$W/next/K1/MANIFEST.sha256"
cat >"$W/preflight" <<'EOF'
#!/bin/sh
exit 0
EOF
cat >"$W/slot" <<'EOF'
#!/bin/sh
echo candidate_verify_code=0
echo hook_verify_code=0
echo armed=test
echo consumed=test
exit 0
EOF
chmod +x "$W/preflight" "$W/slot"

cat >"$W/boot.ini" <<EOF
# R36OS-K1-BOOT-ONCE-HOOK
# candidate_id=$CID
EOF
BOOTSHA="$(sha256sum "$W/boot.ini" | awk '{print $1}')"
cat >"$W/next/hook.conf" <<EOF
candidate_id=$CID
hooked_boot_sha256=$BOOTSHA
EOF
printf 'root=UUID=test-root r36os.kernel_slot=legacy\n' >"$W/cmdline"
printf 'pstore-evidence\n' >"$W/pstore/dmesg-test"

run_audit(){
  out="$1"
  R36OS_STATE_ROOT="$W/state"   R36OS_KERNEL_NEXT_ROOT="$W/next"   R36OS_LEGACY_BOOT="$W/boot.ini"   R36OS_K1_HOOK_META="$W/next/hook.conf"   R36OS_CMDLINE_FILE="$W/cmdline"   R36OS_PSTORE_ROOT="$W/pstore"   R36OS_EARLY_MARKER="$W/run/early.conf"   R36OS_K1_PREFLIGHT="$W/preflight"   R36OS_KERNEL_SLOT_HELPER="$W/slot"   R36OS_K1_BOOT_AUDIT_OUT="$out"   bash "$H" >/dev/null
}
REQ="$W/next/boot-next.$CID.once"
CON="$W/next/boot-next.$CID.consumed"

run_audit "$W/none.conf"
grep -qx 'marker_state=NONE' "$W/none.conf"
grep -qx 'candidate_preflight_rc=0' "$W/none.conf"
grep -qx 'boot_hook_marker=yes' "$W/none.conf"
grep -qx 'boot_candidate_marker=yes' "$W/none.conf"
grep -qx 'hook_boot_hash_match=yes' "$W/none.conf"
grep -qx 'pstore_files=1' "$W/none.conf"

cat >"$REQ" <<EOF
format=R36OS_K1_BOOT_REQUEST_V1
candidate_id=$CID
candidate_manifest_sha256=$(sha256sum "$W/next/K1/MANIFEST.sha256" | awk '{print $1}')
EOF
BEFORE_REQ="$(sha256sum "$REQ")|$(stat -c '%s:%Y' "$REQ")"
run_audit "$W/pending.conf"
AFTER_REQ="$(sha256sum "$REQ")|$(stat -c '%s:%Y' "$REQ")"
test "$BEFORE_REQ" = "$AFTER_REQ"
grep -qx 'marker_state=ARMED_PENDING' "$W/pending.conf"

cp "$REQ" "$CON"
BEFORE_BOTH="$(sha256sum "$REQ" "$CON")|$(stat -c '%s:%Y' "$REQ" "$CON")"
run_audit "$W/consumed.conf"
AFTER_BOTH="$(sha256sum "$REQ" "$CON")|$(stat -c '%s:%Y' "$REQ" "$CON")"
test "$BEFORE_BOTH" = "$AFTER_BOTH"
grep -qx 'marker_state=CONSUMED_WITH_REQUEST' "$W/consumed.conf"
grep -qx 'request_consumed_hash_match=yes' "$W/consumed.conf"

rm -f "$REQ"
BEFORE_CON="$(sha256sum "$CON")|$(stat -c '%s:%Y' "$CON")"
run_audit "$W/orphan.conf"
AFTER_CON="$(sha256sum "$CON")|$(stat -c '%s:%Y' "$CON")"
test "$BEFORE_CON" = "$AFTER_CON"
grep -qx 'marker_state=ORPHAN_CONSUMED' "$W/orphan.conf"

echo R45_PASSIVE_MARKER_MATRIX=PASS
