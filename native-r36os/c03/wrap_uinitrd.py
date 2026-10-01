#!/usr/bin/env python3
"""Preserve the physically proven R54 uInitrd U-Boot header while replacing only its payload."""
from pathlib import Path
import argparse,binascii,struct,tempfile,os
MAGIC=0x27051956
EXPECTED_BASE_SHA="023a0d2adc113b2d1fea6826387ab6e03e4d479cf5fa36c9b9ff86cf41fd1925"

def sha256(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def base_header(path):
    if sha256(path)!=EXPECTED_BASE_SHA:
        raise SystemExit("base R54 uInitrd sha mismatch")
    full=path.read_bytes()
    h=bytearray(full[:64])
    if len(h)!=64 or struct.unpack(">I",h[:4])[0]!=MAGIC:
        raise SystemExit("bad uImage header")
    sh=struct.unpack_from(">I",h,4)[0]
    chk=bytearray(h); chk[4:8]=b"\0"*4
    if (binascii.crc32(chk)&0xffffffff)!=sh:
        raise SystemExit("base header CRC invalid")
    payload=full[64:]
    if struct.unpack_from(">I",h,12)[0]!=len(payload):
        raise SystemExit("base payload size invalid")
    if (binascii.crc32(payload)&0xffffffff)!=struct.unpack_from(">I",h,24)[0]:
        raise SystemExit("base payload CRC invalid")
    return h

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("base",type=Path)
    ap.add_argument("payload",type=Path)
    ap.add_argument("output",type=Path)
    a=ap.parse_args()
    h=base_header(a.base); p=a.payload.read_bytes()
    if not p.startswith(b"\x1f\x8b"):
        raise SystemExit("native initramfs must be gzip")
    h[8:12]=struct.pack(">I",0)
    h[12:16]=struct.pack(">I",len(p))
    h[24:28]=struct.pack(">I",binascii.crc32(p)&0xffffffff)
    h[31]=1
    h[4:8]=b"\0"*4
    h[4:8]=struct.pack(">I",binascii.crc32(h)&0xffffffff)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=a.output.name+".",dir=str(a.output.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(h);f.write(p);f.flush();os.fsync(f.fileno())
        os.replace(tmp,a.output)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
    print("C03_UINITRD_WRAP=PASS")
if __name__=="__main__":
    main()
