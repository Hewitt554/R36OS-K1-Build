#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

CURRENT_SHA = "e389b843ca85cbed59e9227247b2735356f5f551351e8e274e2731fbb15e3c9c"
LEGACY_SHA = "b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e"
K1_CID = "9d7bd2334f315d98b482f850"
NATIVE_BEGIN = "# R36OS-NATIVE-C03-BOOT-ONCE-HOOK\n"
NATIVE_END = "# R36OS-NATIVE-C03-BOOT-ONCE-HOOK-END\n"
K1_BEGIN = "# R36OS-K1-BOOT-ONCE-HOOK\n"
K1_END = "# R36OS-K1-BOOT-ONCE-HOOK-END\n"

def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def strip_block(text: str, begin: str, end: str) -> str:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise AssertionError("block marker count")
    a = text.index(begin)
    b = text.index(end, a) + len(end)
    while b < len(text) and text[b] == "\n":
        b += 1
    return text[:a] + text[b:]

def model(
    *,
    request: bool,
    consumed: bool,
    write_ok: bool = True,
    readback_ok: bool = True,
    size_ok: bool = True,
    image_ok: bool = True,
    initrd_ok: bool = True,
    dtb_ok: bool = True,
    booti_returns: bool = False,
):
    state = {
        "attempted": False,
        "fallthrough": True,
        "consumed_written": consumed,
        "stage": "no-request",
    }
    if not request:
        return state
    state["stage"] = "request-visible"
    if consumed:
        state["stage"] = "already-consumed"
        return state
    if not write_ok:
        state["stage"] = "consumed-write-failed"
        return state
    state["consumed_written"] = True
    state["stage"] = "consumed-written"
    if not readback_ok:
        state["stage"] = "consumed-readback-failed"
        return state
    if not size_ok:
        state["stage"] = "consumed-size-mismatch"
        return state
    if not image_ok:
        state["stage"] = "image-load-failed"
        return state
    if not initrd_ok:
        state["stage"] = "initrd-load-failed"
        return state
    if not dtb_ok:
        state["stage"] = "dtb-load-failed"
        return state
    state["attempted"] = True
    state["fallthrough"] = booti_returns
    state["stage"] = "booti-return" if booti_returns else "linux-handoff"
    return state

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("current_hook", type=Path)
    ap.add_argument("generated_hook", type=Path)
    ap.add_argument("native_id")
    ap.add_argument("rootfs_sha")
    ns = ap.parse_args()

    current_b = ns.current_hook.read_bytes()
    generated_b = ns.generated_hook.read_bytes()
    assert sha_bytes(current_b) == CURRENT_SHA
    current = current_b.decode()
    generated = generated_b.decode()

    assert strip_block(generated, NATIVE_BEGIN, NATIVE_END).encode() == current_b

    k1a = current.index(K1_BEGIN)
    k1b = current.index(K1_END, k1a) + len(K1_END)
    original_k1 = current[k1a:k1b]
    assert generated.count(original_k1) == 1

    legacy = strip_block(current, K1_BEGIN, K1_END).encode()
    assert sha_bytes(legacy) == LEGACY_SHA

    assert generated.index(NATIVE_BEGIN) < generated.index(K1_BEGIN)
    assert f'boot-native.{ns.native_id}.once' in generated
    assert f'boot-next.{K1_CID}.once' in generated
    assert "R36N3.CNS" in generated
    assert "R36K1.CNS" in generated

    assert f"r36os.native_candidate={ns.native_id}" in generated
    assert f"r36os.native_rootfs_sha={ns.rootfs_sha}" in generated
    assert "r36os.kernel_attempt=NATIVE_C03" in generated
    assert f"r36os.kernel_candidate={K1_CID}" in generated

    block_a = generated.index(NATIVE_BEGIN)
    block_b = generated.index(NATIVE_END, block_a)
    block = generated[block_a:block_b]
    order = [
        'load mmc 1:3 ${loadaddr} "R36OS-NativeNext/C03/boot-native.',
        'fatwrite mmc 1:3 ${loadaddr} "R36N3.CNS"',
        'load mmc 1:3 ${loadaddr} "R36N3.CNS"',
        'if test ${filesize} = ${r36os_native_req_size}',
        'load mmc 1:3 ${loadaddr} "R36OS-KernelNext/K1/Image"',
        'load mmc 1:3 ${initrd_loadaddr} "R36OS-NativeNext/C03/uInitrd"',
        'load mmc 1:3 ${dtb_loadaddr} "R36OS-KernelNext/K1/rk3326-r36s-k1.dtb"',
        'booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}',
    ]
    pos = [block.index(x) for x in order]
    assert pos == sorted(pos)
    assert block.count("fatwrite ") == 1
    assert "saveenv" not in block

    assert 'R36OS-NativeNext/C03/Image' not in block
    assert 'R36OS-NativeNext/C03/rk3326-r36s-k1.dtb' not in block

    cases = [
        (dict(request=False, consumed=False), "no-request", False, False),
        (dict(request=True, consumed=True), "already-consumed", False, True),
        (dict(request=True, consumed=False, write_ok=False), "consumed-write-failed", False, False),
        (dict(request=True, consumed=False, readback_ok=False), "consumed-readback-failed", False, True),
        (dict(request=True, consumed=False, size_ok=False), "consumed-size-mismatch", False, True),
        (dict(request=True, consumed=False, image_ok=False), "image-load-failed", False, True),
        (dict(request=True, consumed=False, initrd_ok=False), "initrd-load-failed", False, True),
        (dict(request=True, consumed=False, dtb_ok=False), "dtb-load-failed", False, True),
        (dict(request=True, consumed=False), "linux-handoff", True, True),
        (dict(request=True, consumed=False, booti_returns=True), "booti-return", True, True),
    ]
    for kwargs, stage, attempted, consumed_written in cases:
        got = model(**kwargs)
        assert got["stage"] == stage, (kwargs, got)
        assert got["attempted"] == attempted, (kwargs, got)
        assert got["consumed_written"] == consumed_written, (kwargs, got)

    for key in ("readback_ok", "size_ok", "image_ok", "initrd_ok", "dtb_ok"):
        first_kwargs = dict(request=True, consumed=False)
        first_kwargs[key] = False
        first = model(**first_kwargs)
        assert first["consumed_written"]
        second = model(request=True, consumed=True)
        assert not second["attempted"] and second["stage"] == "already-consumed"

    print("R36OS_NATIVE_C03_BOOT_MODEL=PASS cases=10")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
