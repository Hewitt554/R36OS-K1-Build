from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: transform_prepare.py <r48-prepare> <r49-prepare>")
src=Path(sys.argv[1]); out=Path(sys.argv[2])
s=src.read_text()

if s.count('0.5.48.0') != 1:
    raise SystemExit(f'unexpected R48 prepare version count: {s.count("0.5.48.0")}')
s=s.replace('0.5.48.0','0.5.49.0',1)

anchor='SLOT="${R36OS_KERNEL_SLOT_HELPER:-/usr/local/bin/r36os-kernel-slot}"\n'
if s.count(anchor)!=1:
    raise SystemExit('prepare helper variable anchor mismatch')
s=s.replace(anchor, anchor + 'POLICY="${R36OS_R36UPDATE_POLICY:-/usr/local/bin/r36os-r36update-policy}"\nMAINT="${R36OS_R36UPDATE_MAINT:-/usr/local/bin/r36os-r36update-maint}"\nPRIVATE="${R36OS_R36UPDATE_PRIVATE_RW:-/run/r36os-r36update-rw}"\n',1)

old_fail='''fail(){
  progress FAIL 100 "K1 preparation failed" "$2 (code $1)"
  printf 'status=FAIL\\ncode=%s\\ndetail=%s\\n' "$1" "$2" >"$RESULT" 2>/dev/null
'''
new_fail='''fail(){
  # A failed K1 preparation must never leave the FAT handoff partition writable.
  if [ -x "${MAINT:-}" ]; then "$MAINT" marker-abort-ro >/dev/null 2>&1 || true; fi
  if [ -x "${POLICY:-}" ]; then "$POLICY" finish-ro >/dev/null 2>&1 || true; fi
  progress FAIL 100 "K1 preparation failed" "$2 (code $1)"
  printf 'status=FAIL\\ncode=%s\\ndetail=%s\\n' "$1" "$2" >"$RESULT" 2>/dev/null
'''
if s.count(old_fail)!=1:
    raise SystemExit('prepare fail anchor mismatch')
s=s.replace(old_fail,new_fail,1)

start='progress RUNNING 8 "K1 candidate verified" "Checking R36UPDATE safety"\n'
end='if [ "$CMD" = stage-only ]; then\n'
i=s.find(start); j=s.find(end)
if i<0 or j<0 or j<=i:
    raise SystemExit('prepare staging block anchors not found')
replacement=r'''progress RUNNING 8 "K1 candidate verified" "Entering controlled R36UPDATE maintenance"
CID="$(val "$SRC/K1.conf" candidate_id)"; [ -n "$CID" ] || fail 12 candidate-id
[ -s "$HOOK" ] && [ -s "$META_SRC" ] || fail 13 packaged-hook-missing
[ "$(val "$META_SRC" candidate_id)" = "$CID" ] || fail 14 packaged-hook-candidate
[ -x "$POLICY" ] || fail 20 r36update-policy-missing
[ -x "$MAINT" ] || fail 21 r36update-maint-missing

"$MAINT" prepare-stage >/run/r36os-r36update-maint.console 2>&1 || fail 25 r36update-maintenance
grep -q '^status=PASS_RO_STAGED$' /run/r36os-r36update-maint.result 2>/dev/null || fail 26 r36update-maint-result

mountpoint -q "$UPDATE_MOUNT" 2>/dev/null || fail 27 r36update-not-mounted-readonly
MOPTS="$(findmnt -n -o OPTIONS "$UPDATE_MOUNT" 2>/dev/null | head -1)"
case ",$MOPTS," in *,ro,*) ;; *) fail 28 r36update-not-readonly-after-maintenance;; esac
DEV="$(findmnt -n -o SOURCE "$UPDATE_MOUNT" 2>/dev/null | head -1)"
DEV_REAL="$(readlink -f "$DEV" 2>/dev/null || printf '%s' "$DEV")"
[ "$DEV_REAL" = /dev/mmcblk0p3 ] || fail 29 r36update-source-after-maintenance
UUID="$(blkid -s UUID -o value "$DEV_REAL" 2>/dev/null | tr 'a-f' 'A-F')"
[ "$UUID" = "$EXPECTED_UPDATE_UUID" ] || fail 30 r36update-uuid-after-maintenance

"$PREFLIGHT" "$DST" >/dev/null 2>&1 || fail 31 maintained-candidate-preflight
[ "$(sha "$DST/MANIFEST.sha256")" = "$(sha "$SRC/MANIFEST.sha256")" ] || fail 32 maintained-manifest-mismatch
[ "$(candidate_tree_digest "$DST")" = "$SRC_TREE_DIGEST" ] || fail 33 maintained-tree-mismatch
[ -s "$META" ] && [ "$(sha "$META")" = "$(sha "$META_SRC")" ] || fail 34 maintained-hook-meta
progress RUNNING 30 "R36UPDATE maintenance complete" "FAT clean, exact K1 staging locked read-only"
'''
s=s[:i]+replacement+s[j:]

old_stage='''if [ "$CMD" = stage-only ]; then
  progress PASS 100 "K1 candidate staged" "Legacy boot remains unchanged"
  printf 'status=PASS\\ncode=0\\ndetail=candidate-staged\\ncandidate_id=%s\\n' "$CID" >"$RESULT"; echo "status=PASS candidate_id=$CID result=STAGED"; exit 0
fi
'''
new_stage='''if [ "$CMD" = stage-only ]; then
  "$POLICY" finish-ro >/dev/null 2>&1 || fail 35 r36update-final-readonly
  progress PASS 100 "K1 candidate staged" "R36UPDATE is read-only; legacy boot remains unchanged"
  printf 'status=PASS\\ncode=0\\ndetail=candidate-staged-readonly\\ncandidate_id=%s\\n' "$CID" >"$RESULT"
  echo "status=PASS candidate_id=$CID result=STAGED_READONLY"
  exit 0
fi
'''
if s.count(old_stage)!=1:
    raise SystemExit('prepare stage-only anchor mismatch')
s=s.replace(old_stage,new_stage,1)

old_tail='''progress RUNNING 95 "Arming next boot only" "Writing candidate-bound one-shot request"
"$SLOT" arm-once >/run/r36os-k1-arm.result 2>&1 || fail 51 arm-once
sync
progress PASS 100 "K1 Boot Next Once armed" "Restart to test; later boot falls back to legacy"
printf 'status=PASS\\ncode=0\\ndetail=armed-once\\ncandidate_id=%s\\n' "$CID" >"$RESULT"
echo "status=PASS candidate_id=$CID result=ARMED_ONCE"
exit 0
'''
new_tail='''progress RUNNING 94 "Opening private marker window" "Normal processes remain blocked from the real FAT filesystem"
"$MAINT" marker-open >/run/r36os-r36update-marker-open.result 2>&1 || fail 51 marker-window-open
PNEXT="$PRIVATE/R36OS-KernelNext"

progress RUNNING 96 "Arming next boot only" "Writing candidate-bound one-shot request on the private FAT mount"
if ! R36OS_KERNEL_NEXT_ROOT="$PNEXT" R36OS_UPDATE_MOUNT="$PRIVATE" "$SLOT" arm-once >/run/r36os-k1-arm.result 2>&1; then
  R36OS_KERNEL_NEXT_ROOT="$PNEXT" R36OS_UPDATE_MOUNT="$PRIVATE" "$SLOT" disarm >/run/r36os-k1-arm-cleanup.result 2>&1 || true
  "$MAINT" marker-abort-ro >/dev/null 2>&1 || true
  fail 52 arm-once
fi
sync

progress RUNNING 98 "Closing boot handoff" "Unmounting the private FAT window and leaving R36UPDATE closed for restart"
if ! "$MAINT" marker-close-unmounted >/run/r36os-r36update-final-unmount.result 2>&1; then
  R36OS_KERNEL_NEXT_ROOT="$PNEXT" R36OS_UPDATE_MOUNT="$PRIVATE" "$SLOT" disarm >/run/r36os-k1-final-unmount-cleanup.result 2>&1 || true
  "$MAINT" marker-abort-ro >/dev/null 2>&1 || true
  fail 53 final-clean-unmount
fi
mountpoint -q "$UPDATE_MOUNT" 2>/dev/null && fail 54 final-r36update-still-mounted
mountpoint -q "$PRIVATE" 2>/dev/null && fail 55 final-private-still-mounted

progress PASS 100 "K1 Boot Next Once armed" "R36UPDATE closed cleanly; restart to test once"
printf 'status=PASS\\ncode=0\\ndetail=armed-once-private-window-r36update-unmounted\\ncandidate_id=%s\\n' "$CID" >"$RESULT"
echo "status=PASS candidate_id=$CID result=ARMED_ONCE_PRIVATE_WINDOW_R36UPDATE_UNMOUNTED"
exit 0
'''
if s.count(old_tail)!=1:
    raise SystemExit('prepare arm tail anchor mismatch')
s=s.replace(old_tail,new_tail,1)

out.write_text(s)
