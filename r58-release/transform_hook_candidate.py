from pathlib import Path
import hashlib,re,sys

if len(sys.argv)!=6:
    raise SystemExit("usage: transform_hook_candidate.py <current-hook> <current-meta> <newcid> <out-hook> <out-meta>")

src=Path(sys.argv[1]); ms=Path(sys.argv[2]); cid=sys.argv[3]; out=Path(sys.argv[4]); mout=Path(sys.argv[5])
if not re.fullmatch(r'[0-9a-f]{24}',cid): raise SystemExit('bad new cid')
m=dict(line.split('=',1) for line in ms.read_text().splitlines() if '=' in line)
old=m.get('candidate_id',''); oldsha=m.get('hooked_boot_sha256','')
if m.get('format')!='R36OS_K1_BOOT_HOOK_V6': raise SystemExit('expected current hook V6')
if not re.fullmatch(r'[0-9a-f]{24}',old): raise SystemExit('bad old cid')
if hashlib.sha256(src.read_bytes()).hexdigest()!=oldsha: raise SystemExit('current hook sha mismatch')
s=src.read_text()
if s.count(old)<3: raise SystemExit('old candidate not present enough')
s=s.replace(old,cid)
out.write_text(s)
newsha=hashlib.sha256(out.read_bytes()).hexdigest()
lines=[]
for line in ms.read_text().splitlines():
    if line.startswith('candidate_payload_change='):
        continue
    if line.startswith('format='): line='format=R36OS_K1_BOOT_HOOK_V7'
    elif line.startswith('candidate_id='): line='candidate_id='+cid
    elif line.startswith('hooked_boot_sha256='): line='hooked_boot_sha256='+newsha
    elif line.startswith('previous_hook_sha256='): line='previous_hook_sha256='+oldsha
    elif line.startswith('request='): line=f'request=R36OS-KernelNext/boot-next.{cid}.once'
    lines.append(line)
lines += [
    'candidate_payload_change=kernel-image+modules-uinput',
    'legacy_fallthrough=yes',
    'uinput_kernel_support=built-in',
]
mout.write_text('\n'.join(lines)+'\n')
