from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_identity.py <r55-script> <r56-script>")
s=Path(sys.argv[1]).read_text()
for a,b in [('0.5.55.0','0.5.56.0'),('Alpha 5R55','Alpha 5R56'),('r55-runtime-lock','r56-runtime-lock')]:
    s=s.replace(a,b)
Path(sys.argv[2]).write_text(s)
