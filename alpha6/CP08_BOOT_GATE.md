# Alpha 6 CP08 — Recovery boot gate and offline transaction model

Status: DEVELOPMENT-ONLY, NOT FLASHABLE, NOT BOOT-TESTED.

## Audited boot input
The original Alpha 5R3 boot.ini is exactly 5,108 bytes. SHA-256:
b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e
It uses U-Boot 'load mmc 1:1', the legacy Image, uInitrd, a Panel-selected device tree and root UUID e139ce78-9841-40fe-8823-96a304a09859.

## Working CP08 source
- boot/build-recovery-gate.py requires the exact original boot.ini checksum and byte length. It inserts a separate rescue boot branch immediately before the legacy root bootargs, and writes ONLY an offline alternate candidate with exclusive file creation.
- The gate checks the existence of BOOT FAT32 marker R36OS/RECOVERY.ON, then loads R36OS/rescue.uInitrd with the original Image and Panel-selected DTB and rdinit=/init. The gate does not write to BOOT or SD storage.
- boot/recovery-transaction-model.py is a simulated state machine for verified snapshots, rescue arming, offline application, trial health, interruption and restore.
- Both are covered by independent offline tests in GitHub Actions.

## Explicit safety limits
The gate is not installed and RECOVERY.ON is not created by CP08. The generated candidate has not been tested against a full boot.ini (only synthetic fixtures). No physical R36S or Panel 4 boot has been performed. The recovery ramdisk has not booted on the legacy 4.4 kernel. The U-Boot command syntax is inferred from the CP01 boot audit, NOT confirmed in the device bootloader for this new branch.

If rescue loading or booti fails/returns, execution may continue to the legacy boot branch; thus this does NOT guarantee automatic recovery or isolation of damaged roots. The presence-only marker is not authentication and gives no permission to restore storage.

The CP08 transaction model is not a real filesystem updater, persistent journal, backup or power-failure-safe restore. Health checks and an automatic on-next-boot selector still need implementation. No user should flash, install or replace boot.ini based on this source.

## Next engineering steps
Extract the complete original R3 boot.ini read-only and run the strict candidate generator against it. Validate the generated syntax with real U-Boot parser/bootloader tests. Validate rescue boot with the known-working legacy kernel/Panel 4 on a spare card before enabling a recovery marker. Implement independent verified backup and interrupted restore under controlled tests. Preserve the original image and live R36OS release channel.
