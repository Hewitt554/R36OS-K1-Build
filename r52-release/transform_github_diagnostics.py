from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_github_diagnostics.py <r39-diag> <r52-diag>")
s=Path(sys.argv[1]).read_text()
anchor='''  cp -f /run/r36os-kernel-slot.result "$tmp/kernel-slot-result.txt" 2>/dev/null || true
  cp -f /run/r36os-github-update.status "$tmp/github-update-status.txt" 2>/dev/null || true
  cp -f /r36state/logs/kernel-next/*.conf "$tmp/" 2>/dev/null || true'''
new='''  cp -f /run/r36os-kernel-slot.result "$tmp/kernel-slot-result.txt" 2>/dev/null || true
  cp -f /run/r36os-k1-attempt.status "$tmp/k1-attempt-status.txt" 2>/dev/null || true
  cp -f /run/r36os-kernel-lab.status "$tmp/kernel-live-status.txt" 2>/dev/null || true
  cp -f /r36state/logs/k1-attempts/latest.conf "$tmp/k1-attempt-latest.txt" 2>/dev/null || true
  if command -v r36os-kernel-slot >/dev/null 2>&1; then
    r36os-kernel-slot status >"$tmp/kernel-slot-live.txt" 2>&1 || true
  fi
  {
    echo 'format=R36OS_K1_ROOT_BREADCRUMBS_V1'
    for f in R36K1.CNS K1CON.OK K1IMG.OK K1INI.OK K1DTB.OK K1BOT.OK K1RET.OK; do
      if [ -s "/r36update/$f" ]; then echo "$f=yes size=$(stat -c %s "/r36update/$f" 2>/dev/null || echo unknown)"; else echo "$f=no"; fi
    done
  } >"$tmp/k1-root-breadcrumbs.txt" 2>/dev/null || true
  cp -f /run/r36os-github-update.status "$tmp/github-update-status.txt" 2>/dev/null || true
  cp -f /r36state/logs/kernel-next/*.conf "$tmp/" 2>/dev/null || true'''
if s.count(anchor)!=1: raise SystemExit('diagnostics capture anchor')
s=s.replace(anchor,new,1)
Path(sys.argv[2]).write_text(s)
