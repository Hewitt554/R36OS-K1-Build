from pathlib import Path
import hashlib,re,sys
if len(sys.argv)!=6:
    raise SystemExit('usage: transform_hook_r59.py <r54-hook> <r54-meta> <newcid> <out-hook> <out-meta>')
src=Path(sys.argv[1]); ms=Path(sys.argv[2]); cid=sys.argv[3]; out=Path(sys.argv[4]); mout=Path(sys.argv[5])
OLD_CID='4c70486f70ba16acf7437403'
OLD_HOOK_SHA='6b7fcb76bbd989c24c74da3b59523198c5310f6598a51c2d0d5c4646dee7de43'
OLD_META_SHA='fca5e6321bb92fc895a1cfa3409b0e298e4abc08ab87ceb2a3e55d2450c968d5'
if not re.fullmatch(r'[0-9a-f]{24}',cid): raise SystemExit('bad new cid')
if hashlib.sha256(src.read_bytes()).hexdigest()!=OLD_HOOK_SHA: raise SystemExit('R54 hook SHA mismatch')
if hashlib.sha256(ms.read_bytes()).hexdigest()!=OLD_META_SHA: raise SystemExit('R54 hook metadata SHA mismatch')
m=dict(line.split('=',1) for line in ms.read_text().splitlines() if '=' in line)
if m.get('format')!='R36OS_K1_BOOT_HOOK_V6': raise SystemExit('expected R54 hook V6')
if m.get('candidate_id')!=OLD_CID: raise SystemExit('R54 candidate mismatch')
if m.get('hooked_boot_sha256')!=OLD_HOOK_SHA: raise SystemExit('R54 hook metadata hash mismatch')
s=src.read_text()
if s.count(OLD_CID)!=3: raise SystemExit(f'expected exactly 3 R54 candidate references, found {s.count(OLD_CID)}')
s=s.replace(OLD_CID,cid)
out.write_text(s)
newsha=hashlib.sha256(out.read_bytes()).hexdigest()
lines=[]
seen_payload=False
for line in ms.read_text().splitlines():
    if line.startswith('format='): line='format=R36OS_K1_BOOT_HOOK_V7'
    elif line.startswith('candidate_id='): line='candidate_id='+cid
    elif line.startswith('hooked_boot_sha256='): line='hooked_boot_sha256='+newsha
    elif line.startswith('previous_hook_sha256='): line='previous_hook_sha256='+OLD_HOOK_SHA
    elif line.startswith('request='): line=f'request=R36OS-KernelNext/boot-next.{cid}.once'
    elif line.startswith('candidate_payload_change='):
        line='candidate_payload_change=modules-rtl8xxxu'
        seen_payload=True
    lines.append(line)
if not seen_payload: lines.append('candidate_payload_change=modules-rtl8xxxu')
lines += [f'previous_candidate_id={OLD_CID}','module_payload_change=yes','image_change=no','uinitrd_change=no','dtb_change=no']
mout.write_text('\n'.join(lines)+'\n')
