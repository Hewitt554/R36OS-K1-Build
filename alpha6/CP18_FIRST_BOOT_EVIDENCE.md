# CP18 — K1 first-boot preflight and legacy boot safety

**STATUS: DEVELOPMENT ONLY — NEVER FLASH OR INSTALL.** No R36S/U-Boot/Panel 4 boot is proved by this checkpoint. No disk image, original boot script, bootloader, automatic rollback, or installable file is produced.

## What CP18 actually checks

CP18 retrieves the pinned successful September 2026 K1 candidate and the last passing CP17 Panel 4 diagnostic ramdisks from GitHub Actions. It reuses CP13's manifest and artifact verification, validates both CP17 U-Boot variants (ARM header ID 2 and ARM64 header ID 22), verifies that their compressed payloads match, and cross-checks the CP17 K1 DTB provenance against the K1 archive digest and the DTB SHA-256. CP17's Panel 4 report must still declare its generic DSI panel and untested display status.

The output is exclusively a JSON preflight report, a `DO NOT FLASH` notice, and their SHA-256 hashes. It does **not** package the kernel or initramfs for installing to a card.

## Key new discovery from the genuine R3 BOOT audit

The supplied CP01 user-audited R3 boot script is **5,108 bytes**, SHA-256 `b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e`. Its selected relevant lines contain **`fatwrite mmc 1:1`** operations and **`saveenv`**. These can write the FAT BOOT filesystem and save U-Boot environment changes. These effects may be conditional on GPIO/panel choices; this audit is not a full execution trace. It would be incorrect to call the *legacy boot script itself* read-only or a verified independent fallback. CP08's earlier marker-gate prototype is still uninstalled and cannot be approved for deployment from current evidence.

**CP01 selected-line audit is not the complete original 5,108 bytes.** CP11 includes a Windows read-only extraction tool for the user's original R3 raw SD image; we have not run CP18 against those original bytes. CP18 records the absence of that evidence rather than inventing a boot script.

## Explicit remaining blockers

1. The exact original R3 boot.ini bytes, GPIO/panel chooser and bootloader memory-address contract must be reviewed before modifying any boot configuration.
2. A physically verified way to select a diagnostic or old working kernel is required. A marker branch that simply falls through to the old Linux root is not a tested rollback.
3. The K1 Panel 4 DTB advertises `rocknix,generic-dsi`, not an explicit NV3051D panel. The physical 640×480 display, orientation and input must be tested.
4. Both U-Boot initramfs header formats are offline-valid, but acceptance by the actual R36S U-Boot is untested.
5. Independent rescue boot, damaged-root response, power-loss recovery and a safe return to the original OS have not been hardware-proven.

This is an evidence integration checkpoint; **do not treat CI success as a boot-ready image.** Next is an isolated spare-SD *hardware test protocol* after the original boot script and rescue entry are fully verified, never a blind overwrite of production SD1.