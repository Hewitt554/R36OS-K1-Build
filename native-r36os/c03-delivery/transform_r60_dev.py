from pathlib import Path
import hashlib,sys

EXPECTED={
  "r36os-kernel-next-prepare":"12de19215cbe591673e84a71ab21b8225c2cea5dc0a12a40e97aa1ee96506a4e",
  "r36os-kernel-slot":"3a58d020a342874787892a553471bd4fe46998b8230d22df16c594028b63a2c0",
  "r36os-r36update-maint":"4b4de8cb4c3f9f222d07b9449b67f84e0e4b29e410d0a91b15dbeb1b1a6a5b4a",
}

if len(sys.argv)!=3:
    raise SystemExit("usage: transform_r60_dev.py <input> <output>")
src=Path(sys.argv[1]); out=Path(sys.argv[2])
name=src.name
if name not in EXPECTED:
    raise SystemExit(f"unsupported helper: {name}")
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
actual=sha(src)
if actual!=EXPECTED[name]:
    raise SystemExit(f"{name}: R60 input sha mismatch: {actual}")

s=src.read_text()
count=s.count("0.5.60.0")
if count<1:
    raise SystemExit(f"{name}: expected R60 version gate missing")
s=s.replace("0.5.60.0","0.5.60.1")
s=s.replace("Alpha 5R60","Alpha 5R60 C03Dev1")
if "0.5.60.0" in s:
    raise SystemExit(f"{name}: stale R60 version remains")
out.write_text(s)
print(f"C03DEV_HELPER_TRANSFORM=PASS name={name} replacements={count} sha256={sha(out)}")
