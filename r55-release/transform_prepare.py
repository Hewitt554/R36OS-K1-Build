from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: transform_prepare.py <r54-prepare> <r55-prepare>")

src=Path(sys.argv[1])
out=Path(sys.argv[2])
s=src.read_text()

# R55 installs on the physically recovered/working R54 release.
if s.count("0.5.54.0") != 1:
    raise SystemExit(f"expected one R54 version gate, found {s.count('0.5.54.0')}")
s=s.replace("0.5.54.0","0.5.55.0",1)

old='''verify_modules(){
  [ -d "$MODDST" ] || return 1
  [ ! -L "$MODDST" ] || return 1
  [ -s "$MODDST/modules.dep" ] || return 1
  [ -s "$MODMETA" ] || return 1
  [ "$(val "$MODMETA" candidate_id)" = "$CID" ] || return 1
  [ "$(val "$MODMETA" kernel_release)" = "$KREL" ] || return 1
  [ "$(val "$MODMETA" archive_sha256)" = "$(sha "$DST/modules.tar.xz")" ] || return 1
  [ "$(find "$MODDST" -type l -print -quit 2>/dev/null)" = "" ] || return 1
  FC="$(find "$MODDST" -type f ! -name .r36os-k1-candidate | wc -l | tr -d ' ')"; [ "$FC" = "$MODFILES" ] || return 1
  BY="$(find "$MODDST" -type f ! -name .r36os-k1-candidate -printf '%s\\n' | awk '{s+=$1} END{printf "%.0f",s}')"; [ "$BY" = "$MODBYTES" ] || return 1
  return 0
}
if [ -e "$MODDST" ]; then
  progress RUNNING 54 "Checking existing K1 modules" "Reusing candidate-bound module tree when valid"
  verify_modules || fail 67 existing-modules-invalid
  progress RUNNING 82 "K1 modules ready" "Existing module tree verified"
else'''

new='''verify_modules(){
  [ -d "$MODDST" ] || return 1
  [ ! -L "$MODDST" ] || return 1
  [ -s "$MODDST/modules.dep" ] || return 1
  [ -s "$MODMETA" ] || return 1
  # Module validity is content-bound, not whole-candidate-bound.  A K1
  # candidate ID also changes when only uInitrd/DTB metadata changes.
  [ "$(val "$MODMETA" kernel_release)" = "$KREL" ] || return 1
  [ "$(val "$MODMETA" archive_sha256)" = "$(sha "$DST/modules.tar.xz")" ] || return 1
  [ "$(find "$MODDST" -type l -print -quit 2>/dev/null)" = "" ] || return 1
  FC="$(find "$MODDST" -type f ! -name .r36os-k1-candidate | wc -l | tr -d ' ')"; [ "$FC" = "$MODFILES" ] || return 1
  BY="$(find "$MODDST" -type f ! -name .r36os-k1-candidate -printf '%s\\n' | awk '{s+=$1} END{printf "%.0f",s}')"; [ "$BY" = "$MODBYTES" ] || return 1
  return 0
}
write_module_meta(){
  TMPMETA="$MODMETA.tmp.$$"
  {
    echo 'format=R36OS_K1_MODULES_V1'
    echo "candidate_id=$CID"
    echo "kernel_release=$KREL"
    echo "archive_sha256=$(sha "$DST/modules.tar.xz")"
    echo "file_count=$MODFILES"
    echo "uncompressed_bytes=$MODBYTES"
  } >"$TMPMETA" || { rm -f "$TMPMETA"; return 1; }
  chmod 0644 "$TMPMETA" 2>/dev/null || true
  sync
  mv -f "$TMPMETA" "$MODMETA" || { rm -f "$TMPMETA"; return 1; }
  sync
  [ "$(val "$MODMETA" candidate_id)" = "$CID" ] || return 1
  [ "$(val "$MODMETA" kernel_release)" = "$KREL" ] || return 1
  [ "$(val "$MODMETA" archive_sha256)" = "$(sha "$DST/modules.tar.xz")" ] || return 1
  return 0
}
if [ -e "$MODDST" ]; then
  progress RUNNING 54 "Checking existing K1 modules" "Verifying kernel release and exact module archive contents"
  verify_modules || fail 67 existing-modules-invalid
  OLD_MOD_CID="$(val "$MODMETA" candidate_id)"
  if [ "$OLD_MOD_CID" != "$CID" ]; then
    progress RUNNING 70 "Rebinding K1 module metadata" "Module payload unchanged; updating candidate metadata only"
    write_module_meta || fail 83 modules-meta-rebind
    verify_modules || fail 84 modules-rebind-readback
  fi
  progress RUNNING 82 "K1 modules ready" "Existing module tree content verified"
else'''

if s.count(old) != 1:
    raise SystemExit("module reuse anchor mismatch")
s=s.replace(old,new,1)

# Use the same metadata writer for fresh extraction so both paths share one
# canonical metadata format.
old2='''  {
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
  verify_modules || fail 81 modules-readback'''

new2='''  {
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
  [ "$(val "$MODMETA" candidate_id)" = "$CID" ] || fail 85 modules-meta-candidate-readback'''

if s.count(old2) != 1:
    raise SystemExit("fresh extraction metadata anchor mismatch")
s=s.replace(old2,new2,1)

out.write_text(s)
