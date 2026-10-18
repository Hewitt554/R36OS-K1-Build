# CP19 — Full original R3 boot script recovered and audited (17 October 2026)

**DEVELOPMENT ONLY. Not boot tested; not flashable. Never install CP08's boot-gate candidate.**

## What was received and verified

The user supplied `R36OS_CP11_VERIFIED_R3_BOOT_ORIGINAL.bin` and `R36OS_CP11_BOOT_VALIDATION.json`, generated read-only from the original `R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img` on Windows. Local raw-file verification produced **5108 bytes**, SHA-256 **b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e**, matching the CP01 reference. The uploaded report says `PASS_VERIFIED_ORIGINAL_R3_BOOT_INI` and `read_only_source=true`. The raw 5108-byte source is intentionally **not committed to the public GitHub project**; the published `CP19_VERIFIED_ORIGINAL_R3_BOOT_AUDIT.json` is a derived, source-hash-bound evidence report. CI can verify that report's safety constraints but cannot independently re-read the original bytes unless supplied out of band.

## Exact boot-flow findings from actual script (line numbers)

- Lines **4–16**: R1 + Volume-minus conditionally uses `fatwrite` to create `nopanelchooser` in FAT BOOT. This is **persistent**, not a read-only boot chain.
- Lines **21–37**: loads `nopanelchooser` and `unsetpanelchooser`; `unsetpanelchooser` invokes `env delete -f` and **`saveenv`**, modifying persistent bootloader environment.
- Lines **40–167**: panel chooser uses R1 then directional/face buttons. **Left (gpio b14)** selects **Panel 4** at line 116; the branch saves `PanelNum`, `PanelPath`, `PanelPathSlash` via `saveenv` at line 119, copies selected panel DTB into FAT32 BOOT with `fatwrite` at line 123 and powers off. Legacy Panel 4 boot therefore depends on saved selection and copied panel data.
- Lines **170–172**: U-Boot load addresses: kernel `0x02000000`, initrd `0x01100000`, device tree `0x01f00000`.
- Line **174**: legacy `bootargs` includes the fixed root UUID `e139ce78-9841-40fe-8823-96a304a09859`, rw/rootwait/rotation and ttyFIQ0 arguments.
- Lines **176–190**: selects Image; **Panel 5 custom-kernel load at 182 is followed by unconditional default `Image` load at 185**, likely overriding it. This is separate from the Panel 4 path.
- Lines **193/198/200**: loads `uInitrd` and panel-specific `rk3326-r35s-linux.dtb`, then calls `booti`. These load commands **are not guarded for failure**, unlike some earlier panel-chooser file reads.
- Lines **202–203**: `sleep 3; reset` on return from `booti`. This is not an independent rescue path.
- Seven original `fatwrite` commands and seven `saveenv` commands occur in the script. Most are under optional button/chooser conditions, **not necessarily executed on every normal boot**, but their existence means persistent state writes are possible.

## CP08 safety correction

CP08 inserts its historical selector at the **bootargs line (174)**, *after* the memory addresses (170–172). An earlier provisional claim that the hook ran before address initialisation was incorrect and has been corrected. **CP08 remains rejected** because it can fall through to legacy boot when recovery is unavailable/returns, relies on the untested old 4.4 kernel and panel paths for rescue, lacks a reliable boot-once state and has never booted physically. A real fallback must also account for U-Boot `saveenv` and FAT `fatwrite` mutations.

CP19 changes both CP08 candidate generators to fail closed for the real original R3 fingerprint. CP11 production extraction continues to return the verified original boot script **without generating the retired CP08 candidate**. Synthetic fixture tests can still exercise historical behavior without producing real candidates.

## Remaining blockers

A physically tested independent bootloader/recovery path, spare-SD Panel 4 proof, known-good K1 boot and diagnostics on real hardware, no-write manual fallback and power-loss-safe rollback are NOT implemented or proven. The original R3 SD image is preserved. No boot.ini, flashable image, partition modification or hardware SD test is produced in CP19. See derived JSON for machine-readable line numbers.

## Next

Develop an **offline-only** U-Boot boot-flow simulation from this exact line ordering; test boot-once / marker absence / failed load / invalid Panel chooser permutations. Then prove independent rescue boot from a **spare card** while keeping the original image untouched. Actual bootloader interpreter and Panel 4 physical behavior remain unknown until hardware validation.