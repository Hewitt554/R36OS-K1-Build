# R36OS Alpha 6 CP17 — Static Panel 4 DTB and First-Boot Diagnostics

**STATUS: SOURCE + DISPOSABLE ARM64 CI ONLY. DO NOT FLASH OR INSTALL.**

CP16 verified that ext4, JBD2, MMC core/block, DesignWare Rockchip host, and Rockchip pinctrl were compiled into the pinned Linux 6.12.94 K1 kernel. It did not establish that the Panel 4 display, buttons, regulators or MMC device-tree wiring function on physical R36S hardware.

## What CP17 builds

1. A minimal self-contained diagnostic `/init` using only the statically linked BusyBox and a statically compiled Linux framebuffer helper. It mounts only proc, sysfs, devtmpfs and RAM-backed tmpfs. It **never mounts an SD partition** and has no updater or restoration functions.
2. It prints kernel version, model, `/sys/class/graphics/fb*`, DRM connectors, MMC devices, input event nodes and power-supply names to the early console. Diagnostic output is **not saved to a file or network**; if the kernel console isn't displayed, user observation/serial access would still be needed.
3. If `/dev/fb0` is present, it attempts to draw coloured bars and a simple R36OS CP17 test banner in framebuffer **video RAM only**. Only 16/32-bit Linux fbdev geometry is supported; DRM-only devices will not display this test. A successful call does not prove colours, orientation, timing or Panel 4 electrical compatibility.
4. When there is no framebuffer, diagnostic messages remain on the early kernel console if that console works. It does not claim the screen works. By default the init stays on screen and waits, without rebooting. A manual diagnostic shell is opt-in via `r36os.cp17_shell=1`, **not** set by the builder.
5. Builds two mutually alternative U-Boot ramdisks from identical compressed ARM64 userspace: one with U-Boot architecture id ARM=2 and one ARM64=22. Both are for offline format validation. The real U-Boot's acceptance of either is unknown.
6. Strictly verifies the **pinned historical K1 artifact** with the existing CP13 manifest verifier. It parses the actual `rk3326-r36s-k1.dtb` Flattened Device Tree without executing it, reports root compatibles, enabled MMC nodes, DSI/panel candidate nodes, RK817/power and GPIO-key candidate nodes. A syntactically valid DTB is not proof of display function or correct wiring.

## CI behaviour

The ARM64 GitHub workflow builds the independent initramfs and static C framebuffer helper, validates both U-Boot headers with CRCs, checks the DTB's structure, and uploads **diagnostic artifacts only**. CI intentionally never creates or patches a live boot.ini, U-Boot image, RECOVERY.ON marker, SD disk image, recovery restore routine, or flashable system.

## What is still required for a safe *physical* test

- Original R3 `boot.ini` (exact 5108 bytes with SHA-256 `b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e`) obtained **read-only** via existing CP11 tool. Nothing in CP17 reuses or modifies this script.
- Review legacy U-Boot/Panel 4 addresses/selection and choose verified header format. Early bootloader sectors need to be copied from a known-valid spare card image, not recreated or written to the user's active SD1.
- A fresh **spare SD card only** and a tested, independent way to boot the known-working R3 OS if K1 fails. Merely including a recovery ramdisk in BOOT is insufficient. Never write CP17 files to the current SD1 or overwrite ArkOS/R3 without verified fallback.
- Physical K1 boot, visible framebuffer test, MMC-root detection, input event presence, RK817 status and actual read-only root handoff still untested.

No new downloads, diagnostics, or SD operations are required on the user's Windows PC just to run this GitHub CI workflow. It is **not** a first-boot test report until someone explicitly tests it on real hardware.

## Static K1 DTB findings (October 14 CI)

The pinned K1 device tree identifies the RK3326 board and has **two enabled actual MMC host nodes** at `/mmc@ff370000` and `/mmc@ff380000`. Older reports included pinctrl group names in the MMC count; the CP17 classifier now excludes those pin groups. The device tree exposes `/dsi@ff450000` and `/dsi@ff450000/panel@0` with a **generic** panel compatible `rocknix,generic-dsi` rather than an explicit NV3051D compatible. It also contains the RK817 PMIC compatible. That is static evidence of node declarations only, not proof that the display will initialise or match the Panel 4 640x480 timing.