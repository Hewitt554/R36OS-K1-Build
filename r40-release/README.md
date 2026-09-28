# R40 WIP — general private log upload

This directory is a work-in-progress continuation from verified Alpha 5R39.

Goal:
- Diagnostics -> A(bottom) becomes **Capture + upload logs**.
- Full manual archive still stays local.
- A smaller privacy-redacted bundle uploads to the dedicated private repo.
- Bundle includes bounded latest game-session evidence plus selected OS/kernel/runtime evidence.
- Failed/not-configured uploads remain queued on R36STATE.
- Public `Hewitt554/R36OS-K1-Build` remains forbidden as a diagnostic destination.

Private destination:
`Hewitt554/R36OS-Device-Logs`

UI source authority:
Recovered CP08 R37 worktree `source/r36os_alpha5.c`, later carried into R38/R39.
Apply `apply_ui_upload_logs.py`, then rebuild with the existing freestanding static AArch64 clang/lld command.

This WIP is NOT an installable R40 release yet. The device currently has a genuine dirty R36UPDATE FAT condition and K1 code 25 must not be bypassed.

Current WIP behavior:
- The dedicated repo defaults to `Hewitt554/R36OS-Device-Logs`.
- Upload mode defaults to automatic when no explicit config exists.
- The token is still required locally on the device and is never embedded in this public repository.
- Manual Diagnostics export performs one synchronous queue/upload attempt so the UI can show a deterministic result.
- Nested latest-game-session/latest-os-session files are recursively redacted and privacy-scanned before archive creation.
- The remote bundle stays capped at 8 MiB; individual noisy game/OS files are tail-bounded.
- If upload cannot run, the bundle remains queued on R36STATE and the normal full local export is still preserved.

UI behavior:
- Diagnostics -> A(bottom) displays **Capture + upload logs**.
- Final modal distinguishes uploaded / queued / setup-required while preserving the local archive path.
