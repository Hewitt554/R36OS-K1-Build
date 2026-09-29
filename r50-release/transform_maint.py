from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_maint.py <r49-maint> <r50-maint>")
s=Path(sys.argv[1]).read_text()
if s.count('0.5.49.0')!=1: raise SystemExit(f'version count {s.count("0.5.49.0")}')
s=s.replace('0.5.49.0','0.5.50.0',1)
old='''  REQ="$LIVE_NEXT/boot-next.$CID.once"
  CONSUMED="$LIVE_NEXT/boot-next.$CID.consumed"
  GREQ="$LIVE_NEXT/boot-next.once"
  GCON="$LIVE_NEXT/boot-next.consumed"
  [ ! -s "$CONSUMED" ] && [ ! -s "$GCON" ] || fail 55 consumed-marker-present'''
new='''  REQ="$LIVE_NEXT/boot-next.$CID.once"
  CONSUMED="$MOUNT/R36K1.CNS"
  OLD_CONSUMED="$LIVE_NEXT/boot-next.$CID.consumed"
  GREQ="$LIVE_NEXT/boot-next.once"
  GCON="$LIVE_NEXT/boot-next.consumed"
  [ ! -s "$CONSUMED" ] && [ ! -s "$OLD_CONSUMED" ] && [ ! -s "$GCON" ] || fail 55 consumed-marker-present'''
if s.count(old)!=1: raise SystemExit('live consumed anchor')
s=s.replace(old,new,1)
old='''  WREQ="$WNEXT/boot-next.$CID.once"
  WCON="$WNEXT/boot-next.$CID.consumed"
  WGREQ="$WNEXT/boot-next.once"
  WGCON="$WNEXT/boot-next.consumed"

  [ ! -s "$WCON" ] && [ ! -s "$WGCON" ] || fail 65 consumed-marker-after-repair
  rm -f "$WREQ" "$WREQ.tmp" "$WGREQ" "$WNEXT/boot-next.once.tmp" 2>>"$LOG" || fail 66 stale-request-clear'''
new='''  WREQ="$WNEXT/boot-next.$CID.once"
  WCON="$PRIVATE/R36K1.CNS"
  WOLD="$WNEXT/boot-next.$CID.consumed"
  WGREQ="$WNEXT/boot-next.once"
  WGCON="$WNEXT/boot-next.consumed"

  [ ! -s "$WCON" ] && [ ! -s "$WGCON" ] || fail 65 consumed-marker-after-repair
  rm -f "$WOLD" "$WREQ" "$WREQ.tmp" "$WGREQ" "$WNEXT/boot-next.once.tmp" 2>>"$LOG" || fail 66 stale-request-clear'''
if s.count(old)!=1: raise SystemExit('private consumed anchor')
s=s.replace(old,new,1)
Path(sys.argv[2]).write_text(s)
