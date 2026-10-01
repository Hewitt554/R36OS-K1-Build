from pathlib import Path
import hashlib, sys

if len(sys.argv) != 3:
    raise SystemExit("usage: transform_identity.py <input> <output>")

src=Path(sys.argv[1])
out=Path(sys.argv[2])
name=src.name

EXPECTED={
    "r36os-kernel-next-prepare": (
        "91debcce0a8cf72498d8b914f2bdaf8aa1768234af916b4da2dbd9119d65379e",
        "12de19215cbe591673e84a71ab21b8225c2cea5dc0a12a40e97aa1ee96506a4e",
    ),
    "r36os-kernel-slot": (
        "651d8c9294641e37c762424a65af2290d13b527c3233f685c669665410cacbf9",
        "3a58d020a342874787892a553471bd4fe46998b8230d22df16c594028b63a2c0",
    ),
    "r36os-r36update-maint": (
        "5ea557733e6ae2632051bb1dad931571d0c70e4ba1a6e67743a7f170887c29ea",
        "4b4de8cb4c3f9f222d07b9449b67f84e0e4b29e410d0a91b15dbeb1b1a6a5b4a",
    ),
}
if name not in EXPECTED:
    raise SystemExit(f"unsupported helper: {name}")

sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
before, after=EXPECTED[name]
actual=sha(src)
if actual != before:
    raise SystemExit(f"{name}: R59 input sha mismatch: {actual}")

s=src.read_text()
if s.count("0.5.59.0") < 1:
    raise SystemExit(f"{name}: missing 0.5.59.0 release gate")
s=s.replace("0.5.59.0","0.5.60.0")
s=s.replace("Alpha 5R59","Alpha 5R60")
if "0.5.59.0" in s:
    raise SystemExit(f"{name}: stale 0.5.59.0 remains")
out.write_text(s)
actual_after=sha(out)
if actual_after != after:
    raise SystemExit(f"{name}: R60 output sha mismatch: {actual_after}")
print(f"R60_IDENTITY_TRANSFORM=PASS name={name} sha256={actual_after}")
