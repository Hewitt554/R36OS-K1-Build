# R36OS K1 — Run #11 Success Recovery Handover

## Authoritative recovery point
- Repository: Hewitt554/R36OS-K1-Build
- Backup branch: backup/run11-success-2026-09-28
- Successful source commit: `42464c308fafe64cb754f33734f41eb292a591af`
- Run: #11
- Run ID: `36384548493`
- Job ID: `108807082129`
- Workflow: `.github/workflows/build-k1.yml`
- Bootstrap: `bootstrap_r36os_k1.sh`
- Kernel release: `6.12.94-r36os-k1`
- Canonical Panel-4 DTB: `rk3326-r36s-k1.dtb`

## Verified Run #11 result
Run #11 completed successfully. The final log explicitly records:
- CP04 artifact validation: PASS
- uInitrd_status=PASS
- CP05 candidate validation: PASS
- CP05 candidate complete
- STATUS=PASS CP04+CP05 result packaged
- CP04_CP05_EXTERNAL_BUILD=PASS
- CLOUD_BUILD=PASS

Final inner result archive:
- `R36OS_K1_CP04_CP05_RESULT_20260928T071300Z.tar.gz`
- SHA-256: `b6cb1bf7d85592ff08a16a292d6db113c48919393c5442da24c1b8d4603dc443`

GitHub Actions success artifact:
- Name: `R36OS-K1-CP04-CP05-result`
- Artifact ID: `10956121963`
- Uploaded ZIP size: `560630700` bytes
- Uploaded ZIP SHA-256: `8e990c485b68e0dac3752da7d46ea0aca10fcedec04818fa304b0ceb3fd6df2f`
- Retention expiry reported by GitHub: 2026-10-12T07:14:05Z

Important: the GitHub connector cannot download this artifact because it exceeds its 512 MiB connector limit. Retrieve it directly from GitHub Actions before expiry if an offline copy is required.

## Cloud8 fix that made Run #11 pass
Runs #9 and #10 proved the kernel/DTB/modules build was already good. The remaining failure was the BUILD.log checksum race.

Cloud8:
1. Uses the exact immutable Run #9 bootstrap as its base.
2. Verifies the Run #9 bootstrap Git blob SHA-1 before patching.
3. Inserts its correction after the CP04 build/tee has closed.
4. Discovers the real checksum manifest by locating the unique checksum entry for `BUILD.log` rather than assuming a filename.
5. Refreshes only the final BUILD.log SHA-256.
6. Self-verifies the refreshed digest.
7. Leaves the normal CP04 validator and CP05 path intact.

Run #11 proves this fix works:
`CLOUD8=PASS refreshed final BUILD.log digest manifest=SHA256SUMS.txt`
followed by repeated CP04 and CP05 PASS results.

## K1 project safety requirements that remain mandatory
- Legacy Linux 4.4 remains untouched as the stable fallback.
- K1 must be tested as a Boot Once candidate first.
- Do not make K1 permanent until on-device validation passes.
- Candidate layout target:
  `R36UPDATE/R36OS-KernelNext/K1/{Image,uInitrd,DTB,manifest,modules,BUILD_INFO}`
- Boot Once prechecks: SHA-256, Panel-4 match, root UUID, clean FAT, not marked bad.
- U-Boot must write a consumed marker before jumping to K1 so a failed/hung K1 attempt falls back to legacy on next boot.
- Preserve pstore/ramoops diagnostics where possible.

## First on-device K1 success criteria
Verify:
- screen and backlight
- SD storage
- controls/input/FN
- audio and headphones
- battery/charge reporting
- USB
- power button and clean shutdown
- thermals and CPUfreq
- Panfrost binding
- `/dev/dri` nodes
- no kernel Oops/panic/hang

Only after those pass should the project move on to modern Mesa/Panfrost userspace, Wayland/Weston, accelerated Xwayland, Box64/Wine validation and GPU telemetry.

## Performance/build workflow improvement still planned
The current workflow caches frozen downloads, but a validator-only change still forces a full ~1 hour kernel rebuild.
Next workflow improvement should:
- preserve successful CP04 binaries independently from validation,
- key CP04 build reuse to exact kernel source/config/DTS/patch inputs,
- restore CP04 outputs for validator/CP05-only retries,
- optionally add compiler ccache,
- avoid aggressive kernel-config trimming until the first successful on-device K1 boot.

## R36OS project reminders
- Hardware: RK3326, 1 GB RAM, Mali-G31, RK817, Panel 4 640x480 MIPI-DSI.
- Current K1 target is Linux 6.12 LTS with Panfrost.
- Existing legacy 4.4 stack must remain recoverable.
- User wants a safe path with no brick risk.
- R36STATE expansion is already complete.
- FAT partition must be clean before staging K1.
- Kexec is unavailable on legacy 4.4.

## Recovery procedure
If development goes wrong:
1. Checkout `backup/run11-success-2026-09-28`.
2. Confirm HEAD is based on success commit `42464c308fafe64cb754f33734f41eb292a591af`.
3. Use the bootstrap/workflow from this branch as the known-good cloud build state.
4. Compare any later changes against this branch.
5. Do not discard the successful Run #11 artifact metadata/checksums above.
6. Continue from the Boot Once/on-device test milestone, not from kernel compilation.

