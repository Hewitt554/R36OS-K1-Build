# R36OS Alpha 5R43 pre-change audit

Date: 2026-09-28

## Physical R42 evidence

The latest physical Alpha 5R42 diagnostics establish the real failure boundary:

- R36UPDATE is exactly `/dev/mmcblk0p3`, vfat, UUID `C49E-0225`.
- The boot still reports `Volume was not properly unmounted` for `mmcblk0p3`.
- The R41 generic systemd generator executed on the handheld and reported `status=ARMED` with output `/run/systemd/generator`.
- The first-boot repair runner executed.
- The pre-repair backup was successfully created at `/r36state/recovery/r36update/R36UPDATE-pre-fsck-20260928-174913.tar`.
- The repair engine reached the real FAT checker and failed with `code=57`, `detail=fat-repair-failed-rc-134`.
- The shell recorded the shipped `fsck.fat` as `Aborted`, meaning SIGABRT/exit 134.
- K1 remains unarmed and the legacy kernel remains the normal boot path.
- Private GitHub diagnostic upload now works and must be preserved.

## Relevant-file audit

### R40 static fsck build

The shipped AArch64 binary was built on Ubuntu 24.04 with the current cross-glibc and `-static`. Configure reported `checking for iconv... yes` and `checking for working iconv... guessing yes`; the compiled binary contains glibc/gconv/iconv runtime machinery.

Critical validation gap: the old R40 loopback repair test did **not** execute the shipped ARM binary. It overrode `R36OS_FSCK_FAT` with the GitHub runner's native `/usr/sbin/fsck.fat`. Therefore CI proved the repair shell logic but did not prove the binary delivered to the R36S could execute.

R43 decision: rebuild dosfstools 4.2 in an Ubuntu 20.04 cross-build environment, statically for AArch64, with `--without-iconv`, and run it in the `C` locale. CI must execute the actual AArch64 binary under qemu-user on FAT images and must also drive the full repair helper through a qemu wrapper.

### R40 repair helper

The device/UUID binding, armed-marker refusal, R36STATE backup, normal unmount, read-only post-check, K1 candidate integrity check and final unmount are sound and are retained.

The `-V` option asks dosfstools to perform an internal second verification pass, while the helper already performs a separate explicit `-n` read-only pass. R43 removes `-V` to reduce duplicated paths and keeps the explicit `-a` then `-n` sequence.

R43 also verifies the packaged checker SHA-256 and runs a harmless startup self-test before any unmount.

### R41 generator/service/first-boot wiring

The physical device proved the generic generator path is working. Do not redesign it. R43 retains both generator install locations and the same service ordering, updates the one-shot release identity, and re-arms exactly one retry.

### R41 diagnostic snapshot

The snapshot preserved `LAST.conf`, first-boot status and console output, but not the actual `repair-*.log`. That prevented the remote log from showing all fsck output around the abort.

R43 adds a bounded copy of the newest full repair log plus checker path/SHA/startup output.

### R42 private diagnostics bootstrap

The temporary device-local credential and private-log configuration are working. R43 must not carry, replace, print or expose that credential. The existing two-pass queued upload behavior is preserved. The public R43 package contains no secret payload.

### K1

No K1 Image, DTB, uInitrd or module archive is changed by R43. Boot Next Once remains blocked until the physical post-R43 log proves R36UPDATE clean.

## Release blockers

R43 cannot be published unless all of the following pass in one validation workflow:

1. Exact published R41 base package identity is verified.
2. Exact pinned dosfstools 4.2 source identity is verified.
3. New AArch64 checker is static and built with iconv disabled.
4. The actual AArch64 checker executes under qemu-user, repairs a deliberately dirty FAT32 image, and then returns clean under `-n`.
5. The full R36UPDATE helper executes with that actual target checker through qemu and reaches `PASS_REBOOT_REQUIRED`.
6. Armed K1 marker still blocks repair.
7. Simulated checker abort remains fail-closed.
8. R43 package contains no credential/token and no `/r36state/secrets` payload.
9. R43 package carries no K1 binary and no active `/boot` or module-tree payload.
10. K1 helper release identity is coherent at 0.5.43.0.
11. Package builds twice byte-for-byte identically.
