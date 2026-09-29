from pathlib import Path
import sys
if len(sys.argv)!=3: raise SystemExit("usage: transform_prepare.py <r49-prepare> <r50-prepare>")
s=Path(sys.argv[1]).read_text()
if s.count('0.5.49.0')!=1: raise SystemExit(f'version count {s.count("0.5.49.0")}')
s=s.replace('0.5.49.0','0.5.50.0',1)
Path(sys.argv[2]).write_text(s)
