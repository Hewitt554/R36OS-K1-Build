# R36OS Alpha 6 CP09: Verified offline backup and restore fixture

**STATUS: Offline filesystem prototype only. Not boot-tested, not flashable, not a real R36S restore utility.**

The CP04 audit established that the inherited Ubuntu 19.10 / ArkOS root occupied around 6.8 GiB of the 10 GiB original root partition. CP06 built a clean Debian 12 ARM64 system archive with 219 packages (~562 MiB allocated, no hardware stack). CP07 built an approximately 0.96 MiB diagnostic-only ARM64 rescue ramdisk. CP08 added a strict SHA256-pinned, uninstalled boot-gate candidate and an in-memory transaction state model.

CP09 adds *real filesystem operations in a disposable test sandbox* so interruption handling is verified beyond an in-memory model:

- Tests only directories inside the system temporary area named `r36os-cp09-sandbox-*` and containing the exact test marker; refuses system roots, drives and unnamed directories.
- Snapshots test files into a ZIP with a SHA-256 manifest and checksums per file.
- Rejects missing/corrupt backups, dangerous relative paths, symlinks, unsupported file types and oversized test fixtures.
- Prepares and hashes all restored files **before** changing the active test directory.
- Writes a journal file with flush/fsync and atomic replace; changes between `active`, `staged` and `quarantine` using same-filesystem renames.
- Injects simulated interruption after writing the journal, moving original data aside, and activating the staged restore; verifies restart/resumption, corrupt staging refusal and retention of the previous directory.
- Never deletes the quarantined original.

## What this does NOT do

The fixture does **not** preserve UNIX metadata, directory permissions, symlinks, device nodes, hardlinks, extended attributes, security labels or empty directories. It is therefore **not suitable for a real Linux root filesystem**. The manifest is an integrity check, **not an authenticated signature**. The tests do not prove journal persistence under actual SD power loss, ext4 health, bootloader behavior, rescue-console output, or automatic fallback. It is not safe to point at `/`, `/boot`, `/dev` or an SD card, and the code intentionally refuses such targets.

CP08's boot candidate still has a fail-open risk if the `booti` attempt returns; it has not been installed. No root filesystem is modified by GitHub CI, and nothing was flashed or published to the live R36OS update channel.

## Path to real recovery

1. Validate exact original 5108-byte `boot.ini` rather than synthetic scripts, and prove the rescue kernel + DTB boot with Panel 4 on a spare SD.
2. Choose a format that preserves ext4 root metadata and special files, plus a signed/version-bound manifest and strict target-partition identity checks.
3. Implement disk-space preflight and a durable two-phase journal on R36STATE, with recovery starting independently of a broken main OS.
4. Simulate SD-card removal/corruption and restore recovery with a loopback ext4 image on a Linux CI host before permitting any hardware repair.
5. Only then generate a complete flashable Alpha 6 installation image and test physical boot with a *spare* SD card.
