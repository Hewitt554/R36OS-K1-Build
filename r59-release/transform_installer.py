from pathlib import Path
import hashlib,re,sys
if len(sys.argv)!=3:
    raise SystemExit('usage: transform_installer_r59.py <r54-installer> <out>')
src=Path(sys.argv[1]); out=Path(sys.argv[2])
EXPECTED='1f745e279b5940955657f09a8bf8bf40346e5696c321e1307a71f96c68190ebc'
CURRENT_HOOK='6b7fcb76bbd989c24c74da3b59523198c5310f6598a51c2d0d5c4646dee7de43'
if hashlib.sha256(src.read_bytes()).hexdigest()!=EXPECTED: raise SystemExit('R54 installer SHA mismatch')
s=src.read_text()
old=re.search(r"PREV_HOOK_SHA='([0-9a-f]{64})'",s)
if not old: raise SystemExit('PREV_HOOK_SHA missing')
s=s[:old.start()]+f"PREV_HOOK_SHA='{CURRENT_HOOK}'"+s[old.end():]
out.write_text(s)
