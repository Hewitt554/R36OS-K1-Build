# Native R36OS C03 — physical Boot Once test plan

Status: PREPARED, NOT YET RUN
Candidate: 8f8eaa3bae6ad4352b4e01ef

This test must be run only after the frozen C03 candidate has been delivered
to the handheld through a controlled developer package. The live R60 update
channel is not advanced by Chapter 3.

## Before arming

Boot normal legacy R60 first and confirm:
- R36OS menu works;
- current controller works;
- R36STATE is mounted;
- no normal K1 Boot Once request is pending;
- diagnostics/log export still works.

The developer-delivery package should first run:
- C03 bundle verification;
- host/version/UUID verification;
- normal K1 stage-only verification;
- native root staging;
- hook installation.

The native request must NOT exist during stage-only.

## Stage-only checkpoint

Run the C03 preparation in stage-only mode first.

Expected:
- native root exists at /r36state/r36os-next/rootfs;
- C03_READY.conf is present;
- exact candidate/rootfs hashes match;
- current normal boot is still unchanged because no native request exists.

Reboot normally once after stage-only if desired. R60 should still boot normally.

## Arm once

Only after stage-only is verified:
- ensure normal K1 Boot Once is not armed;
- invoke C03 arm-once;
- the native request must be the final boot-affecting write;
- R36UPDATE/private write window must be closed/unmounted before success is shown.

Do not repeatedly arm the candidate.

## Expected U-Boot stages

The device should show:

R36OS Native C03 one-shot boot

followed by:
- [1/5] Native one-shot guard verified
- [2/5] Existing K1 Image loaded
- [3/5] Native C03 initramfs loaded
- [4/5] Existing Panel-4 DTB loaded
- [5/5] Starting native Debian userspace on 6.12.94-r36os-k1

If it remains on one of these lines, photograph the screen and power-cycle.

## Expected initramfs stages

The tiny /init writes kernel/console messages including:
- stage=native-initramfs-start
- stage=state-discovery
- stage=state-mounted
- stage=native-root-ready
- stage=exec-native-systemd

Before switch-root it should persist:
- /r36state/logs/native-boot/C03_EARLY.conf

If /init fails, it should display:
- FAIL: <reason>
- Power-cycle to return to the untouched legacy boot path.

Do not repeatedly retry.

## Expected native systemd result

Success screen:

R36OS Native C03
=================
PASS: native Debian systemd root reached HEALTHY.

The health service should persist:
- /r36state/logs/native-boot/C03_HEALTH.conf

Expected PASS detail:
- status=PASS
- detail=native-systemd-healthy

Chapter 3 does not require graphics, Wi-Fi, audio, gaming or the R36OS UI to
work inside the native root. Those are later bring-up chapters.

## Recovery behavior

The native consumed marker is written before Linux starts.

Therefore:
- a hang does not automatically retry C03 on the following boot;
- a power cycle should return to the normal existing R60/legacy path;
- the normal K1 one-shot request namespace remains separate;
- no repartitioning or U-Boot binary replacement has occurred.

If normal boot does not return after power-cycle, stop testing and use the
frozen recovery material; do not manually delete random boot files.

## Evidence to collect after the test

Whether PASS or FAIL:
- C03_EARLY.conf
- C03_HEALTH.conf if present
- dmesg from the next legacy boot
- kernel command line evidence
- current boot-slot/native-marker status
- normal R60 diagnostic bundle

Do not start Chapter 4 until this physical Boot Once test is reviewed.

## Pass criterion

C03 physical PASS means:
- one-shot guard consumed exactly once;
- existing K1 Image + Panel-4 DTB started;
- native C03 initramfs found exact R36STATE;
- switch-root reached the native Debian root;
- PID 1 became systemd;
- journald + udevd became active;
- C03_HEALTH.conf reports PASS;
- subsequent reboot/power-cycle returns to normal R60/legacy boot.

Only then may Chapter 4 begin.
