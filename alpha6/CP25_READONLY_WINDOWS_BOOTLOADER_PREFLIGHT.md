# R36OS Alpha 6 — CP25: Windows first-test evidence capture

**This is an evidence-collection checkpoint, not the promised actual device boot. CP25 does not contain a K1 installer, flashing image, U-Boot patch or rescue key.** The original SD1 has previously been bricked; no physical test should proceed until a separate spare SD card and a genuinely independent recovery plan are confirmed. The legacy R3 `boot.ini` has conditional `fatwrite` and `saveenv` commands: merely swapping cards is not yet proven to undo their effects.

## Why CP25 is gated

CP24 left three critical unknowns: whether an original working SD1 now boots, whether a completely separate spare SD1 is available, and where the actual R3 U-Boot persists its environment. The exact U-Boot binaries and environment storage config have not been proven from the 18.4 GB original image. These are **not** solvable by pretending the precompiled K1 Linux or ARM64 initramfs have booted the R36S; they have not.

The CP25 source has two user-runnable, **read-only Windows tools**. They can run without a connected handheld, do not format or write SD media, and intentionally refuse physical drives in the raw-image inspector.

### 01 — original firmware image inspection

Drag the **original** `R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img` onto `01_INSPECT_ORIGINAL_R3.cmd`, or double click it and supply the complete `.img` path. Existing Python 3 is required (the same software used by CP11). It validates the original 18,375,245,824 byte length, the first two MBR partition entries and the MBR signature. It reads **only the first 16 MiB** of the regular image file, which is entirely before the original FAT BOOT partition, and records the SHA-256 of that 16 MiB plus offsets of selected U-Boot-like strings. It **does not** hash the whole 18.4 GB file, reproduce the original bootloader, locate the saved environment definitively or prove any hardware boot.

The output is `alpha6/cp25/CP25_RESULTS_<UTC>/CP25_R3_EARLY_BOOT_READONLY_REPORT.json` and does not contain binary bootloader bytes, a username path or device serial numbers. The original image file is opened `rb`; no existing files are overwritten. Upload **only the JSON report** for review, not the original 18.4 GB `.img`.

### 02 — optional read-only Windows disk inventory

`02_LIST_CARDS_READ_ONLY.cmd` lists attached disks through Windows `Get-Disk` / `Get-Partition`, and writes a new JSON in `alpha6/cp25/CP25_CARD_RESULTS`. It never accesses `\\.\PhysicalDrive` directly and never formats disks. The inventory includes the host PC's own drives; **it is not a list of safe destinations**. Disk numbers may change, reported capacity can be counterfeit, and the tool cannot certify a card is spare. If you send the report, check whether any disk names you want to keep private appear in it.

### Exact next action before a physical first boot

Ask the user whether (1) a dedicated spare SD1 physically exists and (2) the original SD1 still boots normally, with the test card unplugged. Do not ask them to touch either SD until the questions are answered. The R3 `saveenv` backend still needs investigation using the read-only evidence; the string scan is not confirmation of its location or lack of internal storage. A physical first boot can only proceed after a test SD identity/rollback plan is reviewed, after explicit destructive-write permission for the spare **and** after an independent recovery path is physically verified.

## Validated offline behavior and limits

The Python audit is exercised using a **16 MiB disposable regular-file MBR fixture** and negative-path tests. The companion card inventory's PowerShell source has static non-mutating-command checks. CI never reads the real user's 18.4 GB image, does not access a physical R36S and cannot validate the Windows PowerShell runtime. No user hardware testing has been reported.

Safety assertions: `safe_to_flash=false`, `persistent_uboot_env_storage_location_proven=false`, `independent_manual_fallback_physically_proven=false`, `physical_sd_card_opened=false`, `source_img_fully_sha256_verified_this_run=false`.

## Hardware-test milestone

CP25 is **first-test preparation** rather than pretending that a physical test has occurred. Once the reports and spare/working-card status are reviewed, the next checkpoint should finalise the first actual spare-card diagnostic test. This may take CP26 or later if the bootloader environment location/recovery mechanism remains unverified. Do not put the CP17 diagnostic initrds or new K1 image on the production SD1.