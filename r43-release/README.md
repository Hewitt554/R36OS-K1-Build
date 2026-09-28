# R36OS Alpha 5R43 — FAT checker runtime compatibility fix

R43 is a focused follow-up to the physical R42 repair failure. R42 proved that the generator/service activation is fixed, but the R40 static fsck.fat aborted with rc 134 on the real RK3326 Linux 4.4 system.

R43 does not change the K1 Image, uInitrd, DTB, modules or candidate identity.

Changes:
- rebuild dosfstools 4.2 fsck.fat using an older AArch64 glibc-era cross toolchain;
- validation rejects the newer __libc_arm_za_disable runtime from this checker;
- run read-only fsck preflight before any repair write;
- use fsck.fat -a without the redundant -V mode;
- independently verify with fsck.fat -n;
- save complete latest fsck output as /r36state/logs/r36update-repair/LAST-fsck.log;
- include that log, live repair status and kernel-slot status in remote diagnostics;
- re-arm the one-time R36UPDATE repair on first R43 boot;
- preserve the existing device-local GitHub diagnostics credential without shipping it in R43.

K1 remains legacy-default and must not be Boot Next Once tested until a post-R43 diagnostic confirms the FAT warning is gone and repair verification passed.
