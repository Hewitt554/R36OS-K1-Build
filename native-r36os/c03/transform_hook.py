#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,re

EXPECTED_HOOK_SHA="e389b843ca85cbed59e9227247b2735356f5f551351e8e274e2731fbb15e3c9c"
K1_CID="9d7bd2334f315d98b482f850"
STATE_UUID="a25488c6-742d-4555-82d1-e28ffc848af3"
KREL="6.12.94-r36os-k1"
ANCHOR="# R36OS-K1-BOOT-ONCE-HOOK"

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path)
    ap.add_argument("native_id")
    ap.add_argument("rootfs_sha")
    ap.add_argument("output",type=Path)
    ap.add_argument("metadata",type=Path)
    a=ap.parse_args()
    if not re.fullmatch(r"[0-9a-f]{24}",a.native_id):
        raise SystemExit("invalid native candidate")
    if not re.fullmatch(r"[0-9a-f]{64}",a.rootfs_sha):
        raise SystemExit("invalid rootfs sha")
    if sha(a.input)!=EXPECTED_HOOK_SHA:
        raise SystemExit("current hook sha mismatch")
    s=a.input.read_text()
    if s.count(ANCHOR)!=1:
        raise SystemExit("K1 hook anchor count mismatch")
    if "R36OS-NATIVE-C03-BOOT-ONCE-HOOK" in s:
        raise SystemExit("native hook already present")

    n=a.native_id
    block=f'''# R36OS-NATIVE-C03-BOOT-ONCE-HOOK
# native_candidate={n}
setenv r36os_native_probe "hook_seen"
setenv r36os_native_attempted "no"
if load mmc 1:3 ${loadaddr} "R36OS-NativeNext/C03/boot-native.{n}.once"
then
    setenv r36os_native_probe "request_visible"
    setenv r36os_native_attempted "yes"
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
                                setenv bootargs "${bootargs} r36os.kernel_slot=next r36os.kernel_attempt=NATIVE_C03 r36os.kernel_candidate={K1_CID} r36os.native_candidate={n} r36os.native_state_uuid={STATE_UUID} r36os.native_probe=${r36os_native_probe} console=tty1 loglevel=8 ignore_loglevel earlycon plymouth.enable=0 systemd.show_status=1"
                                echo "[5/5] Starting native Debian userspace on {KREL}"
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
    out=s.replace(ANCHOR,block+ANCHOR)
    if out.count(ANCHOR)!=1 or out.count("# R36OS-NATIVE-C03-BOOT-ONCE-HOOK\n")!=1:
        raise SystemExit("generated hook marker count mismatch")
    for needle in [
        f'R36OS-KernelNext/boot-next.{K1_CID}.once',
        'R36K1.CNS',
        'R36OS-KernelNext/K1/uInitrd',
        'load mmc 1:1 ${initrd_loadaddr} uInitrd',
        'rk3326-r35s-linux.dtb',
    ]:
        if needle not in out:
            raise SystemExit("existing boot path missing: "+needle)
    a.output.write_text(out)
    h=hashlib.sha256(out.encode()).hexdigest()
    a.metadata.write_text(
        "format=R36OS_NATIVE_C03_HOOK_V1\n"
        f"native_candidate={n}\n"
        f"k1_candidate={K1_CID}\n"
        f"kernel_release={KREL}\n"
        f"state_uuid={STATE_UUID}\n"
        f"rootfs_sha256={a.rootfs_sha}\n"
        f"previous_hook_sha256={EXPECTED_HOOK_SHA}\n"
        f"hooked_boot_sha256={h}\n"
        f"request=R36OS-NativeNext/C03/boot-native.{n}.once\n"
        "consumed=R36N3.CNS\n"
        "existing_k1_hook_preserved=yes\n"
        "legacy_boot_preserved=yes\n"
    )
    print("C03_HOOK_TRANSFORM=PASS",h)

if __name__=="__main__":
    main()
