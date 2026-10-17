# R36OS Alpha 6 CP22 — Fail-closed migration for K1-dependent CI

**DEVELOPMENT-ONLY. No SD writes, no U-Boot / BOOT changes, no firmware, no flashable image.**

## Why CP22 does not activate the new pin yet

The old K1 archive from GitHub Actions ID `11124161537` expired and now returns HTTP 404. CP20 launched a new pinned-source build in [Actions run 39038977056](https://github.com/Hewitt554/R36OS-K1-Build/actions/runs/39038977056). At CP22 design time that job was still compiling; it had neither completed CP13 SHA256 checks nor uploaded a replacement. A timeout or failed job is possible. **No valid replacement archive digest or run provenance exists yet**. CP21 deliberately keeps `k1-candidate-pin.json` in `PENDING_REBUILD`. 

CP22 prepares **six exact, reversible, review-only workflow patch files** to replace stale K1 run/artifact references with the CP21 helper, WITHOUT editing the original workflows. It does so only in a fresh marked `/tmp/r36os-cp22-workflow-drafts-*` directory; its GitHub Actions artifact is clearly labeled `DRAFTS-REVIEW-ONLY-NOT-ACTIVATED`. These drafts are not deployed automatically and MUST NOT be applied before the exact K1 run and archive are verified.

## Source consumer inventory

| Workflow | Historical K1 failure | Draft change |
|---|---|---|
| CP13 | Old K1 artifact unavailable | Exact CP21 download, preserves full CP13 SHA/CRC verifier |
| CP14 | Old K1 artifact unavailable | CP21 helper then module ABI/real ext4 integration |
| CP15 | Old K1 artifact unavailable | CP21 helper then native-root initrd builder |
| CP16 | Old K1 artifact unavailable | CP21 helper then compiled-in driver configuration audit |
| CP17 | Old K1 artifact unavailable | CP21 helper then generic DSI/Panel4 audit |
| CP18 | Old K1 artifact unavailable | CP21 helper **but keeps a SECOND independent CP17 artifact dependency** |

**Important:** CP18 also requires CP17 old artifact ID `11924001285` from run `38624606064`. Repinning K1 alone does not revalidate this separate diagnostic artifact. If a newly rebuilt K1 archive differs in kernel/DTB hash, **CP17 must be rerun and its new artifact verified and independently pinned before CP18 can assert K1/CP17 provenance agreement.** Keep its old reference as an explicit blocker; never pretend CP18 is repaired by changing one ID.

## Safety contracts

- The CP22 migration tool requires a known set of six workflow names and single exact historical K1 step/ID occurrences. Rejects duplicated steps, missing IDs, unexpected path changes and repeat application.
- Staged downloads use `alpha6/k1/cp21-download-pinned-k1.sh`, which first requires a **ready** CP21 pin, exact GitHub successful `push` workflow run, matching repository, branch and head commit, and the full K1 tar.gz SHA256 plus internal CP13 manifest.
- Generated K1 candidate paths are scoped to the GitHub-runner scratch temp and do not overwrite existing files.
- All outputs explicitly set `safe_to_flash=false`, `hardware_boot_tested=false`, `ready_to_apply_to_development_branch=false`.
- CP22's new workflow proves the **actual existing repository consumer templates** match the migration assumptions without changing Git-tracked workflows. Synthetic fixtures alone are not sufficient.
- If the CP20 new K1 build fails/times out, investigate build logs/source dependencies; do **not** forge a pin, reuse the retired kernel result, or re-run unsafe boot installs.

## Next step, after CP20 actually succeeds

1. Inspect the fresh `r36os-alpha6-cp20-REBUILT-K1-HARDWARE-UNTESTED` artifact, CP20 provenance report and complete archive SHA256.
2. Validate its actual GitHub run ID, source commit, artifact identity and CP13 content contract; record the checked tuple in the CP21 pin through an explicit reviewed change.
3. Run CP21 ready-pin tests on the real downloaded archive; apply CP22 draft changes to **development workflows only**, then rerun CP13–CP17.
4. Regenerate a CP17 diagnostic bundle from the same new K1 and independently pin its **run and full artifact checksums** before updating CP18.
5. Continue work on truly independent, tested rescue and eventual spare-SD physical boot. No installation on the user's primary SD is authorized.

This creates a maintainable workflow-repair path, **not** a bootable Alpha 6 release.