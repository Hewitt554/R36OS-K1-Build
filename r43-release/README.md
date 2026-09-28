# R36OS Alpha 5R43 — audited FAT repair runtime fix

R43 is a focused follow-up to the physical R42 failure. R42 proved that first-boot activation and private GitHub diagnostics now work, but the R40 static fsck.fat aborted with rc 134 on the real RK3326/Linux 4.4 device.

The audited R43 design deliberately changes no K1 Image, uInitrd, DTB, modules or candidate identity.

R43:
- reconstructs and hash-verifies the exact non-secret R42 baseline before building;
- replaces the R40 checker with a pinned older AArch64 glibc 2.31-era static build targeted at Cortex-A35;
- requires fsck --help before backup;
- requires a read-only scan of the real R36UPDATE volume before any filesystem write;
- repairs with fsck -a only after that preflight;
- verifies in a new fsck -n process instead of using the R40 same-process -V path;
- keeps complete fsck output in diagnostics;
- removes stale version-labelled snapshots from remote bundles;
- re-arms exactly one repair attempt;
- preserves the device-local R42 GitHub credential without shipping it in the public R43 update.

Boot Next Once remains blocked until a post-R43 physical diagnostic proves the repair passed and a clean reboot has no mmcblk0p3 dirty-volume warning.
