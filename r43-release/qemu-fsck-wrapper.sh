#!/bin/sh
: "${R36OS_FSCK_QEMU_BIN:?R36OS_FSCK_QEMU_BIN is required}"
exec /usr/bin/qemu-aarch64-static "$R36OS_FSCK_QEMU_BIN" "$@"
