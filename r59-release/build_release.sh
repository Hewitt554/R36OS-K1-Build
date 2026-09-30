#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 6 ] || { echo "usage: build_release.sh <exact-r58.r36upd> <exact-r54.r36upd> <validated-k1-dir> <rtl8188eufw.bin> <LICENCE.rtlwifi_firmware.txt> <out-dir>" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
R58="$1"; R54="$2"; NEWK1="$3"; FW="$4"; FWLIC="$5"; OUT="$6"
REPO='Hewitt554/R36OS-K1-Build'
TAG='alpha5r48'
NAME='00-R36OS-Alpha5R59-K1RTL8188EUWiFi-FromR58.r36upd'
EXPECTED_R58='7d8b5483d1bf3d104072366b1879fedb08ba49dcd7be4d56ee411d332873983b'
EXPECTED_R54='ed3b331fe1fb6cb23bf60aa997d2bd1fc6634039f2ec176d93d0dd2561ce166e'
OLD_CID='4c70486f70ba16acf7437403'
KREL='6.12.94-r36os-k1'
EXPECTED_IMAGE='a7a388d5ca21b276bddcc0e3892b0c965b73d92f2c0238cb9c25a210dba7c97e'
EXPECTED_DTB='e2145905b1beb8d0f5b9dee6c5a21d31c29474be8762c893e81506fc40e627f4'
EXPECTED_UINITRD='023a0d2adc113b2d1fea6826387ab6e03e4d479cf5fa36c9b9ff86cf41fd1925'
OLD_MODULES='f0c78a5ba54b4a800c0a64581c8fde977f8e6b02331d56b7771a00268821c7b2'
FW_BLOB='4ae7e1c5deb7846e59c461546a49679504ffed28'
FW_SIZE='13904'
LIC_BLOB='d70921f493795acb9af2a38f405193ba7a1b28a3'
LIC_SIZE='2115'
WORK="${RUNNER_TEMP:-/tmp}/r36os-r59-release"

sha(){ sha256sum "$1" | awk '{print $1}'; }
val(){ awk -F= -v k="$2" '$1==k{print substr($0,index($0,"=")+1);exit}' "$1"; }
blob_sha(){ python3 - "$1" <<'PY'
import hashlib,sys
b=open(sys.argv[1],'rb').read()
h=hashlib.sha1(); h.update(f'blob {len(b)}\0'.encode()); h.update(b); print(h.hexdigest())
PY
}
fail(){ echo "R59_RELEASE_BUILD=FAIL $*" >&2; exit 1; }

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/r58" "$WORK/r54" "$WORK/full-k1"   "$WORK/update/payload/root/etc"   "$WORK/update/payload/root/usr/local/bin"   "$WORK/update/payload/root/opt/r36os/features"   "$WORK/update/payload/root/opt/r36os/kernel-next/K1"   "$WORK/update/payload/root/lib/firmware/rtlwifi"   "$WORK/update/payload/root/lib/firmware"   "$OUT"

test "$(sha "$R58")" = "$EXPECTED_R58" || fail r58-sha-mismatch
test "$(sha "$R54")" = "$EXPECTED_R54" || fail r54-sha-mismatch

tar -xzf "$R58" -C "$WORK/r58"
tar -xzf "$R54" -C "$WORK/r54"
(cd "$WORK/r58" && sha256sum -c checksums.sha256 >/dev/null) || fail r58-checksums
(cd "$WORK/r54" && sha256sum -c checksums.sha256 >/dev/null) || fail r54-checksums
R58ROOT="$WORK/r58/payload/root"; R54ROOT="$WORK/r54/payload/root"; ROOT="$WORK/update/payload/root"
test "$(val "$WORK/r58/manifest.conf" version)" = '0.5.58.0' || fail r58-version
test "$(val "$WORK/r58/manifest.conf" candidate_id)" = "$OLD_CID" || fail r58-candidate
test "$(val "$WORK/r54/manifest.conf" candidate_id)" = "$OLD_CID" || fail r54-candidate
CORE="$R58ROOT/etc/r36os-core-manifest.sha256"; test -s "$CORE" || fail r58-core-manifest

R54K1="$R54ROOT/opt/r36os/kernel-next/K1"
test "$(sha "$R54K1/uInitrd")" = "$EXPECTED_UINITRD" || fail r54-uinitrd-sha
test "$(sha "$R54ROOT/opt/r36os/kernel-next/hooked-boot.ini")" = '6b7fcb76bbd989c24c74da3b59523198c5310f6598a51c2d0d5c4646dee7de43' || fail r54-hook-sha
test "$(sha "$R54ROOT/opt/r36os/kernel-next/hook.conf")" = 'fca5e6321bb92fc895a1cfa3409b0e298e4abc08ab87ceb2a3e55d2450c968d5' || fail r54-hook-meta-sha
test "$(sha "$R54ROOT/usr/local/bin/r36os-k1-install-hook")" = '1f745e279b5940955657f09a8bf8bf40346e5696c321e1307a71f96c68190ebc' || fail r54-installer-sha

for f in Image uInitrd rk3326-r36s-k1.dtb modules.tar.xz K1.conf BUILD_INFO.txt MANIFEST.sha256; do test -s "$NEWK1/$f" || fail "new-k1-missing-$f"; done
(cd "$NEWK1" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail new-k1-manifest
test "$(val "$NEWK1/K1.conf" kernel_release)" = "$KREL" || fail new-k1-krel
test "$(sha "$NEWK1/Image")" = "$EXPECTED_IMAGE" || fail image-regression
test "$(sha "$NEWK1/rk3326-r36s-k1.dtb")" = "$EXPECTED_DTB" || fail dtb-regression
NEW_MODULES_SHA="$(sha "$NEWK1/modules.tar.xz")"
test "$NEW_MODULES_SHA" != "$OLD_MODULES" || fail modules-did-not-change

read -r MODROOT MODFILES MODBYTES RTLKO_COUNT MODDEP_OK MODALIAS_OK < <(python3 - "$NEWK1/modules.tar.xz" "$KREL" <<'PY'
import sys,tarfile
p,k=sys.argv[1:]; expected='modules-'+k
files=0; total=0; rtl=0; dep=0; aliasok=0; roots=set()
with tarfile.open(p,'r:xz') as t:
    members=t.getmembers()
    for m in members:
        name=m.name.lstrip('./')
        if name: roots.add(name.split('/',1)[0])
        if m.issym() or m.islnk(): raise SystemExit('archive contains link: '+m.name)
        if name.startswith('/') or '..' in name.split('/'): raise SystemExit('unsafe path: '+m.name)
        if m.isfile():
            files+=1; total+=m.size
            if name.endswith('/rtl8xxxu.ko'): rtl+=1
            if name == expected+'/modules.dep' and m.size > 0: dep=1
            if name == expected+'/modules.alias' and m.size > 0:
                raw=t.extractfile(m).read().decode('utf-8','replace')
                if any(line.startswith('alias usb:v0BDAp0179') and line.rstrip().endswith(' rtl8xxxu') for line in raw.splitlines()):
                    aliasok=1
if roots != {expected}: raise SystemExit(f'bad archive roots: {roots!r}')
print(expected,files,total,rtl,dep,aliasok)
PY
) || fail module-archive-audit
test "$MODROOT" = "modules-$KREL" || fail module-root
test "$MODFILES" -gt 0 && test "$MODBYTES" -gt 0 || fail module-counts
test "$RTLKO_COUNT" = 1 || fail rtl8xxxu-module-count
test "$MODDEP_OK" = 1 || fail modules-dep-missing
test "$MODALIAS_OK" = 1 || fail rtl8xxxu-modalias-missing
RTL_MEMBER="$(tar -tJf "$NEWK1/modules.tar.xz" | grep '/rtl8xxxu\.ko$' | head -1)"
test -n "$RTL_MEMBER" || fail rtl8xxxu-path
RTL_PATH="${RTL_MEMBER#./}"
mkdir -p "$WORK/rtlko"; tar -xJf "$NEWK1/modules.tar.xz" -C "$WORK/rtlko" "$RTL_MEMBER"
RTLKO="$WORK/rtlko/$RTL_PATH"
file "$RTLKO" | grep -Eq 'ARM aarch64|ARM64' || fail rtl8xxxu-not-arm64
RTLINFO="$(modinfo "$RTLKO")" || fail rtl8xxxu-modinfo
grep -Eq '^alias:[[:space:]]+usb:v0BDAp0179' <<<"$RTLINFO" || fail rtl8xxxu-usb-alias
grep -Eq '^firmware:[[:space:]]+rtlwifi/rtl8188eufw.bin$' <<<"$RTLINFO" || fail rtl8xxxu-firmware-declaration

test "$(stat -c %s "$FW")" = "$FW_SIZE" || fail firmware-size
test "$(blob_sha "$FW")" = "$FW_BLOB" || fail firmware-git-blob
test "$(stat -c %s "$FWLIC")" = "$LIC_SIZE" || fail firmware-licence-size
test "$(blob_sha "$FWLIC")" = "$LIC_BLOB" || fail firmware-licence-git-blob
FW_SHA="$(sha "$FW")"; LIC_SHA="$(sha "$FWLIC")"

cp "$NEWK1/Image" "$WORK/full-k1/Image"
cp "$R54K1/uInitrd" "$WORK/full-k1/uInitrd"
cp "$NEWK1/rk3326-r36s-k1.dtb" "$WORK/full-k1/rk3326-r36s-k1.dtb"
cp "$NEWK1/modules.tar.xz" "$WORK/full-k1/modules.tar.xz"
cp "$R54K1/K1.conf" "$WORK/full-k1/K1.conf"
python3 - "$WORK/full-k1/K1.conf" "$MODFILES" "$MODBYTES" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); files,bytes_=sys.argv[2:]; lines=[]
for line in p.read_text().splitlines():
    if line.startswith('candidate_id='): line='candidate_id=__CID__'
    elif line.startswith('modules_uncompressed_bytes='): line='modules_uncompressed_bytes='+bytes_
    elif line.startswith('modules_file_count='): line='modules_file_count='+files
    lines.append(line)
p.write_text('\n'.join(lines)+'\n')
PY
CID="$(cd "$WORK/full-k1"; { sha256sum Image; sha256sum uInitrd; sha256sum rk3326-r36s-k1.dtb; sha256sum modules.tar.xz; printf 'kernel_release=%s\n' "$KREL"; } | sha256sum | awk '{print substr($1,1,24)}')"
echo "$CID" | grep -Eq '^[0-9a-f]{24}$' || fail candidate-id-format
test "$CID" != "$OLD_CID" || fail candidate-id-unchanged
sed -i "s/__CID__/$CID/" "$WORK/full-k1/K1.conf"
cat >"$WORK/full-k1/BUILD_INFO.txt" <<EOF_BUILD
R36OS K1 Alpha 5R59 RTL8188EU Wi-Fi candidate
Kernel release: $KREL
Candidate ID: $CID
Image SHA256: $EXPECTED_IMAGE (unchanged from physically booted R58)
Panel-4 DTB SHA256: $EXPECTED_DTB (unchanged from physically booted R58)
uInitrd SHA256: $EXPECTED_UINITRD (unchanged R54 /opt/r36i handoff)
Modules SHA256: $NEW_MODULES_SHA (changed: maintained in-tree rtl8xxxu)
Module archive root: $MODROOT
Modules uncompressed bytes: $MODBYTES
Modules file count: $MODFILES
Wi-Fi USB ID: 0bda:0179 RTL8188EU
Firmware: rtlwifi/rtl8188eufw.bin SHA256 $FW_SHA Git blob $FW_BLOB
Safety: Boot Next Once only; legacy Linux 4.4/U-Boot files untouched
EOF_BUILD
(cd "$WORK/full-k1" && sha256sum BUILD_INFO.txt Image K1.conf modules.tar.xz rk3326-r36s-k1.dtb uInitrd > MANIFEST.sha256)
(cd "$WORK/full-k1" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail reconstructed-manifest
RECHECK_CID="$(cd "$WORK/full-k1"; { sha256sum Image; sha256sum uInitrd; sha256sum rk3326-r36s-k1.dtb; sha256sum modules.tar.xz; printf 'kernel_release=%s\n' "$KREL"; } | sha256sum | awk '{print substr($1,1,24)}')"
test "$RECHECK_CID" = "$CID" || fail candidate-id-recheck

for f in modules.tar.xz K1.conf BUILD_INFO.txt MANIFEST.sha256; do cp "$WORK/full-k1/$f" "$ROOT/opt/r36os/kernel-next/K1/$f"; chmod 0644 "$ROOT/opt/r36os/kernel-next/K1/$f"; done
cp "$FW" "$ROOT/lib/firmware/rtlwifi/rtl8188eufw.bin"
cp "$FWLIC" "$ROOT/lib/firmware/LICENCE.rtlwifi_firmware.txt"
chmod 0644 "$ROOT/lib/firmware/rtlwifi/rtl8188eufw.bin" "$ROOT/lib/firmware/LICENCE.rtlwifi_firmware.txt"

python3 "$HERE/transform_prepare.py" "$R58ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-next-prepare"
python3 "$HERE/transform_identity.py" slot "$R58ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-kernel-slot"
python3 "$HERE/transform_identity.py" maint "$R58ROOT/usr/local/bin/r36os-r36update-maint" "$ROOT/usr/local/bin/r36os-r36update-maint"
python3 "$HERE/transform_hook_candidate.py" "$R54ROOT/opt/r36os/kernel-next/hooked-boot.ini" "$R54ROOT/opt/r36os/kernel-next/hook.conf" "$CID" "$ROOT/opt/r36os/kernel-next/hooked-boot.ini" "$ROOT/opt/r36os/kernel-next/hook.conf"
python3 "$HERE/transform_installer.py" "$R54ROOT/usr/local/bin/r36os-k1-install-hook" "$ROOT/usr/local/bin/r36os-k1-install-hook"
cp "$HERE/r36os-k1-hardware-snapshot" "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot"
chmod 0755 "$ROOT/usr/local/bin/"*
chmod 0644 "$ROOT/opt/r36os/kernel-next/hooked-boot.ini" "$ROOT/opt/r36os/kernel-next/hook.conf"

cat >"$ROOT/etc/r36os-release" <<EOF_RELEASE
R36OS_NAME="R36OS"
R36OS_VERSION="Alpha 5R59"
R36OS_PACKAGE_VERSION="0.5.59.0"
R36OS_HARDWARE="R36XX-RK3326"
R36OS_CHANNEL="system-core"
R36OS_BUILD_DATE="2026-09-30"
R36OS_COMPATIBILITY="K1 maintained rtl8xxxu support for built-in Realtek RTL8188EU USB Wi-Fi"
R36OS_NOTES="Alpha 5R59 keeps the physically proven R58 Image, Panel-4 DTB, R54 /opt/r36i uInitrd, direct split-input UI, legacy 4.4 fallback and Boot Next Once safety. K1 modules change only to enable the maintained Linux 6.12 rtl8xxxu stack for USB 0bda:0179. The exact rtl8188eufw.bin firmware and Realtek firmware licence are included. Because modules.tar.xz changes while the kernel release stays $KREL, preparation stages/verifies the complete new module tree beside the old R36STATE tree and atomically swaps it with rollback on readback failure."
EOF_RELEASE
cat >"$ROOT/opt/r36os/features/alpha5r59" <<EOF_FEATURE
R36OS Alpha 5R59
- Physical R58 proof: K1 boots, UI works, gpio-keys + adc-joystick controller works.
- Physical R58 Wi-Fi evidence: USB 0bda:0179 enumerates but NetworkManager reports WIFI-HW missing.
- Adds maintained Linux 6.12 rtl8xxxu support for RTL8188EU (0bda:0179).
- Includes exact rtlwifi/rtl8188eufw.bin firmware and its Realtek redistribution licence.
- Image unchanged: $EXPECTED_IMAGE
- Panel-4 DTB unchanged: $EXPECTED_DTB
- R54 /opt/r36i uInitrd unchanged: $EXPECTED_UINITRD
- New K1 candidate: $CID
- Same kernel release: $KREL
- New modules archive: $NEW_MODULES_SHA
- Existing R36STATE module tree is never deleted before the complete new tree is staged and verified.
- Failed activation/readback restores the previous tree.
- R56 R1 single-flight remains present.
- Hardware snapshot now derives candidate ID dynamically instead of hard-coding the R55-R58 candidate.
- R58 direct split-input native UI is untouched.
- Legacy Linux 4.4 normal boot path is untouched.
EOF_FEATURE
chmod 0644 "$ROOT/etc/r36os-release" "$ROOT/opt/r36os/features/alpha5r59"

python3 - "$CORE" "$ROOT" "$ROOT/etc/r36os-core-manifest.sha256" <<'PY'
from pathlib import Path
import hashlib,sys
base=Path(sys.argv[1]); root=Path(sys.argv[2]); out=Path(sys.argv[3]); entries={}; order=[]
for line in base.read_text().splitlines():
    if not line.strip(): continue
    h,p=line.split(None,1); p=p.strip(); entries[p]=h; order.append(p)
changed=[
'/usr/local/bin/r36os-kernel-next-prepare','/usr/local/bin/r36os-kernel-slot','/usr/local/bin/r36os-r36update-maint',
'/usr/local/bin/r36os-k1-install-hook','/usr/local/bin/r36os-k1-hardware-snapshot',
'/opt/r36os/kernel-next/hooked-boot.ini','/opt/r36os/kernel-next/hook.conf','/opt/r36os/kernel-next/K1/MANIFEST.sha256',
'/lib/firmware/rtlwifi/rtl8188eufw.bin','/lib/firmware/LICENCE.rtlwifi_firmware.txt']
for p in changed:
    fp=root/p.lstrip('/')
    if not fp.is_file(): raise SystemExit('missing changed core file '+p)
    entries[p]=hashlib.sha256(fp.read_bytes()).hexdigest()
    if p not in order: order.append(p)
out.write_text(''.join(f'{entries[p]}  {p}\n' for p in order))
PY

cat >"$WORK/update/manifest.conf" <<EOF_MAN
format=R36UPD2
version=0.5.59.0
hardware=R36XX-RK3326
base_version=0.5.58.0
channel=system-core
requires_reboot=true
description=Alpha 5R59 adds K1 RTL8188EU Wi-Fi via maintained rtl8xxxu while preserving the physically proven R58 Image, DTB, uInitrd and input UI.
candidate_id=$CID
kernel_release=$KREL
k1_binary_change=yes
candidate_id_change=yes
k1_image_change=no
k1_dtb_change=no
k1_uinitrd_change=no
module_payload_change=yes
module_payload_replace_safe=yes
wifi_driver=rtl8xxxu
wifi_usb_id=0bda:0179
wifi_firmware=rtlwifi/rtl8188eufw.bin
legacy_kernel_change=no
native_ui_change=no
direct_k1_split_input_preserved=yes
r1_singleflight_preserved=yes
EOF_MAN
(cd "$WORK/update" && find payload/root -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > checksums.sha256)

! find "$ROOT" -type f | grep -Eq '/boot/' || fail active-boot-payload
! find "$ROOT" -type f | grep -Eq '/(lib|usr/lib)/modules/' || fail active-module-tree-payload
! find "$ROOT" -type l -print -quit | grep -q . || fail symlink-payload
for f in "$ROOT/usr/local/bin/r36os-kernel-next-prepare" "$ROOT/usr/local/bin/r36os-kernel-slot" "$ROOT/usr/local/bin/r36os-r36update-maint" "$ROOT/usr/local/bin/r36os-k1-install-hook" "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot"; do bash -n "$f" || fail script-syntax; done
python3 -m py_compile "$HERE/"*.py
test ! -e "$ROOT/usr/local/bin/r36os-alpha5" || fail ui-replacement-forbidden
test ! -e "$ROOT/usr/local/bin/r36os-session" || fail session-replacement-forbidden
test ! -e "$ROOT/etc/systemd/system/r36os.service.d/99-k1-input-wrapper.conf" || fail input-dropin-replacement-forbidden
test ! -e "$ROOT/opt/r36os/kernel-next/K1/Image" || fail image-overlay-forbidden
test ! -e "$ROOT/opt/r36os/kernel-next/K1/uInitrd" || fail uinitrd-overlay-forbidden
test ! -e "$ROOT/opt/r36os/kernel-next/K1/rk3326-r36s-k1.dtb" || fail dtb-overlay-forbidden
for f in modules.tar.xz K1.conf BUILD_INFO.txt MANIFEST.sha256; do test -s "$ROOT/opt/r36os/kernel-next/K1/$f" || fail "missing-overlay-$f"; done
grep -Fq 'R36OS_K1_LOCKDIR:-/run/r36os-k1-prepare.lock' "$ROOT/usr/local/bin/r36os-kernel-next-prepare" || fail r1-lock-regression
grep -Fq 'duplicate-request-ignored-in-progress' "$ROOT/usr/local/bin/r36os-kernel-next-prepare" || fail r1-duplicate-regression
grep -Fq 'stage_new_modules(){' "$ROOT/usr/local/bin/r36os-kernel-next-prepare" || fail module-replace-missing
grep -Fq 'modules-backup-rename' "$ROOT/usr/local/bin/r36os-kernel-next-prepare" || fail module-rollback-missing
grep -Fq '0.5.59.0' "$ROOT/usr/local/bin/r36os-kernel-next-prepare" || fail prepare-version
grep -Fq "$CID" "$ROOT/opt/r36os/kernel-next/hook.conf" || fail hook-candidate
grep -Fq "$CID" "$ROOT/opt/r36os/kernel-next/hooked-boot.ini" || fail hooked-boot-candidate
! grep -Fq "CID='$OLD_CID'" "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot" || fail snapshot-old-candidate
grep -Fq 'r36os.kernel_candidate' "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot" || fail snapshot-dynamic-candidate
test "$(grep -Fc 'format=R36OS_K1_HARDWARE_SNAPSHOT_V1' "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot")" -eq 1 || fail snapshot-body-count
test "$(grep -Fc 'R36OS-K1 hardware snapshot saved.' "$ROOT/usr/local/bin/r36os-k1-hardware-snapshot")" -eq 1 || fail snapshot-tail-count
test "$(blob_sha "$ROOT/lib/firmware/rtlwifi/rtl8188eufw.bin")" = "$FW_BLOB" || fail packaged-firmware-blob
test "$(blob_sha "$ROOT/lib/firmware/LICENCE.rtlwifi_firmware.txt")" = "$LIC_BLOB" || fail packaged-licence-blob
(cd "$WORK/full-k1" && sha256sum -c MANIFEST.sha256 >/dev/null) || fail final-candidate-manifest
test "$(val "$WORK/full-k1/K1.conf" candidate_id)" = "$CID" || fail final-candidate-conf

(cd "$WORK/update"; tar --sort=name --mtime='UTC 2026-09-30 00:00:00' --owner=0 --group=0 --numeric-owner -cf - manifest.conf checksums.sha256 payload | gzip -1 -n >"$OUT/$NAME")
SHA="$(sha "$OUT/$NAME")"; SIZE="$(stat -c %s "$OUT/$NAME")"
printf '%s  %s\n' "$SHA" "$NAME" >"$OUT/$NAME.sha256"
AUD="$WORK/audit"; mkdir -p "$AUD"; tar -xzf "$OUT/$NAME" -C "$AUD"; (cd "$AUD" && sha256sum -c checksums.sha256 >/dev/null) || fail package-readback

cat >"$OUT/latest.conf" <<EOF_LATEST
format=R36OS_REMOTE_UPDATE_V1
repo=$REPO
available=yes
channel=alpha
version=0.5.59.0
base_version=0.5.58.0
filename=$NAME
size_bytes=$SIZE
sha256=$SHA
url=https://github.com/$REPO/releases/download/$TAG/$NAME
candidate_id=$CID
kernel_release=$KREL
EOF_LATEST
cat >"$OUT/RELEASE_REPORT.txt" <<EOF_REPORT
R36OS Alpha 5R59 audited release build PASS
base_version=0.5.58.0
version=0.5.59.0
old_candidate_id=$OLD_CID
candidate_id=$CID
kernel_release=$KREL
r58_source_sha256=$EXPECTED_R58
r54_source_sha256=$EXPECTED_R54
image_sha256=$EXPECTED_IMAGE
image_change=no
dtb_sha256=$EXPECTED_DTB
dtb_change=no
uinitrd_sha256=$EXPECTED_UINITRD
uinitrd_change=no
modules_sha256=$NEW_MODULES_SHA
modules_change=yes
modules_file_count=$MODFILES
modules_uncompressed_bytes=$MODBYTES
wifi_driver=rtl8xxxu
wifi_usb_id=0bda:0179
firmware_sha256=$FW_SHA
firmware_git_blob=$FW_BLOB
firmware_licence_sha256=$LIC_SHA
module_payload_replace_safe=yes
native_ui_change=no
legacy_kernel_change=no
package=$NAME
size_bytes=$SIZE
sha256=$SHA
EOF_REPORT
printf 'R59_RELEASE_BUILD=PASS candidate_id=%s size=%s sha256=%s\n' "$CID" "$SIZE" "$SHA"
