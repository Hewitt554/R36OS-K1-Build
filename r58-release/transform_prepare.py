from pathlib import Path
import sys

if len(sys.argv)!=3:
    raise SystemExit("usage: transform_prepare.py <r57-prepare> <r58-prepare>")

s=Path(sys.argv[1]).read_text()

if s.count("0.5.57.0") != 1:
    raise SystemExit(f"expected one R57 version gate, found {s.count('0.5.57.0')}")
s=s.replace("0.5.57.0","0.5.58.0",1)

old='''if [ -e "$MODDST" ]; then
  progress RUNNING 54 "Checking existing K1 modules" "Verifying kernel release and exact module archive contents"
  verify_modules || fail 67 existing-modules-invalid
  OLD_MOD_CID="$(val "$MODMETA" candidate_id)"
  if [ "$OLD_MOD_CID" != "$CID" ]; then
    progress RUNNING 70 "Rebinding K1 module metadata" "Module payload unchanged; updating candidate metadata only"
    write_module_meta || fail 83 modules-meta-rebind
    verify_modules || fail 84 modules-rebind-readback
  fi
  progress RUNNING 82 "K1 modules ready" "Existing module tree content verified"
else
  progress RUNNING 38 "Checking R36STATE space" "Reserving module tree plus 256 MiB safety headroom"
  STATE_AVAIL_KB="$(df -Pk "$STATE_MOUNT" 2>/dev/null | awk 'NR>1{v=$4} END{print v}')"; echo "$STATE_AVAIL_KB" | grep -Eq '^[0-9]+$' || fail 82 r36state-space-measure
  MODULE_NEED_KB=$(((MODBYTES + 1023) / 1024 + 262144)); [ "$STATE_AVAIL_KB" -ge "$MODULE_NEED_KB" ] || fail 82 r36state-space
  progress RUNNING 42 "Preparing K1 modules" "Validating module archive before extraction"
  mkdir -p "$MODBASE" || fail 68 modules-root-create
  TMPM="$MODBASE/.stage-$CID-$$"; rm -rf "$TMPM"; mkdir -p "$TMPM" || fail 69 modules-stage-create
  # Authenticated archive is already covered by K1 MANIFEST; reject unsafe paths/links before extraction.
  tar -tJf "$DST/modules.tar.xz" >/run/r36os-k1-modules-list.$$ 2>/dev/null || { rm -rf "$TMPM"; fail 70 modules-list; }
  if grep -Eq '(^/|(^|/)\.\.(/|$))' /run/r36os-k1-modules-list.$$; then rm -rf "$TMPM" /run/r36os-k1-modules-list.$$; fail 71 modules-path; fi
  if tar -tvJf "$DST/modules.tar.xz" 2>/dev/null | awk 'substr($1,1,1)=="l" || substr($1,1,1)=="h" {bad=1} END{exit bad?0:1}'; then rm -rf "$TMPM" /run/r36os-k1-modules-list.$$; fail 72 modules-link; fi
  rm -f /run/r36os-k1-modules-list.$$
  progress RUNNING 52 "Extracting K1 modules" "First preparation may take several minutes"
  tar -xJf "$DST/modules.tar.xz" -C "$TMPM" >/dev/null 2>&1 || { rm -rf "$TMPM"; fail 73 modules-extract; }
  progress RUNNING 72 "Verifying extracted modules" "Checking file count, size and modules.dep"
  [ -d "$TMPM/$MODROOTNAME" ] || { rm -rf "$TMPM"; fail 74 modules-extracted-root; }
  [ "$(find "$TMPM/$MODROOTNAME" -type l -print -quit 2>/dev/null)" = "" ] || { rm -rf "$TMPM"; fail 75 modules-extracted-link; }
  FC="$(find "$TMPM/$MODROOTNAME" -type f | wc -l | tr -d ' ')"; [ "$FC" = "$MODFILES" ] || { rm -rf "$TMPM"; fail 76 modules-file-count; }
  BY="$(find "$TMPM/$MODROOTNAME" -type f -printf '%s\n' | awk '{s+=$1} END{printf "%.0f",s}')"; [ "$BY" = "$MODBYTES" ] || { rm -rf "$TMPM"; fail 77 modules-byte-count; }
  [ -s "$TMPM/$MODROOTNAME/modules.dep" ] || { rm -rf "$TMPM"; fail 78 modules-dep; }
  {
    echo 'format=R36OS_K1_MODULES_V1'
    echo "candidate_id=$CID"
    echo "kernel_release=$KREL"
    echo "archive_sha256=$(sha "$DST/modules.tar.xz")"
    echo "file_count=$MODFILES"
    echo "uncompressed_bytes=$MODBYTES"
  } > "$TMPM/$MODROOTNAME/.r36os-k1-candidate" || { rm -rf "$TMPM"; fail 79 modules-meta; }
  sync
  mv "$TMPM/$MODROOTNAME" "$MODDST" || { rm -rf "$TMPM"; fail 80 modules-activate; }
  rmdir "$TMPM" 2>/dev/null || true
  sync
  verify_modules || fail 81 modules-readback
  [ "$(val "$MODMETA" candidate_id)" = "$CID" ] || fail 85 modules-meta-candidate-readback
  progress RUNNING 82 "K1 modules ready" "R36STATE module tree verified"
fi'''

new='''MODULE_REPLACE=0
if [ -e "$MODDST" ]; then
  progress RUNNING 54 "Checking existing K1 modules" "Verifying kernel release and exact module archive contents"
  if verify_modules; then
    OLD_MOD_CID="$(val "$MODMETA" candidate_id)"
    if [ "$OLD_MOD_CID" != "$CID" ]; then
      progress RUNNING 70 "Rebinding K1 module metadata" "Module payload unchanged; updating candidate metadata only"
      write_module_meta || fail 83 modules-meta-rebind
      verify_modules || fail 84 modules-rebind-readback
    fi
    progress RUNNING 82 "K1 modules ready" "Existing module tree content verified"
  else
    MODULE_REPLACE=1
    progress RUNNING 38 "K1 module payload changed" "Staging replacement beside current verified tree"
  fi
fi

if [ ! -e "$MODDST" ] || [ "$MODULE_REPLACE" = 1 ]; then
  progress RUNNING 40 "Checking R36STATE space" "Reserving replacement module tree plus 256 MiB safety headroom"
  STATE_AVAIL_KB="$(df -Pk "$STATE_MOUNT" 2>/dev/null | awk 'NR>1{v=$4} END{print v}')"; echo "$STATE_AVAIL_KB" | grep -Eq '^[0-9]+$' || fail 82 r36state-space-measure
  MODULE_NEED_KB=$(((MODBYTES + 1023) / 1024 + 262144)); [ "$STATE_AVAIL_KB" -ge "$MODULE_NEED_KB" ] || fail 82 r36state-space
  progress RUNNING 44 "Preparing K1 modules" "Validating module archive before extraction"
  mkdir -p "$MODBASE" || fail 68 modules-root-create
  TMPM="$MODBASE/.stage-$CID-$$"; rm -rf "$TMPM"; mkdir -p "$TMPM" || fail 69 modules-stage-create
  tar -tJf "$DST/modules.tar.xz" >/run/r36os-k1-modules-list.$$ 2>/dev/null || { rm -rf "$TMPM"; fail 70 modules-list; }
  if grep -Eq '(^/|(^|/)\.\.(/|$))' /run/r36os-k1-modules-list.$$; then rm -rf "$TMPM" /run/r36os-k1-modules-list.$$; fail 71 modules-path; fi
  if tar -tvJf "$DST/modules.tar.xz" 2>/dev/null | awk 'substr($1,1,1)=="l" || substr($1,1,1)=="h" {bad=1} END{exit bad?0:1}'; then rm -rf "$TMPM" /run/r36os-k1-modules-list.$$; fail 72 modules-link; fi
  rm -f /run/r36os-k1-modules-list.$$
  progress RUNNING 54 "Extracting K1 modules" "Replacement is staged without touching the current tree"
  tar -xJf "$DST/modules.tar.xz" -C "$TMPM" >/dev/null 2>&1 || { rm -rf "$TMPM"; fail 73 modules-extract; }
  progress RUNNING 70 "Verifying staged K1 modules" "Checking file count, size and modules.dep before activation"
  [ -d "$TMPM/$MODROOTNAME" ] || { rm -rf "$TMPM"; fail 74 modules-extracted-root; }
  [ "$(find "$TMPM/$MODROOTNAME" -type l -print -quit 2>/dev/null)" = "" ] || { rm -rf "$TMPM"; fail 75 modules-extracted-link; }
  FC="$(find "$TMPM/$MODROOTNAME" -type f | wc -l | tr -d ' ')"; [ "$FC" = "$MODFILES" ] || { rm -rf "$TMPM"; fail 76 modules-file-count; }
  BY="$(find "$TMPM/$MODROOTNAME" -type f -printf '%s\n' | awk '{s+=$1} END{printf "%.0f",s}')"; [ "$BY" = "$MODBYTES" ] || { rm -rf "$TMPM"; fail 77 modules-byte-count; }
  [ -s "$TMPM/$MODROOTNAME/modules.dep" ] || { rm -rf "$TMPM"; fail 78 modules-dep; }
  {
    echo 'format=R36OS_K1_MODULES_V1'
    echo "candidate_id=$CID"
    echo "kernel_release=$KREL"
    echo "archive_sha256=$(sha "$DST/modules.tar.xz")"
    echo "file_count=$MODFILES"
    echo "uncompressed_bytes=$MODBYTES"
  } > "$TMPM/$MODROOTNAME/.r36os-k1-candidate" || { rm -rf "$TMPM"; fail 79 modules-meta; }
  sync

  OLDMOD=""
  if [ "$MODULE_REPLACE" = 1 ]; then
    OLDMOD="$MODBASE/.previous-$KREL-$$"
    [ ! -e "$OLDMOD" ] || { rm -rf "$TMPM"; fail 86 modules-backup-exists; }
    mv "$MODDST" "$OLDMOD" || { rm -rf "$TMPM"; fail 87 modules-backup; }
  fi

  if ! mv "$TMPM/$MODROOTNAME" "$MODDST"; then
    [ -n "$OLDMOD" ] && [ -d "$OLDMOD" ] && mv "$OLDMOD" "$MODDST" 2>/dev/null || true
    rm -rf "$TMPM"
    fail 80 modules-activate
  fi
  rmdir "$TMPM" 2>/dev/null || true
  sync

  if ! verify_modules || [ "$(val "$MODMETA" candidate_id)" != "$CID" ]; then
    rm -rf "$MODDST"
    [ -n "$OLDMOD" ] && [ -d "$OLDMOD" ] && mv "$OLDMOD" "$MODDST" 2>/dev/null || true
    sync
    fail 88 modules-new-readback-rollback
  fi

  if [ -n "$OLDMOD" ] && [ -d "$OLDMOD" ]; then
    rm -rf "$OLDMOD" || fail 89 modules-old-cleanup
    sync
  fi
  progress RUNNING 82 "K1 modules ready" "New module tree verified and activated transactionally"
fi'''

if s.count(old)!=1:
    raise SystemExit(f"module block anchor mismatch: {s.count(old)}")
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
