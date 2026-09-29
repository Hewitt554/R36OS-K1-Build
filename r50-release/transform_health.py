from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_health.py <r49-health> <r50-health>")
s=Path(sys.argv[1]).read_text()
s=s.replace('# R36OS Alpha 5R49 K1 health/fallback recorder with isolated R36UPDATE.','# R36OS Alpha 5R50 K1 health/fallback recorder with root-level U-Boot consumed marker.',1)
old='''  REQ="$NEXT/boot-next.$CID.once"; CONSUMED="$NEXT/boot-next.$CID.consumed"
  MANSHA="$(sha "$K1/MANIFEST.sha256")"; [ -n "$MANSHA" ] || return 31'''
new='''  REQ="$NEXT/boot-next.$CID.once"; CONSUMED="${R36OS_UPDATE_MOUNT:-/r36update}/R36K1.CNS"; OLD_CONSUMED="$NEXT/boot-next.$CID.consumed"
  MANSHA="$(sha "$K1/MANIFEST.sha256")"; [ -n "$MANSHA" ] || return 31'''
if s.count(old)!=1: raise SystemExit('health marker anchor')
s=s.replace(old,new,1)
old='''  pnext="$PRIVATE/R36OS-KernelNext"
  preq="$pnext/boot-next.$CID.once"
  pcon="$pnext/boot-next.$CID.consumed"
  rm -f "$preq" "$pcon" "$preq.tmp"
  sync
  ok=0
  [ ! -e "$preq" ] && [ ! -e "$pcon" ] && ok=1'''
new='''  pnext="$PRIVATE/R36OS-KernelNext"
  preq="$pnext/boot-next.$CID.once"
  pcon="$PRIVATE/R36K1.CNS"
  pold="$pnext/boot-next.$CID.consumed"
  rm -f "$preq" "$pcon" "$pold" "$preq.tmp"
  sync
  ok=0
  [ ! -e "$preq" ] && [ ! -e "$pcon" ] && [ ! -e "$pold" ] && ok=1'''
if s.count(old)!=1: raise SystemExit('health clear anchor')
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
