# CP14 — K1 kernel module ABI integrated with native ARM64 root (development)

**Not flashable, not boot-tested, not recovery-capable.** This checkpoint combines the real compiled K1 modules from GitHub Actions run 36763257082 with the clean Debian 12 ARM64 root from CP06 inside a disposable CI workspace, creates and checks a genuine ext4 filesystem image, then discards the image. Neither the R36S SD card nor any existing release is touched.

The CP13 provenance verifier checks the complete K1 candidate archive, SHA256 manifest, ARM64 kernel Image, panel device tree and U-Boot ramdisk header. CP14 streams the nested `modules.tar.xz`, refuses escaping paths, unexpected ABI names, symlinks other than discarded compiler `source`/`build` links, special files, and unexpected files outside `lib/modules`. The validated module tree is moved into the Debian usr-merged `/usr/lib/modules/6.12.94-r36os-k1` only after verification. Failure leaves the original clean root intact. It does not change the old K1 `uInitrd` or its embedded root mount assumptions.

CP14 then writes a **temporary scratch ext4 regular file** (no `losetup`, no SD device, no physical flash) from the combined root, runs read-only `e2fsck -fn`, records filesystem UUID, and uploads only a JSON compatibility report. The ext4 image is deleted after testing.

## Not fixed by CP14

1. Original K1.conf uses the legacy R3 root UUID, not the new scratch native root UUID. The pinned K1 candidate may omit the `state_uuid` and `modules_storage` identity fields and uses a U-Boot `IH_ARCH_ARM` uInitrd header. CP13 records these compatibility gaps. They must **not** be papered over by editing K1.conf without rebuilding and validating the actual initramfs and module-mount path.
2. K1 Linux 6.12.94 has not been booted on Panel 4 hardware. DTB manifest validation alone cannot prove LCD, backlight, RK817, controls or SD2 work.
3. No U-Boot early sectors, boot.ini, boot-slot hook, independent recovery selection, health watchdog or fail-safe rollback has been installed in a flashable OS image.
4. The CP06 Debian root does not yet contain a production launcher, graphics compositor or Box64/Wine runtime.
5. No production partition size is finalized. The test ext4 file is a disposable 4 GiB fixture, **not** a recommendation to consume 4 GiB of fixed root space.

## Next safe milestone

Rebuild the K1 initramfs with an explicit new-native-root filesystem identity and a documented init/root handoff, add a kernel-module ABI startup check, verify a read-only recovery route and bring up a spare SD on Panel 4. The original R3 image, Panel4 legacy kernel, SD media and main release channel remain untouched.