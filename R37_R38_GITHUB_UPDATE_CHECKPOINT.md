# R36OS — R37 GitHub Updater → R38 K1 delivery checkpoint

Date: 2026-09-28

## Why this checkpoint exists
The physical BOOT partition is too small for the first K1 update package. The delivery architecture was therefore split:

1. Alpha 5R37 / 0.5.37.0 is a tiny GitHub Updater Bootstrap that still fits the legacy BOOT-based update path.
2. R37 downloads future verified updates to R36STATE instead of BOOT.
3. Alpha 5R38 / 0.5.38.0 is the first GitHub-delivered K1 Boot Next Once update.
4. R38 remains a normal R36UPD2 transactional update; GitHub changes only transport/storage, not installation safety.

## R37 bootstrap
Filename:
`00-R36OS-Alpha5R37-GitHubUpdater-FromR36.r36upd`

Base:
- from 0.5.36.0
- to 0.5.37.0

Size:
- 106097 bytes

SHA-256:
`594cb6eb0e433e08fabcbc20e00395795607f962e7cb768d81dad336d723bc48`

R37 carries no kernel, DTB, initramfs, active /boot payload, or module payload.

R37 adds:
- GitHub release-channel checking
- resumable download to /r36state/update/downloads
- .part handling
- exact size/SHA-256 verification
- strict repository/release URL allowlisting
- embedded R36UPD2 manifest verification
- handoff to the existing transactional updater
- local .r36upd install remains available
- retention of only the last two completed downloaded update packages

The combined UI fails closed for K1 on R37 and tells the user that K1 arrives with Alpha 5R38.

## R38 GitHub Release
Release tag:
`alpha5r38`

Release:
`R36OS Alpha 5R38 — K1 Boot Next Once`

Filename:
`00-R36OS-Alpha5R38-K1BootNextOnce-FromR37.r36upd`

Base:
- from 0.5.37.0
- to 0.5.38.0

Published size:
- 264539986 bytes

Published SHA-256:
`68db42212fc0e13a9bad777daf68f4634bb86f58aa2347a923dde8cd71db30c0`

GitHub release asset ID:
- 595192907

Publish workflow:
- name: Publish R36OS Alpha 5R38
- successful run: #4
- run ID: 36412818918
- job ID: 108896801040
- successful source commit: 8e68bd1d9a44bcb96279e41f59b179e43b3b3c9f

Release-channel publication commit:
`2244ad641a6092cb892378bca196f4ceefa8e63b`

## Published channel manifest
Path:
`r36os-release-channel/latest.conf`

Content identity:
- format=R36OS_REMOTE_UPDATE_V1
- repo=Hewitt554/R36OS-K1-Build
- channel=alpha
- version=0.5.38.0
- base_version=0.5.37.0
- size_bytes=264539986
- sha256=68db42212fc0e13a9bad777daf68f4634bb86f58aa2347a923dde8cd71db30c0
- candidate_id=e551eb6598d6da7a8e8320e9
- kernel_release=6.12.94-r36os-k1

The release asset metadata, workflow output and latest.conf were checked against each other and match exactly.

## K1 identity in R38
Candidate ID:
`e551eb6598d6da7a8e8320e9`

Kernel:
`6.12.94-r36os-k1`

Run #11 Image SHA-256 retained exactly:
`a7a388d5ca21b276bddcc0e3892b0c965b73d92f2c0238cb9c25a210dba7c97e`

Run #11 Panel-4 DTB SHA-256 retained exactly:
`e2145905b1beb8d0f5b9dee6c5a21d31c29474be8762c893e81506fc40e627f4`

Hardened uInitrd SHA-256:
`6d44f435bd88b54e91af569fd6445db460b9ab80313062b8136796f27b888f6e`

Module tree:
- 1290 files
- 1091383701 uncompressed bytes
- sanitized before candidate packaging

Cloud build output:
`R38_RELEASE_BUILD=PASS candidate_id=e551eb6598d6da7a8e8320e9 size=264539986 sha256=68db42212fc0e13a9bad777daf68f4634bb86f58aa2347a923dde8cd71db30c0`

## Safety model remains unchanged
- Installing R37 does not change the kernel/boot payload.
- Installing R38 still leaves legacy Linux 4.4 as normal/default.
- R38 does not auto-arm K1.
- K1 is attempted only through explicit Boot Next Once.
- Matching 6.12 modules are staged to exact R36STATE, not over legacy modules.
- Candidate integrity, root/state identities and boot state are validated before arming.
- U-Boot consumed-marker logic is required before jumping to K1.
- A failed/hung K1 attempt is expected to return to legacy on the next power cycle.
- One successful K1 boot is not permission to promote it to permanent/default.

## Recovery
Pinned recovery branch:
`backup/r37-r38-github-updater-2026-09-28`

Branch base:
`2244ad641a6092cb892378bca196f4ceefa8e63b`

Older Run #11 recovery branch remains:
`backup/run11-success-2026-09-28`

If later updater/release work breaks, recover the transport layer from the R37/R38 branch and the K1 binary foundation from the Run #11 branch.
