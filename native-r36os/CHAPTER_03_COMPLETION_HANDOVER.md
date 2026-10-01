# Native R36OS Chapter 3 — definitive completion handover

Date: 2026-10-01
Status: PASS
Readiness: READY_FOR_PHYSICAL_BOOT_ONCE_TEST

Chapter 3 is complete as a software/build/safety milestone.
It has NOT yet been physically booted on the R36S and has NOT been published
to the live R60 update channel.

## Definitive frozen source state

Working branch:
- work/native-c02-c03-rootfs-bootonce-2026-10-01

Definitive Chapter-3 validated source head:
- e0eafefcab9c00de271790ae503a20fe700a74cc

Final static source validation:
- run: 36886675777
- artifact: 11173519890 / R36OS-Native-C03-static-safety
- source head: 7bc37d0680e54c2c22cab6dccdb94c191d9c9bf9
- result: PASS

Only the integration workflow changed after the pinned static source head.
The definitive integration workflow proves no C03 implementation source
changed after that static validation.

Definitive full integration validation:
- run: 36886819015
- job: 110452130034
- validated head: e0eafefcab9c00de271790ae503a20fe700a74cc
- artifact: 11175525608 / R36OS-Native-C03-bootonce-candidate
- artifact zip size: 71490469 bytes
- artifact zip SHA-256:
  6c580cceb0fc3bdbef96b77a30f33282775a92bb4b92396a4f30856b3d8ace2f
- result: PASS

Independent K1 built-in storage proof:
- run: 36884764632
- result: PASS
- ext4/MMC/dw_mmc/dw_mmc-rockchip are built into the exact K1 Image used by
  R59/R60, so the C03 initramfs can reach R36STATE before external modules
  are available.

## Frozen Chapter-2 prerequisite

Chapter-2 validation:
- run: 36853590230
- artifact: 11157737003 / R36OS-Native-C02-rootfs
- source head: 182f51989b457ff30cce26f4305f6785d3d1c70c

C02 rootfs:
- SHA-256:
  42eec8dc524fcd821d0919bb3d185a3a0894f5bbf48fa0bf36d0a3834b454fac
- compressed bytes: 71184225
- resolved ARM64 package count: 180
- package-manifest SHA-256:
  04df91501f801e3af2149167230e25a68f9c68ab33582389dfe52f22cff9a600
- file-manifest SHA-256:
  c6fc6f8f9eb3a7bc2dcfdbdd54f8ec56fc3ab7fbf55bcf43d7cfa82618f45305

## Proven current boot lineage

Proven boot-lineage probe:
- run: 36850324460
- artifact: 11155008267 / R36OS-Native-C03-proven-lineage

Physically proven R54 uInitrd SHA-256:
- 023a0d2adc113b2d1fea6826387ab6e03e4d479cf5fa36c9b9ff86cf41fd1925

Current R60/K1 hook SHA-256:
- e389b843ca85cbed59e9227247b2735356f5f551351e8e274e2731fbb15e3c9c

Frozen legacy boot.ini SHA-256:
- b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e

Existing K1 candidate reused:
- 9d7bd2334f315d98b482f850
- kernel: 6.12.94-r36os-k1

## Definitive C03 candidate identity

Native candidate:
- 8f8eaa3bae6ad4352b4e01ef

Native C03 rootfs:
- SHA-256:
  08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4
- compressed bytes: 71167554
- deterministic unpacked logical size: 303322 KiB
- regular-file manifest SHA-256:
  0e85850b239d7621e64a371f74dee5071e5a37a6aa93811ee336fbd070773649

Native C03 uInitrd:
- SHA-256:
  be567cd71bc95c35cfdaf7100ee0846517df5cd78538e4f3da6157a7fa61d694

Freestanding ARM64 init:
- SHA-256:
  9433ff746d17e08ca957325d1668c80c9be0b18076918d3937e6d05ed8f2ef33

Generated boot hook:
- SHA-256:
  087c8a523154e32a4bd617c683d5c4ba19d6240f591b8979658ca62ca3652b65

Prepare helper:
- SHA-256:
  a214a3fb799103cb7286b9e7b3b9fca1c93cbbccb057444aa0cdadaa8dd1273c

Install-hook helper:
- SHA-256:
  05b83091b5172f8ad9ceb8dd6f4dfcabbf9f101394924bdf9b34fa687ab1b179

R36STATE UUID:
- a25488c6-742d-4555-82d1-e28ffc848af3

Native request:
- R36OS-NativeNext/C03/boot-native.8f8eaa3bae6ad4352b4e01ef.once

Native consumed marker:
- R36N3.CNS

## What Chapter 3 built

1. Candidate-bound native root
- exact validated C02 Debian ARM64 root plus only C03 identity/health pieces;
- no ArkOS, PortMaster, Westonpack, Xwayland, Wine, Box64, Steam,
  libMali/Bifrost or CrustyGBM dependencies.

2. Tiny fail-closed native initramfs
- freestanding ARM64 /init with no libc/dynamic-loader dependency;
- validates kernel attempt, K1 candidate, native candidate, R36STATE UUID,
  staged root identity and exact rootfs SHA before switch-root;
- discovers R36STATE by UUID;
- verifies K1 module tree availability;
- exposes only persistent logs, authenticated ready marker and exact K1
  module directory;
- moves /dev, /proc and /sys;
- switch-roots into native /sbin/init.

3. Separate Native Boot Once namespace
- does not reuse ordinary K1 request marker;
- consumed marker is written/read back before Linux;
- existing K1 Image and Panel-4 DTB are reused unchanged;
- only the C03 uInitrd is new;
- exact candidate/rootfs identities are appended to bootargs;
- no U-Boot environment save.

4. Transactional staging/arming
- requires exact expected R60/legacy host state;
- refuses pending normal K1 one-shot;
- verifies bundle before writes;
- stages beside active root and verifies every regular-file hash;
- same-filesystem rename activation with rollback;
- hook install refuses unknown/drifted boot.ini;
- frozen legacy recovery copy is mandatory;
- existing private R36UPDATE maintenance window is reused;
- native request is the final boot-affecting write.

5. Native systemd health gate
PASS requires:
- exact K1 kernel;
- exact K1/native candidate IDs;
- exact rootfs identity;
- PID 1 = systemd;
- persistent log bind;
- K1 modules visible;
- native release identity;
- systemd-journald active;
- systemd-udevd active;
- authenticated ready marker matches booted candidate/root.

Persistent evidence:
- /r36state/logs/native-boot/C03_EARLY.conf
- /r36state/logs/native-boot/C03_HEALTH.conf

## Final automated coverage

The definitive integration run passed:
- prerequisite validation lineage;
- exact C02 artifact/hash/size;
- exact proven R54 uInitrd;
- exact current R60 K1 hook;
- K1 ext4/MMC built-in prerequisite;
- two complete C03 builds with identical bundle files;
- bundle manifest verification;
- deterministic staged-root size check;
- ARM64 native-root audit;
- forbidden legacy dependency scan;
- ARM64 static initramfs audit;
- transactional production hook installation;
- rejection of unknown/drifted boot.ini;
- rejection of missing legacy recovery copy;
- rejection of corrupted production bundle;
- prepare failure/rollback model;
- native Boot Once state model;
- proof C03 contains no replacement Image, DTB or modules.

## Explicit unchanged areas

Chapter 3 does NOT change:
- legacy Linux 4.4 kernel;
- K1 Image;
- Panel-4 DTB;
- K1 module tree;
- U-Boot binary;
- partition table;
- live R60 update channel;
- current R60 installation on the handheld.

## Device impact

NONE so far.

No C03 payload has been installed on the physical R36S.

## Chapter boundary

Chapter 3 ends at:

READY_FOR_PHYSICAL_BOOT_ONCE_TEST

It does NOT claim:

NATIVE_OS_PROVEN

Prepared physical plan:
- native-r36os/C03_PHYSICAL_BOOT_ONCE_TEST.md

The first physical test must be one controlled Boot Once attempt.
Chapter 4 must not begin until that result is reviewed.

Chapter 3 status: PASS.
