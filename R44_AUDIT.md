# R36OS Alpha 5R44 — K1 FAT staging audit

Date: 2026-09-29

Physical Alpha 5R43 evidence:
- R36UPDATE repair completed and final FAT verify_rc=0.
- The subsequent boot no longer reported the mmcblk0p3 improperly-unmounted warning.
- Boot Next Once then failed before arming K1 with code=33, detail=stage-copy.
- Remote failure bundle was uploaded automatically.
- The exact K1 candidate was not booted; legacy Linux 4.4.189 remained active.

Reproduction:
- Exact published R38 K1 candidate size: 281048 KiB.
- On a vfat image, the R43 cp -a staging operation returns 1 with:
  failed to preserve ownership ... Operation not permitted.
- Recursive data copy on the same FAT image returns 0.
- Every copied regular file then matches the source SHA-256.

R44 staging design:
1. Exact existing K1 preflight before touching R36UPDATE.
2. Reject symlink/device/FIFO/socket entries in packaged candidate.
3. Compute deterministic whole regular-file-tree digest.
4. Preserve existing R36UPDATE device/UUID/read-write/FAT-health checks.
5. Preserve candidate size + 64 MiB headroom requirement.
6. Remove only stale candidate-bound .K1.stage.<candidate>.* directories.
7. Stage into a new sibling directory using recursive data copy, not cp -a.
8. Reject non-regular entries after copy.
9. Require staged whole-tree digest to equal source.
10. Run K1 preflight on staged FAT copy.
11. Require MANIFEST.sha256 readback match.
12. Rename staged directory to K1 only after all verification passes.
13. Re-run preflight and whole-tree digest after activation.
14. Only then continue to hook metadata, module staging and one-shot arming.

R44 does not change K1 Image, DTB, uInitrd or modules and does not re-arm the R43 FAT repair.
