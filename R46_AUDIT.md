# R36OS Alpha 5R46 — update-health timing + K1 U-Boot handoff probe

Physical evidence from the user's complete Alpha 5R44 result archives:

- Before K1 was staged, the R44 session reached its post-start checks in about 20 seconds.
- After the K1 candidate was staged, R44 session startup consistently took about 69-70 seconds.
- The transactional update health watchdog waits only 25 seconds (50 x 0.5 s).
- R45 was staged successfully as target 0.5.45.0 and rebooted, then returned to R44.
- Therefore an update after K1 staging can time out before R36OS reaches first-frame health.
- The K1 request remained armed=yes and consumed=no after the attempted K1 restart and after the R45 rollback.
- candidate_verify_code=0 and hook_verify_code=0 on R44.
- Running kernel remained 4.4.189.
- This proves U-Boot never consumed the one-shot request; K1 was not attempted.

R46 fixes the update-health timing hazard and instruments the K1 boot handoff without changing any K1 binary.

Changes:
1. update health watchdog wait 25s -> 120s;
2. kernel-slot status becomes a quick structural/marker check and does not hash the 281 MB candidate during ordinary boot status collection;
3. full candidate verification remains mandatory for arm-once;
4. K1 boot hook encodes its progress in r36os.k1_probe=... on the kernel command line;
5. hook distinguishes hook execution, request visibility, R36UPDATE candidate visibility, consumed write/readback, payload loads, and booti return;
6. hook installer may migrate only from the exact previously audited hook hash or the frozen legacy boot.ini;
7. no K1 Image, DTB, uInitrd or modules are replaced;
8. R45 remains withdrawn from the live update channel; R46 is based directly on R44.
