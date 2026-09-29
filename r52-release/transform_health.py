from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_health.py <r50-health> <r52-health>")
s=Path(sys.argv[1]).read_text()
s=s.replace('# R36OS Alpha 5R50 K1 health/fallback recorder with root-level U-Boot consumed marker.','# R36OS Alpha 5R52 K1 health/fallback recorder with persistent visible boot trace.',1)
anchor='''write_record(){
  KIND="$1"; OUTDIR="$STATE/logs/kernel-next"; OUT="$OUTDIR/$KIND-$CID.conf"; TMP="$OUT.tmp"'''
insert='''breadcrumb_append(){
  target="$1"; deepest=none
  for spec in K1CON.OK:guard_verified K1IMG.OK:image_loaded K1INI.OK:initramfs_loaded K1DTB.OK:dtb_loaded K1BOT.OK:booti_invoked K1RET.OK:booti_returned; do
    f="${spec%%:*}"; st="${spec#*:}"
    if [ -s "${R36OS_UPDATE_MOUNT:-/r36update}/$f" ]; then
      echo "breadcrumb_$f=yes" >>"$target"
      deepest="$st"
    else
      echo "breadcrumb_$f=no" >>"$target"
    fi
  done
  echo "deepest_uboot_stage=$deepest" >>"$target"
  BREADCRUMB_DEEPEST="$deepest"
}
write_record(){
  KIND="$1"; OUTDIR="$STATE/logs/kernel-next"; OUT="$OUTDIR/$KIND-$CID.conf"; TMP="$OUT.tmp"'''
if s.count(anchor)!=1: raise SystemExit('write_record anchor')
s=s.replace(anchor,insert,1)
old='''  echo "pstore_files_copied=$COPIED" >>"$RECORD"
  echo "legacy_cmdline_sha256=$(sha "$CMDLINE")" >>"$RECORD"
  sync
  if command -v r36os-github-diagnostics >/dev/null 2>&1; then
    R36OS_DIAG_FAILURE_CODE=K1_FALLBACK R36OS_DIAG_FAILURE_DETAIL="pstore_files=$COPIED" r36os-github-diagnostics capture "k1-fallback-$CID" >/dev/null 2>&1 || true'''
new='''  echo "pstore_files_copied=$COPIED" >>"$RECORD"
  echo "legacy_cmdline_sha256=$(sha "$CMDLINE")" >>"$RECORD"
  breadcrumb_append "$RECORD"
  sync
  if command -v r36os-github-diagnostics >/dev/null 2>&1; then
    R36OS_DIAG_FAILURE_CODE=K1_FALLBACK R36OS_DIAG_FAILURE_DETAIL="pstore_files=$COPIED deepest=$BREADCRUMB_DEEPEST" r36os-github-diagnostics capture "k1-fallback-$CID" >/dev/null 2>&1 || true'''
if s.count(old)!=1: raise SystemExit('fallback capture anchor')
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
