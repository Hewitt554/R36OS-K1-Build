# R36OS Alpha 6 CP20 — Boot-flow model and expired K1 artifact rebuild

**Development only. NO BOOTLOADER OR SD WRITES. NOT FLASHABLE. NOT BOOT TESTED.**

## Exact user R3 boot.ini source

CP19 verified the exact 5108-byte original user's `boot.ini` by SHA256 `b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e`. CP20 uses the public *derived* CP19 report with hash, original line numbers, boot commands, memory addresses and persistence. The exact raw script is **not in this repository**. Its SHA was independently rechecked locally against the provided original before producing `CP20_ORIGINAL_LOCAL_VERIFIED_BOOT_MATRIX.json`. GitHub CI cannot independently verify the script bytes; it verifies derived provenance and tests the model only.

### What the model proves and does not prove

`python3 alpha6/boot/cp20_bootflow_sim.py --audit alpha6/CP19_VERIFIED_ORIGINAL_R3_BOOT_AUDIT.json --output /tmp/new-cp20-matrix.json` runs 15 deliberately chosen branch scenarios, including: no-button normal boot, R1 panel chooser Left / Panel4, R1 + Volume-minus marker creation, `nopanelchooser` precedence, `unsetpanelchooser`, priority of simultaneous chooser inputs, panel-DTB load failure, failed U-Boot persistence calls, missing Image/initramfs/DTB and return from `booti`. **No code is executed on U-Boot, Linux kernel, SD card or raw image.** This is a constrained state model grounded in specific source lines and explicit assumed file/GPIO outcomes, NOT a real interpreter, CPU emulator, or reliable predictor of whether a physical boot succeeds.

The model records all calls that would **attempt** `fatwrite` or `saveenv` under those inputs. It never claims a successful disk write, and never tries a live one. An unguarded kernel, initrd or DTB read failure leaves U-Boot with unknown RAM state; the model correctly labels the subsequent `booti` attempt **indeterminate**, not automatically a safe fallback. If `booti` returns, the actual script calls `sleep 3` and `reset`; this is **not rollback**. `CP08`'s prototype gate remains blocked and is not evaluated as an install path.

## K1 original archive expiry

The earlier Sept 30 K1 Actions artifact **11124161537** now returns GitHub API HTTP 404; this explains CP13–CP18 failures on Oct 17 after previously passing. A green source-only workflow does not repair that dependency. Re-running a failed old workflow without re-pinning a new verified artifact won't help.

New workflow `.github/workflows/r36os-alpha6-cp20-refresh-k1.yml` starts a **fresh cloud compile** from the already-committed pinned `bootstrap_r36os_k1.sh`. It checks the exact historical Git bootstrap commit and blob ID before running, uses the original builder and build cache, then verifies the rebuilt output using CP13's **full SHA-256 manifest verifier**. Upon success it uploads a **new development-only artifact** with a requested 90-day retention. It does not recreate the historic artifact ID and does not automatically repin CP13–CP18; that requires success, checking the new archive fingerprint and editing downstream references. Note: requesting 90 days is not permanent archival or build bit-for-bit reproducibility. A release-grade durable storage and rebuild strategy is still needed.

The rebuild job is a GitHub hosted developer workflow and does not run on the handheld or modify the user's SDs. If the pinned source or its external downloads are no longer available, it will fail honestly with an uploaded log. The new artifact is **not authenticated cryptographically beyond hash consistency** or boot tested on R36S.

## Known blockers

- The legacy script has seven `fatwrite` and seven `saveenv` commands on conditional paths; a read-only **safe fallback is not yet implemented**.
- Legacy normal boot reads Image, uInitrd and DTB without checking failures. Its original R3 `booti` return resets, not rescue.
- K1 Panel 4 DSI is generic and neither it nor K1 U-Boot header acceptance has been tested on hardware.
- Full independent recovery and power-loss-safe rollback require real hardware verification on a separate SD. Nothing here authorizes a first boot on the primary SD.
- Native Debian read-only root, graphics, input, battery, speaker, launcher, Box64/Wine and first-boot persistence are still incomplete/untested.

**Next CP21:** re-pin K1-dependent workflows to the newly rebuilt checksum-verified artifact *if CP20 rebuild succeeds*, and add a clean bootloader-free fallback specification. Only after independent rescue is actually boot-tested on a spare SD should any boot-chain replacement be considered.