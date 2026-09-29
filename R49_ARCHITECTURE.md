# R36OS Alpha 5R49 — R36UPDATE isolation / maintenance redesign

Date: 2026-09-29

## Why R49 exists

Physical R48 evidence established:
- stale K1 request cleanup succeeded (STALE_K1_DISARM_PASS);
- the device remained safely on Linux 4.4.189;
- the old FAT repair then stopped at rc=51;
- rc=51 is pre-repair-backup-failed;
- fsck had not yet run.

The R43-R48 repair architecture required a full tar backup of the mounted R36UPDATE FAT filesystem before unmounting it. Meanwhile legacy R36OS components still treated R36UPDATE as general writable storage for caches, logs, update paths and Kernel Lab. This is an architectural conflict, not a reason to keep adding repair exceptions.

## New invariant

/dev/mmcblk0p3 (R36UPDATE, UUID C49E-0225) is boot-handoff storage only.

Normal userspace:
- real R36UPDATE is mounted read-only;
- there is no public policy command that remounts /r36update read/write;
- legacy writable subpaths are compatibility bind mounts backed by R36STATE when their FAT directories already exist.

Controlled K1 maintenance:
- verifies the authoritative K1 source under /opt/r36os/kernel-next/K1;
- unmounts the real FAT filesystem;
- blocks normal processes with a read-only empty guard mounted at /r36update;
- runs fsck against the unmounted block device;
- mounts the real FAT read/write only at /run/r36os-r36update-rw;
- reuses the staged K1 only when it exactly matches the authoritative source, otherwise reconstructs it from /opt;
- returns the real FAT read-only after staging;
- installs/verifies the U-Boot hook while FAT is read-only;
- opens another guarded private marker window for the one-shot request;
- cleanly unmounts the real FAT before reporting Boot Next Once armed.

The long K1 copy and tiny one-shot marker writes never expose the actual FAT as writable at /r36update.

## Recovery model

The full-partition tar backup is retired.

Recovery evidence now consists of:
- authoritative K1 candidate ID;
- authoritative manifest hash;
- authoritative full file-tree digest;
- staged manifest/identity where readable;
- FAT file index;
- fsck precheck/repair/final verify codes;
- mount transitions and maintenance log.

K1 staging is reconstructible from the authoritative /opt source. The exact published R38 package is separately validated to contain the K1 candidate. Later K1 updates must maintain the same two-copy model: authoritative root source + disposable FAT staging copy.

## Existing writable-path compatibility

R49 does not rewrite every old cache/log consumer in one release. Instead, when these directories already exist on R36UPDATE, the read-only base mount is overlaid with R36STATE bind mounts:
- /r36update/R36OS-Cache
- /r36update/R36OS-Logs
- /r36update/R36OS-KernelLab
- /r36update/update

This keeps old paths writable without writing the FAT filesystem.

## Update / rollback behavior

R49's transactional rollback isolates and normally unmounts R36UPDATE before rollback restores/removes R49 files. Rollback evidence is stored on R36STATE/SD2, not on FAT.

The old automatic first-boot FAT repair helper is retired. Its compatibility entry point reports RETIRED rather than modifying FAT.

## K1 health behavior

K1 success/fallback marker cleanup also uses the guarded private FAT window. It does not remount public /r36update writable.

## Non-goals

R49 does not:
- replace K1 Image, DTB, uInitrd or modules;
- make K1 permanent;
- remove legacy Linux 4.4;
- change U-Boot raw sectors;
- fix the flashing blue top-left cursor. That remains a separate boot/TTY visual issue.

## Publish gates

R49 cannot publish unless CI proves:
1. exact published R48/R47/R43/R39 input SHA-256 values;
2. exact published R38 package contains the authoritative K1 source files;
3. deterministic double-build;
4. no K1 binaries in the R49 payload;
5. exact R43 target-validated fsck checker/fixture retained;
6. normal /r36update is read-only;
7. public RW policy commands do not exist;
8. legacy writable compatibility paths land on R36STATE, not FAT;
9. direct slot arm fails on the normal read-only mount;
10. clean FAT maintenance succeeds;
11. repair-needed FAT path runs precheck -> repair -> final clean verification;
12. checker failure restores safe read-only state;
13. staging failure restores safe read-only state;
14. marker-write failure is recoverable without leaving FAT exposed writable;
15. busy final private unmount fails closed and can be restored to read-only;
16. successful Boot Next Once ends with both public and private FAT mounts absent;
17. rollback contains no forced/lazy unmount or forced reboot.