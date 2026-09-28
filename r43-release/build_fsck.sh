#!/usr/bin/env bash
set -euo pipefail
SRC="${1:?dosfstools-4.2.tar.gz required}"
OUT="${2:?output directory required}"
EXPECTED_SRC='64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527'
WORK="${TMPDIR:-/tmp}/r36os-r43-fsck-build"
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT"
[[ "$(sha256sum "$SRC" | awk '{print $1}')" == "$EXPECTED_SRC" ]] || { echo source-sha-mismatch >&2; exit 10; }
tar -xzf "$SRC" -C "$WORK" --strip-components=1
cd "$WORK"
./configure \
  --host=aarch64-linux-gnu \
  --without-iconv \
  CC=aarch64-linux-gnu-gcc \
  CFLAGS='-O2 -fno-plt' \
  LDFLAGS='-static'
make -C src -j2 fsck.fat
cp src/fsck.fat "$OUT/fsck.fat-static"
chmod 0755 "$OUT/fsck.fat-static"
SHA="$(sha256sum "$OUT/fsck.fat-static" | awk '{print $1}')"
printf '%s  fsck.fat-static\n' "$SHA" >"$OUT/fsck.fat-static.sha256"
{
  echo 'upstream=dosfstools/dosfstools'
  echo 'version=4.2'
  echo 'source_sha256=64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527'
  echo 'toolchain_os=ubuntu-20.04'
  echo 'target=aarch64-linux-gnu'
  echo 'link=static'
  echo 'iconv=disabled'
  echo 'runtime_locale=C'
  echo "sha256=$SHA"
} >"$OUT/BUILD_INFO.txt"
echo "R43_FSCK_BUILD=PASS sha256=$SHA"
