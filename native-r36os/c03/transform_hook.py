#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, re

EXPECTED_HOOK_SHA = "e389b843ca85cbed59e9227247b2735356f5f551351e8e274e2731fbb15e3c9c"
K1_CID = "9d7bd2334f315d98b482f850"
STATE_UUID = "a25488c6-742d-4555-82d1-e28ffc848af3"
KREL = "6.12.94-r36os-k1"
ANCHOR = "# R36OS-K1-BOOT-ONCE-HOOK\n"

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("native_id")
    ap.add_argument("rootfs_sha")
    ap.add_argument("output", type=Path)
    ap.add_argument("metadata", type=Path)
    a = ap.parse_args()

    if not re.fullmatch(r"[0-9a-f]{24}", a.native_id):
        raise SystemExit("invalid native candidate")
    if not re.fullmatch(r"[0-9a-f]{64}", a.rootfs_sha):
        raise SystemExit("invalid rootfs sha")
    if sha(a.input) != EXPECTED_HOOK_SHA:
        raise SystemExit("current hook sha mismatch")

    s = a.input.read_text()
    if s.count(ANCHOR) != 1:
        raise SystemExit("K1 hook anchor count mismatch")
    if "R36OS-NATIVE-C03-BOOT-ONCE-HOOK" in s:
        raise SystemExit("native hook already present")

    block = r'''# R36OS-NATIVE-C03-BOOT-ONCE-HOOK
# native_candidate=__NATIVE_ID__
# rootfs_sha256=__ROOTFS_SHA__
setenv r36os_native_probe "hook_seen"
if load mmc 1:3 ${loadaddr} "R36OS-NativeNext/C03/boot-native.__NATIVE_ID__.once"
then
    setenv r36os_native_probe "request_visible"
    setenv r36os_native_req_size ${filesize}
    if load mmc 1:3 ${loadaddr} "R36N3.CNS"
    then
        setenv r36os_native_probe "already_consumed"
        echo "[SAFE] Native C03 attempt already consumed"
        echo "[SAFE] Continuing normal boot"
    else
        if fatwrite mmc 1:3 ${loadaddr} "R36N3.CNS" ${r36os_native_req_size}
        then
            setenv r36os_native_probe "consumed_written"
            if load mmc 1:3 ${loadaddr} "R36N3.CNS"
            then
                setenv r36os_native_probe "consumed_readback"
                if test ${filesize} = ${r36os_native_req_size}
                then
                    setenv r36os_native_probe "guard_verified"
                    echo ""
                    echo "R36OS Native C03 one-shot boot"
                    echo "----------------------------"
                    echo "[1/5] Native one-shot guard verified"
                    if load mmc 1:3 ${loadaddr} "R36OS-KernelNext/K1/Image"
                    then
                        setenv r36os_native_probe "image_loaded"
                        echo "[2/5] Existing K1 Image loaded"
                        if load mmc 1:3 ${initrd_loadaddr} "R36OS-NativeNext/C03/uInitrd"
                        then
                            setenv r36os_native_probe "initrd_loaded"
                            echo "[3/5] Native C03 initramfs loaded"
                            if load mmc 1:3 ${dtb_loadaddr} "R36OS-KernelNext/K1/rk3326-r36s-k1.dtb"
                            then
                                setenv r36os_native_probe "payloads_loaded"
                                echo "[4/5] Existing Panel-4 DTB loaded"
                                setenv r36os_native_saved_bootargs "${bootargs}"
                                setenv bootargs "${bootargs} r36os.kernel_slot=next r36os.kernel_attempt=NATIVE_C03 r36os.kernel_candidate=__K1_CID__ r36os.native_candidate=__NATIVE_ID__ r36os.native_state_uuid=__STATE_UUID__ r36os.native_rootfs_sha=__ROOTFS_SHA__ r36os.native_probe=${r36os_native_probe} console=tty1 loglevel=8 ignore_loglevel earlycon plymouth.enable=0 systemd.show_status=1"
                                echo "[5/5] Starting native Debian userspace on __KREL__"
                                echo "If this line stays on screen, photograph it."
                                booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}
                                echo "[RETURN] Native Linux returned to U-Boot"
                                setenv bootargs "${r36os_native_saved_bootargs}"
                                setenv r36os_native_probe "booti_return"
                            else
                                setenv r36os_native_probe "dtb_load_failed"
                                echo "[FAIL] Native C03 Panel-4 DTB load failed"
                            fi
                        else
                            setenv r36os_native_probe "initrd_load_failed"
                            echo "[FAIL] Native C03 initramfs load failed"
                        fi
                    else
                        setenv r36os_native_probe "image_load_failed"
                        echo "[FAIL] Existing K1 Image load failed"
                    fi
                else
                    setenv r36os_native_probe "consumed_size_mismatch"
                    echo "[FAIL] Native consumed marker size mismatch"
                fi
            else
                setenv r36os_native_probe "consumed_readback_failed"
                echo "[FAIL] Native consumed marker read-back failed"
            fi
        else
            setenv r36os_native_probe "consumed_write_failed"
            echo "[FAIL] Native consumed marker write failed"
        fi
    fi
fi
setenv bootargs "${bootargs} r36os.native_probe=${r36os_native_probe}"
# R36OS-NATIVE-C03-BOOT-ONCE-HOOK-END

'''
    block = (
        block.replace("__NATIVE_ID__", a.native_id)
             .replace("__ROOTFS_SHA__", a.rootfs_sha)
             .replace("__K1_CID__", K1_CID)
             .replace("__STATE_UUID__", STATE_UUID)
             .replace("__KREL__", KREL)
    )
    out = s.replace(ANCHOR, block + ANCHOR)

    if out.count(ANCHOR) != 1:
        raise SystemExit("existing K1 hook marker count changed")
    if out.count("# R36OS-NATIVE-C03-BOOT-ONCE-HOOK\n") != 1:
        raise SystemExit("native hook marker count mismatch")
    if "${loadaddr}" not in out or "${bootargs}" not in out:
        raise SystemExit("literal U-Boot variables were not preserved")

    for needle in [
        f'R36OS-KernelNext/boot-next.{K1_CID}.once',
        'R36K1.CNS',
        'R36OS-KernelNext/K1/uInitrd',
        'load mmc 1:1 ${initrd_loadaddr} uInitrd',
        'rk3326-r35s-linux.dtb',
        f'r36os.native_rootfs_sha={a.rootfs_sha}',
    ]:
        if needle not in out:
            raise SystemExit("existing/required boot path missing: " + needle)

    a.output.write_text(out)
    h = hashlib.sha256(out.encode()).hexdigest()
    a.metadata.write_text(
        "format=R36OS_NATIVE_C03_HOOK_V1\n"
        f"native_candidate={a.native_id}\n"
        f"k1_candidate={K1_CID}\n"
        f"kernel_release={KREL}\n"
        f"state_uuid={STATE_UUID}\n"
        f"rootfs_sha256={a.rootfs_sha}\n"
        f"previous_hook_sha256={EXPECTED_HOOK_SHA}\n"
        f"hooked_boot_sha256={h}\n"
        f"request=R36OS-NativeNext/C03/boot-native.{a.native_id}.once\n"
        "consumed=R36N3.CNS\n"
        "existing_k1_hook_preserved=yes\n"
        "legacy_boot_preserved=yes\n"
    )
    print("C03_HOOK_TRANSFORM=PASS", h)

if __name__ == "__main__":
    main()
