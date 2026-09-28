# R36OS Alpha 5R40 — audited candidate source

R40 is a small userspace/safety update built only from the exact published Alpha 5R39 package plus the pinned static ARM64 FAT checker. It does **not** rebuild or replace the K1 kernel candidate.

## Authoritative R40 files

- `build_release.sh` — deterministic R39 -> R40 delta builder.
- `r36os-export-current-logs-wrapper` — existing Diagnostics export entrypoint; captures the R40 snapshot, then executes the verified inherited exporter.
- `r36os-r40-github-snapshot` — bounded latest game/OS/resource evidence written into the kernel-next diagnostic area so the verified R39 privacy-redacted uploader includes it.
- `r36os-r36update-repair` — exact-device, offline, backed-up FAT repair helper.
- `r36os-r40-firstboot-repair` — one-time first-boot gate for the confirmed mmcblk0p3 dirty-volume condition and non-secret private-log-repo defaults.
- `r36os-r40-repair-generator` + `r36os-r40-firstboot-repair.service` — one-time systemd wiring.

There is deliberately **no R40 fork of the GitHub uploader**. The package extracts the audited R39 uploader from the exact published R39 base and requires it to remain byte-for-byte identical. R40 supplies extra game/OS evidence through one bounded snapshot file that is then processed by the same R39 redaction/privacy checks.

The inherited full local exporter is installed as `/usr/local/libexec/r36os/base-export-current-logs`; no stale R39 revision label is kept in an installed runtime path.

## Logging behavior

The existing Diagnostics A(bottom) export action now performs the normal full local export and also attempts the existing privacy-redacted GitHub queue/upload path. The full raw archive remains local. The remote bundle includes the R40 bounded snapshot containing latest game output/session, launch results, milestones, performance summary, Linux preflight, Weston output, selected UI/game-scan diagnostics, resource log, and failed-service state.

The configured private destination is `Hewitt554/R36OS-Device-Logs`. No GitHub authentication token is embedded in this public repository or R40 package. A token must exist locally on the handheld before upload can succeed; otherwise the redacted bundle stays queued on R36STATE.

## R36UPDATE code-25 repair

The physical R39 logs confirmed a real dirty warning for `/dev/mmcblk0p3`, UUID `C49E-0225`. R40 therefore carries a one-time repair gate rather than bypassing code 25.

Before any repair it verifies the exact mounted source, VFAT type, UUID, R36STATE free space, absence of a K1 one-shot/consumed marker, and the existing K1 manifest. It makes and verifies a full R36UPDATE tar backup on R36STATE, performs no forced/lazy unmount, runs the pinned static `fsck.fat` only while R36UPDATE is unmounted, runs a read-only second check, mounts R36UPDATE read-only, verifies the UUID and K1 candidate/manifest again, then leaves R36UPDATE unmounted and requires a clean reboot.

The one-time first-boot runner attempts this only when the exact `FAT-fs (mmcblk0p3)` dirty/not-properly-unmounted/read-only warning is present. Any unexpected identity, busy mount, backup error, fsck error, candidate mismatch, or verification failure stops closed and preserves local evidence.

## Frozen identities

- R39 base SHA-256: `406aa63aedf893b39fdff16f6131f605d99883aa759286228c1cf607dce74ebd`
- K1 candidate: `e551eb6598d6da7a8e8320e9`
- K1 kernel: `6.12.94-r36os-k1`
- Static ARM64 fsck.fat SHA-256: `fe165b0784dd3c301cdf422691b1e5630bd5fab11bca15b8419906b10900d665`
- dosfstools 4.2 source SHA-256: `64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527`

R40 must contain no active `/boot`, `/lib/modules`, `/usr/lib/modules`, K1 Image, DTB, uInitrd, or modules payload.
