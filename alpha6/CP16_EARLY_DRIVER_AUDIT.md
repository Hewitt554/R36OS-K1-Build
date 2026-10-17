# R36OS Alpha 6 CP16 — K1 early storage-driver evidence audit

**Development only; not boot-tested, not flashable.** No stable firmware, BOOT partition, original R3 image or SD media is changed.

CP15 successfully built an ARM64 native root, 6.12.94-r36os-k1 kernel module tree and 1.23 MiB native initramfs. The initramfs currently has **no early kernel-module loader**. It therefore depends on the actual kernel having the MMC host/core, MMC block and ext4 filesystems available *built into the kernel* before it can find the root partition. A successful kernel build, valid uInitrd, or a complete `/lib/modules` tree on the new ext4 root is not evidence that drivers are usable **before** that root mounts.

## CP16 implementation

- Downloads the pinned September 30 K1 build artifact from GitHub Actions run `36763257082` using read-only permissions.
- Reuses CP13's full SHA-256-verifying historical artifact validator. Does **not** install anything or modify the original candidate.
- Streams K1's real nested `modules.tar.xz` and examines `modules.builtin`, `modules.dep`, and actual `.ko` inventory, checking exact kernel release.
- Looks for the compiled `.config` inside the verified archive, and if absent looks for a properly compressed `IKCFG_ST` configuration embedded in the kernel `Image`.
- Classifies critical ext4, journal, MMC core/block, DesignWare MMC host/Rockchip and pinctrl module identities as built-in, loadable module or not evidenced. Calculates the declared dependency closure for a modular driver, but **does not** stage or load it.
- If the exact compiled `.config` cannot be recovered, the report refuses to claim core `CONFIG_` prerequisites were verified. It will still report file-based evidence separately.
- Checks `CONFIG_BLK_DEV_INITRD`, `CONFIG_DEVTMPFS`, `CONFIG_PROC_FS`, `CONFIG_SYSFS`, `CONFIG_TMPFS`, `CONFIG_ARM64`, `CONFIG_BINFMT_ELF` when verified `.config` is available. Optionally records Rockchip clock, regulator and display configs without assuming a particular PCB/DTB is physically validated.
- Emits JSON with `safe_to_flash=false`, `boot_tested=false` and `early_boot_verified=false` regardless of which checks pass. There is no bootloader, flash image or automatic fallback in CP16.

## Important bounds

`modules.builtin` and `modules.dep` are evidence of how the archived modules were packaged. They are not a complete hardware hardware bring-up test. Drivers with differing filenames or built-in subsystems that do not publish a module identity may be reported as **unverified** even if present. CP16 does not validate the actual Panel 4 device-tree's storage topology, U-Boot architecture/addresses, SD slot ordering, display, RK817 power, input or battery support. No module dependencies are copied into the initramfs yet. Kernel `.config` is a primary verification source only when it can be tied to the matching verified kernel artifact.

## Next step depending on results

If the required drivers are demonstrably built in, proceed to review actual K1 device-tree storage controllers and physical spare-SD boot diagnostics. If any are modular, implement a version-pinned early module-loader and closure inside a **disposable** development initramfs, then verify its order and module signatures offline. If `.config` is absent, recover the original effective kernel config from the pinned build source or reproducible kernel build first. **Do not flash CP15 or CP16 as they stand.**