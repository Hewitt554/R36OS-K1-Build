# Native R36OS Chapter 2 completion handover

Date: 2026-10-01
Status: PASS
Validation run: 36853590230
Validation artifact: R36OS-Native-C02-rootfs
Artifact ID: 11157737003
Validated source head: 182f51989b457ff30cce26f4305f6785d3d1c70c
Recovery branch: backup/native-c02-complete-green-2026-10-01

## Frozen native root

Debian base:
- Debian 13 trixie
- ARM64
- exact snapshot: 20261001T082322Z
- mmdebstrap minbase
- install recommends disabled

Artifact:
- r36os-native-c02-rootfs.tar.zst
- SHA-256: 42eec8dc524fcd821d0919bb3d185a3a0894f5bbf48fa0bf36d0a3834b454fac
- size: 71,184,225 bytes
- resolved package count: 180
- package manifest SHA-256:
  04df91501f801e3af2149167230e25a68f9c68ab33582389dfe52f22cff9a600
- file manifest SHA-256:
  c6fc6f8f9eb3a7bc2dcfdbdd54f8ec56fc3ab7fbf55bcf43d7cfa82618f45305

## Validation evidence

Two independent clean builds from the same pinned Debian snapshot produced:
- identical requested-package manifest;
- identical resolved package/version manifest;
- identical full file/hash manifest;
- identical ROOTFS.conf;
- identical forbidden-dependency report;
- byte-for-byte identical rootfs.tar.zst;
- identical rootfs SHA-256.

The ARM64 audit also passed:
- native ARM64 systemd;
- /sbin/init present;
- systemctl, journalctl and udevadm present;
- kmod/modprobe present;
- nmcli, iw, rfkill and lsusb present;
- static BusyBox present for recovery use;
- machine-id intentionally empty;
- R36OS native identity present.

Forbidden legacy scan PASS:
- no ArkOS runtime;
- no PortMaster path;
- no Weston/Westonpack;
- no Xwayland;
- no Wine;
- no Box64;
- no Steam;
- no EmulationStation;
- no libMali proprietary userspace;
- no CrustyGBM/libcrusty.

## Chapter boundary

Chapter 2 has not:
- installed anything on the R36S;
- modified the live R60 updater;
- changed U-Boot;
- changed legacy 4.4;
- changed K1 Image/DTB/modules;
- changed partitions;
- attempted to boot the new root.

Chapter 3 may consume only the exact rootfs SHA above. If its C02 input differs,
Chapter 3 must fail closed.

Chapter 2 status: PASS.
