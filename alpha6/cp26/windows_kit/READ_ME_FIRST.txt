R36OS ALPHA 6 / CP26 — FIRST K1 HARDWARE DIAGNOSTIC (EXPERIMENTAL)
====================================================================
THIS IS NOT THE COMPLETE NATIVE ALPHA 6 OS, AND IT HAS NOT BEEN BOOTED
ON YOUR PANEL 4 R36S. THE ORIGINAL R3 IMAGE ALSO DID NOT BOOT ON YOUR
CURRENT CARD. NO RECOVERY BOOT HAS BEEN PROVEN ON THE HANDHELD.

This ONE Windows ZIP contains: K1 Linux 6.12.94 Image, Panel 4 DTB,
RAM-only diagnostic uInitrd, diagnostic boot.ini, manifest and Windows
install/restore scripts. It does NOT contain the 18.4 GB original R3 image
or the full native Debian root, Box64 UI or Windows applications.

NO EXTRA FULL-SIZED IMAGE COPY IS REQUIRED ON THE PC.

STEP 1 — First run 00_VERIFY_EXISTING_R3_IMAGE.cmd. It reads the
existing 18.4 GB IMG in place and checks its FULL SHA256. It creates NO
second copy. If it reports FAIL, STOP.

STEP 2 — Reflash your existing SD1 with the ORIGINAL 18,375,245,824-byte
file you already have on your Windows PC:
  F:\r36\R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img
Use your trusted image-flashing application (such as Raspberry Pi Imager
or Win32 Disk Imager) to write that original file DIRECTLY to SD1.
Read the device name, capacity and drive identity TWICE. This ERASES SD1.
Never choose SD2, your PC's OS drive, or an attached HDD/SSD. This
CP26 ZIP intentionally contains NO physical disk writer, so there is
no risk of a mislabeled automatic erase by our experimental scripts.

STEP 3 — When Windows mounts the newly restored SD1 BOOT partition,
keep SD2 disconnected from the PC and launch:
  03_CHECK_SD1_BOOT.cmd
Select its FAT32 BOOT volume letter. It should report R3_ORIGINAL.
If not, STOP. Do not run 01. Ignore Windows prompts to format ext4 volumes.

STEP 4 — Launch:
  01_INSTALL_AFTER_R3_FLASH.cmd
Choose the same FAT32 BOOT letter and type the exact confirmation phrase.
The installer verifies the ORIGINAL 5,108-byte boot.ini SHA256. It
writes three separate CP26 assets, stores a verified R3BOOT.BAK, and
replaces ONLY the BOOT partition's boot.ini with a write-free diagnostic
boot script. It never intentionally touches SD2 or the Linux partitions.
Install from the kit's extracted folder, not by dragging files from ZIP.

STEP 5 — Safely eject SD1 from Windows; insert it into the R36S SD1 slot.
Power on without holding R1 or a panel chooser combination. Allow ~60 s.
The ideal outcome is a basic diagnostic test pattern and system info,
NOT the main R36OS launcher. If screen stays black, record whether the
backlight lights or the device vibrates/LEDs appear, and a photo/video.
Do NOT keep repeated reboot loops running indefinitely; power off.

STEP 6 — If the test fails and SD1 remains Windows-readable, run:
  02_RESTORE_R3_BOOT.cmd
This restores the ORIGINAL boot.ini from the verified R3BOOT.BAK.
The original R3 system ALREADY did not boot; this is NOT a guaranteed
full functional rollback. Reflashing your existing 18.4 GB original R3
IMG using your imaging app is the complete SD1 reflash path. Neither
option proves recovery from U-Boot environment changes internal to device.

IMPORTANT LIMITATIONS
- K1, Panel 4 screen, old U-Boot's RAM loading and power controls are
  still physically UNTESTED, even though our CI checks their file hashes.
- The boot selector from CP08 is RETIRED and not used here.
- boot.ini contains NO saveenv/fatwrite; U-Boot loaded before boot.ini
  may still have other behaviors which are NOT independently proven.
- This runs only the CP17 diagnostic initramfs in RAM; it does not
  switch the original R3 root to native Debian.
- The installer has offline/synthetic Python tests only, NOT a real
  successful Windows SD test. If it refuses the target, STOP and send log.
- No automatic A/B rollback, filesystem repair or bootloader rescue.

SEND BACK: whether the diagnostic screen appeared, a photo, and any
error text from install/restore. Do not try any other CP08/CP17 files.