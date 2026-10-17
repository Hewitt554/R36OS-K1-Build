# R36OS Alpha 6 — CP12: whole-disk CI assembly smoke test

**Not bootable. Not for SD-card flashing.** This checkpoint creates and then destroys a real four-partition **disposable disk image** during GitHub Actions. It is intended to verify the builder's file layout, filesystem integrity and integration of the previously built native ARM64 root plus diagnostic recovery ramdisk. The GitHub artifact is only a small JSON validation report, **not** the image.

## CP12 construction

On a fresh Ubuntu ARM64 CI runner, CP06 builds a Debian 12 ARM64 rootfs; CP07 separately builds an ARM64 rescue `uInitrd`. CP12 creates four separate filesystem images with actual mkfs.fat and mkfs.ext4, unpacks the native root into `R36SYS`, stores the rescue image as a **non-active file** in `R36BOOT`, and assembles an MBR image with four aligned partitions:

| Partition | CI fixture size | Filesystem | Contents |
|---|---:|---|---|
| R36BOOT | 128 MiB | FAT32 | diagnostic-only rescue file, warning text; NO boot.ini/bootloader/kernel |
| R36SYS | 1 GiB | ext4 | CP06 native ARM64 root, disabled updater |
| R36UPDATE | 64 MiB | FAT32 | empty staging filesystem |
| R36STATE | 128 MiB | ext4 | empty persistent-data filesystem |

The image starts with a reserved 16 MiB early bootloader region containing **no bootloader**. It checks MBR geometry/non-overlap, filesystem signatures, byte-for-byte partition SHA256 after assembly, read-only filesystem checks (`e2fsck -fn`, `fsck.fat -n`) and whole-image SHA256. No mount, loop device or block-device write occurs. The image is deleted at the end of a successful job; only the report is retained.

The CI layout sizes are **deliberately scaled** and are not the provisional production capacities. CP11's 64 GB disk simulation considers 512 MiB R36BOOT, 8–12 GiB R36SYS, 1 GiB R36UPDATE and the rest R36STATE, but final sizing requires hardware and software measurements.

## What CP12 does NOT establish

- No legacy R3 bootloader or actual 5108-byte verified `boot.ini` is installed. The first 16 MiB is intentionally blank.
- No bootable Linux `Image` or Panel 4 `dtb` is staged. The K1 6.12 kernel remains unbooted on this handheld.
- The CP07 rescue is a data file only. The independent recovery boot gate and hardware recovery are not enabled or tested.
- The CP06 native Debian root lacks a production R36OS UI, hardware drivers, games, Box64/Wine and functioning updater/recovery integration.
- No end-to-end hardware validation, dynamic partition expansion, compressed snapshot sizing, spare SD flash test or guaranteed power-loss recovery.

This is a **builder integration test, not a release image**. Never flash the CI test fixture even if the job passes.