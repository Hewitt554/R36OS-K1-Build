from pathlib import Path
import gzip,hashlib,struct,sys,zlib
if len(sys.argv)!=3: raise SystemExit("usage: patch_uinitrd.py OLD_UINITRD NEW_UINITRD")
src=Path(sys.argv[1]).read_bytes()
EXPECTED='6d44f435bd88b54e91af569fd6445db460b9ab80313062b8136796f27b888f6e'
if hashlib.sha256(src).hexdigest()!=EXPECTED: raise SystemExit('unexpected source uInitrd')
if len(src)<64 or struct.unpack('>I',src[:4])[0]!=0x27051956: raise SystemExit('not legacy uImage')
hdr=bytearray(src[:64]); size=struct.unpack('>I',hdr[12:16])[0]
payload=src[64:64+size]
if (zlib.crc32(payload)&0xffffffff)!=struct.unpack('>I',hdr[24:28])[0]: raise SystemExit('source data crc mismatch')
hchk=bytearray(hdr); oldhc=struct.unpack('>I',hchk[4:8])[0]; hchk[4:8]=b'\0'*4
if (zlib.crc32(hchk)&0xffffffff)!=oldhc: raise SystemExit('source header crc mismatch')
cpio=gzip.decompress(payload)
a=b'/newroot/sbin/init\0'; b=b'/newroot/opt/r36i\0\0'
if len(a)!=len(b) or cpio.count(a)!=1: raise SystemExit('newroot init anchor mismatch')
cpio=cpio.replace(a,b,1)
a=b'\0/sbin/init\0mount proc failed'; b=b'\0/opt/r36i\0\0mount proc failed'
if len(a)!=len(b) or cpio.count(a)!=1: raise SystemExit('exec init anchor mismatch')
cpio=cpio.replace(a,b,1)
if b'/newroot/opt/r36i\0' not in cpio or b'\0/opt/r36i\0' not in cpio: raise SystemExit('patched init paths missing')
newpayload=gzip.compress(cpio,compresslevel=9,mtime=0)
hdr[12:16]=struct.pack('>I',len(newpayload))
hdr[24:28]=struct.pack('>I',zlib.crc32(newpayload)&0xffffffff)
hdr[4:8]=b'\0'*4
hdr[4:8]=struct.pack('>I',zlib.crc32(hdr)&0xffffffff)
out=bytes(hdr)+newpayload
Path(sys.argv[2]).write_bytes(out)
print('source_sha256='+EXPECTED)
print('patched_sha256='+hashlib.sha256(out).hexdigest())
print('patched_size='+str(len(out)))
