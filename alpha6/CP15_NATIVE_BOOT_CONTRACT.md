# R36OS Alpha 6 CP15 — K1 native initramfs and root identity contract

**Development-only. NOT BOOT TESTED. NOT FLASHABLE.** Do not install or use with current SD1/SD2, U-Boot `boot.ini`, or an R36S until separately hardware-validated.

## Boot flow model

CP14 has a genuine Debian 12 ARM64 native userspace with the Linux `6.12.94-r36os-k1` module tree (1,278 `.ko*` files) installed into `/usr/lib/modules/6.12.94-r36os-k1`. Its disposable 4 GiB ext4 root was checked with read-only e2fsck but was **not booted**. The historic K1 `uInitrd` still expects the old R3 root UUID.

CP15 creates its *own* statically linked ARM64 BusyBox `newc`/gzip initramfs. The `/init` script reads exact required kernel parameters:

    rdinit=/init r36os.boot_mode=native-dev r36os.root_uuid=<NEW_ROOT_EXT4_UUID> r36os.kernel_release=6.12.94-r36os-k1

The selected root UUID is obtained from **the CP14 disposable ext4 build report** for each CI run. This is not a fixed production UUID, boot script or end-user setting. The script refuses missing/duplicate parameters, any legacy R3 root UUID, wrong kernel release, wrong filesystem identity, and a native OS without its fail-closed update policy or matching modules.dep. It probes `mmcblk*p*` using a tiny statically linked AArch64 C utility (`r36os-probe-root`), which reads only the fixed ext4 superblock bytes to verify UUID, ext4 extents feature and the R36SYS label. The historical BusyBox-static build lacks `blkid`, so no BusyBox `blkid` dependency is assumed. The probe refuses non-MMC/non-block paths in the deployed build. GitHub tests the same filesystem parsing on a regular scratch ext4 file through a distinct fixture-only compile flag. Root is mounted ext4 **read-only, `noload`**, and the basic native identity is checked before `switch_root /newroot /sbin/init`. It never applies updates or writes backup/restore commands.

CP15 packages **two mutually alternative development headers** around identical gzip payload bytes: a U-Boot AArch64 (`IH_ARCH_ARM64=22`) ramdisk and the ARM (`IH_ARCH_ARM=2`) header observed on the archived K1 `uInitrd`. Valid CRC/metadata in both variants does not establish physical bootloader acceptance. The boot-argument preview must **never** be copied to `boot.ini` without a reviewed, hardware-tested boot chain.

## Still blocking device boot

1. The Linux 6.12.94 K1 kernel must have the MMC host/SD and ext4 root drivers built-in, **or CP15 must be extended with an ABI-matched minimal early-module closure and dependencies**. CP15 intentionally does not embed 1 GiB of general-purpose modules into RAM. This is NOT YET VERIFIED.
2. The native root must be paired with a real stable filesystem UUID and the same versioned kernel modules on the actual card. CI scratch UUIDs are ephemeral.
3. U-Boot parser/addresses/Panel 4 DTB, bootloader early sectors and start-of-boot framebuffer/console are not hardware tested.
4. Systemd and services may not function fully with the root mounted read-only. This is a **diagnostic first-boot contract only**, not a production read/write system.
5. The original exact `boot.ini` has not yet been supplied as 5108 full bytes to test CP11 against physical R3. There is no reliable boot counter, complete updater, independent fallback or tested rollback. The recovery gate must not fall through to a damaged root.
6. RAM on handheld is 1 GiB; both experimental initrds are small by design, but no hardware memory use has been profiled.

## GitHub verification

`r36os-alpha6-cp15-native-initrd.yml` runs 18+ standalone tests, reuses the pinned historic K1 kernel archive, builds a clean native ARM64 Debian root, integrates its matching modules through CP14, creates a *new* scratch ext4 root UUID, builds and validates both independent U-Boot `uInitrd` headers against that UUID, and uploads only the development initrds, example bootargs and small reports. No flashable disk image or bootloader changes are produced.

## Next acceptance step

Inspect the effective kernel `.config` to prove MMC/ext4 required drivers built in (or compute minimal early module closure), then create a boot-once / serial diagnostic candidate for an isolated spare SD with a guaranteed legacy fallback. Do not boot the development ramdisks blindly on the existing SD1.