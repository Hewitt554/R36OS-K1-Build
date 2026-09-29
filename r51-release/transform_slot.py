from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_slot.py <r50-slot> <r51-slot>")
s=Path(sys.argv[1]).read_text()
for a,b,count in [('0.5.50.0','0.5.51.0',2),('Alpha 5R50','Alpha 5R51',1),('r50-runtime-lock','r51-runtime-lock',1)]:
    if s.count(a)!=count: raise SystemExit(f'identity count {a}: {s.count(a)} expected {count}')
    s=s.replace(a,b)
old='''  rm -f "$CONSUMED" "$OLD_CONSUMED" "$REQ.tmp"; sync
  [ ! -e "$CONSUMED" ] && [ ! -e "$OLD_CONSUMED" ] || return 61'''
new='''  rm -f "$CONSUMED" "$OLD_CONSUMED" "$REQ.tmp"
  rm -f "$UPDATE_MOUNT/K1CON.OK" "$UPDATE_MOUNT/K1IMG.OK" "$UPDATE_MOUNT/K1INI.OK" "$UPDATE_MOUNT/K1DTB.OK" "$UPDATE_MOUNT/K1BOT.OK" "$UPDATE_MOUNT/K1RET.OK"
  sync
  [ ! -e "$CONSUMED" ] && [ ! -e "$OLD_CONSUMED" ] || return 61'''
if s.count(old)!=1: raise SystemExit('arm cleanup anchor')
s=s.replace(old,new,1)
anchor='''status(){
  quick_candidate; V=$?'''
insert='''breadcrumb_status(){
  deepest=none
  for spec in K1CON.OK:guard_verified K1IMG.OK:image_loaded K1INI.OK:initrd_loaded K1DTB.OK:dtb_loaded K1BOT.OK:booti_invoked K1RET.OK:booti_returned; do
    f="${spec%%:*}"; st="${spec#*:}"
    if [ -s "$UPDATE_MOUNT/$f" ]; then
      echo "breadcrumb_$f=yes"
      deepest="$st"
    else
      echo "breadcrumb_$f=no"
    fi
  done
  echo "breadcrumb_deepest=$deepest"
}
status(){
  quick_candidate; V=$?'''
if s.count(anchor)!=1: raise SystemExit('status anchor')
s=s.replace(anchor,insert,1)
old='''  echo "full_payload_verification=required-on-arm-once"
}'''
new='''  echo "full_payload_verification=required-on-arm-once"
  breadcrumb_status
}'''
if s.count(old)!=1: raise SystemExit('status end anchor')
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
