from pathlib import Path
import hashlib,sys
if len(sys.argv)!=4:
    raise SystemExit('usage: transform_identity_r59.py <kind> <r58-script> <out>')
kind,srcp,outp=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])
expected={
 'slot':'5467a873d1f0166d93a6a37ce4b14591eab6ed25bb15d44eec275a5faf5ac656',
 'maint':'fb0710f7aaaefb2513d63e12ee39561e7b7201344ee7233839b9c2e948e4d9cf',
}
if kind not in expected: raise SystemExit('bad kind')
if hashlib.sha256(srcp.read_bytes()).hexdigest()!=expected[kind]: raise SystemExit(f'R58 {kind} SHA mismatch')
s=srcp.read_text()
want={'slot':2,'maint':1}[kind]
if s.count('0.5.58.0') != want: raise SystemExit(f'expected {want} R58 version gates in {kind}, found {s.count("0.5.58.0")}')
s=s.replace('0.5.58.0','0.5.59.0')
s=s.replace('Alpha 5R58','Alpha 5R59').replace('r58-runtime-lock','r59-runtime-lock')
outp.write_text(s)
