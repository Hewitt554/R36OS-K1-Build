# R36OS K1 — Alpha 5R37 first-device-test checkpoint

Date: 2026-09-28

## Status

The project has reached the first **Boot Next Once** hardware-test boundary.

- Kernel: Linux 6.12.94-r36os-k1
- Successful kernel build: GitHub Actions Run #11 / run ID 36384548493
- Run #11 source commit: 42464c308fafe64cb754f33734f41eb292a591af
- Canonical Panel-4 DTB: rk3326-r36s-k1.dtb
- Hardened CP05 candidate ID: 7dd6168d3246720c461d17e2
- Alpha 5R37 package version: 0.5.37.0
- Final device-test package: 00-R36OS-Alpha5R37-K1BootNextOnce-FromR36.r36upd
- Final package SHA-256: b6250ad44aa28be6ae893ed579a3d22d6930ca610a7bda8720b64f6fbaa817d2
- Final package size: 217225582 bytes

## Real candidate changes after Run #11

Run #11's Image and Panel-4 DTB remain byte-for-byte unchanged.

CP05 was hardened so the K1 boot has its matching 6.12 modules without replacing legacy Linux 4.4 modules:

- modules are stored on the expanded R36STATE partition;
- exact R36STATE UUID is required: a25488c6-742d-4555-82d1-e28ffc848af3;
- module archive is sanitized (CI build symlink removed; link entries forbidden);
- module archive has 1290 files / 1091383701 uncompressed bytes;
- arm-once extracts and verifies modules before any boot-affecting operation;
- K1 initramfs mounts exact R36STATE and bind-mounts the matching module tree before switch-root;
- health validation checks state/module/candidate identity.

Candidate hashes:
- Image: a7a388d5ca21b276bddcc0e3892b0c965b73d92f2c0238cb9c25a210dba7c97e
- DTB: e2145905b1beb8d0f5b9dee6c5a21d31c29474be8762c893e81506fc40e627f4
- uInitrd: 6d44f435bd88b54e91af569fd6445db460b9ab80313062b8136796f27b888f6e
- modules.tar.xz: e3f95975fb7a588a6fd9493c43c2b2895ccf46bc524bf135508d5e1ec4b70074

## Validation

- CP05 real candidate: PASS
- CP06 one-shot/fallback model: PASS
- CP07 destructive failure matrix: 30/30 PASS
- CP08 release/package integration matrix: 45/45 PASS
- actual real-package stage-only simulation: PASS
- actual real-package arm-once simulation: PASS
- real module extraction/readback: PASS
- final package archive safety/checksums/candidate byte identity: PASS
- no active /boot or installed /lib/modules payload: PASS
- no one-shot marker shipped: PASS
- exact frozen legacy boot.ini backup path tested: PASS

Builder hardening completed:
- invalid/synthetic production build requests can no longer delete an existing final artifact;
- fixture validation preserves the final artifact byte-for-byte;
- final R36UPD2 archive is deterministic;
- repeated builds produced the same SHA-256 above.

## Safety

Installing R37 still boots the legacy Linux 4.4 path normally. K1 remains inert until the user explicitly selects **Boot Next Once**. A successful first K1 boot does not authorize promotion to permanent/default.

Remaining checks are device-only: physical FAT health, real U-Boot behavior, and hardware bring-up.
