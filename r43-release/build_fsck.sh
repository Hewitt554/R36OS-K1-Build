#!/usr/bin/env bash
set -euo pipefail
SRC="${1:?dosfstools-4.2.tar.gz required}"
OUT="${2:?output directory required}"
EXPECTED_SRC='64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r43-fsck"
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/src" "$OUT"
[[ "$(sha256sum "$SRC" | awk '{print $1}')" == "$EXPECTED_SRC" ]] || { echo source-sha-mismatch >&2; exit 10; }
tar -xzf "$SRC" -C "$WORK/src" --strip-components=1
cd "$WORK/src"
./configure --host=aarch64-linux-gnu --without-iconv CC=aarch64-linux-gnu-gcc CFLAGS='-O2 -fno-plt' LDFLAGS='-static'
make -j2
test -x src/fsck.fat
cp src/fsck.fat "$OUT/fsck.fat-static"
chmod 0755 "$OUT/fsck.fat-static"
sha256sum "$OUT/fsck.fat-static" | sed 's#  .*/#  #' >"$OUT/fsck.fat-static.sha256"
cat >"$OUT/BUILD_INFO.txt" <<'EOF_INFO'
format=R36OS_FSCK_BUILD_V1
upstream=dosfstools/dosfstools
version=4.2
source_sha256=64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527
toolchain_os=ubuntu-20.04
arch=aarch64
link=static
iconv=disabled
locale=C
purpose=R36OS R43 offline R36UPDATE FAT repair
EOF_INFO
