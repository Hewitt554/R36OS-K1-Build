# R36OS Alpha 6 CP24 — Reviewed artifact retention and spare-SD first-test gates

## Checked provenance (17 October 2026)

- [CP20 K1 rebuild](https://github.com/Hewitt554/R36OS-K1-Build/actions/runs/39038977056) PASS; Actions artifact `12103773756`, SHA256 of **inner K1 result tar.gz** `d5945b6760df7b52b4036aec3896b9491498fe2b556e48ef253f677407b581d8`, expiry **2027-01-15 14:01:22 UTC**. A GitHub artifact ZIP's checksum is different from the inner K1 archive checksum. CP21 validates the latter along with CP13's internal checksum manifest.
- [CP17 renewed Panel4 diagnostic](https://github.com/Hewitt554/R36OS-K1-Build/actions/runs/39044552247) PASS; artifact **12105631029**, source commit `d549a763a56c5b18b833ee6fe876be7655732a18`, expiry **2027-01-15 15:19:45 UTC**.
- CP17 and CP18 workflow uploads now explicitly request **90-day retention**, replacing previous 14-day requests. The new artifacts' GitHub metadata showed the expected January 2027 expiration. These artifacts remain hardware-untested and cannot be converted into production releases by reuploading them.
- CP18 must download **the exact renewed CP17**. It checks its pinned K1 archive separately through CP21. This work does not erase the underlying R3 bootloader, Panel4/DRM or independent recovery gaps.
- `alpha6/cp24/pinned-artifact-ledger.json` contains only artifact identities, run IDs, workflow paths, K1 archive SHA256 and no private original boot-script bytes. It does **not** authenticate authorship of the K1 archive or prove device boot.

## CP24 read-only CI audit

`alpha6/cp24/artifact_guard.py` validates live GitHub artifact and source-run API fields. It verifies ID, name, expiry flag, real expiration time, created-to-expiry duration, repository/branch/workflow/commit and that the artifact is attached to its pinned run. It warns under **21 days** and CI fails under **7 days** until a maintainer renews and re-pins evidence. Binary SHA256 is a **separate** CP13/CP18 test, not this metadata audit.

**Monitoring limitation:** CP24's workflow runs on development-branch pushes, PR changes and manual dispatch when available. GitHub Actions `schedule` only runs workflows on the default branch. Because `main` is deliberately unchanged, **there is no automatically scheduled daily renewal job**. Do not rely on CP24 to alert automatically if no new builds occur. A later approved release/ops process must provide active monitoring and durable archiving outside short-lived CI artifacts.

## CP24 physical test readiness

`spare_test_contract.py` reads the exact user-provided original boot script (from the secure conversation environment) and the development-only K1 pin/ledger, then emits JSON denials and a CP25 target checklist, never an SD image or bootloader script. The user original file is not committed. The software **cannot know whether a separate test SD or known-working original card exists**; those status fields stay false until proven.

Before attempting the first physical K1 boot, the operator must confirm a distinct spare SD1 and an independently working fallback. The R3 boot script can call `saveenv`, and its environment storage location is **not yet proven**; merely swapping cards may not guarantee recovery if firmware stores variables elsewhere. First-boot testing must not touch production SD1/SD2 and must not depend on the untested CP08 rescue.

## Hard state after CP24

`safe_to_flash=false`, `boot_tested=false`, `manual_spare_first_boot_authorized=false`, and `independent_recovery_proven=false`.

**CP25 target** is first physical diagnostics if physical-card and bootloader safety gates can be met. If not met, disclose the remaining blocker and do not fabricate a flashable package.