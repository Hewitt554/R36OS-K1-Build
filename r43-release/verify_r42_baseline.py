#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

EXPECTED_EXPORT = "ef3330f91db693f8278952b67453fe096e70b48bcbce07d029681ff90894cd40"
EXPECTED_PREPARE = "0336d0f6d389641ddd4305a4d3f87ea85702fdeb5b750815397369e5160d3815"
EXPECTED_SLOT = "8ac6a7ec87d218c468fc1b4330ba61ad786eb6a728a5da7425b06379ce487805"
EXPECTED_CORE_MANIFEST = "c15ab3d6da735f1a9db034a3a2c12b2150afb7a07defd9d888ccbfb63c95c898"

if len(sys.argv) != 4:
    raise SystemExit("usage: verify_r42_baseline.py EXTRACTED_R41 EXPORT_SOURCE OUTDIR")

base = Path(sys.argv[1])
export_source = Path(sys.argv[2])
out = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

prepare_src = (base / "payload/root/usr/local/bin/r36os-kernel-next-prepare").read_text()
if prepare_src.count("0.5.41.0") != 1:
    raise SystemExit("unexpected R41 prepare release identity")
prepare = prepare_src.replace("0.5.41.0", "0.5.42.0")
(out / "r36os-kernel-next-prepare").write_text(prepare)

slot_src = (base / "payload/root/usr/local/bin/r36os-kernel-slot").read_text()
for needle in ("0.5.41.0", "Alpha 5R41", "r41-runtime-lock"):
    if slot_src.count(needle) != 1:
        raise SystemExit(f"unexpected R41 slot identity: {needle}")
slot = (slot_src.replace("0.5.41.0", "0.5.42.0")
                .replace("Alpha 5R41", "Alpha 5R42")
                .replace("r41-runtime-lock", "r42-runtime-lock"))
(out / "r36os-kernel-slot").write_text(slot)

export_bytes = export_source.read_bytes()
(out / "r36os-export-current-logs").write_bytes(export_bytes)

checks = {
    "r36os-export-current-logs": EXPECTED_EXPORT,
    "r36os-kernel-next-prepare": EXPECTED_PREPARE,
    "r36os-kernel-slot": EXPECTED_SLOT,
}
for name, expected in checks.items():
    actual = sha((out / name).read_bytes())
    if actual != expected:
        raise SystemExit(f"R42 reconstruction hash mismatch for {name}: {actual}")

entries = {}
manifest = base / "payload/root/etc/r36os-core-manifest.sha256"
for line in manifest.read_text().splitlines():
    if not line.strip():
        continue
    digest, path = line.split(None, 1)
    entries[path.strip()] = digest

entries["/usr/local/bin/r36os-export-current-logs"] = EXPECTED_EXPORT
entries["/usr/local/bin/r36os-kernel-next-prepare"] = EXPECTED_PREPARE
entries["/usr/local/bin/r36os-kernel-slot"] = EXPECTED_SLOT

r42_manifest = "".join(f"{entries[path]}  {path}\n" for path in entries)
(out / "r36os-core-manifest.sha256").write_text(r42_manifest)
actual_manifest = sha(r42_manifest.encode())
if actual_manifest != EXPECTED_CORE_MANIFEST:
    raise SystemExit(f"R42 core manifest mismatch: {actual_manifest}")

print("R42_NONSECRET_BASELINE_AUDIT=PASS")
print(f"r42_core_manifest_sha256={actual_manifest}")
