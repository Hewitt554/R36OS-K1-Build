#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import re

FORBIDDEN_PATH_PARTS = [
    "/opt/system/Tools/PortMaster",
    "/opt/tools/PortMaster",
    "/roms/ports/PortMaster",
]
FORBIDDEN_NAMES = [
    "weston_pkg.squashfs",
    "westonwrap.sh",
    "gptokeyb",
    "libMali.so",
    "libcrusty",
]
FORBIDDEN_TEXT = [
    "CFW_NAME=ArkOS AeUX",
    "Bifrost-r13p0",
    "Bifrost r13p0",
    "crusty_glx_gl4es",
]
FORBIDDEN_PACKAGES = [
    re.compile(r"^(weston|xwayland|wine|wine64|wine32|steam|emulationstation|box64)$", re.I),
    re.compile(r"^lib.*mali", re.I),
]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("--packages",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    ns=ap.parse_args()
    root=ns.root.resolve()
    failures=[]

    for p in root.rglob("*"):
        rel="/"+str(p.relative_to(root))
        if any(x in rel for x in FORBIDDEN_PATH_PARTS):
            failures.append(f"FORBIDDEN_PATH {rel}")
        if any(x.lower() in p.name.lower() for x in FORBIDDEN_NAMES):
            failures.append(f"FORBIDDEN_NAME {rel}")
        if p.is_file() and p.stat().st_size <= 8*1024*1024:
            try:
                data=p.read_bytes()
            except OSError:
                continue
            text=data.decode("utf-8","ignore")
            for marker in FORBIDDEN_TEXT:
                if marker.lower() in text.lower():
                    failures.append(f"FORBIDDEN_TEXT {marker!r} {rel}")

    for line in ns.packages.read_text().splitlines():
        if not line.strip():
            continue
        pkg=line.split("\t",1)[0]
        for rx in FORBIDDEN_PACKAGES:
            if rx.search(pkg):
                failures.append(f"FORBIDDEN_PACKAGE {pkg}")

    ns.report.parent.mkdir(parents=True,exist_ok=True)
    if failures:
        ns.report.write_text("R36OS_NATIVE_C02_FORBIDDEN_SCAN=FAIL\n"+"\n".join(sorted(set(failures)))+"\n")
        print(ns.report.read_text(),end="")
        return 1
    ns.report.write_text("R36OS_NATIVE_C02_FORBIDDEN_SCAN=PASS\n")
    print("R36OS_NATIVE_C02_FORBIDDEN_SCAN=PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
