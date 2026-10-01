# Native R36OS C04 — required C03 physical gate

Chapter 4 preparation may exist in Git before the handheld is tested, but no
C04 native boot candidate may be built/published until the exact C03 candidate
has physically reached its systemd health gate.

Required physical evidence:

- C03 native candidate: 8f8eaa3bae6ad4352b4e01ef
- C03 rootfs SHA-256:
  08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4
- K1 candidate: 9d7bd2334f315d98b482f850
- kernel: 6.12.94-r36os-k1
- C03_HEALTH.conf status=PASS
- C03_HEALTH.conf detail=native-systemd-healthy
- PID 1 reported as systemd

A reviewed gate file will use:

format=R36OS_NATIVE_C03_PHYSICAL_RESULT_V1
status=PASS
source=physical-r36s
native_candidate=8f8eaa3bae6ad4352b4e01ef
rootfs_sha256=08214b18d833b8abed0ab86c0140774a0759f075e4d8ea454d85567590b53ec4
k1_candidate=9d7bd2334f315d98b482f850
kernel_release=6.12.94-r36os-k1
health_status=PASS
health_detail=native-systemd-healthy
pid1=systemd
c03_health_sha256=<sha256 of uploaded physical C03_HEALTH.conf>
evidence_bundle_sha256=<sha256 of the reviewed uploaded diagnostics bundle>

The validator deliberately rejects:
- missing gate;
- FAIL/unknown status;
- wrong candidate/root/kernel identities;
- non-physical source;
- missing evidence hashes;
- placeholder hashes.

Until this gate exists and has been reviewed, C04 remains PREPARATION ONLY.
