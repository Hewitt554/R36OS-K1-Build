# CP11 Engineering report

## What is confirmed before physical boot

1. CP01 previously audited the original Alpha 5R3 BOOT FAT32 partition (112 MiB), extracted boot-choice lines, and recorded the boot.ini's SHA256. Original full bytes were not in the audit report.
2. CP08's candidate generator was checksum-pinned but only tested on fixture input. CP11 now composes the actual CP01 FAT32 reader with that exact CP08 candidate function without altering either upstream module.
3. The Windows executable `.cmd` uses `%~1` (quoted drag-and-drop image path) and `%~dp0` for scripts/reports. No Linux ext4 tooling or admin permissions required.
4. `cp11_extract_validate.py` verifies exact image byte length, BOOT partition start/type/size, FAT32 BOOT label, boot.ini size and SHA256, and the CP08 hook's byte-for-byte removal back to the original. It refuses all changed/unknown scripts and only writes to a uniquely named result directory outside the original image.
5. 16 local tests run on a constructed FAT32 MBR fixture; CP08's strict production pin rejects this synthetic fixture. Full real-R3 validation is **pending** receipt of actual bytes.
6. MBR geometry simulation for 32/64/128 decimal GB media and 8/12 GiB provisional roots generates only a report, not any SD-image files.

## Important unproven assumptions

- CP08 script may be incompatible with this U-Boot variant, or may fall through to the old root after failed rescue boot.
- Panel chooser, DTB and kernel placement must not be modified until a spare-card hardware boot.
- Recovery initramfs CPU and storage detection needs physical validation.
- The original 112MiB BOOT partition is smaller than the proposed 512MiB BOOT; partition changes are not safe on the current production SD.
- A recovery ramdisk size of ~0.96 MiB does not establish room for alternate kernels, graphics assets and backup code.
- The CP10 ext4 snapshot fixture used 32 MiB images; production backups need capacity planning, identity validation, integrity checks and actual power-loss testing.

## Explicit acceptance criteria for next stage

(1) Full boot.ini from user PC passes CP11 hash; (2) static verified candidate byte diff and bootloader interpreter compatibility test; (3) live Panel 4 rescue boot from spare media; (4) durable and authenticated state recovery; (5) full image construction with U-Boot-compatible early sectors and proved panel support.