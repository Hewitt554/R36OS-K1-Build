# Native R36OS Chapter 2 — reproducible native rootfs

Chapter 2 builds the first ArkOS-independent ARM64 userspace. It does not boot
or install it on the handheld.

Pinned Debian archive:
- suite: trixie
- architecture: arm64
- snapshot: 20261001T082322Z
- archive: snapshot.debian.org
- package installation uses --no-install-recommends semantics.

The root deliberately excludes:
- ArkOS/EmulationStation runtime;
- PortMaster;
- proprietary ARM Mali/Bifrost userspace;
- CrustyGBM/libcrusty;
- Weston/Westonpack;
- Xwayland/X11;
- SDL;
- Wine;
- Box64;
- Steam;
- audio/Bluetooth desktop stacks.

Those components have their own later chapters.

Chapter-2 output:
- r36os-native-c02-rootfs.tar.zst
- SHA-256
- requested package list
- resolved dpkg package/version manifest
- full normalized file/hash manifest
- rootfs metadata
- forbidden-dependency scan report.

The root is intended eventually to live at:
/r36state/r36os-next/rootfs

Chapter 3, not Chapter 2, owns staging and Boot Once.
