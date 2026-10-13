# R36OS Alpha 6 Native ARM64 Root (CP06, experimental)

This produces a **development-only ARM64 userspace tarball**, not a bootable or flashable disk image. It does not access the original R3 image or SD cards, and it does not update the live OS release channel.

A GitHub Actions PR workflow executes a Debian 12 debootstrap on an ARM64 Linux runner, adds only R36OS-specific identity, a read-only hardware reporting service, and a fail-closed update preflight. It saves a package/version inventory and SHA256 of the compressed native root.

Linux K1 6.12, Panel4, gamepad, RK817 charging, graphics, Wi-Fi, SD2 mounting and independently bootable recovery remain unverified. No ArkOS system binaries are copied. Debian remains our upstream userspace dependency source; R36OS has its own identity/configuration, not its own reimplemented libc.
