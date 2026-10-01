# Native R36OS migration — Chapter 0 frozen baseline

Date: 2026-10-01

This file freezes the exact pre-native-migration state.  It is intentionally
descriptive only: Chapter 0 makes no runtime, kernel, bootloader, updater,
partition, or device changes.

## Frozen public release

GitHub main at freeze:
- commit: c1f582edf876349269b4212aa6a78f1387aa7ecc
- commit title: Publish Alpha 5R60 update channel via verified carrier asset

Live update channel:
- R36OS Alpha 5R60 / package 0.5.60.0
- base package: 0.5.59.0
- updater asset: 00-R36OS-Alpha5R60-K1WiFiGraphicsLab-FromR59.r36upd
- size: 24880 bytes
- SHA-256: 0f17ef90423984f163a5a25a306c9bee346c24a958c921b03a1bda3ba01c05c2

K1:
- kernel: 6.12.94-r36os-k1
- candidate ID: 9d7bd2334f315d98b482f850
- K1 remains Boot Next Once only
- legacy Linux 4.4 fallback remains mandatory
- Panel-4 DTB, R54 uInitrd, R59 K1 Image/modules are frozen for this migration audit

Permanent Chapter-0 recovery branch:
- backup/native-c00-r60-freeze-2026-10-01

Working audit branch:
- work/native-c00-c01-baseline-audit-2026-10-01

## Physical R60 result used as the migration baseline

Five Alpha 5R60 result bundles were reviewed from the physical device.

What is physically proven under K1:
- Linux 6.12.94-r36os-k1 reaches userspace and the R36OS UI.
- R36STATE/root/storage paths are usable.
- Panel-4 / Rockchip DRM display path reaches a visible framebuffer/UI.
- K1 controller path works through split gpio-keys + adc-joystick handling.
- USB host enumerates the onboard Realtek Wi-Fi device 0bda:0179.
- Panfrost probes the Mali-G31 and DRM nodes are created.
- the R36OS core regression test reports 17 PASS / 0 FAIL, but this is no
  longer considered sufficient proof of complete K1 hardware health.

What is physically NOT working under K1:
- Wi-Fi does not provide a usable wlan interface.
- rtl8xxxu reaches the RTL8188EU/ETV firmware-start path but firmware startup
  fails and probe returns -11.
- Graphics Lab does not complete a rendered graphics test.
- the inherited graphics/session stack still contains ArkOS/PortMaster-era
  Westonwrap/CrustyGBM/proprietary-Mali assumptions.
- current Graphics Lab fault classification is not sufficiently diagnostic:
  a matching process entering D-state is currently promoted directly to a
  KERNEL_DRIVER_FAULT label without first preserving PID/wchan/kernel stack.
- journald/system service completeness under K1 is not yet clean.
- old/stale diagnostics still exist and can report misleading historical
  version/service assumptions.

## Why the migration starts now

The project has reached the limit of patching an ArkOS-derived userspace while
changing the kernel/hardware stack underneath it.

The migration goal is NOT:
- remove ArkOS files in-place;
- make K1 permanent immediately;
- repartition the user's current card immediately;
- replace the known-good legacy fallback.

The migration goal IS:
- keep the current R60/legacy environment recoverable;
- build a reproducible ArkOS-independent ARM64 R36OS userspace beside it;
- boot that userspace as a one-shot K1 candidate from R36STATE first;
- validate hardware in layers;
- later promote that userspace into a standalone R36OS A/B image only after
  the native environment is physically proven.

## Non-negotiable safety rules

1. Never overwrite/remove the known-good legacy 4.4 boot path during Chapters
   0-13.
2. K1 stays Boot Next Once until a later chapter explicitly proves otherwise.
3. Do not raw-write U-Boot during this migration.
4. Do not repartition the user's active card during the early native-root work.
5. Do not reuse inherited graphics/network components merely because they
   happen to be present.  Every dependency must be classified in Chapter 1.
6. One chapter = one narrow goal.
7. Every chapter ends with:
   - a design/decision document;
   - exact source/build inputs;
   - automated/static validation where possible;
   - a physical test procedure when applicable;
   - a result/evidence note;
   - a frozen backup branch.
8. If a chapter fails, stay in that chapter.  Do not hide the failure by
   modifying later chapters.
9. The live updater channel stays on the last physically tested release unless
   an explicitly validated test update is required.
10. A clean native userspace must never depend on an untracked ArkOS path.

## Chapter sequence

C00 — freeze R60 and migration safety baseline.
C01 — dependency audit / ArkOS fault map.
C02 — reproducible minimal ARM64 native rootfs.
C03 — safe native-root Boot Once / switch_root path.
C04 — minimal native hardware bring-up without graphics desktop.
C05 — Wi-Fi driver laboratory.
C06 — native Mesa/Panfrost graphics stack.
C07 — native Wayland/Weston/Xwayland.
C08 — native input/session architecture.
C09 — native R36OS shell/UI.
C10 — audio/Bluetooth/battery/time/power hardware.
C11 — Box64/Wine/native PC-gaming stack.
C12 — Steam/heavier gaming services.
C13 — native diagnostics/health matrix.
C14 — native A/B update/recovery architecture.
C15 — standalone flashable R36OS image and removal of ArkOS dependency.

## Chapter 0 exit criteria

PASS when:
- exact R60 public/live identity is recorded;
- permanent pre-native recovery branch exists;
- native-migration working branch exists;
- current K1 physical successes/failures are recorded;
- safety rules are written before Chapter 1 work begins.

Chapter 0 status: PASS.
