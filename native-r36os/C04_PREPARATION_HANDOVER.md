# Native R36OS Chapter 4 preparation handover

Date: 2026-10-01
Status: PREPARED / BLOCKED_ON_C03_PHYSICAL_PASS

Working branch:
- work/native-c04-hardware-baseline-prep-2026-10-01

Current prepared head:
- 71ee3290fa6ef8bcb99e99e90b4241c7d0a10582

Parent frozen C03 engineering checkpoint:
- backup/native-c03-final-green-2026-10-01
- 9bf1c2930130d0b7d5eaca0bead20f4ec3a6fe12

## Important chapter boundary

Chapter 4 has NOT been started as a physical/native-root milestone yet.

The repository now contains C04 design, probes, tests and an offline K1
platform audit, but no C04 native boot candidate may be produced until the
physical C03 Boot Once result is reviewed and its exact C03_HEALTH.conf reports
PASS.

If C03 fails, stay in Chapter 3 and ignore the prepared C04 execution path.

## Green preparation validation

Main C04 preparation CI:
- run: 36928163751
- job: 110590527049
- result: PASS

Passed:
- preparation branch changes only allowed C04 paths/workflows;
- passive probe shell/safety checks;
- privacy checks;
- fail-closed physical C03 gate validator;
- healthy synthetic R36S fixture -> PASS;
- missing gpio-keys/battery fixture -> FAIL;
- manual R36STATE write/read/hash/delete helper;
- bounded brightness change/readback/restore helper;
- UUID-based SD2 discovery;
- multiple SD2 candidates -> WARN / no guessing.

## Frozen K1/platform audit

Workflow:
- run: 36927824901
- job: 110589403346
- result: PASS
- artifact: 11194771043
- name: R36OS-Native-C04-frozen-K1-platform-audit

Inputs:
- R38 full K1 carrier for the exact Panel-4 DTB.
- R59 current K1 module tree.
- Panel-4 DTB SHA-256:
  e2145905b1beb8d0f5b9dee6c5a21d31c29474be8762c893e81506fc40e627f4
- K1 candidate:
  9d7bd2334f315d98b482f850
- kernel:
  6.12.94-r36os-k1

Confirmed present in K1 module metadata:
- adc-joystick
- gpio_keys
- rk805-pwrkey
- rk817 charger support
- RK817 audio codec support
- pwm backlight
- rockchip thermal
- cpufreq-dt
- DWC2
- exFAT
- Panfrost
- Rockchip DRM

Previously proven built-in and revalidated:
- ext4
- MMC core
- MMC block
- dw_mmc
- dw_mmc-rockchip
- Panfrost

Relevant DTB content confirmed:
- two MMC aliases used by the board
- CPU OPP table
- SOC/GPU thermal zones
- RK817 PMIC
- charger node
- DWC2 USB node
- multiple MMC controllers
- Mali-G31/Bifrost GPU node used by Panfrost
- adc-joystick
- simple-battery
- pwm-backlight
- gpio-keys
- RK817 sound card / headphone detect routing

This strongly supports the current Chapter-4 design: the frozen K1 kernel/DTB
already contains the basic platform pieces we need, so C04 should focus first
on native userspace ownership, udev/module loading and hardware verification
rather than another kernel rebuild.

## Prepared C04 tools

### r36os-native-c04-baseline
Passive/read-only hardware baseline.

Checks:
- exact K1 kernel
- systemd PID1
- journald
- udevd
- R36STATE
- K1 module tree
- adc-joystick
- gpio-keys
- rk805 power key
- RK817 headphone input
- backlight
- battery
- charger interface
- thermal zone
- CPUfreq
- USB 0bda:0179 enumeration/bind state
- DRM nodes
- SD2 mount status
- cgroup-v2 state

Explicitly marks as deferred:
- functional Wi-Fi -> C05
- rendered GPU test -> C06
- audio playback -> C10

Explicitly marks as untested:
- active storage write test
- active brightness write/restore
- clean physical shutdown

Even when passive overall=PASS, it writes:
- chapter4_complete=no

until the physical active gates have been reviewed.

### r36os-native-c04-snapshot
Privacy-safe read-only evidence capture.

Captures:
- native/kernel identity
- service status
- block/mount topology
- input device names
- backlight
- battery/charger
- thermal zones
- CPUfreq
- exact Realtek USB enumeration
- DRM nodes/drivers
- relevant modules
- filtered hardware-related dmesg

Intentionally avoids:
- SSIDs
- Wi-Fi scans
- passwords/PSKs
- saved connections
- MAC-address dumps
- IP-address dumps

### r36os-native-c04-storage-test
Manual only.

Allowed targets:
- /r36state
- /roms2

Procedure:
- write canonical tiny payload
- fsync
- SHA-256 readback
- delete
- sync

Refuses arbitrary paths.

### r36os-native-c04-brightness-test
Manual only.

Procedure:
- locate one writable backlight class device
- save original brightness
- move by exactly one safe step
- read back
- restore original
- verify restore
- trap interruption and attempt restore

Never auto-runs.

### r36os-native-c04-storage-discover
Read-only SD2 discovery.

Strategy:
- find R36STATE source
- identify its parent MMC device
- enumerate exFAT partitions on other block devices
- if one candidate exists, report device/filesystem/UUID
- if zero candidates, WARN
- if multiple candidates, WARN and require selection
- never mount automatically
- never assume /dev/mmcblk1p1 permanently

Future adopted storage is intended to be mounted by UUID.

### validate_c03_physical_gate.py
Prevents accidental progression into C04.

Required identities:
- physical-r36s evidence source
- C03 candidate:
  8f8eaa3bae6ad4352b4e01ef
- C03 rootfs:
  08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4
- K1:
  9d7bd2334f315d98b482f850
- kernel:
  6.12.94-r36os-k1
- C03 health PASS / native-systemd-healthy
- PID1=systemd
- real non-placeholder hashes for C03_HEALTH and uploaded evidence bundle

## Architecture decisions frozen

- C04 remains console/platform-only.
- Network must not be a C04 boot dependency.
- R36STATE remains authoritative persistent state.
- SD2 is discovered then adopted by UUID.
- no hardcoded permanent /dev/mmcblk1p1 path.
- raw physical input only; no uinput/virtual controller requirement.
- battery values are read from exported kernel interfaces, not invented.
- thermals/CPUfreq are observational only.
- DRM kernel nodes are required, but rendering is C06.
- unified cgroup v2 is preferred and recorded.
- zram tuning waits until native RAM usage is measured.
- clean shutdown is a physical-only C04 gate.

## What is intentionally NOT done yet

No C04 rootfs has been built.
No C04 uInitrd has been built.
No C04 boot hook has been built.
No C04 updater has been built.
No C04 package has been published.
No live release channel has moved.
No current R60/C03 files on the handheld have changed.

## Tomorrow's decision point

If C03 physical Boot Once FAILS:
- stop;
- review C03_EARLY/C03_HEALTH/boot-stage evidence;
- remain in Chapter 3;
- make no C04 candidate.

If C03 physical Boot Once PASSES:
1. create reviewed C03 physical gate file from the actual uploaded evidence;
2. consume the exact frozen C03 root as the C04 parent;
3. add the prepared C04 passive/snapshot/manual tools to the native root;
4. implement R36OS-owned SD2 adoption/mount flow;
5. build a new candidate-bound C04 root/uInitrd/Boot Once package;
6. validate it twice and freeze it;
7. perform the C04 physical baseline;
8. test storage, brightness and clean shutdown explicitly;
9. close Chapter 4 only after the resulting physical evidence passes.

Current C04 status:
PREPARED / WAITING_FOR_C03_PHYSICAL_RESULT
