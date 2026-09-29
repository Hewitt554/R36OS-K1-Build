from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_identity.py <r51-script> <r52-script>")
s=Path(sys.argv[1]).read_text()
for a,b in [('0.5.51.0','0.5.52.0'),('Alpha 5R51','Alpha 5R52'),('r51-runtime-lock','r52-runtime-lock')]:
    s=s.replace(a,b)
Path(sys.argv[2]).write_text(s)
