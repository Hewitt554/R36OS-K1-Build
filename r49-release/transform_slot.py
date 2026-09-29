from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: transform_slot.py <r48-slot> <r49-slot>")
s=Path(sys.argv[1]).read_text()
checks=[('0.5.48.0','0.5.49.0',2),('Alpha 5R48','Alpha 5R49',1),('r48-runtime-lock','r49-runtime-lock',1)]
for a,b,count in checks:
    if s.count(a)!=count:
        raise SystemExit(f'unexpected R48 slot identity count for {a}: {s.count(a)} expected {count}')
    s=s.replace(a,b)

anchor='CMD="${1:-status}"\n'
if s.count(anchor)!=1:
    raise SystemExit('slot command anchor mismatch')
s=s.replace(anchor,anchor+'UPDATE_MOUNT="${R36OS_UPDATE_MOUNT:-/r36update}"\n',1)

old='''  verify_hook || { R=$?; echo "status=FAIL code=$R detail=verification"; return "$R"; }
  mkdir -p "$NEXT" || return 60
'''
new='''  verify_hook || { R=$?; echo "status=FAIL code=$R detail=verification"; return "$R"; }
  mountpoint -q "$UPDATE_MOUNT" 2>/dev/null || { echo 'status=FAIL code=67 detail=controlled-write-window-required'; return 67; }
  opts="$(findmnt -n -o OPTIONS "$UPDATE_MOUNT" 2>/dev/null | head -1)"
  case ",$opts," in *,rw,*) ;; *) echo 'status=FAIL code=67 detail=controlled-write-window-required'; return 67;; esac
  mkdir -p "$NEXT" || return 60
'''
if s.count(old)!=1:
    raise SystemExit('slot arm anchor mismatch')
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
