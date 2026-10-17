# R36OS Alpha 6 CP23 — reviewed K1 rebuild pin and five CI consumer migrations

**Development only. Not flashable, not hardware boot-tested. No SD, bootloader or production image writes.**

The CP20 compiled replacement for the expired 30 September K1 Actions artifact finished successfully on 17 October 2026. Verification includes the CP13 full-archive SHA256 manifest and K1 kernel/ramdisk/DTB/module checks.

| Key | Reviewed value |
|---|---|
| GitHub Actions run | `39038977056` |
| Source commit | `b593608d9cdc5f0275cc7f6471e31ff4db5bb366` |
| Source workflow | `.github/workflows/r36os-alpha6-cp20-refresh-k1.yml` |
| Artifact ID | `12103773756` |
| Artifact name | `r36os-alpha6-cp20-REBUILT-K1-HARDWARE-UNTESTED` |
| SHA256 of **inner** K1 `.tar.gz` archive (NOT the downloadable ZIP) | `d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8` |
| Outer GitHub artifact ZIP size | `560334073` bytes |
| GitHub artifact expiry reported | `2027-01-15T14:01:22Z` (storage is **not permanent**) |
| Hardware boot status | **NOT TESTED** |
| Safe to flash | **NO** |

## Activation guard

`alpha6/k1/k1-candidate-pin.json` records the reviewed run ID, exact source SHA and **inner archive SHA256**. The CP21 downloader verifies source branch/workflow/repository/conclusion and the archive hash and re-runs CP13's internal artifact checks **after download** before giving callers a scratch path. It never selects the newest artifact automatically.

`cp23_verify_metadata.py` independently checks the reviewed run and artifact identity from live GitHub API metadata, with negative tests. It does **not** download or rehash the whole archive; CP13/14/15/16/17 downstream CI is required to perform full new-archive validation.

## Migration scope

Only the five CP13, CP14, CP15, CP16 and CP17 active workflow definitions are updated to use the CP21 exact-hash downloader. The CP22 migration was previewed in a temporary review folder and regression tested beforehand.

**CP18 remains explicitly unresolved.** It depends on *both* K1 provenance and the old CP17 diagnostic report. The old CP17 report is tied to the *previous* K1 archive SHA; updating K1 alone would make the report inconsistent, even if CP17's historical artifact is still available. Regenerate CP17 against the newly pinned archive, review its new run/artifact SHA, then migrate CP18 as a separately validated step. Do not make CP18 silently accept mismatched source hashes.

## Outstanding blockers

This checkpoint is CI/provenance only; it does NOT verify any physical U-Boot image load, Panel 4 640×480 scanout, exact DSI driver timing, boot once/rollback safety, original R3 fallback independence, native init handoff, input, battery, sound or first-user-session graphics. Original R3 `boot.ini` can persistently write `fatwrite`/`saveenv` and CP08's candidate remains retired. No flashable Alpha 6 image may be distributed.