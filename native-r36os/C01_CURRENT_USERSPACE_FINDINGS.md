# Native R36OS C01 — current inherited userspace findings

Date: 2026-10-01
Source: Alpha 5R60 physical-device evidence + preserved R36 source lineage
Status: audit evidence only; no device/runtime changes

## 1. Current root is an inherited distribution root, not a native R36OS root

R60 K1 mounts:
- /dev/mmcblk0p2 -> /
- /dev/mmcblk0p4 -> /r36state
- /dev/mmcblk0p4 -> /usr/lib/modules/6.12.94-r36os-k1
- /dev/mmcblk1p1 -> /roms2
- /dev/mmcblk1p1 -> /opt/system/Tools
- /dev/mmcblk0p1 -> /boot
- /dev/mmcblk0p3 -> /r36update

Important consequence:
- K1 already depends on a hybrid layout where the kernel/module tree is partly
  supplied from R36STATE while the root userspace remains inherited.
- /opt/system/Tools is a legacy ArkOS/PortMaster-style bind from SD2 and must
  not become a native-root dependency.

## 2. Current systemd/userspace age and incompleteness

R60 boots systemd 242 with default-hierarchy=hybrid.

Observed boot issues:
- systemd-journald.service is not loaded.
- journald sockets are refused because their service is missing.
- many units report inability to connect stdout to the journal socket.
- NetworkManager has no usable journal in the exported result.
- the current dbus socket unit still references legacy /var/run and systemd
  rewrites it to /run.
- current cgroups expose both cgroup2 and multiple cgroup-v1 controllers.

Native-root decision:
- Chapter 2 must provide a coherent systemd/udev/journald set from one package
  snapshot.
- Do not reproduce the current partially missing journald installation.
- Do not inherit current unit files wholesale.
- Prefer one deliberate systemd cgroup model supported by the chosen native
  distribution rather than copying the present hybrid setup.

## 3. Legacy services still leak through the current root

R60 status shows:
- 351mp.service loaded and failed.
- emulationstation.service masked.
- play-video.service masked.
- networkwatchdaemon.service masked.
- getty/console services inherited from the base.
- several R36OS-owned units queried by diagnostics are not installed:
  r36os-resource.service
  r36os-boot-recovery.service
  r36os-audio-compat.service

Native-root decision:
- do not copy the inherited service directory;
- build an allow-list of intended native units;
- 351mp, EmulationStation, play-video and networkwatchdaemon are excluded from
  the native base unless a later hardware audit explicitly proves a need;
- every R36OS unit shipped in the native root must have a single owner,
  versioned source file and an automated enablement/ordering test.

## 4. Graphics userspace is definitively legacy-coupled

R60 external-session logs identify:
- CFW_NAME=ArkOS AeUX
- Westonwrap 0.2.7.1
- Crusty/libcrusty loading
- EGL vendor ARM
- EGL version 1.4 Bifrost-r13p0-01rel0
- GL renderer Mali-G31

This is not proof of a healthy Panfrost userspace.  It proves that the inherited
runtime is still supplying the proprietary ARM/Bifrost user libraries while
the K1 kernel uses Panfrost.

Preserved R36 source also has explicit dependencies on:
- weston_pkg.squashfs
- westonwrap.sh
- /opt/system/Tools/PortMaster/gptokeyb
- /opt/tools/PortMaster/gptokeyb
- /roms/ports/PortMaster/gptokeyb
- /usr/local/lib/aarch64-linux-gnu paths used by old graphics probes

Native-root decision:
- no Westonpack in the K1 base;
- no CrustyGBM/libcrusty in the K1 base;
- no proprietary ARM r13p0 EGL/GLES in the K1 base;
- first graphics proof is native DRM/Mesa/Panfrost without Xwayland and
  without the game runtime;
- Weston and Xwayland are added only after the direct native render path works.

## 5. Current R36OS binaries reveal required native library groups

Preserved R36 ELF dependency scan shows:
- r36os-alpha5: statically linked AArch64.
- r36os-input-supervisor: statically linked AArch64.
- r36os-uinitrd-tool: statically linked AArch64.
- ARM64 direct graphics probe:
  libgbm.so.1
  libEGL.so.1
  libGLESv2.so.2
- ARM64 X11 graphics probe:
  libX11.so.6
  libEGL.so.1
  libGLESv2.so.2
- old SDL graphics lab:
  libSDL2-2.0.so.0
- x86-64 test/HUD/loading binaries require the x86-64 dynamic loader and
  glibc/X11/EGL/GLES libraries as appropriate.

Native-root decision:
- static R36OS utilities can be useful in early bring-up because they reduce
  host-library ambiguity;
- dynamic graphics probes must be rebuilt/revalidated against the new native
  Mesa stack;
- x86-64 host compatibility libraries are NOT part of the first native boot;
  they belong to C11.

## 6. Wi-Fi failure is a platform/driver issue, not a missing network daemon

R60 proves:
1. DWC2 USB host initializes.
2. Realtek 0bda:0179 enumerates at 480 Mbps.
3. cfg80211 begins loading.
4. rtl8xxxu identifies RTL8188EU rev D / 1T1R.
5. rtl8188eufw.bin is opened and firmware revision 11.1 is read.
6. firmware fails to start.
7. rtl8xxxu probe exits -11.
8. no wlan interface appears.
9. NetworkManager therefore reports WIFI-HW=missing.

Native-root decision:
- NetworkManager can be evaluated separately from driver selection.
- C05 must compare wireless driver implementations using the same clean root.
- Do not spend C02/C03 adding more network-service workarounds for a failed
  kernel driver probe.

## 7. Input hardware is suitable for a native platform profile

R60 exposes:
- event0: rk805 pwrkey
- event1: rk817_int Headphones
- event2: adc-joystick
- event3: gpio-keys

Native-root decision:
- board profile owns these physical devices;
- the R36OS shell may consume gpio-keys + adc-joystick directly;
- a virtual Xbox/game controller is a separate compatibility layer, not a
  prerequisite for the OS or graphics;
- old single GO-Super/Gamepad assumptions are retired from native architecture.

## 8. Storage makes side-by-side migration practical

R60 physical sizes:
- current / root: ~9.9 GiB, ~6.9 GiB used
- R36STATE: ~48 GiB, ~38 GiB free
- SD2 /roms2: ~239 GiB
- /boot: ~111 MiB
- /r36update: ~1 GiB

Native-root decision:
- first native root is staged under /r36state/r36os-next/rootfs;
- no repartitioning is required for C02/C03;
- user data stays outside the native root;
- native-root failure cannot erase the inherited root.

## 9. Diagnostics also depend on inherited packages

Preserved source explicitly probes for tools including:
- curl, wget
- lsusb
- nmcli
- rfkill
- findmnt, lsblk, blkid
- file, readelf, strings
- plymouth
- kexec
- sfdisk, fdisk, resize2fs
- 7z/7za, cabextract, bsdtar
- pactl, pw-cli, wpctl, wireplumber
- chvt
- gzip, xz, lz4, zstd, cpio
- OpenSSH/dropbear variants

Current R60 evidence also shows an old USB diagnostic calling lsusb when lsusb
is not installed, while identifying itself as Alpha 5R3.

Native-root decision:
- Chapter 2 gets an explicit package manifest;
- diagnostic tools are packages, not assumptions;
- all shipped diagnostics use the authoritative R36OS release helper;
- missing optional tools must report NOT_INSTALLED rather than emit shell
  command-not-found noise.

## 10. Chapter-2 design implications

The first native root should deliberately be boring:
- ARM64 only.
- no Wine.
- no Steam.
- no x86-64 libraries.
- no Xwayland.
- no Weston initially.
- no proprietary Mali userspace.
- no PortMaster runtime.
- no ArkOS services.
- no EmulationStation.
- no game launcher required for the first boot.

Its purpose is only:
- systemd/udev/journald;
- mounts/storage;
- kernel module handling;
- raw input;
- network tooling;
- diagnostics;
- clean shutdown/reboot;
- enough tooling to bring up C05/C06 later.

The framebuffer R36OS UI may be added after the console/base hardware boot is
proven, because it is R36OS-owned and statically linked, but it is not allowed
to hide a broken native base.

## 11. Audit conclusion at this checkpoint

The migration should not be approached as "remove ArkOS packages from R60".

It should be approached as:
1. preserve R60 as rescue/reference;
2. construct a new root from a package allow-list;
3. add only R36OS-owned/platform components whose dependencies are explicit;
4. boot that new root one-shot;
5. validate each hardware layer independently;
6. only later retire the inherited root.

This evidence strengthens the decision to build beside ArkOS rather than
continue deleting/masking services in-place.
