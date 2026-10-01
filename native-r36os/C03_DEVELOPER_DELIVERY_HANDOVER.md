# Native R36OS C03 developer delivery — validated handover

Date: 2026-10-01
Status: PASS
Purpose: private physical delivery of frozen Chapter-3 candidate

## Public channel

Unchanged.

main:
- c1f582edf876349269b4212aa6a78f1387aa7ecc

Public latest.conf remains:
- Alpha 5R60
- 0.5.60.0
- 00-R36OS-Alpha5R60-K1WiFiGraphicsLab-FromR59.r36upd

The C03 developer package is NOT published through latest.conf.

## Private developer revision

Version:
- 0.5.60.1

Display identity:
- Alpha 5R60 C03Dev1

Package:
- 00-R36OS-Alpha5R60-C03Dev1-FromR60.r36upd

Size:
- 71635937 bytes

SHA-256:
- 905b55550aafbad7a91f7c82fd3d58710f1d44018f060c692cde46a47c005e67

Validation:
- workflow run 36904408982
- job 110511221938
- artifact 11182474031
- artifact name R36OS-Alpha5R60-C03Dev1-private-update
- result PASS

Two independent clean builds produced byte-identical updater packages.

## Frozen native candidate

Native C03 candidate:
- 8f8eaa3bae6ad4352b4e01ef

Native rootfs SHA-256:
- 08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4

Native C03 uInitrd SHA-256:
- be567cd71bc95c35cfdaf7100ee0846517df5cd78538e4f3da6157a7fa61d694

K1 candidate:
- 9d7bd2334f315d98b482f850

Kernel:
- 6.12.94-r36os-k1

The developer package does not alter:
- legacy Linux 4.4;
- K1 Image;
- K1 DTB;
- K1 module tree;
- U-Boot binary;
- partitions.

## UI/control change

The existing R58/R60 framebuffer UI was reconstructed from exact audited
source lineage and rebuilt with one developer-only control surface.

Diagnostics:
- R1 opens Native C03 developer controls.

Controls:
- Status / refresh
- Stage native root only
- Arm Native Boot Once
- Disarm native request

Arm Native Boot Once has a second confirmation screen.

Rebuilt UI SHA-256:
- 4a5941bbee504b18ab018d8dea017ef4ce95c97e254645d1f9f3d562ed7a4f9c

The R58 K1 split-input behavior remains in the rebuilt UI.

## Version-gated helper transforms

Authenticated R60 inputs were transformed only from 0.5.60.0 to 0.5.60.1.

r36os-kernel-next-prepare:
- output SHA-256
  51ff760497aa34adc15656fdee47938bf560131a3e27b737a9bb1f15fe9c0756

r36os-kernel-slot:
- output SHA-256
  3c690c9ea7e8b29d21e041aad4f479ce4ed54c6bda1efd5852cadad17ab27f4a

r36os-r36update-maint:
- output SHA-256
  1961d1938224e046d41aa281383883f97d592c209c4b90d99e66e086e095c5fc

The packaged C03 prepare helper was also changed only from:
- EXPECTED_VERSION=0.5.60.0
to:
- EXPECTED_VERSION=0.5.60.1

Its C03 bundle manifest was regenerated afterward.

## Automatic-action safety

Final package audit proves:
- auto_stage=no
- auto_arm=no
- auto_boot=no
- public_channel_change=no

The update payload contains:
- no boot-native.*.once request;
- no R36N3.CNS consumed marker;
- no systemd unit that automatically invokes stage-only or arm-once;
- no /boot replacement;
- no /lib/modules replacement;
- no /usr/lib/modules replacement.

Installing C03Dev1 therefore returns to the normal R36OS UI first.

## Intended physical sequence

1. Install C03Dev1 from normal legacy R60.
2. Reboot and allow the normal transactional updater to finish.
3. Confirm R36OS identifies as Alpha 5R60 C03Dev1.
4. Diagnostics -> R1 -> Native C03 developer controls.
5. Choose Stage native root only.
6. Confirm Status shows staged/ready.
7. Only then choose Arm Native Boot Once.
8. Confirm the second warning screen.
9. Reboot exactly once for the native C03 test.
10. Return to legacy after PASS/failure and upload diagnostics/evidence.

Full physical procedure:
- native-r36os/C03_DEVELOPER_DELIVERY_TEST.md
- native-r36os/C03_PHYSICAL_BOOT_ONCE_TEST.md
