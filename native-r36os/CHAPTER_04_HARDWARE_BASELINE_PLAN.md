# Native R36OS Chapter 4 — hardware baseline plan

Date opened: 2026-10-01
Status: PREPARATION ONLY
Branch: work/native-c04-hardware-baseline-prep-2026-10-01
Parent checkpoint: backup/native-c03-final-green-2026-10-01

## Hard gate

Chapter 4 implementation may be prepared in advance, but Chapter 4 may not be
called started/green and no C04 boot package may be produced until the physical
C03 Boot Once result has been reviewed.

Required C03 prerequisite:
- native C03 reaches systemd and C03_HEALTH.conf reports PASS.

If C03 fails before native systemd, stay in Chapter 3.

## Chapter 4 goal

Prove that the clean ArkOS-independent root can operate the R36S/R36XX base
hardware without depending on ArkOS services, PortMaster or a graphics/gaming
stack.

Chapter 4 does not attempt:
- Wi-Fi association/driver selection: C05
- Mesa/Panfrost rendering: C06
- Weston/Xwayland: C07
- normalized game-controller/uinput layer: C08
- full R36OS shell: C09
- audio playback/Bluetooth/PipeWire: C10
- Box64/Wine/Steam: later chapters

## Chapter 4 sub-checkpoints

### C04A — native service/platform sanity
Required:
- Linux 6.12.94-r36os-k1
- PID 1 = systemd
- systemd-journald active
- systemd-udevd active
- /dev, /proc, /sys mounted
- R36STATE persistent log bind available
- exact K1 module tree available
- no failed critical native service

This is primarily a stronger continuation of the C03 health gate.

### C04B — storage and filesystem baseline
Passive:
- identify root backing path
- verify R36STATE mount and filesystem
- detect SD2 independently of ArkOS mount scripts
- inventory /boot and /r36update without writing them

Optional manually invoked active test:
- create a small temporary file on R36STATE
- fsync
- verify SHA-256
- delete it
- repeat on SD2 only after the correct user-data device/mount is identified

Never:
- repartition
- format
- resize filesystems
- write /boot as part of C04

### C04C — raw input/platform devices
Required enumeration:
- adc-joystick
- gpio-keys
- rk805/rk817 power-key input if exported by K1
- rk817 headphone/jack input if exported by K1

Chapter 4 proves kernel/udev enumeration only.
It does not create a virtual Xbox controller and does not require /dev/uinput.

### C04D — backlight/display-kernel interfaces
Required:
- a valid backlight class device
- readable current/max brightness
- current brightness in valid range
- DRM nodes/inventory recorded

No Mesa/EGL/GBM rendering requirement exists here.
Panfrost render testing is Chapter 6.

An optional brightness-write test will be designed but not auto-run.

### C04E — power/battery/charge interfaces
Discover by sysfs type rather than fixed battery pathname where possible.
Record:
- power-supply names/types
- battery status
- capacity
- voltage/current where exported
- charger/online state where exported

Values are evidence; Chapter 4 must not manufacture a battery percentage from
unknown fields.

### C04F — thermals and CPU frequency
Required discovery:
- at least one usable thermal-zone temperature
- CPU cpufreq policy/frequency information
- available governor/frequency limits where exported

Chapter 4 is observation only.
Performance tuning belongs later.

### C04G — USB/platform inventory
Required:
- USB host is enumerated
- onboard Realtek 0bda:0179 is visible as USB hardware
- exact bound driver is recorded if any

Wi-Fi functionality is deliberately NOT required for C04 PASS.
C05 owns the RTL8188EU driver decision.

### C04H — shutdown/reboot behaviour
Physical only:
- native userspace can perform a clean shutdown without hanging
- native one-shot semantics still return to the normal legacy path afterward

This cannot be proven in CI and remains pending until physical testing.

## Result model

Primary report:
- /r36state/logs/native-hardware/C04_BASELINE.conf

Detailed snapshots:
- /r36state/logs/native-hardware/C04_INPUT.txt
- /r36state/logs/native-hardware/C04_STORAGE.txt
- /r36state/logs/native-hardware/C04_POWER.txt
- /r36state/logs/native-hardware/C04_THERMAL.txt
- /r36state/logs/native-hardware/C04_USB.txt
- /r36state/logs/native-hardware/C04_DRM.txt

Each check uses:
- PASS: required function positively observed
- WARN: available but incomplete/non-blocking
- FAIL: required function missing/broken
- DEFERRED: belongs to a later chapter
- UNTESTED: physical action has not yet been performed

A Chapter-4 PASS must never hide a FAIL by converting it to WARN.

## Today / pre-physical work

Allowed now:
- result schema
- passive probe implementation
- synthetic-fixture CI
- optional storage active-test implementation
- K1 module/capability inventory
- documentation and recovery branch

Blocked until C03 physical PASS:
- adding C04 overlay to the native root
- producing C04 Boot Once candidate
- changing C03 native root
- claiming any C04 hardware check physically passed
- progressing to C05

## Exit criteria

Chapter 4 eventually closes only when physical evidence proves:
- native service base healthy
- R36STATE usable
- SD2 detected/mounted by R36OS-owned logic
- raw controller devices present
- backlight interface usable
- battery/charge interfaces present
- thermal/cpufreq interfaces present
- USB host/device inventory healthy
- clean native shutdown/reboot behaviour
- no ArkOS service/path is required for any of the above

Current status: PREPARATION ONLY.
