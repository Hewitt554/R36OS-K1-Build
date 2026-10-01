# Native R36OS C01 — base userspace decision

Decision status: ACCEPTED FOR CHAPTER 2 PROTOTYPE
Date: 2026-10-01

## Decision

Use Debian 13 "trixie" arm64 as the base userspace for the first native R36OS
root filesystem.

This means:
- Debian supplies the ARM64 userspace package ecosystem.
- R36OS supplies policy, platform integration, UI, gaming stack and updates.
- The R36OS K1 kernel remains the kernel.
- Debian's generic kernel/bootloader is not the target platform kernel.
- The known-good R36S U-Boot/Panel-4/K1 boot chain remains separate from this
  userspace decision.

Current upstream basis at the time of this decision:
- Debian 13 is current stable.
- Current point release is Debian 13.7.
- arm64 is an officially supported Debian 13 architecture.

Official references:
- https://www.debian.org/releases/
- https://www.debian.org/News/2026/20260912
- https://www.debian.org/releases/stable/debian-installer/

## Why Debian stable

### Suitable package ecosystem

The eventual R36OS needs:
- systemd/udev/journald;
- modern Mesa/Panfrost;
- NetworkManager/wireless userspace;
- PipeWire/WirePlumber/BlueZ;
- Xwayland/Wayland;
- common Linux gaming libraries;
- Box64/Wine host dependencies;
- debugging/recovery utilities.

A Debian stable ARM64 base provides those from one coherent package ecosystem
instead of manually assembling unrelated binaries.

### Appropriate for 1 GiB hardware

The native root will not install a Debian desktop task.
Only explicit packages are included.

Debian is the package source, not the R36OS user experience.

R36OS can therefore remain a small framebuffer/Wayland gaming shell even
though the underlying libraries come from Debian packages.

### Better fit than copying the inherited root

The purpose of migration is to make every host dependency explicit.
Building from a clean Debian package manifest lets us:
- audit every requested package;
- record every resolved package version;
- build the root in CI;
- reject ArkOS/PortMaster/proprietary-Mali files;
- reproduce the same userspace independently of the user's existing card.

### Stable rather than testing/unstable

The R36S platform itself is already an unusual target and the K1 work is still
being proven.  The base userspace should reduce moving parts.

Newer Mesa or wireless userspace can be backported or built deliberately in
later chapters if stable's version is insufficient.  That is preferable to
making the whole root a rolling distribution.

## Build method direction

Chapter 2 should use an explicit rootfs builder such as mmdebstrap/debootstrap
from CI rather than unpacking a prebuilt generic image.

Preferred approach:
1. select a Debian repository snapshot date;
2. build architecture=arm64;
3. install only the Chapter-2 allow-list;
4. disable recommended packages unless explicitly required;
5. add R36OS-owned files in a separate overlay;
6. generate dpkg/package manifest;
7. generate full file/hash manifest;
8. scan for forbidden legacy strings/paths/libraries;
9. build twice and compare normalized manifests/artifacts.

A repository snapshot is important because "stable" still receives point
updates.  The Chapter-2 build must not silently change package versions
between CI runs.

## What Debian does NOT own

Debian base selection does NOT mean using:
- Debian generic RK3326 boot scripts;
- Debian generic kernel instead of K1;
- GRUB;
- a Debian desktop;
- Debian branding;
- Debian installer on the handheld;
- an automatically generated fstab that overwrites the current storage plan.

R36OS owns:
- hardware/board profile;
- boot handoff;
- system layout;
- R36STATE policy;
- game storage;
- UI;
- diagnostics;
- kernel candidate policy;
- update/recovery policy.

## Initial architecture

Kernel/platform:
  R36OS K1 Linux 6.12.94-r36os-k1
  + known-good Panel-4 DTB
  + R36OS native initramfs later in C03

Userspace:
  Debian 13 trixie arm64 package base
  + R36OS platform layer
  + R36OS services/diagnostics

State:
  /r36state

Games/user data:
  /roms2

Prototype root:
  /r36state/r36os-next/rootfs

## Alternatives considered

### Buildroot

Advantages:
- extremely small;
- highly controlled image.

Not selected for the first prototype because the eventual R36OS gaming stack
needs a broad, conventional Linux library ecosystem.  Maintaining Steam/Wine,
Mesa, PipeWire and many host libraries manually would transfer a large package
maintenance burden into R36OS.

Buildroot remains useful conceptually for a future tiny rescue image.

### Arch/rolling base

Advantages:
- very recent Mesa and userspace.

Not selected as the base because reproducibility/stability matters more than
having every package at the newest release.  Individual newer components can
be deliberately introduced and tested.

### Continue ArkOS as the package base

Rejected for the native root.  That is the architecture we are migrating away
from.

## Chapter 2 must still decide

Before implementation:
- exact Debian snapshot timestamp;
- exact package allow-list;
- whether NetworkManager uses wpa_supplicant or iwd initially;
- DNS/resolver approach;
- locale policy;
- timezone/NTP policy;
- root account/recovery-console policy;
- machine-id generation policy;
- package cache stripping policy;
- package documentation/manpage stripping policy;
- native-root archive format.

Those are Chapter-2 build decisions and do not require changes to the current
R60 device.
