from pathlib import Path
import sys
if len(sys.argv)!=3:
    raise SystemExit("usage: transform_identity.py <r56-script> <r57-script>")
s=Path(sys.argv[1]).read_text()
for a,b in [
    ('0.5.56.0','0.5.57.0'),
    ('Alpha 5R56','Alpha 5R57'),
    ('r56-runtime-lock','r57-runtime-lock'),
]:
    s=s.replace(a,b)
Path(sys.argv[2]).write_text(s)
