#!/usr/bin/env python3
from pathlib import Path
import hashlib, io, sys, tarfile

if len(sys.argv) != 3:
    raise SystemExit("usage: reconstruct_r39_helpers.py R38.r36upd OUTDIR")
r38=Path(sys.argv[1])
out=Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

expected_r38="68db42212fc0e13a9bad777daf68f4634bb86f58aa2347a923dde8cd71db30c0"
if hashlib.sha256(r38.read_bytes()).hexdigest()!=expected_r38:
    raise SystemExit("R38 SHA-256 mismatch")

names=["r36os-kernel-slot","r36os-kernel-next-health"]
with tarfile.open(r38,"r:gz") as tf:
    for n in names:
        member=f"payload/root/usr/local/bin/{n}"
        f=tf.extractfile(member)
        if f is None: raise SystemExit(f"missing {member}")
        (out/n).write_bytes(f.read())

p=out/"r36os-kernel-slot"
s=p.read_text()
s=s.replace("# R36OS Alpha 5R38 candidate-specific Kernel Next slot manager.",
            "# R36OS Alpha 5R39 candidate-specific Kernel Next slot manager.")
s=s.replace("= 0.5.38.0 ] || return 19","= 0.5.39.0 ] || return 19")
s=s.replace("detail=r37-runtime-lock","detail=r39-runtime-lock")
p.write_text(s)

p=out/"r36os-kernel-next-health"
s=p.read_text()
s=s.replace("# R36OS Alpha 5R38 K1 health/fallback recorder.",
            "# R36OS Alpha 5R39 K1 health/fallback recorder.")
old='''  echo "legacy_cmdline_sha256=$(sha "$CMDLINE")" >>"$RECORD"
  sync
  clear_markers || { echo 'status=FAIL code=93 detail=fallback-marker-clear'; exit 93; }'''
new='''  echo "legacy_cmdline_sha256=$(sha "$CMDLINE")" >>"$RECORD"
  sync
  if command -v r36os-github-diagnostics >/dev/null 2>&1; then
    R36OS_DIAG_FAILURE_CODE=K1_FALLBACK R36OS_DIAG_FAILURE_DETAIL="pstore_files=$COPIED" r36os-github-diagnostics capture "k1-fallback-$CID" >/dev/null 2>&1 || true
    r36os-github-diagnostics upload-queued >/dev/null 2>&1 &
  fi
  clear_markers || { echo 'status=FAIL code=93 detail=fallback-marker-clear'; exit 93; }'''
if old not in s: raise SystemExit("health patch anchor missing")
p.write_text(s.replace(old,new))

expected={
"r36os-kernel-slot":"5a62ef487c6ee1fcb30e89d3b02119d2dfc440067bb285ecdea835cc94250acc",
"r36os-kernel-next-health":"43d93da3988e739912d6ad82791cefe9218d40dd4ae00761dbcc4487ced1d4d7",
}
for n,sha in expected.items():
    got=hashlib.sha256((out/n).read_bytes()).hexdigest()
    if got!=sha: raise SystemExit(f"{n} SHA mismatch {got}")
print("R39_HELPER_RECONSTRUCTION=PASS")
