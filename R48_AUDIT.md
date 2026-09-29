# R36OS Alpha 5R48 audit checkpoint

Date: 2026-09-29

## Physical R47 evidence

The device installed Alpha 5R47 and remained on legacy Linux 4.4.189.

The post-R47 boot still showed:
- FAT-fs (mmcblk0p3): Volume was not properly unmounted.
- r36os-firstboot-update-repair.service exited with status 45.

Inspection of the exact validated R47 package proves repair code 45 means:
- k1-one-shot-marker-present

The repair helper deliberately refuses any filesystem write while a K1 boot-once request or consumed marker exists.

The stale marker comes from the earlier R44 K1 attempt. Prior evidence already established:
- armed=yes
- consumed=no
- candidate verification PASS
- hook verification PASS
- Linux stayed 4.4.189
- no evidence K1 kernel entry occurred

Therefore R47's repair ordering was incomplete: it re-armed FAT repair without first clearing the stale armed/unconsumed one-shot request.

## R48 corrective scope

R48 does not alter K1 Image, DTB, uInitrd or modules.

R48:
1. Defers the repair during the transactional activation boot while /r36state/update/pending.conf exists. This prevents FAT repair/full K1 verification from competing with the update health watchdog.
2. On the next ordinary boot, checks the current kernel is exactly legacy 4.4.189.
3. Runs r36os-kernel-slot status.
4. Automatic marker cleanup is permitted only for the exact state armed=yes and consumed=no.
5. candidate_verify_code and hook_verify_code must both be 0 before cleanup.
6. r36os-kernel-slot disarm is hardened so it:
   - performs full candidate verification,
   - returns failure if verification fails,
   - removes only request/consumed/temp markers,
   - never touches K1 payloads,
   - syncs,
   - verifies the candidate-specific markers are actually absent,
   - fails code 66 if readback says marker removal failed.
7. Any consumed=yes or otherwise unexpected state fails closed and does not repair FAT.
8. After verified stale-marker cleanup, the exact published R43 FAT repair helper, checker and self-test fixture run unchanged.
9. Bounded R36OS_R48 markers are written to /dev/kmsg so the existing remote diagnostic bundle can show:
   - FIRSTBOOT_DEFERRED
   - STALE_K1_DISARM_START/PASS/SKIP
   - FAT_REPAIR_START/PASS/FAIL
10. R47 rollback clean-unmount hardening and R46's 120-second update health behavior remain installed.

## Required physical sequence

1. Install R48 from R47 using the normal GitHub updater.
2. R48 activation boot must reach the UI on Linux 4.4.189.
3. Do not use Boot Next Once.
4. Perform one ordinary restart.
5. On that ordinary boot R48 may clear only the stale armed/unconsumed marker and then run FAT repair.
6. A successful repair results in an automatic reboot.
7. Export diagnostics after the resulting boot.
8. Boot Next Once remains forbidden until diagnostics prove:
   - stale marker cleanup PASS or no marker needed,
   - FAT repair PASS,
   - mmcblk0p3 no longer reports the unclean-volume warning,
   - candidate remains intact,
   - legacy Linux 4.4.189 remains available.

## Flashing blue underscore observation

The user reports a flashing blue "_" at the top-left, with varying blink rate.

This is tracked separately as a likely boot/TTY/framebuffer cursor exposure. It is not supported by current logs as the cause of code 45 or the FAT problem. R48 intentionally does not alter boot branding/cursor behavior because filesystem recovery should remain a narrow safety change.

## Release blockers

R48 cannot publish unless CI proves:
- exact published R47 input SHA matches,
- exact published R43 input SHA matches,
- deterministic double-build,
- package hashes verify,
- exact R43 repair helper/checker/fixture preserved byte-for-byte,
- automatic cleanup gate is only armed=yes/consumed=no,
- transaction-pending deferral exists,
- disarm performs full verification and marker-clear readback,
- unexpected marker states fail closed,
- K1 binaries absent,
- active /boot and module-tree payload absent,
- no credential/token payload,
- release identity is coherent at 0.5.48.0.
