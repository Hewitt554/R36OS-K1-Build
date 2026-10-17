# R36OS Alpha 6 CP13 — K1 kernel artifact inspection and boot-files staging

**DEVELOPMENT ONLY. NEVER FLASH OR REPLACE THE LEGACY BOOT FILES.**

### Verified provenance being checked
K1 Linux 6.12.94 was compiled on GitHub Actions run 36763257082 (30 September 2026). A successful, still-available result artifact (ID 11124161537) contains the candidate, including kernel Image, U-Boot initramfs, Panel 4 device tree, and modules. The build being successful does NOT prove on-device boot.

CP13 retrieves this *exact* result with GitHub Actions read-only permissions. The verifier checks the archive's K1.conf R36XX/RK3326/Panel4 identity, expected original root/state UUIDs, release and modules-storage contract; verifies the K1 SHA-256 manifest; checks Linux ARM64 Image magic, DTB header, U-Boot ramdisk header and modules XZ magic. It generates a provenance JSON report and stages three kernel boot files in a distinct folder named CP13_UNTESTED_K1_BOOT_FILES. There are no SD writes and no boot.ini modifications.

### Still missing
The old K1 root UUID and R36STATE assumptions are not the proposed native Alpha 6 partition UUIDs. This candidate must be rebuilt or explicitly updated in a controlled future root-layout integration. K1 modules must be installed for the exact kernel version. The rescue uInitrd built in CP07 is NOT interchangeable with this K1 candidate without hardware testing. Bootloader early sectors and Panel 4 text/output behavior cannot be verified by manifest checks.

A full byte-for-byte original R3 boot.ini is still needed before any candidate boot-selection script can be validated on actual R3 bytes (CP11 Windows extraction tooling is available), and first boots must use an independent spare SD. CP08's current presence-triggered rescue fallback can fall through to a damaged root; it is NOT a proven recovery route. Auto-rollback after repeated boot failure has not been built. CP13 must remain draft, no stable branch changes.

The K1 manifest is an integrity check, NOT an authenticated digital signature. Artifact retention may expire; for production the K1 toolchain and source should be pinned and rebuilt reproducibly rather than relying on an archived Actions run.
