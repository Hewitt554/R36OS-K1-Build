# Alpha 5R43 pre-validation audit

Date: 2026-09-28

## Physical evidence from R42

The private diagnostics transport is now working and uploaded the R40/R41 backlog plus R42 bundles.

The first-boot generator is confirmed active on the physical systemd 242 device:
- status=ARMED
- output=/run/systemd/generator

The one-time R36UPDATE repair progressed through prerequisite checking, K1 precheck, backup and unmount, then failed when the bundled R40 static fsck.fat process aborted:
- status=FAIL
- code=57
- detail=fat-repair-failed-rc-134
- shell reported: Aborted "$FSCK" -a -V "$EXPECTED_DEV"
- verified pre-repair backup exists on R36STATE.

The subsequent R42 boot still reports:
FAT-fs (mmcblk0p3): Volume was not properly unmounted. Some data may be corrupt. Please run fsck.

Therefore K1 Boot Next Once remains blocked.

## Checker audit

The R40 checker was built on Ubuntu 24.04 with the current AArch64 GNU libc cross-toolchain. Inspection of that binary shows it is static and has Linux ABI 3.7.0, but it also contains the newer AArch64 glibc SME runtime symbol/message __libc_arm_za_disable.

That is a compatibility lead, not proof that SME handling caused rc 134, because R42 did not preserve the checker stderr itself.

R43 therefore removes both uncertainties:
1. build dosfstools 4.2 with an older AArch64 glibc 2.31-era toolchain that predates the newer SME runtime;
2. preserve the complete latest fsck output in redacted diagnostics if any step fails again.

R43 also removes the redundant fsck.fat -V mode. It performs:
- a read-only fsck.fat -n preflight after safe unmount;
- fsck.fat -a repair;
- a separate fsck.fat -n verification that must return clean.

## R42 baseline reconstruction

The private R42 package is not used in CI and its credential is never uploaded.

R43 reconstructs the exact non-secret R42 core delta from the published R41 package and verifies these known hashes:
- r36os-export-current-logs: ef3330f91db693f8278952b67453fe096e70b48bcbce07d029681ff90894cd40
- r36os-kernel-next-prepare: 0336d0f6d389641ddd4305a4d3f87ea85702fdeb5b750815397369e5160d3815
- r36os-kernel-slot: 8ac6a7ec87d218c468fc1b4330ba61ad786eb6a728a5da7425b06379ce487805

The credential and /r36state secret are not part of the R36OS core manifest and are deliberately absent from R43.

## Release blockers

Validation must prove:
- exact published R41 source package identity;
- exact reconstruction of the three non-secret R42 core changes;
- two deterministic old-runtime fsck.fat builds;
- static AArch64 binary, Linux ABI compatible, and no __libc_arm_za_disable symbol/string;
- qemu execution of --help and a read-only FAT image check;
- new repair helper loopback PASS;
- K1 armed-marker refusal still PASS;
- generator activation PASS;
- deterministic R43 package build;
- no K1 binaries, active boot files, module tree, device credentials, or token-shaped strings in R43;
- full fsck log is included by diagnostic snapshot;
- K1 candidate identity is unchanged.
