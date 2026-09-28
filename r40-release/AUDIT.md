# R40 consolidated pre-validation audit — 2026-09-28

Status: source audit completed before the next validation run.

## Why previous validation runs are discarded

Several WIP commits triggered validation independently. They failed before a stable candidate existed. Runs associated with those incremental edits are not release evidence.

The audit found:
1. The prior `.github/workflows/validate-r40.yml` had duplicated/corrupted YAML near the package-audit step; the newest malformed revisions could not even create a job.
2. An unused WIP `r40-release/r36os-github-diagnostics` had duplicated text after its case statement and failed `bash -n`.
3. That modified uploader was not actually used by the current builder, which already had the safer architecture of extracting the exact verified R39 uploader.
4. Unused UI/token/compatibility experiments remained in `r40-release/`, creating multiple possible source authorities.
5. The K1 slot helper transformation changed only `0.5.39.0` and would have left stale `Alpha 5R39` / `r39-runtime-lock` identity in an installed runtime script.
6. The inherited exporter runtime path contained `r39` even though R40 requires authoritative current-version identity.

## Consolidated resolution

- One authoritative source set only; unused/corrupted WIP files are removed.
- Verified R39 GitHub uploader remains byte-for-byte immutable.
- R40 game/OS evidence enters the redacted remote bundle via one bounded snapshot `.conf`.
- Inherited exporter runtime path is revision-neutral: `base-export-current-logs`.
- K1 prepare/slot are derived from the exact R39 package and receive only the required R40 userspace identity changes; K1 binaries remain untouched.
- Packaging fails if stale R39 version identity remains in installed runtime scripts.
- One clean validation workflow performs syntax checks, privacy self-test, FAT repair loopback tests, deterministic double build, package/path audit, immutable-uploader comparison, game-log redaction integration, and corresponding-source preservation.
- The next validation commit/run is the first evidence to consider for R40 release readiness.
