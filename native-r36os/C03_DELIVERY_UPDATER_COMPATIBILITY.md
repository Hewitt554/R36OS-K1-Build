# Native C03 developer delivery — R36UPD2 compatibility audit

Date: 2026-10-01
Status: PASS for the proposed 0.5.60.1 private delivery model

This audit is based on the preserved R36OS transactional updater v3
prepare/stage2/health semantics that the current release lineage retains.

## Why the developer delivery is 0.5.60.1

The normal updater rejects:
- base_version != current installed version;
- version == current installed version;
- versions that sort below the installed version.

Therefore a same-version C03 overlay cannot be delivered safely as an ordinary
.r36upd.

Proposed private delivery:
- installed/base version: 0.5.60.0
- developer target: 0.5.60.1

sort -V ordering:
0.5.60.0 < 0.5.60.1

The public update channel remains 0.5.60.0 and is not advanced.

## Prepare-stage rules

R36UPD2 prepare requires:
- format=R36UPD2;
- hardware=R36XX-RK3326;
- manifest.conf;
- checksums.sha256;
- payload/root;
- exact base-version match;
- higher target version;
- sufficient R36STATE free space;
- no payload symlinks;
- no payload files under:
  /boot
  /lib/modules
  /usr/lib/modules

The C03Dev1 builder explicitly checks those restrictions.

The ~72 MiB package easily fits the previously observed ~38 GiB free
R36STATE space.

## Activation/rollback rules

Stage2:
- re-opens and re-hashes the staged package;
- verifies base version again;
- snapshots every destination that will be replaced;
- records newly created paths separately;
- atomically moves each staged file into place;
- re-hashes every installed payload file;
- leaves pending.conf until runtime health succeeds;
- restores the previous snapshot on activation failure.

This is appropriate for C03Dev1 because it changes only userspace files under
/etc, /usr/local/bin and /opt/r36os.

The developer package does not replace:
- /boot;
- legacy kernel files;
- K1 Image;
- K1 DTB;
- K1 module tree.

## Runtime health compatibility

Updater health requires:
- R36OS first-frame heartbeat;
- UI version == target package version;
- release helper version == target package version;
- core-integrity PASS;
- regression self-test critical_failures=0.

The R36OS framebuffer UI reads R36OS_PACKAGE_VERSION from /etc/r36os-release
at startup and writes that value to /run/r36os-ui-version.

Therefore the developer package updates:
/etc/r36os-release -> 0.5.60.1

and the rebuilt UI will naturally report 0.5.60.1 without embedding a separate
version constant.

The cumulative core manifest is advanced for:
- rebuilt r36os-alpha5;
- the three version-gated K1/R36UPDATE helpers;
- the Native C03 control wrapper;
- the critical small C03 bundle metadata/control files.

## Version-gated helper compatibility

C03 stage/arm relies on:
- r36os-kernel-next-prepare
- r36os-kernel-slot
- r36os-r36update-maint

R60 versions of those helpers contain exact 0.5.60.0 safety gates.
The developer package transforms only those exact authenticated R60 inputs to
0.5.60.1 and rejects unexpected preimage hashes.

The packaged copy of r36os-native-c03-prepare is also transformed from:
EXPECTED_VERSION=0.5.60.0
to:
EXPECTED_VERSION=0.5.60.1

Its C03 bundle manifest is regenerated after that one allowed delivery
transformation. Native candidate, native rootfs, native uInitrd and boot hook
identities are not changed.

## Automatic-action audit

C03Dev1 intentionally has:
- auto_stage=no
- auto_arm=no
- auto_boot=no

No boot-native.*.once request is included in the update payload.
No R36N3.CNS consumed marker is included.
No systemd unit automatically invokes stage-only or arm-once.

The user must explicitly enter the Diagnostics Native C03 developer screen and
choose an action.

Arm Native Boot Once also requires a second confirmation screen.

## Conclusion

The normal transactional updater is an appropriate delivery mechanism for the
private C03 developer revision as long as the final package validation proves
the declared file set and hashes.

This developer revision must not be published through latest.conf.
