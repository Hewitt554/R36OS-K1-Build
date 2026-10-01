# Native R36OS — Chapter 2 reproducible ARM64 rootfs

Status: IN PROGRESS
Opened: 2026-10-01
Branch: work/native-c02-rootfs-2026-10-01
Base checkpoint: backup/native-c01-complete-2026-10-01

## Chapter goal

Produce the first reproducible ArkOS-independent ARM64 R36OS userspace
artifact in CI.

Chapter 2 DOES NOT boot or install the rootfs on the handheld.

The output is only an audited rootfs archive for Chapter 3.

## Base

Userspace distribution:
- Debian 13 trixie
- architecture: arm64

Kernel is deliberately absent from the rootfs artifact.
The eventual hardware boot continues to use the R36OS K1 platform kernel.

Repository snapshot:
- timestamp: 2026-09-30T00:00:00Z
- SOURCE_DATE_EPOCH: 1790726400
- Debian archive:
  https://snapshot.debian.org/archive/debian/20260930T000000Z/
- Debian security archive:
  https://snapshot.debian.org/archive/debian-security/20260930T000000Z/

The snapshot timestamp is part of the build identity.

## Builder

Use mmdebstrap in CI.

Reasons:
- resolves Debian dependencies with apt;
- supports foreign architecture;
- supports explicit architectures;
- supports reproducible output with SOURCE_DATE_EPOCH;
- supports snapshot.debian.org configuration;
- does not require importing a prebuilt generic disk image.

The build script itself is authoritative and hashed into the release report.

## Initial root package policy

No desktop task.
No recommends unless explicitly named.
No generic Debian kernel.
No bootloader package required for the artifact.
No Mesa/Weston/Xwayland in C02.
No Box64/Wine/Steam.
No PipeWire/BlueZ yet.

The package list is stored separately in:
  native-r36os/c02/packages-base.txt

## R36OS overlay

C02 adds only:
- /etc/r36os-release
- minimal /etc/hostname
- deterministic machine-id policy
- basic NetworkManager policy
- prototype fstab describing external mounts for later C03 use
- R36OS native-root marker
- native health/inventory script that does not alter hardware

No current ArkOS /etc file is copied.

## Prototype filesystem intent

When C03 eventually stages this root on the handheld it will live at:
  /r36state/r36os-next/rootfs

Persistent paths will be mounted/bound separately:
  /r36state
  /roms2

C02 does not perform those mounts.

## Explicit forbidden content

The build fails if the root contains R36OS-added or copied payload matching:
- ArkOS / AeUX branding
- PortMaster runtime paths
- Westonpack / weston_pkg.squashfs / westonwrap
- CrustyGBM / libcrusty
- proprietary Mali/Bifrost r13p0 userspace
- EmulationStation service
- play-video.service
- networkwatchdaemon.service
- 351mp.service
- GO-Super/Gamepad hard requirement
- R36UPD stage2 as a boot requirement

Package documentation mentioning unrelated terms is not used as a runtime
dependency signal; the stricter check is applied to executable/configuration
paths and the R36OS overlay.

## Artifact outputs

C02 CI must produce:
- r36os-native-c02-rootfs-arm64.tar.zst
- rootfs SHA-256
- requested package list
- resolved dpkg package/version/architecture list
- full regular-file/symlink manifest with hashes/targets
- R36OS overlay manifest
- forbidden-dependency audit report
- build report including snapshot and tool versions

## Reproducibility

The validation job builds the rootfs twice from scratch.

PASS requires:
- requested package lists identical;
- resolved dpkg manifests identical;
- normalized filesystem manifests identical;
- overlay hashes identical;
- forbidden audit PASS.

Byte-identical compressed rootfs is desired and tested.  If metadata from dpkg
prevents byte-identical rootfs archives despite normalized manifests being
identical, that is treated as a build-system issue to resolve inside C02
before progressing.

## C02 exit criteria

1. Two independent builds pass.
2. Root architecture is arm64.
3. /sbin/init resolves to systemd.
4. systemd, udev and journald binaries/units exist.
5. kmod/module tools exist.
6. storage and diagnostic tool allow-list exists.
7. package manifest is pinned and complete.
8. no forbidden legacy runtime is included.
9. no kernel/Image/DTB/uInitrd is embedded.
10. artifact is not installed or published as the live R36OS update.
11. validation artifact and backup branch exist.

Only then does Chapter 3 begin.
