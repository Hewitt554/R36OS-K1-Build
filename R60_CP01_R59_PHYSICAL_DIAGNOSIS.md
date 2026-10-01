# R36OS R60 checkpoint plan — CP01 R59 physical diagnosis

Date: 2026-10-01
Base: published Alpha 5R59 / main 40f82f43d36299d988381ae189d07f516c120530
K1 candidate tested: 9d7bd2334f315d98b482f850
Kernel: 6.12.94-r36os-k1

## Physical evidence reviewed
Six R59 result bundles from the device:
- R36OS-Alpha5R59-results-20261001-074416.tar.gz
- R36OS-Alpha5R59-results-20261001-074451.tar.gz
- R36OS-Alpha5R59-results-20261001-075144.tar.gz
- R36OS-Alpha5R59-results-20261001-075238.tar.gz
- R36OS-Alpha5R59-results-20261001-075337.tar.gz
- R36OS-Alpha5R59-results-20261001-075357.tar.gz

## CP01 findings

### K1 boot / UI / controller
PASS.
- Kernel command line identifies candidate 9d7bd2334f315d98b482f850.
- Native R36OS shell starts.
- K1 split input path uses gpio-keys + adc-joystick.
- FN+Start quick menu is observed.
- Core self-test reports 17 pass / 0 fail.
- physical_controller=PASS.
- first_frame=PASS and framebuffer=PASS.

### Core diagnostic
PASS for current automated scope.
Latest regression-selftest:
- passes=17
- critical_failures=0
- warnings=1
- warning is uinput only.
The device has one unrelated failed legacy unit: 351mp.service.

### Wi-Fi
FAIL / current primary blocker.
Evidence:
- USB device enumerates as Realtek 0bda:0179 at high speed on 1-1.
- NetworkManager reports WIFI-HW=missing.
- No wlan network interface exists.
- No rtl8xxxu / cfg80211 / mac80211 binding messages appear in dmesg.
- USB diagnostic reports no RTL8188 module loaded.
Conclusion: R59 kernel contains the validated rtl8xxxu module, but the running K1 userspace never loads/binds it. This is now a runtime module-load/bind problem, not a missing USB device or missing compiled driver problem.

### Graphics Lab
FAIL before compositor/client startup.
Kernel graphics baseline itself is positive:
- rockchip DRM initialized.
- Panfrost probes Mali-G31 successfully.
- /dev/dri/card0, card1 and renderD128 exist.
Current Graphics Lab session:
- preflight starts under Alpha 5R59 / K1.
- session log stops at input_supervisor_pid=<pid> ready=no.
- Weston never reaches normal compositor startup in the new R59 attempt.
Conclusion: Graphics Lab is blocked at its input-supervisor readiness/handoff path before meaningful Weston/Panfrost validation. Do not diagnose this as Panfrost failure.

### Additional K1 issue observed
systemd-journald service/socket are missing or unavailable under K1, producing repeated "Failed to connect stdout to the journal socket" messages. This does not currently stop R36OS, but it weakens diagnostics and should become a later checkpoint after Wi-Fi/Graphics Lab.

## Checkpoint sequence
CP01 — COMPLETE: freeze physical diagnosis and recovery branches.
CP02 — Wi-Fi runtime load/bind fix only. Add explicit K1 rtl8xxxu load/bind verification and diagnostics. No Graphics Lab changes.
CP03 — Graphics Lab K1 input-supervisor/handoff fix only. Preserve working K1 UI/input semantics.
CP04 — Core/diagnostics quality: clear user-facing result, journald investigation, 351mp legacy-unit handling if K1-inapplicable.
CP05 — Combined regression validation and one R60 updater only after CP02+CP03 are independently green in CI/static tests.

Safety rules:
- K1 remains Boot Next Once.
- legacy 4.4 fallback remains untouched.
- preserve R49-R59 boot/update safety chain.
- no U-Boot raw writes.
- make a backup branch after every checkpoint.
