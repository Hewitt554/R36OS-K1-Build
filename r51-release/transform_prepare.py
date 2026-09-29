from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_prepare.py <r50-prepare> <r51-prepare>")
s=Path(sys.argv[1]).read_text()
if s.count('0.5.50.0')!=1: raise SystemExit(f'version count {s.count("0.5.50.0")}')
Path(sys.argv[2]).write_text(s.replace('0.5.50.0','0.5.51.0',1))
