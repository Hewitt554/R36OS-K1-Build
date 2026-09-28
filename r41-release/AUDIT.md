# R41 pre-validation audit

Scope is intentionally limited to evidence from the user's first R40 boot.

Observed on the physical device:
- release is Alpha 5R40 / 0.5.40.0;
- active kernel remains legacy 4.4.189;
- R36UPDATE is /dev/mmcblk0p3, UUID C49E-0225;
- the dirty FAT warning is still present at mount time;
- no first-boot repair result is present;
- systemd is version 242;
- GitHub diagnostics queue works (10 queued, 0 sent) but status is upload-disabled;
- K1 is not armed and the staged candidate on R36UPDATE is absent (candidate_verify_code=20), consistent with code 25 having stopped staging before K1 was copied;
- normal boot regression checks pass.

R41 therefore changes only activation/wiring and diagnostic evidence. It reuses the verified R40-installed repair helper and private diagnostics uploader.

Release blockers:
- exact R40 base SHA must match;
- R41 carries no K1 Image/uInitrd/DTB/modules and no active /boot or module-tree payload;
- K1 userspace helpers must require 0.5.41.0 with no stale R40 identity;
- both generator locations must be packaged;
- generator must create the expected transient wants link in an isolated test;
- exact R40 repair helper must pass the same loopback repair and armed-marker refusal tests;
- R41 package must build identically twice;
- effective R40+R41 runtime must have generic snapshot/firstboot names and no superseded R40 version-labelled runtime entries in the core manifest.
