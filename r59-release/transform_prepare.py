from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit('usage: transform_prepare_r59.py <exact-r58-prepare> <r59-prepare>')
src=Path(sys.argv[1]); out=Path(sys.argv[2]); s=src.read_text()
EXPECTED='06cfa9c0b3520268501f65844488752d48923f053223d8ebdee2d82b028ae414'
import hashlib
if hashlib.sha256(src.read_bytes()).hexdigest()!=EXPECTED:
    raise SystemExit('R58 prepare SHA-256 mismatch')
if s.count('0.5.58.0') != 1:
    raise SystemExit('R58 version gate anchor mismatch')
s=s.replace('0.5.58.0','0.5.59.0',1)

start='''if [ -e "$MODDST" ]; then\n  progress RUNNING 54 "Checking existing K1 modules" "Verifying kernel release and exact module archive contents"'''
end='''fi\n# This is the first boot-affecting operation and happens only after explicit user action.'''
if s.count(start)!=1 or s.count(end)!=1:
    raise SystemExit(f'module activation anchors mismatch start={s.count(start)} end={s.count(end)}')
pre,rest=s.split(start,1)
oldbody,post=rest.split(end,1)

new='''stage_new_modules(){
  progress RUNNING 38 "Checking R36STATE space" "Reserving new module tree plus 256 MiB safety headroom"
  STATE_AVAIL_KB="$(df -Pk "$STATE_MOUNT" 2>/dev/null | awk 'NR>1{v=$4} END{print v}')"; echo "$STATE_AVAIL_KB" | grep -Eq '^[0-9]+$' || fail 82 r36state-space-measure
  MODULE_NEED_KB=$(((MODBYTES + 1023) / 1024 + 262144)); [ "$STATE_AVAIL_KB" -ge "$MODULE_NEED_KB" ] || fail 82 r36state-space
  progress RUNNING 42 "Preparing K1 modules" "Validating changed module archive before extraction"
  mkdir -p "$MODBASE" || fail 68 modules-root-create
  STAGE_BASE="$MODBASE/.stage-$CID-$$"; STAGED_MODDST="$STAGE_BASE/$MODROOTNAME"
  rm -rf "$STAGE_BASE"; mkdir -p "$STAGE_BASE" || fail 69 modules-stage-create
  tar -tJf "$DST/modules.tar.xz" >/run/r36os-k1-modules-list.$$ 2>/dev/null || { rm -rf "$STAGE_BASE"; fail 70 modules-list; }
  if grep -Eq '(^/|(^|/)\.\.(/|$))' /run/r36os-k1-modules-list.$$; then rm -rf "$STAGE_BASE" /run/r36os-k1-modules-list.$$; fail 71 modules-path; fi
  # modules_install normally emits top-level build/source symlinks. Permit
  # only those two inert build-time links in the authenticated archive; reject
  # every hardlink, unexpected symlink, unsafe path, or nested member below
  # either link. Both allowed symlinks are removed before runtime validation.
  if tar -tvJf "$DST/modules.tar.xz" 2>/dev/null | awk -v root="$MODROOTNAME" '
    {
      typ=substr($1,1,1)
      if (typ=="h") { bad=1; next }
      if (typ=="l") {
        n=split($0,a," -> "); left=a[1]
        gsub(/^ +| +$/,"",left)
        n=split(left,f,/ +/); p=f[n]
        sub(/^\.\//,"",p)
        if (p!=root"/build" && p!=root"/source") bad=1
      }
    }
    END{exit bad?0:1}
  '; then rm -rf "$STAGE_BASE" /run/r36os-k1-modules-list.$; fail 72 modules-link; fi
  if grep -Eq "^${MODROOTNAME}/(build|source)/" /run/r36os-k1-modules-list.$; then rm -rf "$STAGE_BASE" /run/r36os-k1-modules-list.$; fail 72 modules-link-child; fi
  rm -f /run/r36os-k1-modules-list.$
  progress RUNNING 52 "Extracting K1 modules" "Changed Wi-Fi module payload is staged beside the current tree"
  tar -xJf "$DST/modules.tar.xz" -C "$STAGE_BASE" >/dev/null 2>&1 || { rm -rf "$STAGE_BASE"; fail 73 modules-extract; }
  progress RUNNING 68 "Verifying staged modules" "Removing inert build links, then checking count, bytes, modules.dep and metadata"
  [ -d "$STAGED_MODDST" ] || { rm -rf "$STAGE_BASE"; fail 74 modules-extracted-root; }
  [ ! -L "$STAGED_MODDST" ] || { rm -rf "$STAGE_BASE"; fail 75 modules-extracted-link; }
  for p in "$STAGED_MODDST/build" "$STAGED_MODDST/source"; do
    if [ -L "$p" ]; then rm -f "$p" || { rm -rf "$STAGE_BASE"; fail 75 modules-build-link-remove; }
    elif [ -e "$p" ]; then rm -rf "$STAGE_BASE"; fail 75 modules-build-link-type
    fi
  done
  [ "$(find "$STAGED_MODDST" -type l -print -quit 2>/dev/null)" = "" ] || { rm -rf "$STAGE_BASE"; fail 75 modules-extracted-link; }
  FC="$(find "$STAGED_MODDST" -type f | wc -l | tr -d ' ')"; [ "$FC" = "$MODFILES" ] || { rm -rf "$STAGE_BASE"; fail 76 modules-file-count; }
  BY="$(find "$STAGED_MODDST" -type f -printf '%s\\n' | awk '{s+=$1} END{printf "%.0f",s}')"; [ "$BY" = "$MODBYTES" ] || { rm -rf "$STAGE_BASE"; fail 77 modules-byte-count; }
  [ -s "$STAGED_MODDST/modules.dep" ] || { rm -rf "$STAGE_BASE"; fail 78 modules-dep; }
  {
    echo 'format=R36OS_K1_MODULES_V1'
    echo "candidate_id=$CID"
    echo "kernel_release=$KREL"
    echo "archive_sha256=$(sha "$DST/modules.tar.xz")"
    echo "file_count=$MODFILES"
    echo "uncompressed_bytes=$MODBYTES"
  } > "$STAGED_MODDST/.r36os-k1-candidate" || { rm -rf "$STAGE_BASE"; fail 79 modules-meta; }
  sync
  [ "$(val "$STAGED_MODDST/.r36os-k1-candidate" candidate_id)" = "$CID" ] || { rm -rf "$STAGE_BASE"; fail 86 modules-stage-meta-candidate; }
  [ "$(val "$STAGED_MODDST/.r36os-k1-candidate" kernel_release)" = "$KREL" ] || { rm -rf "$STAGE_BASE"; fail 87 modules-stage-meta-kernel; }
  [ "$(val "$STAGED_MODDST/.r36os-k1-candidate" archive_sha256)" = "$(sha "$DST/modules.tar.xz")" ] || { rm -rf "$STAGE_BASE"; fail 88 modules-stage-meta-archive; }
}
activate_staged_modules(){
  OLD_MODDST=""
  if [ -e "$MODDST" ]; then
    OLD_MODDST="$MODBASE/.previous-$KREL-$$"
    [ ! -e "$OLD_MODDST" ] || fail 89 modules-backup-path-exists
    mv "$MODDST" "$OLD_MODDST" || fail 90 modules-backup-rename
    sync
  fi
  if ! mv "$STAGED_MODDST" "$MODDST"; then
    [ -n "$OLD_MODDST" ] && [ -d "$OLD_MODDST" ] && mv "$OLD_MODDST" "$MODDST" 2>/dev/null || true
    rm -rf "$STAGE_BASE" 2>/dev/null || true
    sync
    fail 91 modules-activate
  fi
  rmdir "$STAGE_BASE" 2>/dev/null || true
  sync
  if ! verify_modules; then
    BROKEN="$MODBASE/.failed-$KREL-$CID-$$"
    mv "$MODDST" "$BROKEN" 2>/dev/null || true
    if [ -n "$OLD_MODDST" ] && [ -d "$OLD_MODDST" ]; then mv "$OLD_MODDST" "$MODDST" 2>/dev/null || true; fi
    sync
    rm -rf "$BROKEN" 2>/dev/null || true
    fail 92 modules-new-readback
  fi
  if [ -n "$OLD_MODDST" ] && [ -d "$OLD_MODDST" ]; then
    rm -rf "$OLD_MODDST" || fail 93 modules-old-cleanup
    sync
  fi
}
if [ -e "$MODDST" ]; then
  progress RUNNING 54 "Checking existing K1 modules" "Verifying exact module archive before deciding reuse or replacement"
  if verify_modules; then
    OLD_MOD_CID="$(val "$MODMETA" candidate_id)"
    if [ "$OLD_MOD_CID" != "$CID" ]; then
      progress RUNNING 70 "Rebinding K1 module metadata" "Module payload unchanged; updating candidate metadata only"
      write_module_meta || fail 83 modules-meta-rebind
      verify_modules || fail 84 modules-rebind-readback
    fi
    progress RUNNING 82 "K1 modules ready" "Existing module tree content verified"
  else
    # R59 deliberately changes modules.tar.xz while keeping the same kernel
    # release. Never delete the known-working old tree first. Stage and verify
    # the complete new archive beside it, then use same-filesystem renames with
    # rollback if activation/readback fails.
    progress RUNNING 56 "K1 module update required" "Existing tree differs from the authenticated R59 module archive"
    stage_new_modules
    activate_staged_modules
    progress RUNNING 82 "K1 modules updated" "New module tree verified; previous tree retired after successful activation"
  fi
else
  stage_new_modules
  activate_staged_modules
  progress RUNNING 82 "K1 modules ready" "New R36STATE module tree verified"
fi
# This is the first boot-affecting operation and happens only after explicit user action.'''

s=pre+new+post
out.write_text(s)
