# R36OS Alpha 6 — CP11 (Boot evidence and image-layout preview)

**Status: DEVELOPMENT ONLY — NO FLASHABLE IMAGE.**

CP11 addresses the evidence missing since CP01 and CP08: our earlier audits included boot-relevant lines, but not the actual full original `boot.ini` needed to validate our recovery-gate candidate. The complete 18 GB R3 image is on your Windows PC, not included here.

## Single Windows step (only when convenient)

1. Extract this CP11 ZIP. You only need the **CP11** subfolder inside the ZIP.
2. Drag your original `R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img` onto `CP11\EXTRACT_CP11_BOOT.cmd`.
3. Send the `R36OS_CP11_BOOT_VALIDATION.json` and `R36OS_CP11_VERIFIED_R3_BOOT_ORIGINAL.bin` from the newly created `CP11_RESULTS_...` folder. These are small.

The Windows tool needs only Python 3, which was used for CP00–CP04. It reads the image, not the SD card. It does not write any byte back to the original image, and it does **not** recompute the full 18 GB SHA256 (already passed in CP00). It only accepts the exact audited boot.ini (5,108 bytes; SHA256 `b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e`).

The generated `R36OS_CP11_BOOT_CANDIDATE_UNTESTED.txt` is for inspection **only**. **Never rename it to `boot.ini`, replace anything on BOOT or copy it to your SD cards.** The recovery selector has not been tested by real U-Boot or on Panel 4 hardware.

## Layout simulation

The JSON in `CP11/docs/CP11_LAYOUT_CAPACITY_SIMULATION.json` simulates an MBR with four partitions: 512 MiB R36BOOT, provisional 8 or 12 GiB R36SYS, 1 GiB R36UPDATE, and remaining R36STATE. A 64 GB marketed card has about 50.09 GiB STATE with 8 GiB root, or 46.09 GiB STATE with 12 GiB root. **No choice is final.** This is a geometry calculator, not an image builder or a partitioning script.

## What is still not built or proven

- K1 Linux 6.12 Panel 4 hardware boot.
- Verified recovery handoff using real bootloader commands.
- Automatic detection of failed boots.
- Trusted identity-bound on-device snapshots and root partition repair after real power loss.
- Fully integrated, physically tested flashable Alpha 6 image.

Do not perform a recovery trial on the installed SD1.