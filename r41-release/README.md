# R36OS Alpha 5R41 — first-boot repair activation fix

The user's first Alpha 5R40 boot proved that the R40 repair generator was not executed on the device's systemd 242 userspace. The physical log still contained:

`FAT-fs (mmcblk0p3): Volume was not properly unmounted. Some data may be corrupt. Please run fsck.`

and GitHub diagnostics remained `upload-disabled` because the same first-boot runner was also responsible for installing the non-secret private-repository defaults.

R41 is deliberately narrow. It is built only from the exact published R40 package (SHA-256 `448c056d9b1eac99443d0fad1ff10be9c9b40c7a8ffc4be33015c52d44ecd1e2`) and does not replace the K1 candidate, kernel binaries, verified GitHub uploader, static FAT checker, or generic FAT repair engine.

The service generator is installed using a generic filename in both `/etc/systemd/system-generators` and `/lib/systemd/system-generators`, covering the older systemd layout seen on the handheld. The generator creates a transient multi-user target dependency only while the generic one-shot marker exists.

The first-boot runner:
- records generator evidence;
- removes superseded version-labelled WIP runtime files;
- installs the non-secret `Hewitt554/R36OS-Device-Logs` / automatic-mode config only when no config exists;
- invokes the already-validated exact-device R36UPDATE repair helper when the mmcblk0p3 dirty warning is present;
- reboots only after repair + read-only verification succeeds;
- fails closed and preserves logs otherwise.

The normal Diagnostics export wrapper now creates a generic game/OS/repair snapshot before executing the inherited verified exporter. This puts repair evidence into both the local manual archive and the existing privacy-redacted remote diagnostic path.

The GitHub authentication token remains device-local and is not embedded in this public source/update.
