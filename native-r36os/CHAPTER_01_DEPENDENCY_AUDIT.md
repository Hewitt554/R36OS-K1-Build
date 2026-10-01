# Native R36OS migration — Chapter 1 dependency audit

Status: PASS
Date opened: 2026-10-01
Working branch: work/native-c00-c01-baseline-audit-2026-10-01
Frozen base: Alpha 5R60 / main c1f582edf876349269b4212aa6a78f1387aa7ecc

Chapter 1 is an audit only.  It must not alter the device runtime, K1 binaries,
live updater, bootloader, partition table, or current R60 installation.

## Evidence set

Physical R60 bundles reviewed:
- R36OS-Alpha5R60-results-20261001-091249.tar.gz
  SHA-256 35b149d6e5a6acb924da75f875677fc9d3ea8d51e9794beb3f2a238019d59060
- R36OS-Alpha5R60-results-20261001-091323.tar.gz
  SHA-256 6899b897fdbcad76f96055ee5498e7838eb322b9d120e3b05f608c1a84d2406d
- R36OS-Alpha5R60-results-20261001-091640.tar.gz
  SHA-256 b8539c88c8a885ac5d67bda42205db35cfaa010c65638fb07b06245ec19da08d
- R36OS-Alpha5R60-results-20261001-091713.tar.gz
  SHA-256 a2db41ad43c409ca411e6cc5f2106dad18ef5518be9ddc501a2b4e9f1fa042a7
- R36OS-Alpha5R60-results-20261001-091735.tar.gz
  SHA-256 df1f925ec0033b65d76662d34adffbf719ac10dc486b9a1a11ca2f36064d9403

Preserved source reference:
- R36OS_Alpha5R36_DEV_HANDOVER_2026-09-27.zip
- SHA-256 18409f46711c8c069d0a823d43b8a59cff68d46ff0543c12e26f09e062b83261
- 131 files under its source tree, including the R36OS UI/session/game/graphics,
  update, input, storage, power and compatibility source lineage used by later
  K1 releases.

Current R60 package:
- 00-R36OS-Alpha5R60-K1WiFiGraphicsLab-FromR59.r36upd
- SHA-256 0f17ef90423984f163a5a25a306c9bee346c24a958c921b03a1bda3ba01c05c2

## Classification vocabulary

KEEP-BOOTSTRAP
: retain temporarily only so the current card remains recoverable.

R36OS-OWNED
: source/component belongs in native R36OS, but may need cleanup/porting.

PLATFORM
: hardware-specific RK3326/R36S implementation; move behind a board/platform
  interface rather than hard-code throughout the OS.

REPLACE-NATIVE
: functionality is required but must come from the new native root, not the
  inherited ArkOS copy.

REMOVE-LEGACY
: inherited ArkOS/PortMaster/proprietary component that must not be in the
  native K1 execution path.

REVALIDATE
: potentially reusable data/runtime, but it is not trusted in the new root
  until physically retested there.

DEFER
: not required for the first minimal native-root milestone.

## Initial dependency map

| Area | Current state / evidence | Classification | Native R36OS direction |
|---|---|---|---|
| Raw RK3326 bootloader/U-Boot | Current card boots both legacy and K1; rollback works | KEEP-BOOTSTRAP | Preserve unchanged through early chapters. Replace/own only in late standalone-image work if necessary. |
| /boot FAT partition | Known-working legacy/K1 handoff | KEEP-BOOTSTRAP | Keep current layout while native root lives under R36STATE. |
| Legacy Linux 4.4.189 | Known recovery kernel | KEEP-BOOTSTRAP | Never place in native root. Retain only as fallback until standalone R36OS is proven. |
| K1 Linux 6.12.94-r36os-k1 | Boots UI, Panel 4, storage, USB, input and probes Panfrost | R36OS-OWNED / PLATFORM | Becomes native kernel baseline. Do not call every userspace failure a kernel failure. |
| Panel-4 DTB | Physically boots NV3051D-style 640x480 display | PLATFORM | Freeze current known-good DTB initially; audit every board-specific node in C04. |
| Current R54/K1 uInitrd | Enables current Boot Next Once and /opt/r36i handoff | KEEP-BOOTSTRAP | Replace with a small native R36OS initramfs in C03 after the new root exists. |
| ArkOS root on mmcblk0p2 | R60 still uses it as /; 9.9 GiB, ~6.9 GiB used | REMOVE-LEGACY | Do not delete. Native root first lives side-by-side under /r36state/r36os-next/rootfs. |
| R36STATE mmcblk0p4 | 48 GiB, ~38 GiB free in R60 evidence | R36OS-OWNED | Use for native-root staging, persistent state, logs, runtimes and recovery. |
| SD2 /roms2 | 239 GiB exFAT in current evidence | R36OS-OWNED data / PLATFORM mount | Preserve user data. Native OS owns mounting; do not depend on ArkOS mount scripts. |
| /opt/system/Tools bind from SD2 | Current ArkOS/PortMaster convention | REMOVE-LEGACY | Eliminate. Explicit R36OS paths replace PortMaster tool discovery. |
| systemd | Current root has systemd but several R36OS units are missing and legacy units remain | REPLACE-NATIVE | Native root supplies a pinned systemd and only intentional R36OS/platform units. |
| udev | Current hardware enumeration depends on inherited userspace rules | REPLACE-NATIVE / PLATFORM | Start from distro udev, then add explicit R36OS board rules only where proven necessary. |
| journald | R60 shows NetworkManager journal unavailable; diagnostics cannot rely on it | REPLACE-NATIVE | Native root must ship/start systemd-journald and validate persistent/volatile logging policy. |
| 351mp.service | Sole failed unit in latest R60 snapshot; inherited device fix | REMOVE-LEGACY | Do not port unless a Chapter-4 hardware audit proves a real requirement. |
| emulationstation.service | Masked by R36OS | REMOVE-LEGACY | Do not ship in native base. |
| play-video.service | Masked by R36OS | REMOVE-LEGACY | Do not ship in native base. |
| networkwatchdaemon.service | Masked by R36OS | REMOVE-LEGACY | Do not ship. Native networking owns link changes without reboot. |
| Plymouth | Current R36OS branding wraps inherited boot environment | REPLACE-NATIVE | Optional native package/theme after minimal boot works; not needed for first console bring-up. |
| NetworkManager | Runs successfully but reports WIFI-HW=missing because no wlan device exists | REPLACE-NATIVE package, concept retained | Use a clean native NetworkManager configuration initially unless later testing justifies iwd-only. |
| Realtek USB device 0bda:0179 | Enumerates reliably at USB high speed | PLATFORM | Board profile records exact device; C05 decides driver. |
| rtl8xxxu | Module loads and identifies RTL8188EU rev D, loads firmware revision 11.1, then firmware fails to start; probe -11 | REVALIDATE / DRIVER-LAB | Do not bake into native platform as the final choice yet. Compare current/upstream rtl8xxxu with a maintained 8188EU vendor-derived driver in C05. |
| Legacy r8188eu/8188eu path | Same physical adapter works under legacy 4.4 | REFERENCE ONLY | Use as behavioral reference and source of hardware quirks; do not copy old binary driver into K1. |
| Rockchip DRM/KMS | Drives visible K1 framebuffer/panel | PLATFORM | Keep kernel side; validate clean userspace DRM access in C06. |
| Panfrost kernel driver | Mali-G31 probes and DRM nodes exist; no proven GPU MMU/Oops fault in R60 test | PLATFORM | Keep as K1 GPU kernel driver unless later direct native evidence disproves it. |
| ARM proprietary Bifrost r13p0 EGL/GLES | R60 Weston log still reports EGL vendor ARM, Bifrost r13p0 | REMOVE-LEGACY for K1 | Must never be selected in native K1 graphics path. Legacy 4.4 may continue using it only in fallback root. |
| CrustyGBM / libcrusty | R60 game/graphics logs show it being injected into Weston | REMOVE-LEGACY | Do not include in native K1 root. |
| Westonpack/westonwrap | Runtime identifies ArkOS AeUX and carries its own graphics stack | REMOVE-LEGACY for native K1 | Native root installs normal Weston built against its own Mesa/libdrm/GBM/EGL. |
| Xwayland from Westonpack | Coupled to inherited Weston image | REMOVE-LEGACY | Native root supplies distro/native Xwayland after pure Wayland graphics works. |
| Mesa/Panfrost userspace | Not yet the authoritative K1 userspace graphics path | REPLACE-NATIVE | C06 installs a pinned modern Mesa stack and proves renderer=panfrost before Weston/games. |
| libgbm/libEGL/libGLESv2 | Existing R36 probes dynamically depend on these and current paths can resolve inherited ARM stack | REPLACE-NATIVE | Native root owns all three libraries and loader paths. Build must fail if K1 resolves proprietary ARM copies. |
| libX11 | Needed by later Xwayland probes/HUD | REPLACE-NATIVE | Add only after native Wayland/DRM path is proven. |
| SDL2 | Some old diagnostics depend on it | DEFER | Do not use SDL as the first graphics proof. Add later for games/UI utilities as required. |
| gpio-keys | K1 physical button half works | PLATFORM | Keep direct Linux input device; board profile maps logical controls. |
| adc-joystick | K1 analogue axis half works | PLATFORM | Keep direct Linux input device; board profile combines semantics. |
| old r36os-input-supervisor | Assumes one GO-Super/Gamepad and /dev/uinput | REMOVE-LEGACY design | Redesign in C08. Do not make native graphics depend on a virtual controller. |
| /dev/uinput | Missing in current K1 | REVALIDATE | Decide intentionally in C08 whether kernel should enable it for compatibility/game mapping. |
| gptokeyb PortMaster search paths | Current game session searches /opt/system/Tools/PortMaster etc. | REMOVE-LEGACY | Replace with R36OS-owned input translation if still required. |
| RK817 power key | event0 physically present | PLATFORM | Native power policy built on normal Linux input/logind integration. |
| RK817 headphone input | event1 physically present | PLATFORM | Audit ALSA/jack behavior in C10. |
| battery sysfs helpers | Current code uses fixed /sys/class/power_supply/battery paths | PLATFORM | Move all battery/charge paths into hardware profile and validate accuracy. |
| backlight sysfs helpers | Current code assumes /sys/class/backlight/backlight | PLATFORM | Move to board profile; preserve FN brightness behavior above it. |
| ALSA/amixer | Current utilities expect amixer and old audio compatibility units | REPLACE-NATIVE | Native ALSA first, then PipeWire/WirePlumber in C10. |
| PipeWire/WirePlumber | Planned but not current reliable baseline | DEFER until C10 | Install natively for game/audio/microphone routing after ALSA hardware works. |
| BlueZ | Planned | DEFER until C10 | Native BlueZ, no ArkOS Bluetooth helper inheritance. |
| Box64 | R36OS owns runner policy; binaries/runtimes stored separately | REVALIDATE | Keep architecture, rebuild/revalidate exact ARM64 host integration under native root in C11. |
| Wine WOW64 | Versioned under R36STATE | REVALIDATE | User/runtime data may be reused, but host library/display assumptions must be retested under native root. |
| Weston image inside Windows runtime | Currently required by game launch | REMOVE-LEGACY | C11 must launch Wine against native R36OS compositor/display stack instead. |
| Wine prefixes | User/game state under R36STATE | R36OS-OWNED data | Preserve; migrate non-destructively and validate rather than recreate unnecessarily. |
| Steam management | R36OS scripts exist but not a core boot dependency | DEFER | C12 only after graphics/network/input/Wine are stable. |
| r36os-alpha5 framebuffer UI | Static AArch64 R36OS-owned binary; proven on K1 | R36OS-OWNED | Valuable early native UI candidate after C04; first native root may use console/diagnostic shell before UI. |
| r36os-session and R36OS helpers | R36OS-owned but assume inherited service/file paths in places | R36OS-OWNED / PORT | Port selectively. No bulk-copy of /usr/local/bin into native root. |
| r36os-core-integrity | Useful concept but current health coverage is incomplete | R36OS-OWNED / REDESIGN | Native integrity hashes plus hardware-stage health matrix in C13. |
| current 17-pass regression test | Can pass while Wi-Fi and graphics are unusable | REPLACE-NATIVE diagnostic definition | C13 PASS criteria must prove actual device functionality, not only file/service presence. |
| USB diagnostics | Old helper reports Alpha 5R3 and calls missing lsusb | REMOVE stale helper / REPLACE-NATIVE | Native root includes usbutils and authoritative release identity. |
| update .r36upd system | Works for current ArkOS-derived root | KEEP-BOOTSTRAP | Continue only for transition/recovery. Native A/B updater replaces it in C14. |
| SSH/dropbear helpers | Current code can use ssh/sshd/dropbear | REPLACE-NATIVE policy | Pick one intentional recovery daemon (likely OpenSSH) and keep disabled unless enabled by user/recovery mode. |
| zram service | R36OS-owned tuning exists | R36OS-OWNED / REVALIDATE | Native root can use a simpler generator/service after real memory measurements. |
| cgroup/resource tuning | Current root exposes mixed cgroup v1 + v2 | REVALIDATE | Native root should deliberately choose/configure one supported systemd cgroup model. |
| time/timezone | Current R36OS has custom timezone offset handling | REPLACE-NATIVE + R36OS UI | Native system clock/timezone/NTP primitives; UI only configures them. |

## Key architecture findings already established

### 1. The current root is still structurally ArkOS-derived

The R60 physical root is /dev/mmcblk0p2, while R36OS overlays its own binaries,
systemd drop-ins and state on top.  The native migration must stop treating
that inherited root as the package/library authority.

### 2. Graphics is the strongest REMOVE-LEGACY area

R60 physical logs show the external runtime advertising ArkOS AeUX,
loading Crusty, and reporting:
- EGL vendor ARM
- EGL 1.4 Bifrost r13p0
- GL renderer Mali-G31

That proves the K1 test path is still resolving the old proprietary Mali
userspace rather than a deliberately owned Mesa/Panfrost userspace.  The native
root must not inherit Westonpack, CrustyGBM or those ARM EGL/GLES libraries.

### 3. Wi-Fi failure is below NetworkManager

R60 proves:
USB enumeration -> rtl8xxxu probe -> RTL8188EU identification -> firmware file
load -> firmware revision read -> firmware start FAIL -> probe -11.

NetworkManager correctly has no Wi-Fi hardware to manage afterward.  C05 must
therefore treat this as a driver/firmware laboratory, not a NetworkManager UI
problem.

### 4. The current mount layout gives us a safe migration path

R60 evidence:
- /dev/mmcblk0p2 -> / (legacy root)
- /dev/mmcblk0p4 -> /r36state (~48 GiB)
- /dev/mmcblk1p1 -> /roms2
- /dev/mmcblk0p1 -> /boot
- /dev/mmcblk0p3 -> /r36update

R36STATE has sufficient free space for the first native rootfs.  Therefore the
initial native root can be staged under R36STATE without repartitioning or
destroying the current root.

### 5. Native R36OS must own dependency resolution

Current scripts explicitly rely on tools such as:
- systemctl/systemd-inhibit
- mount/umount/losetup/findmnt/lsblk/blkid
- curl/wget
- tar/gzip/xz/lz4/zstd/cpio
- sha256sum
- nmcli/rfkill/ip
- modprobe/insmod
- amixer
- chvt
- plymouth
- file/readelf/strings
- 7z/cabextract/bsdtar
- resize2fs/sfdisk/fdisk
- OpenSSH/dropbear variants
- Box64/Wine runtimes

Chapter 2 must turn this into a pinned package manifest rather than depending
on whatever ArkOS happens to provide.

## Native-root package groups implied by this audit

The exact distro/package versions are NOT locked yet, but the first root will
need explicit package groups rather than inherited binaries.

BASE:
- systemd + udev
- bash/dash/coreutils
- util-linux
- procps
- findutils
- grep/sed/gawk
- kmod
- iproute2
- filesystem/mount tools
- ca-certificates
- compression/archive tools needed by R36OS recovery

DIAGNOSTICS:
- usbutils
- pciutils only if useful on this platform
- file/binutils readelf/strings
- ethtool/iw/rfkill
- strace
- systemd-journald/journalctl
- debugfs/pstore access tooling

NETWORK:
- NetworkManager initially
- wpa_supplicant or iwd selected explicitly
- iproute2
- wireless-regdb
- exact selected RTL firmware package/files

GRAPHICS (not in first console-only boot unless needed by C06):
- libdrm
- Mesa Panfrost
- GBM/EGL/GLES
- later Weston
- later Xwayland/libX11

AUDIO (deferred):
- alsa-utils
- later PipeWire/WirePlumber
- BlueZ later

GAMING (deferred):
- Box64
- Wine
- x86-64 compatibility libraries/runtime
- Steam later

## Filesystem/path decisions for the native prototype

Initial native root location:
- /r36state/r36os-next/rootfs

Persistent data remains outside root:
- /r36state/config
- /r36state/logs
- /r36state/wine-prefixes
- /r36state/runtimes
- /roms2 for user/game content

Forbidden native dependencies:
- /opt/system/Tools/PortMaster
- ArkOS EmulationStation services
- ArkOS networkwatch daemon
- play-video service
- proprietary ARM Bifrost r13p0 EGL/GLES under K1
- CrustyGBM/libcrusty
- Westonpack as the K1 system compositor
- stale release-specific helper identities

## Deferred reference captures

A read-only collector has been built and CI-tested for old-root package, fstab,
udev, firmware, ALSA and live-device-tree inventory.  It is deliberately NOT
being pushed to the device as another instrumentation release.

Those facts are not required to construct the clean root because Chapter 2 is
forbidden from copying the inherited package/configuration set.

Hardware-specific unknowns are assigned to the chapters that own them:
- Wi-Fi driver/firmware: C05.
- Mesa/Panfrost graphics userspace: C06.
- input normalization/uinput: C08.
- ALSA/RK817/audio/Bluetooth: C10.
- final complete health matrix: C13.

The collector remains available if one of those chapters needs comparison
against the inherited system.

Chapter-2 base decision:
- Debian 13 trixie arm64 userspace.
- R36OS K1 remains the kernel/platform.
- package versions will be pinned to a repository snapshot in C02.
- C02 root boundary/forbidden-dependency contract is already written.

## Chapter 1 exit criteria

Do not begin Chapter 2 until:
- every required current dependency is classified;
- no known ArkOS/PortMaster/proprietary graphics component is accidentally in
  the K1 native plan;
- the minimum rootfs package list is explicit;
- the hardware/platform profile inputs are explicit;
- all unknowns are either resolved or intentionally assigned to a later
  hardware chapter;
- a Chapter-1 backup branch and handover exist.

Current Chapter 1 status: PASS.
