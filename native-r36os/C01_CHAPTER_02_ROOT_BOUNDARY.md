# Native R36OS C01 — Chapter 2 root boundary contract

Status: audit contract
Date: 2026-10-01
Applies to: first ArkOS-independent native ARM64 rootfs

This contract exists so Chapter 2 cannot quietly become "copy the working
pieces out of ArkOS".  The first native root is constructed from an allow-list
and must fail validation when a forbidden legacy dependency enters it.

## Purpose of the first native root

The first root is NOT a gaming distribution.

Its only job is to provide a coherent ARM64 userspace in which K1 can prove:
- systemd PID 1;
- udev device management;
- journald logging;
- kernel module discovery;
- storage/mounting;
- raw controller/input enumeration;
- USB enumeration;
- network tooling for later C05 driver work;
- power/reboot/shutdown primitives;
- hardware diagnostics;
- a stable foundation for C06 Mesa/Panfrost.

No graphical desktop, Wine, Box64, Steam or game launcher is required to pass
Chapter 2.

## Required native-owned capabilities

### Base init/userspace
Required:
- systemd
- systemd-udevd
- systemd-journald
- systemd-logind where package split requires it
- dbus
- bash
- dash or /bin/sh provider
- coreutils
- findutils
- grep
- sed
- gawk/awk provider
- procps
- util-linux
- kmod
- ca-certificates
- tzdata
- libc/glibc runtime
- dynamic loader
- libgcc/libstdc++ only where native utilities require them

Reason:
The current hybrid root has a partial systemd installation with missing
journald.  The native root must ship one coherent init/udev/journal set.

### Storage/filesystems
Required:
- mount/umount/findmnt/lsblk/blkid
- ext4 userspace tools
- FAT fsck/tools for the existing boot/update partitions
- exFAT userspace support for SD2
- tar
- gzip
- xz
- zstd
- cpio
- lz4 if required by retained initramfs/recovery formats
- sha256sum/coreutils

Not required in the first boot root:
- repartitioning tools for normal boot flow
- filesystem resizing
- destructive formatting tools

Those may exist in a later rescue environment, but the ordinary minimal root
must not depend on them.

### Kernel/platform diagnostics
Required:
- kmod tools: modprobe, insmod, depmod, modinfo, lsmod-equivalent
- iproute2
- rfkill
- iw
- usbutils/lsusb
- file
- binutils readelf/strings
- strace
- dmesg
- journalctl
- sysfs/procfs/debugfs access where kernel configuration permits

Optional diagnostic packages must report MISSING cleanly rather than make the
whole boot fail.

### Networking base
Initial choice:
- NetworkManager as the management layer for bring-up consistency
- explicit Wi-Fi supplicant backend selected by Chapter 2/5 package design
- iproute2
- wireless-regdb
- rfkill
- iw

Important:
NetworkManager inclusion does NOT imply rtl8xxxu is accepted as the final
R36S Wi-Fi driver.  Driver selection remains Chapter 5.

### Firmware
The root must have an explicit firmware manifest.
Do not bulk-copy the inherited /lib/firmware tree without provenance.

Chapter 2 may include only firmware required for hardware already known to
need early userspace access.  Realtek 8188EU firmware remains marked
experimental until C05 resolves the driver choice.

## Platform data allowed from the current system

The following may be reused as *data/reference* after hash/provenance checks:
- known-good K1 kernel Image;
- known-good Panel-4 DTB;
- current K1 module archive/tree;
- board-specific firmware where its source/licence is known;
- hardware profile facts derived from physical evidence;
- R36OS-owned static utilities whose exact source/hashes are preserved.

Reusing those files does not make ArkOS the native userspace base.

## R36OS-owned components allowed in early native root

Potentially allowed after explicit per-file review:
- authoritative r36os-release/version helper;
- read-only diagnostics;
- static AArch64 R36OS utilities;
- minimal health reporter;
- minimal native-root boot marker;
- later the framebuffer R36OS shell after console bring-up passes.

Not allowed:
- bulk-copying /usr/local/bin from the old root;
- copying a helper merely because another helper expects it;
- importing old systemd units without reviewing ownership/order/dependencies.

## Hard forbidden dependencies in K1 native userspace

The Chapter-2 root validator must fail if it finds normal runtime dependencies
on any of the following:

### ArkOS / frontend
- ArkOS branding or release identity
- EmulationStation service/runtime as an OS dependency
- play-video.service
- networkwatchdaemon.service
- 351mp.service unless a later platform audit explicitly reinstates it

### PortMaster
- /opt/system/Tools/PortMaster
- /opt/tools/PortMaster
- /roms/ports/PortMaster
- gptokeyb sourced from PortMaster
- /opt/system/Tools bind as a host-tools dependency

### Legacy graphics
- weston_pkg.squashfs as system compositor/runtime
- westonwrap.sh as system compositor launcher
- CFW_NAME=ArkOS AeUX
- CrustyGBM
- libcrusty
- crusty_glx_gl4es as the K1 system graphics path
- proprietary ARM Mali/Bifrost r13p0 EGL/GLES as K1 libraries
- LD_LIBRARY_PATH injections that intentionally select the old ARM Mali stack

### Legacy game-session assumptions
- one physical device named GO-Super/Gamepad as a boot/graphics prerequisite
- /dev/uinput as a prerequisite for booting the OS or testing graphics
- virtual mouse/gamepad creation as a prerequisite for the compositor
- Windows runtime's bundled Weston image as the native display server

### Inherited update/root assumptions
- normal root requiring R36UPD2 stage2 to become bootable
- package/runtime discovery that searches arbitrary ArkOS directories
- stale hard-coded Alpha revision strings
- use of current ArkOS /etc as the native configuration source

## Deferred from Chapter 2

Explicitly deferred:
- Mesa/Panfrost userspace: C06
- Weston: C07
- Xwayland/X11: C07
- normalized game controller/uinput compatibility: C08
- full R36OS UI: C09
- PipeWire/WirePlumber/BlueZ: C10
- Box64/Wine: C11
- Steam: C12
- final hardware health matrix: C13
- A/B updater: C14

This prevents a Chapter-2 failure from being confused with gaming/display
stack failures.

## Filesystem contract for prototype root

Prototype root:
  /r36state/r36os-next/rootfs

Prototype root must treat these as external persistent state:
  /r36state/config
  /r36state/logs
  /r36state/runtimes
  /r36state/wine-prefixes
  /roms2

Chapter 2 builds a rootfs artifact in CI.  It does not install it to the
handheld automatically.

## Build reproducibility contract

Chapter 2 must record:
- distribution name/version;
- repository/snapshot identifiers;
- architecture=aarch64/arm64;
- exact requested package list;
- resolved package/version list;
- all locally added files + SHA-256;
- rootfs file manifest;
- rootfs archive SHA-256;
- build script SHA-256.

A second clean CI build must produce either:
- byte-identical deterministic output, or
- a normalized manifest proving every file/package is identical when upstream
  archive metadata prevents byte-identical compression.

## Native-root validation contract

Before C02 can be called green, CI must prove at minimum:
1. ARM64 root architecture.
2. systemd/udev/journald are installed coherently.
3. /sbin/init resolves to the intended systemd.
4. kmod tools exist.
5. storage/network/diagnostic command allow-list is present.
6. no forbidden legacy paths/strings exist outside explicit audit docs.
7. no proprietary Mali/Crusty/Westonpack payload exists.
8. no PortMaster executable/runtime exists.
9. no EmulationStation or ArkOS boot service is enabled.
10. package manifest and file manifest are complete.
11. rootfs is built entirely in CI; no files are copied from the user's live
    ArkOS root.

## Physical execution contract

Chapter 2 does NOT boot the rootfs on the device.

C03 owns:
- native initramfs changes;
- mounting R36STATE;
- selecting /r36state/r36os-next/rootfs;
- switch_root;
- Boot Once/fallback;
- health marker/rollback.

This separation is deliberate: a rootfs build failure and a boot-handoff
failure must remain different chapters.
