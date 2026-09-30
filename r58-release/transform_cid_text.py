from pathlib import Path
import re,sys
if len(sys.argv)!=5:
    raise SystemExit("usage: transform_cid_text.py <src> <oldcid> <newcid> <out>")
src=Path(sys.argv[1]); old=sys.argv[2]; new=sys.argv[3]; out=Path(sys.argv[4])
for v in (old,new):
    if not re.fullmatch(r'[0-9a-f]{24}',v): raise SystemExit('bad cid')
s=src.read_text()
if old not in s: raise SystemExit('old cid not found')
s=s.replace(old,new)
out.write_text(s)
