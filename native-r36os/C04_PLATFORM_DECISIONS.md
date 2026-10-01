# Native R36OS C04 — platform decisions

Status: PREPARATION
Date: 2026-10-01

These are architecture decisions that do not require the C03 physical result.

## 1. C04 stays console/platform-only

The first C04 root must not add:
- Mesa userspace
- Weston
- Xwayland
- Box64
- Wine
- Steam
- PipeWire
- Bluetooth services
- old ArkOS frontend/services

The purpose is to isolate hardware/platform failures from higher layers.

## 2. Network is not a C04 boot dependency

NetworkManager remains installed because Chapter 5 will use it, but native C04
health must not wait for Wi-Fi, DHCP or network-online.

C04 only proves:
- USB host is alive;
- Realtek 0bda:0179 physically enumerates;
- bound driver state is recorded if present.

RTL8188EU functionality is Chapter 5.

## 3. R36STATE is authoritative persistent state

The native initramfs owns early discovery/mount of R36STATE.

C04 must not remount/reformat/resize R36STATE.

Persistent C04 paths:
- /r36state/logs/native-hardware/
- /r36state/config/ for future accepted platform configuration

All active C04 tests write only small temporary files and remove them.

## 4. SD2 is discovered, then adopted by UUID

Permanent native configuration must not assume that the games card is always:
- /dev/mmcblk1
- /dev/mmcblk1p1

Initial discovery rule:
1. identify the block device backing R36STATE;
2. enumerate other mmc partitions;
3. inspect filesystem type without mounting;
4. find plausible user-data filesystems, currently expected exFAT;
5. exclude boot/update/state partitions;
6. if there is exactly one plausible candidate, report it;
7. do not auto-mount it until it has been explicitly adopted.

After physical confirmation, record:
- filesystem UUID
- expected filesystem type
- mountpoint=/roms2

in an R36OS-owned configuration under R36STATE.

Future boots mount by UUID, not by mmc device number.

If zero or multiple candidates exist, fail closed and ask for selection instead
of guessing.

## 5. Raw input only in C04

C04 hardware contract:
- gpio-keys exists
- adc-joystick exists
- power-key input exists
- headphone/jack input is recorded if present

No virtual Xbox device is created.
No event device is grabbed.
No /dev/uinput requirement exists.

Detailed button mapping and compatibility normalization remain Chapter 8.

## 6. Backlight test is explicit and restorative

Passive C04 only reads brightness/max-brightness.

The optional active test:
- selects one writable backlight class device;
- changes brightness by exactly one safe step;
- reads it back;
- restores the original value even on interruption;
- reports FAIL if restore cannot be verified.

It is never run automatically during boot.

## 7. Power/battery values are reported, not invented

The platform probe discovers power supplies by sysfs type.

It may record:
- status
- capacity
- voltage/current
- charge/energy values
- charger online state

If the kernel does not export a usable capacity value, C04 reports that fact.
It must not calculate a fictional percentage from unverified voltage curves.

## 8. Thermals/cpufreq are observational

C04 validates:
- at least one readable thermal zone
- at least one readable cpufreq policy

It does not change:
- governors
- min/max frequencies
- OPP tables
- thermal trips

Performance tuning comes only after a stable native platform exists.

## 9. DRM kernel nodes are a C04 requirement

C04 does not render graphics, but the kernel-level display/GPU device model
must still be present.

Therefore:
- missing /dev/dri nodes is a C04 FAIL;
- successful EGL/GBM/Panfrost rendering is deferred to C06.

This keeps kernel enumeration separate from graphics userspace validation.

## 10. systemd/journald/udev are critical

C04 requires:
- PID1=systemd
- systemd-journald active
- systemd-udevd active

The current C02 native root intentionally uses a small volatile journal.
Hardware snapshots are separately persisted under R36STATE.

## 11. Prefer unified cgroup v2

Debian 13 + modern systemd should normally expose unified cgroup v2.

C04 records this as:
- PASS when cgroup.controllers is present;
- WARN otherwise.

No cgroup tuning is done in C04.

## 12. zram stays out of the first hardware baseline

The old R36OS uses aggressive zram ideas, but C04 should first measure:
- base native RAM use
- service footprint
- kernel slab/cache
- idle pressure

Only later do we choose a native zram policy.

## 13. Clean shutdown is a physical-only gate

Automated CI must never simulate C04 completion by merely finding
systemctl/poweroff binaries.

The physical test must prove:
- systemd clean shutdown reaches power-off;
- no shutdown hang;
- next power-on returns through the expected one-shot/fallback path.

## 14. C04 result semantics

C04_BASELINE.conf may report overall=PASS for its passive checks, but also
always reports:

chapter4_complete=no

until the separately reviewed physical active tests are complete.

This prevents a passive diagnostic from being mistaken for a finished chapter.
