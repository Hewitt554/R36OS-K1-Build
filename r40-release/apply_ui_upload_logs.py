#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_ui_upload_logs.py /path/to/r36os_alpha5.c")

p=Path(sys.argv[1])
s=p.read_text()

old='''  if(contains(es,"PASS")&&ea[0]){draw_export_panel("PASS",100,"Export complete","Verified and flushed safely to SD1",ea,el[0]?el:"BOOT/R36OS-Logs",1);logmsg("Diagnostics archive verified on user-visible SD1");}
  else{draw_export_panel("FAIL",100,"Export failed",ed[0]?ed:"No verified archive was created","",el,1);logmsg("ERROR diagnostic export failed verification");}
  wait_export_ok();
}
'''
new='''  if(contains(es,"PASS")&&ea[0]){
    draw_export_panel("RUNNING",94,"Local export complete","Uploading privacy-redacted OS / game / kernel logs to private GitHub",ea,el[0]?el:"BOOT/R36OS-Logs",0);
    logmsg("Diagnostics archive verified locally; private GitHub upload requested");
    run_sh("/usr/local/bin/r36os-github-diagnostics upload-queued >/dev/null 2>&1");
    char gs[1024],gstat[48],gdetail[192],gremote[224];memzero(gs,sizeof(gs));memzero(gstat,sizeof(gstat));memzero(gdetail,sizeof(gdetail));memzero(gremote,sizeof(gremote));
    read_file("/run/r36os-github-diagnostics.status",gs,sizeof(gs));cfg_val(gs,"status",gstat,sizeof(gstat));cfg_val(gs,"detail",gdetail,sizeof(gdetail));cfg_val(gs,"remote_path",gremote,sizeof(gremote));
    if(contains(gstat,"UPLOADED")){draw_export_panel("PASS",100,"Logs uploaded","Local archive saved; redacted diagnostic bundle uploaded to private GitHub",ea,gremote[0]?gremote:"R36OS-Device-Logs",1);logmsg("Private GitHub diagnostic upload PASS");}
    else if(contains(gstat,"QUEUED_NOT_CONFIGURED")){draw_export_panel("PASS",100,"Logs saved locally","GitHub upload needs one-time setup; redacted bundle remains queued safely",ea,el[0]?el:"BOOT/R36OS-Logs",1);logmsg("GitHub diagnostics queued but not configured");}
    else if(contains(gstat,"QUEUED")){draw_export_panel("PASS",100,"Logs queued","Local archive saved; redacted GitHub bundle is queued for the next upload",ea,el[0]?el:"BOOT/R36OS-Logs",1);logmsg("GitHub diagnostics remain queued");}
    else{draw_export_panel("PASS",100,"Logs saved locally",gdetail[0]?gdetail:"GitHub upload did not report success; bundle remains queued",ea,el[0]?el:"BOOT/R36OS-Logs",1);logmsg("GitHub diagnostic upload returned without UPLOADED status");}
  }
  else{draw_export_panel("FAIL",100,"Export failed",ed[0]?ed:"No verified archive was created","",el,1);logmsg("ERROR diagnostic export failed verification");}
  wait_export_ok();
}
'''
if old not in s:
    raise SystemExit("UI export completion anchor missing")
s=s.replace(old,new,1)

old_label='text(246,270,"A(bottom)",1,C_BLUE);text(338,270,"Capture + export diagnostics",1,C_TEXT);'
new_label='text(246,270,"A(bottom)",1,C_BLUE);text(338,270,"Capture + upload logs",1,C_TEXT);'
if old_label not in s:
    raise SystemExit("Diagnostics menu label anchor missing")
s=s.replace(old_label,new_label,1)

p.write_text(s)
print("R40_UI_UPLOAD_LOGS_PATCH=PASS")
