#!/usr/bin/env python3
from pathlib import Path
import re,sys

EXPECTED={
 "format":"R36OS_NATIVE_C03_PHYSICAL_RESULT_V1",
 "status":"PASS",
 "source":"physical-r36s",
 "native_candidate":"8f8eaa3bae6ad4352b4e01ef",
 "rootfs_sha256":"08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4",
 "k1_candidate":"9d7bd2334f315d98b482f850",
 "kernel_release":"6.12.94-r36os-k1",
 "health_status":"PASS",
 "health_detail":"native-systemd-healthy",
 "pid1":"systemd",
}

if len(sys.argv)!=2:
    raise SystemExit("usage: validate_c03_physical_gate.py <C03_PHYSICAL_RESULT.conf>")
p=Path(sys.argv[1])
if not p.is_file():
    raise SystemExit("C04_GATE=FAIL missing-physical-gate")

vals={}
for line in p.read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
        continue
    k,v=line.split("=",1)
    vals[k.strip()]=v.strip()

for k,v in EXPECTED.items():
    if vals.get(k)!=v:
        raise SystemExit(f"C04_GATE=FAIL {k} expected={v!r} got={vals.get(k)!r}")

for k in ("c03_health_sha256","evidence_bundle_sha256"):
    v=vals.get(k,"")
    if not re.fullmatch(r"[0-9a-f]{64}",v):
        raise SystemExit(f"C04_GATE=FAIL invalid-{k}")
    if v=="0"*64:
        raise SystemExit(f"C04_GATE=FAIL placeholder-{k}")

print("C04_GATE=PASS physical C03 native-systemd result accepted")
