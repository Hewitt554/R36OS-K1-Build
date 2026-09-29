# R36OS Alpha 5R47 audit checkpoint

Date: 2026-09-29

## Physical evidence

The Alpha 5R46 physical failure is code 25 with:

- failure_detail=r36update-fat-health-mmcblk0p3
- /dev/mmcblk0p3 is R36UPDATE, UUID C49E-0225, vfat.
- Linux reports: "Volume was not properly unmounted. Some data may be corrupt. Please run fsck."
- The failure occurs before K1 is armed or U-Boot handoff begins.
- Linux remains 4.4.189.

The nine preserved Alpha 5R44 archives show R36UPDATE was clean through the successful R43 repair and subsequent ordinary R44 reboots. The first dirty R36UPDATE boot appears after the failed R45 transactional update/rollback cycle. This separates the current code 25 from the original R43 checker-compatibility problem.

## R47 scope

R47 is a narrow corrective update from exact published Alpha 5R46.

1. Reuse the exact published Alpha 5R43 target-validated AArch64 fsck.fat binary and repair engine.
2. Re-arm one R36UPDATE repair using release-bound marker 0.5.47.0.
3. Preserve the physically proven generator/service repair wiring.
4. Harden r36os-update-rollback so rollback evidence is written first, then R36UPDATE is synced and normally unmounted with bounded retries before the caller reboots.
5. Forced and lazy unmounts are forbidden.
6. Preserve Alpha 5R46's 120-second update-health window and quick non-hashing kernel status.
7. Preserve the R46 K1 hook/probe and all K1 binaries unchanged.
8. Preserve Linux 4.4 as fallback.

## Test sequence after installation

R47 activation itself does not run K1.

After R47 has installed and reached the UI on Linux 4.4.189:

1. Perform one ordinary restart.
2. The existing first-boot repair generator sees the R47 repair marker.
3. R36UPDATE is backed up to R36STATE.
4. The exact R43 checker repairs /dev/mmcblk0p3 while unmounted.
5. A separate read-only fsck verifies the filesystem clean.
6. The K1 candidate manifest and identity are verified again.
7. R36UPDATE is left unmounted.
8. The repair path triggers a clean reboot.
9. Export diagnostics after the resulting boot.
10. Boot Next Once remains forbidden until those diagnostics prove mmcblk0p3 clean.

## Release blockers

R47 cannot be published unless:

- Exact R46 and R43 package SHA-256 values match the published releases.
- R47 builds twice byte-for-byte identically.
- All package payload hashes verify.
- The exact R43 repair helper and fsck binary are retained byte-for-byte.
- r36os-update-rollback contains a normal R36UPDATE unmount path.
- No forced/lazy unmount exists in the rollback helper.
- No K1 Image, DTB, uInitrd or modules are present.
- No active /boot or module-tree payload is present.
- No device credential or token is present.
- Kernel helper release identity is coherent at 0.5.47.0.
