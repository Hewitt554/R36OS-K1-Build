# Native R36OS — Chapter 1 completion handover

Date: 2026-10-01
Status: PASS pending final CI confirmation
Frozen R60 base: c1f582edf876349269b4212aa6a78f1387aa7ecc
Chapter-1 branch: work/native-c00-c01-baseline-audit-2026-10-01

## What Chapter 1 established

1. Do not remove ArkOS in-place.
2. Keep R60 + legacy 4.4 as rescue/reference during migration.
3. Build the first native root beside the old root at:
   /r36state/r36os-next/rootfs
4. Use Debian 13 trixie arm64 as the native userspace package base.
5. Keep the R36OS K1 kernel/Panel-4 platform separately from the Debian
   userspace decision.
6. Native root is built from an allow-list, not copied from the old root.
7. K1 native userspace must reject:
   - ArkOS/AeUX runtime assumptions;
   - PortMaster host-tool paths;
   - Westonpack/westonwrap as system compositor;
   - CrustyGBM/libcrusty;
   - proprietary ARM Bifrost r13p0 EGL/GLES;
   - old GO-Super/uinput assumptions as boot/graphics prerequisites.
8. Wi-Fi driver choice is deferred intentionally to C05.
9. Native Mesa/Panfrost userspace is deferred intentionally to C06.
10. Hardware-specific audio/input unknowns are assigned to their owning later
    chapters instead of blocking clean-root construction.

## Chapter-1 artifacts

- CHAPTER_00_R60_FROZEN_BASELINE.md
- CHAPTER_01_DEPENDENCY_AUDIT.md
- C01_CURRENT_USERSPACE_FINDINGS.md
- C01_CHAPTER_02_ROOT_BOUNDARY.md
- C01_BASE_USERSPACE_DECISION.md
- C01_PHYSICAL_CAPTURE_README.md
- tools/source_dependency_scan.py
- tools/capture_c01_physical_dependencies.sh

## Recovery points

- backup/native-c00-r60-freeze-2026-10-01
- backup/native-c01-initial-map-green-2026-10-01

A final Chapter-1 completion backup must be created after the closing CI run
passes.

## Physical system changes made by C00/C01

NONE.

No change was made to:
- live update channel;
- current R60 installation;
- K1 Image;
- DTB;
- uInitrd;
- module tree;
- U-Boot;
- partitions;
- normal systemd services;
- NetworkManager;
- graphics runtime.

## Chapter 2 entry contract

C02 may:
- create build scripts and CI;
- fetch a pinned Debian 13 arm64 userspace;
- build a rootfs artifact;
- add a separate R36OS overlay;
- validate the artifact.

C02 may NOT:
- boot the new root on hardware;
- write it to the user's device;
- modify the current boot process;
- alter K1 binaries;
- alter the live updater;
- repartition the current card.

Those operations belong to C03 or later.

## C02 first tasks

1. Choose/pin a Debian repository snapshot.
2. Write the explicit package allow-list.
3. Write the rootfs builder.
4. Write the legacy-forbidden scanner.
5. Add R36OS native release identity.
6. Generate dpkg and file manifests.
7. Build twice in CI.
8. Prove the normalized results are deterministic.
9. Produce the first native-root artifact.
10. Freeze C02 before any device boot work begins.
