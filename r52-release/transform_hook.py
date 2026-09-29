from pathlib import Path
import hashlib,sys
if len(sys.argv)!=5: raise SystemExit("usage: transform_hook.py <r51-hook> <r51-meta> <out-hook> <out-meta>")
src=Path(sys.argv[1]); meta_src=Path(sys.argv[2]); out=Path(sys.argv[3]); meta_out=Path(sys.argv[4])
CID='e551eb6598d6da7a8e8320e9'
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=dict(line.split('=',1) for line in meta_src.read_text().splitlines() if '=' in line)
if m.get('format')!='R36OS_K1_BOOT_HOOK_V4': raise SystemExit('expected R51 hook V4')
if m.get('candidate_id')!=CID: raise SystemExit('candidate mismatch')
if m.get('breadcrumbs')!='K1CON.OK,K1IMG.OK,K1INI.OK,K1DTB.OK,K1BOT.OK,K1RET.OK': raise SystemExit('breadcrumb lineage mismatch')
oldsha=m.get('hooked_boot_sha256','')
if sha(src)!=oldsha: raise SystemExit('R51 hook sha mismatch')
s=src.read_text()

repls=[
('''# R51: root-level persistent stage breadcrumbs survive a hard reset.
setenv r36os_k1_probe "hook_seen"''',
'''# R52: persistent breadcrumbs plus visible K1 boot trace.
echo ""
echo "R36OS K1 diagnostic boot"
echo "-----------------------"
setenv r36os_k1_probe "hook_seen"'''),
('''        setenv r36os_k1_probe "already_consumed"
        echo "R36OS K1 attempt already consumed - booting legacy kernel"''',
'''        setenv r36os_k1_probe "already_consumed"
        echo "[SAFE] K1 attempt already consumed"
        echo "[SAFE] Booting legacy kernel"'''),
('''                    setenv r36os_k1_probe "guard_verified"
                    fatwrite mmc 1:3 ${loadaddr} "K1CON.OK" 1''',
'''                    setenv r36os_k1_probe "guard_verified"
                    fatwrite mmc 1:3 ${loadaddr} "K1CON.OK" 1
                    echo "[1/5] One-shot guard verified"'''),
('''                        setenv r36os_k1_probe "image_loaded"
                        fatwrite mmc 1:3 ${loadaddr} "K1IMG.OK" 1''',
'''                        setenv r36os_k1_probe "image_loaded"
                        fatwrite mmc 1:3 ${loadaddr} "K1IMG.OK" 1
                        echo "[2/5] Linux Image loaded"'''),
('''                            setenv r36os_k1_probe "initrd_loaded"
                            fatwrite mmc 1:3 ${loadaddr} "K1INI.OK" 1''',
'''                            setenv r36os_k1_probe "initrd_loaded"
                            fatwrite mmc 1:3 ${loadaddr} "K1INI.OK" 1
                            echo "[3/5] initramfs loaded"'''),
('''                                setenv r36os_k1_probe "payloads_loaded"
                                fatwrite mmc 1:3 ${loadaddr} "K1DTB.OK" 1
                                setenv r36os_legacy_bootargs "${bootargs}"
                                setenv bootargs "${bootargs} r36os.kernel_slot=next r36os.kernel_attempt=K1 r36os.kernel_candidate=e551eb6598d6da7a8e8320e9 r36os.k1_probe=${r36os_k1_probe}"
                                fatwrite mmc 1:3 ${loadaddr} "K1BOT.OK" 1
                                booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}
                                fatwrite mmc 1:3 ${loadaddr} "K1RET.OK" 1''',
'''                                setenv r36os_k1_probe "payloads_loaded"
                                fatwrite mmc 1:3 ${loadaddr} "K1DTB.OK" 1
                                echo "[4/5] Panel-4 DTB loaded"
                                setenv r36os_legacy_bootargs "${bootargs}"
                                setenv bootargs "${bootargs} r36os.kernel_slot=next r36os.kernel_attempt=K1 r36os.kernel_candidate=e551eb6598d6da7a8e8320e9 r36os.k1_probe=${r36os_k1_probe} console=tty1 loglevel=8 ignore_loglevel earlycon plymouth.enable=0 systemd.show_status=1"
                                fatwrite mmc 1:3 ${loadaddr} "K1BOT.OK" 1
                                echo "[5/5] Starting Linux 6.12.94-r36os-k1"
                                echo "If this line stays on screen, photograph it."
                                booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}
                                fatwrite mmc 1:3 ${loadaddr} "K1RET.OK" 1
                                echo "[RETURN] Linux returned to U-Boot"'''),
('''                            else
                                setenv r36os_k1_probe "dtb_load_failed"''',
'''                            else
                                setenv r36os_k1_probe "dtb_load_failed"
                                echo "[FAIL] Panel-4 DTB load failed"'''),
('''                        else
                            setenv r36os_k1_probe "initrd_load_failed"''',
'''                        else
                            setenv r36os_k1_probe "initrd_load_failed"
                            echo "[FAIL] initramfs load failed"'''),
('''                    else
                        setenv r36os_k1_probe "image_load_failed"''',
'''                    else
                        setenv r36os_k1_probe "image_load_failed"
                        echo "[FAIL] Linux Image load failed"'''),
('''                else
                    setenv r36os_k1_probe "consumed_size_mismatch"''',
'''                else
                    setenv r36os_k1_probe "consumed_size_mismatch"
                    echo "[FAIL] consumed marker size mismatch"'''),
('''            else
                setenv r36os_k1_probe "consumed_readback_failed"''',
'''            else
                setenv r36os_k1_probe "consumed_readback_failed"
                echo "[FAIL] consumed marker read-back failed"'''),
('''        else
            setenv r36os_k1_probe "consumed_write_failed"''',
'''        else
            setenv r36os_k1_probe "consumed_write_failed"
            echo "[FAIL] consumed marker write failed"''')
]
for a,b in repls:
    if s.count(a)!=1: raise SystemExit('hook anchor mismatch: '+a.splitlines()[0])
    s=s.replace(a,b,1)
out.write_text(s)
newsha=sha(out)
lines=[]
for line in meta_src.read_text().splitlines():
    if line.startswith('format='): line='format=R36OS_K1_BOOT_HOOK_V5'
    elif line.startswith('hooked_boot_sha256='): line=f'hooked_boot_sha256={newsha}'
    elif line.startswith('previous_hook_sha256='): line=f'previous_hook_sha256={oldsha}'
    lines.append(line)
lines += [
 'visible_trace=yes',
 'visible_trace_stages=guard,image,initramfs,dtb,booti',
 'k1_console_args=console=tty1 loglevel=8 ignore_loglevel earlycon plymouth.enable=0 systemd.show_status=1',
]
meta_out.write_text('\n'.join(lines)+'\n')
