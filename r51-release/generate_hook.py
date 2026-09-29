from pathlib import Path
import hashlib,sys
if len(sys.argv)!=5: raise SystemExit("usage: generate_hook.py <r50-hook> <r50-meta> <out-hook> <out-meta>")
old=Path(sys.argv[1]); oldmeta=Path(sys.argv[2]); out=Path(sys.argv[3]); meta=Path(sys.argv[4])
CID='e551eb6598d6da7a8e8320e9'
LEGACY_SHA='b442894eabd2a9716ba5b8dda817251d94cc13689b341f7a861ad3f33998ec4e'
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=dict(line.split('=',1) for line in oldmeta.read_text().splitlines() if '=' in line)
OLD_HOOK_SHA=m.get('hooked_boot_sha256','')
if not OLD_HOOK_SHA or sha(old)!=OLD_HOOK_SHA or m.get('candidate_id')!=CID: raise SystemExit('current R50 hook/meta mismatch')
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
h=f'''# R36OS-K1-BOOT-ONCE-HOOK
# candidate_id={CID}
# R51: root-level persistent stage breadcrumbs survive a hard reset.
setenv r36os_k1_probe "hook_seen"
if load mmc 1:3 __D__{{loadaddr}} "{req}"
then
    setenv r36os_k1_probe "request_visible"
    setenv r36os_req_size __D__{{filesize}}
    if load mmc 1:3 __D__{{loadaddr}} "{cons}"
    then
        setenv r36os_k1_probe "already_consumed"
        echo "R36OS K1 attempt already consumed - booting legacy kernel"
    else
        if fatwrite mmc 1:3 __D__{{loadaddr}} "{cons}" __D__{{r36os_req_size}}
        then
            setenv r36os_k1_probe "consumed_written"
            if load mmc 1:3 __D__{{loadaddr}} "{cons}"
            then
                setenv r36os_k1_probe "consumed_readback"
                if test __D__{{filesize}} = __D__{{r36os_req_size}}
                then
                    setenv r36os_k1_probe "guard_verified"
                    fatwrite mmc 1:3 __D__{{loadaddr}} "K1CON.OK" 1
                    if load mmc 1:3 __D__{{loadaddr}} "R36OS-KernelNext/K1/Image"
                    then
                        setenv r36os_k1_probe "image_loaded"
                        fatwrite mmc 1:3 __D__{{loadaddr}} "K1IMG.OK" 1
                        if load mmc 1:3 __D__{{initrd_loadaddr}} "R36OS-KernelNext/K1/uInitrd"
                        then
                            setenv r36os_k1_probe "initrd_loaded"
                            fatwrite mmc 1:3 __D__{{loadaddr}} "K1INI.OK" 1
                            if load mmc 1:3 __D__{{dtb_loadaddr}} "R36OS-KernelNext/K1/rk3326-r36s-k1.dtb"
                            then
                                setenv r36os_k1_probe "payloads_loaded"
                                fatwrite mmc 1:3 __D__{{loadaddr}} "K1DTB.OK" 1
                                setenv r36os_legacy_bootargs "__D__{{bootargs}}"
                                setenv bootargs "__D__{{bootargs}} r36os.kernel_slot=next r36os.kernel_attempt=K1 r36os.kernel_candidate={CID} r36os.k1_probe=__D__{{r36os_k1_probe}}"
                                fatwrite mmc 1:3 __D__{{loadaddr}} "K1BOT.OK" 1
                                booti __D__{{loadaddr}} __D__{{initrd_loadaddr}} __D__{{dtb_loadaddr}}
                                fatwrite mmc 1:3 __D__{{loadaddr}} "K1RET.OK" 1
                                setenv bootargs "__D__{{r36os_legacy_bootargs}}"
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
    if load mmc 1:3 __D__{{loadaddr}} "R36OS-KernelNext/K1/K1.conf"
    then
        setenv r36os_k1_probe "candidate_visible_request_missing"
    else
        setenv r36os_k1_probe "r36update_unreadable"
    fi
fi
setenv bootargs "__D__{{bootargs}} r36os.k1_probe=__D__{{r36os_k1_probe}}"
# R36OS-K1-BOOT-ONCE-HOOK-END

'''
h=h.replace('__D__','$')
newtext=legacy.replace(anchor,h+anchor,1)
out.write_text(newtext)
newsha=sha(out)
meta.write_text('\n'.join([
 'format=R36OS_K1_BOOT_HOOK_V4',
 f'candidate_id={CID}',
 f'legacy_boot_sha256={LEGACY_SHA}',
 f'hooked_boot_sha256={newsha}',
 f'previous_hook_sha256={OLD_HOOK_SHA}',
 'update_partition=mmc_1_3',
 'candidate_dtb=rk3326-r36s-k1.dtb',
 f'request={req}',
 f'consumed={cons}',
 'consumed_marker_mode=root-8.3',
 'breadcrumbs=K1CON.OK,K1IMG.OK,K1INI.OK,K1DTB.OK,K1BOT.OK,K1RET.OK',
 'breadcrumbs_mode=root-8.3-best-effort',
 'legacy_fallthrough=yes',
 'probe_cmdline_key=r36os.k1_probe',
])+'\n')
