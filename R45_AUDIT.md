# R36OS Alpha 5R45 — passive K1 boot-handoff diagnostics

Date: 2026-09-29

## Why R45 exists

Alpha 5R44 fixed physical K1 staging code 33. Boot Next Once then reached PASS and the user manually rebooted.

The next uploaded R44 session-start bundle proves:
- running kernel after reboot is legacy Linux 4.4.189
- the staged K1 candidate is present and identifies Linux 6.12.94-r36os-k1
- current diagnostics do not preserve enough direct evidence to distinguish:
  1. request still armed/pending and never consumed, from
  2. request consumed by the bootloader followed by a K1 fallback

R45 is diagnostics-only. It does not change K1 binaries or boot-hook logic.

## Passive evidence recorder

r36os-k1-boot-audit records:
- current kernel
- exact candidate ID/kernel and preflight return code
- request/consumed marker existence, size, SHA-256 and non-secret identity fields
- marker state: NONE / ARMED_PENDING / CONSUMED_WITH_REQUEST / ORPHAN_CONSUMED
- request vs consumed hash equality
- /boot/boot.ini hash and K1 hook/candidate markers
- hook.conf identity and expected boot hash
- relevant r36os.kernel_* command-line values
- early K1 marker status if present
- pstore file count/bytes
- kernel-next health service state
- kernel-slot status output
- existing persistent HEALTHY/FALLBACK record names

The recorder writes only to /r36state/logs/kernel-next/boot-handoff-current.conf.
It never arms, disarms, consumes, renames or removes K1 boot markers.

## Diagnostics integration

Every r36os-github-diagnostics capture invokes the passive recorder first.
The existing uploader already includes /r36state/logs/kernel-next/*.conf.

The normal diagnostic snapshot also refreshes and embeds the same handoff record.

## Release scope

Changed:
- r36os-k1-boot-audit (new)
- r36os-github-diagnostics (invoke passive audit before capture)
- r36os-diagnostic-snapshot (include passive handoff evidence)
- r36os-kernel-next-prepare release guard 0.5.45.0
- r36os-kernel-slot R45 identity
- core manifest / release metadata

Not changed:
- K1 Image, DTB, uInitrd, modules
- K1 boot hook logic
- K1 preflight
- R36UPDATE FAT repair
- R36STATE device-local token/config
- /boot payload

requires_reboot=false. After installation the user should export diagnostics before any deliberate restart.
