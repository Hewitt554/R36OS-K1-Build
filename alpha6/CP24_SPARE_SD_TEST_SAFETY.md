# CP24 — First physical R36OS Alpha 6 test preparation (not flashable)

**Target: CP25 on a *separate spare SD1*, but only once safety conditions are genuinely met.**

## Verified evidence (CI and previously extracted original)

- Original Alpha 5R3 `boot.ini` locally verified from the user's read-only source IMG: exactly **5,108 bytes**, SHA256 `b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e`. Its complete bytes are **not stored in the public GitHub repo**. The derived CP19/CP20 reports are not an actual U-Boot interpreter test.
- Exact K1 Linux 6.12.94 ARM64 build pinned to GitHub Actions run `39038977056`, internal archive SHA256 `d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8`. CP13–CP18 passed GitHub checks after the rebuild. None has booted physically on this R36S Panel4.
- Original R3 boot script has conditional `fatwrite mmc 1:1` and `saveenv`, uses **old** kernel/initrd/Panel4 DTB and fixed legacy root UUID, loads kernel at `0x02000000`, initrd `0x01100000`, DTB `0x01f00000`, and `booti` can return and reset. CP08 prototype is **retired**.
- K1's Panel4 DTB advertises `rocknix,generic-dsi`, not a proven specific panel controller/timing contract. A blank screen during initial diagnostics is possible.

## What CP24 implements

1. Source-bound **90-day retention intent** for renewed CP17/CP18 development-only artifacts, with a separate ledger and a **read-only automated GitHub expiry audit**. Expired artifacts fail closed; items with less than 21 days left are flagged. Github Actions retention is finite, not permanent.
2. A read-only **spare-card test readiness document** generated from the exact original script + K1 pin. It cannot write disks or produce `boot.ini`, a kernel image, a rescue marker, a restore script, or a flashable image.
3. A first-boot checklist that explicitly tracks the missing prerequisites. Unknown status is not treated as approval.

## Hard pre-test gates before even a diagnostic boot

- [ ] Confirm working R3/ArkOS SD1 still boots on the hardware after the previous brick. Keep it unplugged and unchanged during every candidate test. A Windows image backup is not proof of a *working* card.
- [ ] Obtain and uniquely identify **a separate spare microSD card** for SD1. Verify its actual size and carefully distinguish it from both original SD1 and game-data SD2.
- [ ] Establish the location and effect of persisted U-Boot environment saved by `saveenv`, including whether it can alter later boots with a different SD card. Swapping cards should not be advertised as a guaranteed rollback without proving this.
- [ ] Prove an independent fallback (preferably the original card) physically boots after any configuration changes. CP07 rescue initrd/CP08 recovery gate do not count: neither has been boot-tested.
- [ ] On a disposable **regular-file image**, validate all bootloader sectors, Panel4 DTB selection, RAM load addresses and initrd header accepted by actual R36S U-Boot. Our CI byte-level checks are insufficient for physical success.
- [ ] Design the first diagnostic as **RAM-only, no writes to mmc, no persisted U-Boot env changes, no root mount**, and prove the spare boot path does not invoke R3 panel chooser writes (avoid R1/other chooser keys).
- [ ] Ensure the original source IMG exists on the PC (18,375,245,824 bytes) and has been independently hashed, and preserve any SD2 user data separately. Do not format or overwrite either production card.
- [ ] Obtain explicit user approval before any destructive spare-card flashing steps, and perform a physical device identity confirmation directly before writing.

## Physical diagnostics target (when approved)

- Power on with spare test SD1 only; look for CP17 pattern or serial console. A black display is **not sufficient** to conclude that no kernel executed.
- Record panel resolution/rotation/colour if framebuffer appears, input names/events, both MMC controllers, RK817 battery/power and console messages if physically accessible.
- Shut down and remove the test SD. Reinsert the previously proved known-working SD1 to verify manual fallback. If it fails, stop—do not automatically reset or write boot environment.

## Current truth

**`safe_to_flash=false`, `first_hardware_test_authorized=false`, `rescue_boot_tested=false`.** CP25 remains a *target*, not a promise to release an unreviewed writer. CP24 does not produce an installer or testable image.