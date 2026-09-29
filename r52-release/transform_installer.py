from pathlib import Path
import re,sys
if len(sys.argv)!=4: raise SystemExit("usage: transform_installer.py <r51-installer> <r51-meta> <r52-installer>")
s=Path(sys.argv[1]).read_text()
m=dict(line.split('=',1) for line in Path(sys.argv[2]).read_text().splitlines() if '=' in line)
prev=m.get('hooked_boot_sha256','')
if not re.fullmatch(r'[0-9a-f]{64}',prev): raise SystemExit('current hook sha missing')
n=re.sub(r"PREV_HOOK_SHA='[0-9a-f]{64}'",f"PREV_HOOK_SHA='{prev}'",s,count=1)
if n==s: raise SystemExit('PREV_HOOK_SHA anchor missing')
Path(sys.argv[3]).write_text(n)
