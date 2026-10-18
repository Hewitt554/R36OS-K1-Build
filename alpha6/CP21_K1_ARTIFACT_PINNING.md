# R36OS Alpha 6 CP21 — fail-closed K1 source pinning (17 October 2026)

**Development only. No boot.ini, SD-card access, flashable image, or hardware-boot validation.**

## Why this checkpoint exists

The historic K1 result of September 30 had GitHub Actions artifact ID `11124161537`, which now returns HTTP 404. Later CP13–18 workflows failed on a **missing input**, not on a proven kernel defect. CP20 started a new compile using the pinned historical source and requested 90-day retention. Until that job has *completed successfully*, and the new archive has passed the CP13 checks, its exact SHA-256 and run ID are unknown.

CP21 avoids prematurely embedding an unverified run or selecting whichever artifact happens to be latest. The single source of truth is `alpha6/k1/k1-candidate-pin.json`:

- `PENDING_REBUILD` (current state): run ID, commit and archive hash MUST all be null. Attempted downstream resolution errors before any download.
- `PINNED_CI_VERIFIED_NOT_BOOT_TESTED` (future state, **not set yet**): requires exact GitHub workflow run, commit SHA, archive SHA-256, expected repository/branch/workflow and explicit non-boot safety status.
- A completed, successful GitHub API run from the **expected build workflow** must match the pin before an archive may be used.
- The downloaded archive must match the **full-file** pinned SHA-256 and separately pass CP13's inner SHA-256 manifest, ARM64 kernel, Panel 4 DTB, U-Boot header and modules validation. Manifest consistency alone does **not** authenticate source or prove a real boot.
- `cp21-download-pinned-k1.sh` is an optional **CI-only** helper: requires `GH_TOKEN`, `RUNNER_TEMP`, refuses non-scratch destination/overwrite, downloads by *exact* pinned run ID and fails closed. It is **not** connected to the production release or SD boot path.

## To activate after CP20 actually succeeds

1. Inspect the new CP20 run's overall `success` status, full archive provenance report and SHA256. If the rebuild failed, fix and repeat; never publish a placeholder pin.
2. Produce a pin proposal using `cp21_pinned_artifact.py <pending.json> --propose-report <cp20-provenance.json> --run-json <verified-github-api-run.json> --output <NEW proposed.json>`. This is a proposal file only; **it does not write the canonical pin or activate anything.**
3. Review exact run ID, Git commit and full archive checksum, publish the reviewed pin on the **development branch only**, and validate the source via the strict downloader. On download, CP13 archive verification reruns.
4. Reconnect the dependent CP13/14/15/16/17/18 workflows only after this checked activation. CP17's older diagnostic DTB hashes and CP18's cross-artifact comparison must be rebuilt or explicitly reconciled if the fresh K1 output differs.
5. Confirm current K1 archive expiration date, and implement a separately approved long-term durable archive strategy (an Actions artifact with `retention-days: 90` is **temporary**, not permanent).

## Safety and limitations

CP21 is only artifact chain-of-custody engineering and offline regression tests. The pending pin deliberately prevents accidental use. The K1 source's historical checksum manifest is *not cryptographic source authentication*, bit-for-bit reproducibility has not been proved, the old 4.4/Panel4 bootloader is untested with K1, and CP08 is still retired. The original R3 boot.ini can execute `fatwrite` and `saveenv`; independent recovery remains untested and cannot be assumed.

Do not interpret a green CP21 source-unit-test run as a successful K1 rebuild, a passing historical CP13–18 rerun, or permission to flash.