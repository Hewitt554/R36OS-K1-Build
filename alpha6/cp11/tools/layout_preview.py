#!/usr/bin/env python3
"""CP11: non-flashable MBR geometry preview for 32, 64 and 128 GB SD1 cards.
No devices, block writes, mkfs, partitioning or raw disk images used.
"""
import json
from pathlib import Path

SECTOR=512
MIB=1024*1024
GIB=1024**3
ALIGN=2048  # 1MiB LBA alignment

def roundup(value, multiple):
    return (value+multiple-1)//multiple*multiple

def geometry(capacity_bytes, root_gib):
    if capacity_bytes < 30*10**9 or capacity_bytes >= 2**41:
        raise ValueError('Preview only supports realistic 32 GB–2 TB cards')
    if root_gib not in (8,12):
        raise ValueError('Root size preview is only 8 or 12 GiB')
    total=capacity_bytes//SECTOR
    specs=[('R36BOOT','FAT32',0x0c,512*MIB//SECTOR),
           ('R36SYS','ext4',0x83,root_gib*GIB//SECTOR),
           ('R36UPDATE','FAT32',0x0c,1*GIB//SECTOR)]
    start=32768  # 16 MiB reserved U-Boot/MBR area
    items=[]
    for label,fs,ptype,length in specs:
        start=roundup(start,ALIGN)
        if start+length>=total:
            raise ValueError('Partition layout exceeds capacity')
        items.append(dict(label=label,filesystem=fs,mbr_type=hex(ptype),start_sector=start,
                          sectors=length,bytes=length*SECTOR))
        start+=length
    start=roundup(start,ALIGN)
    remaining=((total-start)//ALIGN)*ALIGN
    if remaining < 4*GIB//SECTOR:
        raise ValueError('State partition would be too small')
    items.append(dict(label='R36STATE',filesystem='ext4',mbr_type='0x83',start_sector=start,
                      sectors=remaining,bytes=remaining*SECTOR))
    assert len(items)==4
    assert all(x['start_sector']%ALIGN==0 for x in items)
    assert all(items[i]['start_sector']+items[i]['sectors']<=items[i+1]['start_sector'] for i in range(3))
    assert items[-1]['start_sector']+items[-1]['sectors']<=total
    return {'card_advertised_bytes':capacity_bytes,'card_usable_gib':round(capacity_bytes/GIB,2),
            'provisional_root_gib':root_gib,'partition_count':4,
            'partitions':items,'reserved_legacy_boot_area_mib':16,
            'state_gib':round(remaining*SECTOR/GIB,2),
            'cp06_root_allocated_bytes':589508608,
            'warnings':['SIMULATION ONLY: generates no flashable image or partition table',
                        'R36SYS size not final; hardware and software needs unmeasured',
                        'STATE backups grow over time and must be space-checked',
                        'Actual SD cards may have a different raw capacity than advertised']}

def main():
    results=[geometry(capacity,root) for capacity in (32*10**9,64*10**9,128*10**9) for root in (8,12)]
    result={'status':'DESIGN_ONLY', 'layout_options':results, 'selected':None,
            'rationale':'Compact rescue image in BOOT, one main root, shared update and expandable state; four MBR entries.'}
    dest=Path(__file__).resolve().parents[1]/'docs'/'CP11_LAYOUT_CAPACITY_SIMULATION.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Wrote DESIGN-ONLY comparison:',dest)
if __name__=='__main__':main()