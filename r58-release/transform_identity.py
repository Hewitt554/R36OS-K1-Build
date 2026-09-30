from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_identity.py <r57-script> <r58-script>")
s=Path(sys.argv[1]).read_text()
for a,b in [('0.5.57.0','0.5.58.0'),('Alpha 5R57','Alpha 5R58'),('r57-runtime-lock','r58-runtime-lock')]:
    s=s.replace(a,b)
Path(sys.argv[2]).write_text(s)
