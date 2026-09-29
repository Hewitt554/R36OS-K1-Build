from pathlib import Path
import hashlib,sys
if len(sys.argv)!=5: raise SystemExit("usage: generate_hook.py <r46-hook> <r46-meta> <out-hook> <out-meta>")
old=Path(sys.argv[1]); oldmeta=Path(sys.argv[2]); out=Path(sys.argv[3]); meta=Path(sys.argv[4])
CID='e551eb6598d6da7a8e8320e9'
LEGACY_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=dict(line.split('=',1) for line in oldmeta.read_text().splitlines() if '=' in line)
OLD_HOOK_SHA=m.get('hooked_boot_sha256','')
if not OLD_HOOK_SHA or sha(old)!=OLD_HOOK_SHA or m.get('candidate_id')!=CID: raise SystemExit('current R46 hook/meta mismatch')
text=old.read_text()
start=text.index('# R36OS-K1-BOOT-ONCE-HOOK\n')
end=text.index('# R36OS-K1-BOOT-ONCE-HOOK-END\n',start)+len('# R36OS-K1-BOOT-ONCE-HOOK-END\n')
while end<len(text) and text[end]=='\n': end+=1
legacy=text[:start]+text[end:]
if hashlib.sha256(legacy.encode()).hexdigest()!=LEGACY_SHA: raise SystemExit('legacy recovery mismatch')
anchor='if env exists PanelNum '
if legacy.count(anchor)!=1: raise SystemExit('legacy hook anchor')
req=f'R36OS-KernelNext/boot-next.{CID}.once'
cons='R36K1.CNS'
hook=f'''# R36OS-K1-BOOT-ONCE-HOOK
# candidate_id={CID}
# R50: old R36S U-Boot fatwrite uses a root-level 8.3 consumed marker.
setenv r36os_k1_probe "hook_seen"
if load mmc 1:3 ${{loadaddr}} "{req}"
then
    setenv r36os_k1_probe "request_visible"
    setenv r36os_req_size ${{filesize}}
    if load mmc 1:3 ${{loadaddr}} "{cons}"
    then
        setenv r36os_k1_probe "already_consumed"
        echo "R36OS K1 attempt already consumed - booting legacy kernel"
    else
        if fatwrite mmc 1:3 ${{loadaddr}} "{cons}" ${{r36os_req_size}}
        then
            setenv r36os_k1_probe "consumed_written"
            if load mmc 1:3 ${{loadaddr}} "{cons}"
            then
                setenv r36os_k1_probe "consumed_readback"
                if test ${{filesize}} = ${{r36os_req_size}}
                then
                    setenv r36os_k1_probe "guard_verified"
                    if load mmc 1:3 ${{loadaddr}} "R36OS-KernelNext/K1/Image"
                    then
                        setenv r36os_k1_probe "image_loaded"
                        if load mmc 1:3 ${{initrd_loadaddr}} "R36OS-KernelNext/K1/uInitrd"
                        then
                            setenv r36os_k1_probe "initrd_loaded"
                            if load mmc 1:3 ${{dtb_loadaddr}} "R36OS-KernelNext/K1/rk3326-r36s-k1.dtb"
                            then
                                setenv r36os_k1_probe "payloads_loaded"
                                setenv r36os_legacy_bootargs "${{bootargs}}"
                                setenv bootargs "${{bootargs}} r36os.kernel_slot=next r36os.kernel_attempt=K1 r36os.kernel_candidate={CID} r36os.k1_probe=${{r36os_k1_probe}}"
                                booti ${{loadaddr}} ${{initrd_loadaddr}} ${{dtb_loadaddr}}
                                setenv bootargs "${{r36os_legacy_bootargs}}"
                                setenv r36os_k1_probe "booti_return"
                            else
                                setenv r36os_k1_probe "dtb_load_failed"
                            fi
                        else
                            setenv r36os_k1_probe "initrd_load_failed"
                        fi
                    else
                        setenv r36os_k1_probe "image_load_failed"
                    fi
                else
                    setenv r36os_k1_probe "consumed_size_mismatch"
                fi
            else
                setenv r36os_k1_probe "consumed_readback_failed"
            fi
        else
            setenv r36os_k1_probe "consumed_write_failed"
        fi
    fi
else
    if load mmc 1:3 ${{loadaddr}} "R36OS-KernelNext/K1/K1.conf"
    then
        setenv r36os_k1_probe "candidate_visible_request_missing"
    else
        setenv r36os_k1_probe "r36update_unreadable"
    fi
fi
setenv bootargs "${{bootargs}} r36os.k1_probe=${{r36os_k1_probe}}"
# R36OS-K1-BOOT-ONCE-HOOK-END

'''
newtext=legacy.replace(anchor,hook+anchor,1)
out.write_text(newtext)
newsha=sha(out)
meta.write_text('\n'.join([
 'format=R36OS_K1_BOOT_HOOK_V3',
 f'candidate_id={CID}',
 f'legacy_boot_sha256={LEGACY_SHA}',
 f'hooked_boot_sha256={newsha}',
 f'previous_hook_sha256={OLD_HOOK_SHA}',
 'update_partition=mmc_1_3',
 'candidate_dtb=rk3326-r36s-k1.dtb',
 f'request={req}',
 f'consumed={cons}',
 'consumed_marker_mode=root-8.3',
 'legacy_fallthrough=yes',
 'probe_cmdline_key=r36os.k1_probe',
])+'\n')
