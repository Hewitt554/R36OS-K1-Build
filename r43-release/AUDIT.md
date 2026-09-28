# R36OS Alpha 5R43 — full pre-validation audit

Date: 2026-09-28

This file is the authoritative R43 audit. Earlier work/r43-fat-repair-runtime-fix-2026-09-28 commits are scratch and are not release authority.

## 1. Physical R42 evidence

The private GitHub diagnostics transport is working. The physical device uploaded the R40/R41 backlog and new R42 bundles.

Verified physical state:
- R36OS Alpha 5R42 is running.
- Legacy kernel 4.4.189 remains active.
- R36UPDATE is /dev/mmcblk0p3, vfat, UUID C49E-0225.
- The systemd 242 generator fix works: status=ARMED, output=/run/systemd/generator.
- The one-time repair made and verified its safety backup, safely unmounted R36UPDATE, then the R40 static fsck.fat aborted.
- Result: status=FAIL, code=57, detail=fat-repair-failed-rc-134.
- A later R42 boot still reports: FAT-fs (mmcblk0p3): Volume was not properly unmounted.
- K1 must remain unarmed until this is cleared.

## 2. Exact private R42 package audit

The private transition package was inspected locally without publishing its credential:
- package SHA-256: cbdfa3e3fc37e2c66b3233d17ee1385e3d9deedf8b093855150ced9c218ddc44
- version: 0.5.42.0
- base_version: 0.5.41.0
- K1 binary change: no
- core manifest SHA-256: c15ab3d6da735f1a9db034a3a2c12b2150afb7a07defd9d888ccbfb63c95c898
- r36os-export-current-logs: ef3330f91db693f8278952b67453fe096e70b48bcbce07d029681ff90894cd40
- r36os-kernel-next-prepare: 0336d0f6d389641ddd4305a4d3f87ea85702fdeb5b750815397369e5160d3815
- r36os-kernel-slot: 8ac6a7ec87d218c468fc1b4330ba61ad786eb6a728a5da7425b06379ce487805

The credential is intentionally outside the core manifest and must never appear in public R43 source or package content.

## 3. R40 checker audit

The exact R40 checker is:
- static AArch64 ELF
- Linux ABI 3.7.0
- SHA-256 fe165b0784dd3c301cdf422691b1e5630bd5fab11bca15b8419906b10900d665

It was built with the current Ubuntu 24.04 AArch64 glibc toolchain and contains newer AArch64 glibc SME runtime code including __libc_arm_za_disable.

That is a compatibility lead, not proof of the physical rc 134. The original R42 diagnostics did not preserve fsck stderr. R43 therefore uses two independent mitigations rather than assuming one cause:
1. rebuild with a pinned older glibc 2.31-era AArch64 toolchain targeted at ARMv8-A/Cortex-A35;
2. remove same-process -V verification and verify in a fresh fsck -n process.

## 4. Repair-path audit and corrections

The complete R43 repair path was reviewed before validation.

Corrections made in the audited rebuild:
- fix incorrect fsck --help return-code capture;
- clear stale LAST-extra.conf and LAST-fsck.log at the start of a new attempt;
- require fsck --help to succeed before making a new backup;
- after backup and safe unmount, require a real-volume fsck -n result of 0 or 1 before any write;
- only then allow fsck -a;
- require a fresh fsck -n result of 0 after repair;
- preserve exact device, UUID and K1 armed-marker guards;
- preserve full latest fsck output for diagnostics;
- keep R36UPDATE read-only on post-unmount repair failure when possible;
- never force/lazy unmount;
- never auto-arm K1.

dosfstools 4.2 documents exit 0 as no recoverable errors, exit 1 as recoverable errors/internal inconsistency, and exit 2 as usage error. R43 therefore accepts 0 or 1 for the read-only preflight and repair, but requires 0 for the independent final verification.

## 5. First-boot wiring audit

The R41 generator wiring is retained because the physical R42 device proved it works on systemd 242.

R43:
- installs the generic generator in both /etc/systemd/system-generators and /lib/systemd/system-generators;
- re-arms a release-bound 0.5.43.0 one-shot marker;
- clears a stale generic .failed marker only when a new R43 marker exists;
- queues a redacted diagnostic on PASS, FAIL or clean SKIP;
- does not start an unreliable background uploader from the exiting oneshot service;
- relies on the normal session/Diagnostics exporter to drain queued bundles;
- automatically reboots only after PASS_REBOOT_REQUIRED.

## 6. Diagnostics audit

R42 proved remote uploads work.

R43:
- keeps the exact R42 export wrapper;
- adds full LAST-fsck.log, live repair status, kernel-slot status and GitHub diagnostics status to the generic snapshot;
- removes stale version-labelled rNN-game-os-snapshot.conf files before capture so old R40 evidence is not bundled beside current evidence;
- keeps the 1.5 MiB snapshot bound and the immutable uploader's 8 MiB redacted-bundle bound.

## 7. Builder/source-authority audit

R43 is public and contains no credential.

The builder starts from the exact public R41 package, then reconstructs the exact non-secret R42 state and requires the complete reconstructed R42 core-manifest SHA-256 to match c15ab3d6da735f1a9db034a3a2c12b2150afb7a07defd9d888ccbfb63c95c898 before advancing release-bound guards to 0.5.43.0.

This removes multiple source authorities while preserving the private R42 credential only on the physical device.

## 8. Validation-workflow audit

Before another release run, validation must:
- run static source/secret checks first;
- verify the exact R41 package and exact reconstructed R42 non-secret baseline before building R43;
- build the checker twice from pinned dosfstools 4.2 using the pinned Debian Bullseye snapshot and pinned Debian 11 container digest;
- explicitly install libc6-dev-arm64-cross so static linking is real;
- require static AArch64 ELF, no NEEDED entries, Linux ABI 3.7.0, no newer SME runtime string;
- execute the checker with QEMU Cortex-A35 CPU emulation;
- exercise --help, -n, -a and final -n on a FAT image;
- prove a synthetic rc 134 help failure stops before backup/unmount/write;
- prove a synthetic rc 134 read-only failure stops before repair write;
- prove normal loopback repair PASS;
- prove an armed K1 marker still blocks repair;
- build R43 twice identically;
- audit the final package for no K1 binary, active boot/module payload or credential.

No new validation run should be started until this entire audited source set is committed together.
