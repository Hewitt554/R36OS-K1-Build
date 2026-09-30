from pathlib import Path
import sys

if len(sys.argv)!=3:
    raise SystemExit("usage: transform_prepare.py <r55-prepare> <r56-prepare>")

s=Path(sys.argv[1]).read_text()

if s.count("0.5.55.0") != 1:
    raise SystemExit(f"expected one R55 version gate, found {s.count('0.5.55.0')}")
s=s.replace("0.5.55.0","0.5.56.0",1)

anchor='''sha(){ sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
progress RUNNING 2 "K1 Boot Next Once" "Validating packaged candidate"
val(){ awk -F= -v k="$2" '$1==k{print substr($0,index($0,"=")+1);exit}' "$1" 2>/dev/null; }'''

insert='''sha(){ sha256sum "$1" 2>/dev/null | awk '{print $1}'; }

LOCKDIR=/run/r36os-k1-prepare.lock
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "status=PASS code=0 detail=duplicate-request-ignored-in-progress"
  exit 0
fi
cleanup_lock(){ rmdir "$LOCKDIR" 2>/dev/null || true; }
trap cleanup_lock EXIT INT TERM

SLOT_NOW="$("$SLOT" status 2>/dev/null || true)"
if printf '%s\n' "$SLOT_NOW" | grep -Fxq 'armed=yes'; then
  progress PASS 100 "K1 Boot Next Once already armed" "Duplicate R1 press ignored"
  printf 'status=PASS\ncode=0\ndetail=already-armed-duplicate-ignored\n' >"$RESULT" 2>/dev/null || true
  echo "status=PASS code=0 detail=already-armed-duplicate-ignored"
  exit 0
fi

progress RUNNING 2 "K1 Boot Next Once" "Validating packaged candidate"
val(){ awk -F= -v k="$2" '$1==k{print substr($0,index($0,"=")+1);exit}' "$1" 2>/dev/null; }'''

if s.count(anchor)!=1:
    raise SystemExit("single-flight anchor mismatch")
s=s.replace(anchor,insert,1)

Path(sys.argv[2]).write_text(s)
