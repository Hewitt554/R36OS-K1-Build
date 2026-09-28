# R36OS Alpha 5R43 — full pre-change audit

Date: 2026-09-28
Status: AUDIT COMPLETE ENOUGH TO BEGIN CLEAN IMPLEMENTATION
Rule: the abandoned R43 branch is not a source authority.

## Physical device evidence (Alpha 5R42)

The newest uploaded R42 diagnostics prove:

- Installed userspace: Alpha 5R42 / 0.5.42.0.
- Running kernel remains legacy Linux 4.4.189.
- R36UPDATE is /dev/mmcblk0p3, vfat, UUID C49E-0225.
- The kernel still reports: Volume was not properly unmounted. Some data may be corrupt. Please run fsck.
- The generic R41 systemd generator now executes correctly on the real systemd 242 device.
- The first-boot repair runner executes correctly.
- A pre-repair R36UPDATE tar backup was created successfully on R36STATE.
- The bundled R40 static fsck.fat aborted on the real device with rc=134 / SIGABRT.
- The repair failed closed at code 57.
- K1 remains on the legacy/default path and must not be armed until a later physical log proves R36UPDATE clean.
- The R42 private GitHub diagnostics credential/config works. Remote diagnostic uploads and backlog draining are now proven.

## Exact runtime lineage audited

### R40
R40 introduced:
- r36os-r36update-repair
- static AArch64 fsck.fat
- first-generation one-shot repair wiring
- diagnostics uploader/snapshot integration

The R40 checker binary SHA-256 is:
fe165b0784dd3c301cdf422691b1e5630bd5fab11bca15b8419906b10900d665

It is a statically linked AArch64 glibc executable. Its build log shows:
- iconv detected and enabled
- configure said "checking for working iconv... guessing yes"
- the final binary contains glibc gconv/iconv runtime machinery

Critical R40 validation gap:
the loopback repair test did not execute this shipped ARM binary. It overrode
R36OS_FSCK_FAT with the x86_64 runner's native /usr/sbin/fsck.fat. Therefore
R40 proved the shell repair flow, not target-binary compatibility.

The repair helper also went directly from backup/unmount to:
  fsck.fat -a -V
without a read-only pass against the real filesystem first.

### R41
R41 fixed first-boot activation by installing the generic generator in:
- /etc/systemd/system-generators
- /lib/systemd/system-generators

Physical R42 evidence proves this wiring works. It is retained.

R41 diagnostics record LAST.conf, first-boot status, console output and generator
status, but not the full repair-*.log. This prevented remote diagnostics from
showing the checker stderr around the real abort.

### R42
R42 is a private transition installed on the device. Its effective non-secret
runtime delta from R41 is:
- r36os-kernel-next-prepare release guard 0.5.42.0
- r36os-kernel-slot Alpha 5R42 / 0.5.42.0 / r42-runtime-lock
- r36os-export-current-logs performs two upload-queued passes after the normal
  local export, draining the backlog

R42 also installed the device-local private diagnostics token/config under
/r36state. Those secrets/config are persistent device state and MUST NOT appear
in the public R43 package.

R43 must use the effective R42 core manifest as its baseline. Building a package
that claims base_version=0.5.42.0 while deriving runtime state from R41 is not
acceptable.

### R37 GitHub updater
The updater validates:
- exact repository identity
- alpha channel
- installed version == latest.conf base_version
- target version is newer
- exact filename/size/SHA-256
- pinned GitHub release URL
- embedded R36UPD2 version/base/hardware identity

Therefore a public R43 channel with base_version=0.5.42.0 is compatible with the
current device. The build repository must remain public for anonymous update
transport. The private logs repository remains private.

## Abandoned first R43 attempt — audit failures

The previous work/r43-audited-fat-repair-2026-09-28 branch is rejected as a
source authority because:

1. validate-r43.yml is syntactically invalid YAML. Its Python heredoc bodies
   escaped the YAML block indentation, so GitHub created zero jobs.
2. r43-release/source.tar.gz does not match SOURCE_ARCHIVE.sha256.
   recorded: 0dbc32c64f5345fdab9ae17d733f36b9699140da285f79294b845d437703b2d3
   actual:   8a2384d19c14ac5852e43ec0f43b6a3ff8e6ca5f5d635c226e7963f2a07cab34
3. The committed source.tar.gz is corrupt: gzip reports CRC and length errors.
4. The proposed builder used the published R41 package while declaring
   base_version=0.5.42.0, which could regress the proven R42 uploader/runtime.
5. The proposed full-helper qemu wrapper used an unquoted heredoc containing
   "$@", allowing the outer CI shell to erase the target checker arguments.
6. One result assertion used basic grep with an unescaped alternation:
   '^repair_rc=0|^repair_rc=1', which does not mean alternation without -E.
7. Source was hidden in a binary archive instead of being directly reviewable.

No files from that source archive will be promoted.

## Clean R43 architecture

R43 will use directly committed, reviewable source files. No source.tar.gz.

### FAT checker
- Pinned upstream dosfstools 4.2 source, SHA-256:
  64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527
- Build static AArch64 checker in a pinned older cross-build environment.
- Configure with --without-iconv.
- Run checker with LC_ALL=C / LANG=C.
- Execute the actual AArch64 checker under qemu-user in CI.
- Build it twice and require byte-for-byte identity.
- Package checker SHA metadata.
- Package a small deterministic FAT self-test fixture so the exact checker can
  execute a full read-only filesystem parse on the handheld before R36UPDATE is
  unmounted.

### Repair sequence
1. Exact root/state/device/vfat/UUID/armed-marker checks.
2. Verify packaged checker and fixture hashes.
3. Run packaged checker read-only against the harmless self-test fixture.
4. Verify >=2 GiB R36STATE free.
5. Validate any staged K1 candidate.
6. Create and verify full file backup of R36UPDATE.
7. Normal unmount only; never force/lazy.
8. Run read-only fsck against the real R36UPDATE.
9. If packaged checker cannot complete read-only, probe distinct native
   fsck.fat/dosfsck candidates read-only. No writes have happened yet.
10. Only a checker returning 0 or 1 from the real read-only pass may be used.
11. If precheck says repair is needed, run -a with that checker.
12. Never switch checkers after a write attempt begins.
13. Run final -n verification; require rc=0.
14. Read-only mount; verify UUID and any K1 manifest/candidate identity.
15. Final sync/unmount and PASS_REBOOT_REQUIRED.
16. First-boot runner removes the one-shot marker and automatically reboots only
    after full verification.

### Diagnostics
Capture, bounded/redacted through the existing uploader:
- LAST.conf and LAST-extra.conf
- full newest repair-*.log tail
- checker selection/identity/self-test results
- first-boot console/result
- generator status
- current FAT warning evidence

The R42 two-pass queued upload behavior is preserved exactly.

### K1
R43 does not carry or replace:
- Image
- uInitrd
- DTB
- modules.tar.xz

K1 Boot Next Once remains blocked until the post-R43 physical diagnostics prove:
- repair PASS
- verification rc=0
- clean reboot completed
- no new mmcblk0p3 "Volume was not properly unmounted" warning

## Release blockers

A single clean validation workflow must prove all of these before publication:

1. Source workflow itself parses and starts jobs.
2. No source archive indirection or corrupt source checkpoint.
3. Effective R42 baseline manifest is exact and audited.
4. No token/credential or /r36state secret/config payload.
5. Pinned dosfstools source SHA matches.
6. New checker is AArch64/static/no dynamic NEEDED.
7. New checker is built without iconv.
8. New checker builds twice identically.
9. Actual target checker executes under qemu-user.
10. Clean FAT fixture returns clean under -n.
11. Deliberately dirty FAT32 fixture is detected under -n.
12. Repair corrects the dirty fixture and final -n returns 0.
13. File data survives repair byte-for-byte.
14. Full repair helper uses the actual target checker via a correctly quoted
    qemu wrapper.
15. Armed K1 marker blocks repair before unmount.
16. Simulated checker abort fails closed.
17. Native fallback can only be selected during read-only precheck.
18. No checker switching is possible after write mode starts.
19. Package base_version is exactly 0.5.42.0.
20. K1 helper/runtime identities are exactly 0.5.43.0 / Alpha 5R43.
21. R42 export/upload behavior is preserved.
22. Package contains no active /boot or module-tree payload.
23. Package contains no K1 binary.
24. Package builds twice byte-for-byte identically.
25. Published asset is the exact validated artifact; no rebuild at publish time.
