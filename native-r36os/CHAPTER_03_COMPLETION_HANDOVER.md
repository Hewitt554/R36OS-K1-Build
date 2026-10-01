# Native R36OS Chapter 3 — completion handover

Date: 2026-10-01
Status: PASS
Readiness: READY_FOR_PHYSICAL_BOOT_ONCE_TEST

Chapter 3 is complete as a software/build/safety milestone. It has NOT yet
been physically booted on the R36S and has NOT been published to the live R60
update channel.

## Frozen validation lineage

Chapter 2 prerequisite:
- validation run: 36853590230
- artifact: 11157737003 / R36OS-Native-C02-rootfs
- validated head: 182f51989b457ff30cce26f4305f6785d3d1c70c
- C02 rootfs SHA-256:
  42eec8dc524fcd821d0919bb3d185a3a0894f5bbf48fa0bf36d0a3834b454fac

Proven boot-lineage probe:
- run: 36850324460
- artifact: 11155008267 / R36OS-Native-C03-proven-lineage
- proven R54 uInitrd SHA-256:
  023a0d2adc113b2d1fea6826387ab6e03e4d479cf5fa36c9b9ff86cf41fd1925
- proven current R60/K1 hook SHA-256:
  e389b843ca85cbed59e9227247b2735356f5f551351e8e274e2731fbb15e3c9c
- frozen legacy boot.ini SHA-256:
  b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e

Final C03 static source validation:
- run: 36883632489
- artifact: 11173625563 / R36OS-Native-C03-static-safety
- source head: eb8656312f8d4f4232794b7d002f639e7bb3f5bf

Full tightened-source integration validation:
- run: 36883843370
- artifact: 11173811337 / R36OS-Native-C03-bootonce-candidate
- integration head: 854eba731ddedf5ff41ae4ec2d78b5891986090c
- result: PASS
- readiness recorded by CI: READY_FOR_PHYSICAL_BOOT_ONCE_TEST

Independent K1 built-in storage proof:
- run: 36884764632
- artifact: 11174150534 / R36OS-Native-C03-K1-builtins
- proof head: 7ff82d63b3a725b2600008dd29dcf16f2630291e
- result: PASS

Permanent Chapter-3 recovery branch:
- backup/native-c03-complete-green-2026-10-01

Additional recovery branches:
- backup/native-c02-rootfs-green-2026-10-01
- backup/native-c03-static-green-2026-10-01
- backup/native-c03-integration-green-2026-10-01

## Frozen C03 candidate identity

Native candidate:
- 8f8eaa3bae6ad4352b4e01ef

Native C03 rootfs:
- SHA-256:
  08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4
- compressed bytes: 71167554
- unpacked size recorded by bundle: 324652 KiB

Native C03 uInitrd:
- SHA-256:
  be567cd71bc95c35cfdaf7100ee0846517df5cd78538e4f3da6157a7fa61d694

Freestanding AArch64 /init:
- SHA-256:
  9433ff746d17e08ca957325d1668c80c9be0b18076918d3937e6d05ed8f2ef33

Generated boot.ini hook:
- SHA-256:
  087c8a523154e32a4bd617c683d5c4ba19d6240f591b8979658ca62ca3652b65

Existing K1 candidate reused unchanged:
- candidate: 9d7bd2334f315d98b482f850
- kernel: 6.12.94-r36os-k1
- Image change: NO
- Panel-4 DTB change: NO
- K1 module tree change: NO
- U-Boot binary change: NO
- partition change: NO
- legacy 4.4 kernel change: NO

## What Chapter 3 built

### 1. Candidate-bound native root

The exact C02 Debian ARM64 root is extended only with:
- R36OS Native C03 identity;
- one systemd health service;
- one health helper;
- a runtime bind target for the externally authenticated C03_READY.conf.

The root remains free of the legacy components prohibited by Chapter 2:
- ArkOS runtime dependencies;
- PortMaster;
- Weston/Westonpack;
- Xwayland;
- Wine;
- Box64;
- Steam;
- proprietary libMali/Bifrost userspace;
- CrustyGBM/libcrusty.

### 2. Tiny native initramfs

A deterministic freestanding AArch64 /init is linked without libc or a dynamic
loader.

It:
- validates r36os.kernel_slot=next;
- requires r36os.kernel_attempt=NATIVE_C03;
- verifies exact K1 candidate identity;
- verifies exact native candidate identity;
- verifies exact R36STATE UUID;
- verifies the expected rootfs SHA supplied by the boot hook;
- discovers R36STATE by ext4 UUID rather than hard-coded device numbering;
- checks C03_READY.conf and native-root identity before switch-root;
- checks the existing K1 module tree exists;
- bind-mounts the native root;
- exposes only:
  - R36STATE/logs,
  - the authenticated C03 ready marker,
  - the exact K1 module directory;
- moves /dev, /proc and /sys into the native root;
- switch-roots and execs native /sbin/init.

On an initramfs failure it does not reformat, repartition or retry. It displays
a failure and waits for a power cycle; the already-consumed one-shot guard
prevents another native attempt next boot.

### 3. Separate native Boot Once namespace

Native C03 does not reuse the normal K1 request marker.

Native request:
- R36OS-NativeNext/C03/boot-native.8f8eaa3bae6ad4352b4e01ef.once

Native consumed marker:
- R36N3.CNS

The U-Boot sequence is:
1. detect exact native request;
2. refuse a previously consumed attempt;
3. write consumed marker BEFORE Linux;
4. read the consumed marker back;
5. verify marker size;
6. load the existing K1 Image;
7. load the C03 native uInitrd;
8. load the existing Panel-4 K1 DTB;
9. append candidate/rootfs identities to bootargs;
10. booti.

If any payload load fails after consumption, U-Boot falls through to the
existing K1/legacy path. The next power cycle also sees consumed state and will
not automatically try C03 again.

### 4. Transactional staging and arming

r36os-native-c03-prepare:
- runs only from the expected R60 / legacy-4.4 host environment;
- verifies exact R60 version;
- verifies exact R36STATE UUID;
- refuses a pending normal K1 one-shot;
- reuses the existing audited K1 stage-only path;
- verifies the complete C03 bundle before writes;
- checks R36STATE free space;
- extracts beside the active native root;
- verifies every regular-file hash;
- activates with same-filesystem rename + rollback;
- installs the boot hook transactionally;
- opens R36UPDATE only through the existing R60 private maintenance window;
- verifies the existing K1 payload on FAT;
- stages the native uInitrd;
- writes the native request as the FINAL boot-affecting write;
- closes/unmounts the private write window before reporting success.

A marker-close failure removes the request/consumed marker and aborts the
private write window, returning to safe normal boot state.

### 5. Native health gate

C03 is considered healthy only if the native system reaches:
- exact K1 kernel;
- exact K1/native candidate identities;
- exact rootfs identity;
- PID 1 = systemd;
- persistent R36STATE log bind available;
- K1 modules visible;
- R36OS Native C03 release identity present;
- systemd-journald active;
- systemd-udevd active;
- externally authenticated ready marker matches the booted candidate/rootfs.

Persistent evidence:
- /r36state/logs/native-boot/C03_EARLY.conf
- /r36state/logs/native-boot/C03_HEALTH.conf

## K1 module-free-initramfs prerequisite proved

The exact published/physically tested R59 K1 package was independently audited.

The following are built into the K1 Image rather than requiring initramfs
module loading:
- ext4;
- mmc_core;
- mmc_block;
- dw_mmc;
- dw_mmc-pltfm;
- dw_mmc-rockchip.

Panfrost is also listed in modules.builtin.

This is important because the C03 initramfs needs MMC + ext4 before it can
mount R36STATE and reach the external K1 module tree.

## Validation coverage

Automated validation covers:
- deterministic C02 root build;
- exact boot-lineage hashes;
- deterministic C03 initramfs;
- deterministic C03 root/bundle generation;
- ARM64 architecture checks;
- legacy/PortMaster/proprietary-Mali exclusion scan;
- boot-hook byte preservation;
- legacy boot reconstruction/hash proof;
- one-shot state-machine model;
- staging/arming failure model;
- transactional hook installation;
- fail-closed rejection of unknown/drifted boot.ini;
- fail-closed rejection of missing legacy recovery copy;
- fail-closed rejection of corrupted C03 bundle;
- no replacement Image/DTB/modules in C03;
- K1 ext4/MMC built-in prerequisite.

## Device impact as of Chapter-3 completion

NONE.

The following remain true:
- main/live updater is still Alpha 5R60 / 0.5.60.0;
- current R60 SHA is unchanged;
- no C03 files have been installed on the handheld;
- current /boot/boot.ini has not been changed by this work;
- K1 remains Boot Next Once;
- ArkOS/legacy root remains intact;
- no partitions were changed;
- no U-Boot binary was written.

## Chapter boundary

Chapter 3 ends here.

The next action is NOT Chapter 4 yet.

First, if the user chooses to proceed, package the frozen C03 candidate into a
controlled developer-delivery update and perform ONE physical Native Boot Once
test. The physical result determines whether Chapter 4 can begin.

Until that physical test succeeds, the correct statement is:

READY_FOR_PHYSICAL_BOOT_ONCE_TEST

not:

NATIVE_OS_PROVEN

Chapter 3 status: PASS.
