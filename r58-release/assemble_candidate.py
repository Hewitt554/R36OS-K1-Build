from pathlib import Path
import hashlib,shutil,sys,re

if len(sys.argv)!=4:
    raise SystemExit("usage: assemble_candidate.py <raw-r58-k1-dir> <patched-r54-uInitrd> <out-k1-dir>")

src=Path(sys.argv[1]); patched=Path(sys.argv[2]); out=Path(sys.argv[3])
OLD_INIT='6d44f435bd88b54e91af569fd6445db460b9ab80313062b8136796f27b888f6e'
PATCHED_INIT='023a0d2adc113b2d1fea6826387ab6e03e4d479cf5fa36c9b9ff86cf41fd1925'
DTB='e2145905b1beb8d0f5b9dee6c5a21d31c29474be8762c893e81506fc40e627f4'
KREL='6.12.94-r36os-k1'

sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
for f in ['Image','uInitrd','rk3326-r36s-k1.dtb','modules.tar.xz','MANIFEST.sha256','BUILD_INFO.txt','K1.conf']:
    if not (src/f).is_file(): raise SystemExit('missing raw candidate file: '+f)

# Verify raw candidate's own manifest before merging.
for line in (src/'MANIFEST.sha256').read_text().splitlines():
    if not line.strip(): continue
    h,name=line.split(None,1); name=name.strip().lstrip('*')
    p=src/name
    if not p.is_file() or sha(p)!=h.lower():
        raise SystemExit('raw candidate manifest mismatch: '+name)

if sha(src/'uInitrd')!=OLD_INIT:
    raise SystemExit('raw R58 build no longer has expected Run11 initramfs')
if sha(patched)!=PATCHED_INIT:
    raise SystemExit('patched R54 uInitrd sha mismatch')
if sha(src/'rk3326-r36s-k1.dtb')!=DTB:
    raise SystemExit('Panel-4 DTB changed unexpectedly')

if out.exists(): shutil.rmtree(out)
shutil.copytree(src,out)
shutil.copy2(patched,out/'uInitrd')

conf=out/'K1.conf'
lines=conf.read_text().splitlines()
vals=dict(line.split('=',1) for line in lines if '=' in line)
if vals.get('kernel_release')!=KREL: raise SystemExit('kernel release mismatch')
for k in ['modules_archive_root','modules_uncompressed_bytes','modules_file_count']:
    if not vals.get(k): raise SystemExit('missing K1 conf field '+k)

cid_data=''.join([
    sha(out/'Image')+'  Image\n',
    sha(out/'uInitrd')+'  uInitrd\n',
    sha(out/'rk3326-r36s-k1.dtb')+'  rk3326-r36s-k1.dtb\n',
    sha(out/'modules.tar.xz')+'  modules.tar.xz\n',
    f'kernel_release={KREL}\n'
]).encode()
cid=hashlib.sha256(cid_data).hexdigest()[:24]
if not re.fullmatch(r'[0-9a-f]{24}',cid): raise SystemExit('bad candidate id')

new=[]
seen=False
for line in lines:
    if line.startswith('candidate_id='):
        line='candidate_id='+cid; seen=True
    if line.startswith('uinitrd_handoff=') or line.startswith('uinitrd_handoff_wrapper='):
        continue
    new.append(line)
if not seen: raise SystemExit('candidate_id field missing')
new += ['uinitrd_handoff=opt-r36i-systemd-probe','uinitrd_handoff_wrapper=/opt/r36i','uinput_kernel_support=built-in']
conf.write_text('\n'.join(new)+'\n')

with (out/'BUILD_INFO.txt').open('a') as f:
    f.write(f'''\nR58 uinput merge:\n- candidate_id={cid}\n- Linux Image rebuilt from frozen Linux 6.12.94 inputs with CONFIG_INPUT_UINPUT=y\n- Panel-4 DTB unchanged SHA256 {DTB}\n- uInitrd preserved from proven R54/R57 systemd handoff SHA256 {PATCHED_INIT}\n- modules archive taken from the same R58 kernel build as Image\n- K1-only R57 evdev/uinput compatibility bridge remains userspace consumer\n''')

manifest=[]
for p in sorted(x for x in out.iterdir() if x.is_file() and x.name!='MANIFEST.sha256'):
    manifest.append(f'{sha(p)}  {p.name}')
(out/'MANIFEST.sha256').write_text('\n'.join(manifest)+'\n')

print('candidate_id='+cid)
print('image_sha256='+sha(out/'Image'))
print('uinitrd_sha256='+sha(out/'uInitrd'))
print('dtb_sha256='+sha(out/'rk3326-r36s-k1.dtb'))
print('modules_sha256='+sha(out/'modules.tar.xz'))
