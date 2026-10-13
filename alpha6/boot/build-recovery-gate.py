#!/usr/bin/env python3
"""Generate a separate, UNTESTED recovery-boot candidate from the exact R3 boot.ini."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path

R3_SHA = "b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e"
R3_SIZE = 5108
ANCHOR = b'setenv bootargs "root=UUID='
HOOK = """# R36OS-CP08-RECOVERY-GATE-BEGIN (UNTESTED - NEVER INSTALLED)
if load mmc 1:1 0x02000000 R36OS/RECOVERY.ON
then
  echo R36OS_CP08_RESCUE_REQUESTED
  if load mmc 1:1 ${initrd_loadaddr} R36OS/rescue.uInitrd
  then
    if load mmc 1:1 ${loadaddr} Image
    then
      if load mmc 1:1 ${dtb_loadaddr} "${PanelPathSlash}rk3326-r35s-linux.dtb"
      then
        setenv bootargs "console=/dev/ttyFIQ0 consoleblank=0 fbcon=rotate:0 rdinit=/init r36os.rescue=1"
        if env exists PanelNum
        then
          setenv bootargs "${bootargs} panel=${PanelNum}"
        else
          setenv bootargs "${bootargs} panel=unset"
        fi
        booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}
      fi
    fi
  fi
  echo R36OS_CP08_RESCUE_UNAVAILABLE_FALLING_THROUGH_TO_LEGACY
fi
# R36OS-CP08-RECOVERY-GATE-END
""".encode("ascii")

class UnsafeSource(ValueError):
    pass

def candidate(data: bytes, sha: str = R3_SHA, size: int = R3_SIZE) -> bytes:
    if len(data) != size:
        raise UnsafeSource("source length mismatch")
    if hashlib.sha256(data).hexdigest() != sha:
        raise UnsafeSource("source checksum mismatch")
    if b"R36OS-CP08-RECOVERY-GATE-BEGIN" in data:
        raise UnsafeSource("already modified")
    if data.count(ANCHOR) != 1 or data.count(b"booti ") != 1:
        raise UnsafeSource("unexpected boot structure")
    if b"e139ce78-9841-40fe-8823-96a304a09859" not in data:
        raise UnsafeSource("legacy UUID missing")
    if b"PanelPathSlash" not in data or b"load mmc 1:1" not in data:
        raise UnsafeSource("panel/bootloader contract missing")
    result = data.replace(ANCHOR, HOOK + ANCHOR, 1)
    if result.replace(HOOK, b"", 1) != data:
        raise UnsafeSource("legacy original not preserved byte-for-byte")
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("original", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    original = args.original.resolve(strict=True)
    output = args.output.resolve()
    if original == output or output.name.lower() == "boot.ini":
        raise SystemExit("Refusing to write live boot.ini")
    modified = candidate(original.read_bytes())
    with output.open("xb") as f:
        f.write(modified)
    print("Created offline CP08 candidate:", output)
    print("NOT boot-tested. NEVER install on current BOOT partition.")
if __name__ == "__main__":
    main()
