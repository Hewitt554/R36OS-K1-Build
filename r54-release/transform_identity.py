from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_identity.py <r52-script> <r54-script>")
s=Path(sys.argv[1]).read_text()
for a,b in [('0.5.52.0','0.5.54.0'),('Alpha 5R52','Alpha 5R54'),('r52-runtime-lock','r54-runtime-lock')]:
    s=s.replace(a,b)
Path(sys.argv[2]).write_text(s)
