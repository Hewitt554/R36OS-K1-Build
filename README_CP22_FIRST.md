# R36OS Alpha 6 CP22 — development package

CP22 provides a fail-closed, reviewed migration plan for the six GitHub workflows stranded by the expired September K1 kernel archive. The included script generates proposed CI YAML **only in isolated /tmp**; it cannot modify the repository or any SD cards. This source-only package is not the full R36OS project; the cumulative code lives on the existing GitHub draft PR.

Expected CI status at creation: CP22 unit tests + six actual workflow draft stage PASS; CP20 historical K1 rebuild remains independently running and the canonical CP21 pin stays PENDING_REBUILD. See `alpha6/CP22_K1_DEPENDENCY_MIGRATION.md`.

No firmware is ready to flash or boot-test; preserve all existing R3/SD media.