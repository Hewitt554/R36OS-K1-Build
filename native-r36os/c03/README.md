# Native R36OS Chapter 3 — native-root Boot Once

Chapter 3 creates the first safe path from the current R60 system into the
ArkOS-independent C02 rootfs. It does not make the native root permanent.

## Boot architecture

Normal/default path remains unchanged:

U-Boot -> existing R60 hook -> legacy Linux 4.4 / current R36OS

Existing experimental K1 path remains unchanged:

existing K1 request -> existing K1 one-shot guard -> existing K1 Image +
R54 uInitrd + Panel-4 DTB -> current R60 userspace

New native path is separate and has higher one-shot priority only when its
own request exists:

native request -> R36N3.CNS consumed write/readback -> existing K1 Image +
new C03 uInitrd + existing Panel-4 DTB -> C02/C03 native root on R36STATE

No native request means the new block falls through byte-for-byte into the
previous R60 K1/legacy boot script.

## Frozen inputs

- current R60/K1 boot hook SHA-256:
  e389b843ca85cbed59e9227247b2735356f5f551351e8e274e2731fbb15e3c9c
- frozen legacy boot.ini SHA-256:
  b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e
- physically proven R54 uInitrd SHA-256:
  023a0d2adc113b2d1fea6826387ab6e03e4d479cf5fa36c9b9ff86cf41fd1925
- K1 candidate:
  9d7bd2334f315d98b482f850
- kernel:
  6.12.94-r36os-k1
- R36STATE UUID:
  a25488c6-742d-4555-82d1-e28ffc848af3
- C02 rootfs SHA-256:
  42eec8dc524fcd821d0919bb3d185a3a0894f5bbf48fa0bf36d0a3834b454fac

## Safety invariants

1. Legacy Linux 4.4 Image/uInitrd/DTB are never replaced by C03.
2. Existing K1 Image, module tree and Panel-4 DTB are reused unchanged.
3. C03 builds a new tiny initramfs only; it does not rebuild the kernel.
4. Native root lives under /r36state/r36os-next/rootfs.
5. R36UPDATE writes use the existing R60 private maintenance window.
6. The native one-shot request is the final boot-affecting write.
7. The native request and consumed marker use a namespace distinct from K1:
   - R36OS-NativeNext/C03/boot-native.<native-id>.once
   - R36N3.CNS
8. The consumed marker is written and read back before Image/uInitrd/DTB load.
9. Once consumed, another normal power cycle cannot attempt native C03 again.
10. Failure before request creation leaves normal boot unchanged.
11. Failure after the hook is installed but before request creation is safe:
    the hook is inert without the native request.
12. A boot failure after consumed write falls through to normal boot if U-Boot
    remains in control, and the following power cycle sees consumed state and
    does not make a second native attempt.
13. The initramfs refuses switch-root unless kernel identity, K1 candidate,
    native candidate, R36STATE UUID and exact rootfs SHA agree.
14. The staged rootfs is extracted beside the active native root, verified,
    then activated with same-filesystem renames and rollback.
15. A normal K1 Boot Next Once request must not be pending when native C03 is
    armed.
16. C03 carries the exact pre-C03 R60 hook bytes as recovery evidence.
17. No U-Boot environment is saved by the native hook.
18. The native root does not receive a recursive/full R36STATE bind; only logs,
    C03_READY.conf and the K1 module tree are exposed.

## Native root handoff

The freestanding AArch64 /init:

- mounts devtmpfs, proc and sysfs;
- validates the native C03 command line;
- discovers R36STATE by exact ext4 UUID;
- validates C03_READY.conf;
- validates the native root candidate identity;
- verifies the existing K1 module tree is present;
- bind-mounts the native root;
- bind-mounts only R36STATE/logs, the authenticated C03 ready marker, and the K1 module tree into it;
- writes C03_EARLY.conf;
- moves /dev, /proc and /sys;
- switch-roots into the native Debian userspace;
- execs native /sbin/init.

It never formats, repartitions, fscks, modifies U-Boot, clears the one-shot
consumed marker, or replaces legacy boot payloads.

## Native health gate

The native systemd root is considered C03-healthy only if:

- running kernel is 6.12.94-r36os-k1;
- kernel attempt is NATIVE_C03;
- K1 and native candidate identities match;
- exact rootfs SHA matches the staged ready marker;
- PID 1 is systemd;
- the persistent R36STATE log bind is mounted;
- K1 modules are visible;
- native R36OS release identity is present;
- systemd-journald is active;
- systemd-udevd is active.

The result is persisted to:

/r36state/logs/native-boot/C03_HEALTH.conf

## What Chapter 3 does NOT prove

CI can prove build identity, hook preservation, staging logic and one-shot
state transitions. It cannot prove the R36S physically reaches native systemd.
That physical test belongs after Chapter 3 is frozen and must remain one-shot.

Chapter 3 must therefore end as:

READY_FOR_PHYSICAL_BOOT_ONCE_TEST

not as:

NATIVE_OS_PROVEN
