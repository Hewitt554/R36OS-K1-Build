from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_slot.py <r49-slot> <r50-slot>")
s=Path(sys.argv[1]).read_text()
for a,b,count in [('0.5.49.0','0.5.50.0',2),('Alpha 5R49','Alpha 5R50',1),('r49-runtime-lock','r50-runtime-lock',1)]:
    if s.count(a)!=count: raise SystemExit(f'identity count {a}: {s.count(a)} expected {count}')
    s=s.replace(a,b)
old='''marker_paths(){
  [ -n "${CID:-}" ] || return 1
  REQ="$NEXT/boot-next.$CID.once"
  CONSUMED="$NEXT/boot-next.$CID.consumed"
}'''
new='''marker_paths(){
  [ -n "${CID:-}" ] || return 1
  REQ="$NEXT/boot-next.$CID.once"
  CONSUMED="$UPDATE_MOUNT/R36K1.CNS"
  OLD_CONSUMED="$NEXT/boot-next.$CID.consumed"
}'''
if s.count(old)!=1: raise SystemExit('marker_paths anchor')
s=s.replace(old,new,1)
s=s.replace('rm -f "$CONSUMED" "$REQ.tmp"; sync','rm -f "$CONSUMED" "$OLD_CONSUMED" "$REQ.tmp"; sync',1)
s=s.replace('[ ! -e "$CONSUMED" ] || return 61','[ ! -e "$CONSUMED" ] && [ ! -e "$OLD_CONSUMED" ] || return 61',1)
old='''  rm -f "$REQ" "$CONSUMED" "$REQ.tmp"
  rm -f "$NEXT/boot-next.once" "$NEXT/boot-next.consumed" "$NEXT/boot-next.once.tmp"
  sync
  [ ! -e "$REQ" ] && [ ! -e "$CONSUMED" ] || { echo 'status=FAIL code=66 detail=marker-clear-failed'; return 66; }'''
new='''  rm -f "$REQ" "$CONSUMED" "$OLD_CONSUMED" "$REQ.tmp"
  rm -f "$NEXT/boot-next.once" "$NEXT/boot-next.consumed" "$NEXT/boot-next.once.tmp"
  sync
  [ ! -e "$REQ" ] && [ ! -e "$CONSUMED" ] && [ ! -e "$OLD_CONSUMED" ] || { echo 'status=FAIL code=66 detail=marker-clear-failed'; return 66; }'''
if s.count(old)!=1: raise SystemExit('disarm anchor')
s=s.replace(old,new,1)
old='''    echo "request_path=$REQ"; echo "consumed_path=$CONSUMED"
    echo "armed=$([ -s "$REQ" ]&&echo yes||echo no)"; echo "consumed=$([ -s "$CONSUMED" ]&&echo yes||echo no)"'''
new='''    echo "request_path=$REQ"; echo "consumed_path=$CONSUMED"; echo "legacy_consumed_path=$OLD_CONSUMED"
    echo "armed=$([ -s "$REQ" ]&&echo yes||echo no)"; echo "consumed=$([ -s "$CONSUMED" ]&&echo yes||echo no)"'''
if s.count(old)!=1: raise SystemExit('status anchor')
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
