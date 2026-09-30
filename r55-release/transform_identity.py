from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_identity.py <r54-script> <r55-script>")
s=Path(sys.argv[1]).read_text()
for a,b in [('0.5.54.0','0.5.55.0'),('Alpha 5R54','Alpha 5R55'),('r54-runtime-lock','r55-runtime-lock')]:
    s=s.replace(a,b)
Path(sys.argv[2]).write_text(s)
