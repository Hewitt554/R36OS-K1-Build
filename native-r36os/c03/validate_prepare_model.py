#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

def ordered(text: str, needles: list[str]) -> None:
    positions=[]
    for n in needles:
        p=text.find(n)
        if p < 0:
            raise AssertionError(f"missing required transaction anchor: {n}")
        positions.append(p)
    if positions != sorted(positions):
        raise AssertionError(f"transaction order violated: {list(zip(needles,positions))}")

def model(
    *,
    bundle_ok=True,
    host_ok=True,
    k1_pending=False,
    k1_stage_ok=True,
    root_stage_ok=True,
    hook_install_ok=True,
    marker_open_ok=True,
    private_k1_ok=True,
    fat_payload_ok=True,
    request_write_ok=True,
    marker_close_ok=True,
):
    state={
        "root_staged": False,
        "hook_installed": False,
        "request_present": False,
        "marker_window": False,
        "safe_normal_boot": True,
        "stage": "start",
    }
    if not bundle_ok:
        state["stage"]="bundle-fail"; return state
    if not host_ok:
        state["stage"]="host-fail"; return state
    if k1_pending:
        state["stage"]="k1-pending"; return state
    if not k1_stage_ok:
        state["stage"]="k1-stage-fail"; return state
    if not root_stage_ok:
        state["stage"]="root-stage-fail"; return state
    state["root_staged"]=True
    if not hook_install_ok:
        state["stage"]="hook-install-fail"; return state
    state["hook_installed"]=True
    # Hook alone is inert; normal boot remains safe until request exists.
    if not marker_open_ok:
        state["stage"]="marker-open-fail"; return state
    state["marker_window"]=True
    if not private_k1_ok:
        state["marker_window"]=False
        state["stage"]="private-k1-fail"; return state
    if not fat_payload_ok:
        state["marker_window"]=False
        state["stage"]="fat-payload-fail"; return state
    if not request_write_ok:
        state["marker_window"]=False
        state["stage"]="request-write-fail"; return state

    state["request_present"]=True
    state["safe_normal_boot"]=False
    if not marker_close_ok:
        # Production script deletes request and aborts the private write window.
        state["request_present"]=False
        state["marker_window"]=False
        state["safe_normal_boot"]=True
        state["stage"]="marker-close-fail-cleaned"
        return state

    state["marker_window"]=False
    state["stage"]="armed-once"
    return state

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("prepare",type=Path)
    ns=ap.parse_args()
    s=ns.prepare.read_text()

    # Top-level arming transaction. Restrict the ordering check to the
    # arm case body so function definitions earlier in the file cannot be
    # mistaken for calls.
    case_a=s.index("  stage-only|arm-once)")
    case_b=s.index("    ;;",case_a)
    arm_case=s[case_a:case_b]
    ordered(arm_case,[
        "verify_bundle || fail 110 bundle-verification",
        "verify_host || fail 111 host-verification",
        "verify_no_k1_pending || fail 112 k1-one-shot-pending",
        '"$K1PREP" stage-only',
        "stage_root",
        "stage_fat_and_arm",
    ])

    a=s.index("stage_fat_and_arm(){")
    b=s.index("\ndisarm(){",a)
    arm=s[a:b]
    ordered(arm,[
        '"$HOOK_INSTALL"',
        '"$MAINT" marker-open',
        "verify_private_k1",
        'cp -f "$PKGROOT/uInitrd"',
        "# The request is the FINAL boot-affecting write.",
        'rm -f "$PRIVATE/R36N3.CNS"',
        'K1REQ="$PRIVATE/R36OS-KernelNext/boot-next.',
        '>"$REQ.tmp"',
        'mv -f "$REQ.tmp" "$REQ"',
        '"$MAINT" marker-close-unmounted',
    ])

    # Root activation uses sibling staging and rollback.
    assert '.rootfs.stage-' in s
    assert '.rootfs.previous-' in s
    assert 'mv "$ROOTDST" "$OLD"' in s
    assert 'mv "$TMP" "$ROOTDST"' in s
    assert 'mv "$OLD" "$ROOTDST"' in s
    assert 'rootfs-files.sha256' in s

    # A failed private window is always aborted back to RO.
    fail_a=s.index("fail(){")
    fail_b=s.index("\nfinish_pass(){",fail_a)
    fail_block=s[fail_a:fail_b]
    assert 'if [ "$MARKER_OPEN" = 1 ]' in fail_block
    assert '"$MAINT" marker-abort-ro' in fail_block

    # Marker-close failure explicitly removes an already-created request.
    close_pos=arm.index('if ! "$MAINT" marker-close-unmounted')
    cleanup=arm[close_pos:]
    assert 'rm -f "$REQ" "$PRIVATE/R36N3.CNS"' in cleanup
    assert '"$MAINT" marker-abort-ro' in cleanup

    # The prepare helper itself never formats, repartitions or reboots.
    lowered=s.lower()
    for bad in ("mkfs ", "sfdisk ", "parted ", "poweroff", "shutdown -", "reboot "):
        assert bad not in lowered, bad

    cases=[
        (dict(bundle_ok=False),"bundle-fail",False),
        (dict(host_ok=False),"host-fail",False),
        (dict(k1_pending=True),"k1-pending",False),
        (dict(k1_stage_ok=False),"k1-stage-fail",False),
        (dict(root_stage_ok=False),"root-stage-fail",False),
        (dict(hook_install_ok=False),"hook-install-fail",False),
        (dict(marker_open_ok=False),"marker-open-fail",False),
        (dict(private_k1_ok=False),"private-k1-fail",False),
        (dict(fat_payload_ok=False),"fat-payload-fail",False),
        (dict(request_write_ok=False),"request-write-fail",False),
        (dict(marker_close_ok=False),"marker-close-fail-cleaned",False),
        (dict(),"armed-once",True),
    ]
    for kwargs,stage,armed in cases:
        got=model(**kwargs)
        assert got["stage"]==stage,(kwargs,got)
        assert got["request_present"]==armed,(kwargs,got)
        if not armed:
            assert got["safe_normal_boot"],(kwargs,got)
        assert not got["marker_window"],(kwargs,got)

    print("R36OS_NATIVE_C03_PREPARE_MODEL=PASS cases=12")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
