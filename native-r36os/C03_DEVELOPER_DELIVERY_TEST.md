# Native R36OS C03 developer delivery — physical test sequence

Status: PREPARED, package validation pending

This is a private developer delivery only. It is not part of the public
R36OS update channel.

## Intended developer revision

- Base: Alpha 5R60 / 0.5.60.0
- Private revision: 0.5.60.1
- Public latest.conf remains 0.5.60.0.
- C03 native candidate remains 8f8eaa3bae6ad4352b4e01ef.
- Existing K1 candidate remains 9d7bd2334f315d98b482f850.

The developer update installs the frozen C03 bundle and a Diagnostics control
screen. It does not stage, arm or boot C03 automatically.

## Phase A — install developer update

1. Boot normal legacy R60.
2. Place/install the private C03Dev1 .r36upd using the ordinary R36OS updater.
3. Let the normal transactional updater reboot and apply it.
4. It should return to the normal R36OS UI as Alpha 5R60 C03Dev1.
5. Do NOT select Native Boot Once yet.

Expected normal update health:
- first R36OS frame appears;
- release/UI identity is 0.5.60.1;
- core-integrity gate passes;
- ordinary regression gate passes;
- no native request marker exists.

## Phase B — Stage Only

Open:
Settings -> Diagnostics -> R1 -> Native C03 developer controls

Choose:
Stage native root only

This may take noticeably longer than a normal menu operation because the
~303 MiB logical native root is extracted and every regular file is hashed.

Expected result:
- PASS message;
- native root is staged at /r36state/r36os-next/rootfs;
- C03_READY.conf is present;
- normal boot path remains unchanged;
- no Native C03 one-shot request exists.

After Stage Only:
- use Status / refresh;
- expected Native root = Staged;
- expected Ready marker = Present.

Do not arm if Stage Only reports FAIL.

## Phase C — controlled Arm Once

Only after Stage Only is PASS:

1. Select Arm Native Boot Once.
2. A second confirmation page appears.
3. Confirm with A(bottom).
4. Wait for the explicit PASS message:
   Native C03 armed ONCE - reboot when ready.
5. Do not press Arm again.

The arm transaction:
- verifies the frozen C03 bundle;
- verifies exact host/version/R36STATE;
- refuses a pending ordinary K1 Boot Once;
- re-verifies/stages K1 without arming ordinary K1;
- verifies the staged native root;
- installs the audited C03 boot hook;
- stages the C03 uInitrd;
- writes the native request as the final boot-affecting write;
- closes/unmounts the private R36UPDATE write window.

## Phase D — one physical native boot

After Arm Once PASS, reboot normally once.

Expected U-Boot text:
- R36OS Native C03 one-shot boot
- [1/5] Native one-shot guard verified
- [2/5] Existing K1 Image loaded
- [3/5] Native C03 initramfs loaded
- [4/5] Existing Panel-4 DTB loaded
- [5/5] Starting native Debian userspace on 6.12.94-r36os-k1

Expected initramfs progress includes:
- native-initramfs-start
- state-discovery
- state-mounted
- native-root-ready
- exec-native-systemd

Expected C03 success screen:
PASS: native Debian systemd root reached HEALTHY.

No graphics UI, Wi-Fi, audio, games or Steam are required for C03 PASS.

## Failure handling

If it hangs:
- photograph the exact displayed stage;
- wait long enough to be sure it is not merely extracting/booting;
- power-cycle once.

Do not repeatedly re-arm.

The consumed marker is written before Linux starts, so the following normal
power cycle should return to the existing R60/R60.1 legacy path rather than
attempting C03 again.

If the developer menu was armed by mistake before reboot, choose:
Disarm native request

## Evidence after the attempt

Whether PASS or FAIL, return to the normal legacy environment and upload:
- a normal diagnostics bundle;
- C03_EARLY.conf if present;
- C03_HEALTH.conf if present;
- C03_CONTROL.log;
- any visible boot-stage photo/message.

Chapter 4 must not begin until this evidence is reviewed.
