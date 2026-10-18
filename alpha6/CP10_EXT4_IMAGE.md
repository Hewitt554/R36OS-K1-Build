# R36OS Alpha 6 CP10 — Disposable ext4 image recovery tests

**Status:** development-only, UNTESTED ON DEVICE, not suitable for real SD card recovery. CP10 never writes an SD block device and cannot be used as a system restore command.

CP09 restored regular files in temporary directories but could not preserve Linux filesystem metadata (permissions, symlinks, xattrs, device nodes, ext4 identity). CP10 tests a different approach: create a genuine 32 MiB ext4 image on a CI runner using mke2fs, store the complete image in a gzip backup with SHA-256 checksums, verify the archive, fully materialize a *separate* staged ext4 image, run read-only `e2fsck -fn` and ext4 UUID checks, and only then do reversible same-directory renames between `active.ext4`, `staged.ext4` and `quarantine.ext4`.

The underlying raw filesystem bytes — and therefore all metadata inside the ext4 image, including file modes, symlinks and UUID — are preserved without file-by-file interpretation. The original active image is *never deleted*; the quarantine remains after restoration. CI also uses debugfs to inspect the restored executable mode and symlink inode.

## Guardrails

The sole allowed workspace is a specially named directory below the OS temp directory with a fixed marker. All artifact names are allowlisted and must be regular files; symlinks and other file types are rejected. Neither the tool nor its CI job uses mount/losetup or touches `/dev/mmcblk*`. `mke2fs` is invoked only on a regular 32 MiB *scratch image file*. This is a **test fixture, not production code**. No flash image is produced or installed.

The journal records `READY -> VERIFIED -> PREPARED -> SWAPPING -> RESTORED`. Simulated interruptions occur after recording SWAPPING, after quarantining the prior ext4 image, and after activating the staged image. Resume revalidates snapshot, staged/restored hash, ext4 UUID, and e2fsck result. If any check fails, normal boot is considered unsafe in the model.

## Explicit limitations

- Archive manifest checksums verify accidental corruption; the manifest is **not authenticated** and no signing implementation exists.
- Whole-ext4 backups could be large on a real device; the 32 MiB test is not an estimate for a 64 GB SD installation. Compression ratio depends on free-space zeroing and contents.
- It does not yet recognize real hardware partition identifiers, preserve crash consistency of a *mounted* root, or implement actual writing back to a partition. Source capture would require an offline/quiesced root.
- `fsync` calls and simulated exceptions do not prove power-loss persistence or SD wear handling.
- No R36S kernel 4.4 or K1 rescue image has yet been physically boot-tested; no U-Boot hook is installed; there is no automatic recovery from a failed boot.
- Real root restore requires a safe partition-write method, a separately booted rescue environment and verified target identity before it is ever enabled.

## Next

Validate the full original R3 boot.ini input to CP08; add boot script syntax validation; establish independent recovery boot on a spare SD1; implement signed, identity-bound snapshot manifests and offline restore to a disposable partition device under privileged CI only after safety review. Keep existing public release channel unchanged.