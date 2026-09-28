#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_ui_upload_logs.py /path/to/r36os_alpha5.c")

p=Path(sys.argv[1])
s=p.read_text()

secret_writer_old='static int write_file(const char*p,const char*b,int n,int append){int fl=O_WRONLY|O_CREAT|(append?O_APPEND:O_TRUNC);int fd=openf(p,fl,0644);if(fd<0)return -1;int r=(int)sc3(SYS_write,fd,(long)b,n);sc1(SYS_close,fd);return r;}'
secret_writer_new=secret_writer_old+'\\nstatic int write_secret_file(const char*p,const char*b,int n){int fd=openf(p,O_WRONLY|O_CREAT|O_TRUNC,0600);if(fd<0)return -1;int r=(int)sc3(SYS_write,fd,(long)b,n);sc1(SYS_close,fd);return r;}'
if secret_writer_old not in s:
    raise SystemExit("secret writer anchor missing")
s=s.replace(secret_writer_old,secret_writer_new,1)

old='''  if(contains(es,"PASS")&&ea[0]){draw_export_panel("PASS",100,"Export complete","Verified and flushed safely to SD1",ea,el[0]?el:"BOOT/R36OS-Logs",1);logmsg("Diagnostics archive verified on user-visible SD1");}
  else{draw_export_panel("FAIL",100,"Export failed",ed[0]?ed:"No verified archive was created","",el,1);logmsg("ERROR diagnostic export failed verification");}
  wait_export_ok();
}
'''
new='''  if(contains(es,"PASS")&&ea[0]){
    draw_export_panel("RUNNING",94,"Local export complete","Uploading privacy-redacted OS / game / kernel logs to private GitHub",ea,el[0]?el:"BOOT/R36OS-Logs",0);
    logmsg("Diagnostics archive verified locally; checking private GitHub upload result");
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


repair_funcs=r'''static void draw_r36update_repair_ui(const char*statev,int pct,const char*stage,const char*msg,const char*detail,int final){
  if(pct<0)pct=0;if(pct>100)pct=100;int fail=contains(statev,"FAIL"),ok=contains(statev,"PASS");u32 accent=fail?C_RED:(ok?C_GREEN:C_BLUE);
  header("R36UPDATE repair");rect(34,70,W-68,342,C_PANEL);border(34,70,W-68,342,accent);
  text(58,92,fail?"R36UPDATE repair stopped":(ok?"R36UPDATE repair verified":"Safe FAT repair"),2,fail?C_RED:(ok?C_GREEN:C_TEXT));
  text(58,128,stage&&stage[0]?stage:"Checking update partition",1,accent);
  rect(58,158,W-116,24,C_BG);border(58,158,W-116,24,C_LINE);int fill=(W-120)*pct/100;if(fill>0)rect(60,160,fill,20,accent);
  char pc[24];memzero(pc,sizeof(pc));itoa10(pct,pc);scat(pc,sizeof(pc),"%");text((W-text_width(pc,1))/2,188,pc,1,C_TEXT);
  if(msg&&msg[0])text(58,220,msg,1,fail?C_RED:C_TEXT);if(detail&&detail[0])text(58,248,detail,1,C_MUTED);
  if(final){button((W-176)/2,330,176,"Okay",1);text((W-text_width("A = bottom [printed B]  Okay",1))/2,374,"A = bottom [printed B]  Okay",1,C_MUTED);}
  else{text(58,292,"Full R36UPDATE backup is made on R36STATE first.",1,C_GREEN);text(58,316,"No forced/lazy unmount. K1 markers block repair.",1,C_MUTED);}
  present();
}
static int confirm_r36update_repair(){
  header("Confirm R36UPDATE repair");rect(34,70,W-68,342,C_PANEL);border(34,70,W-68,342,C_YELLOW);
  text(58,94,"Repair the dirty R36UPDATE FAT filesystem?",2,C_TEXT);
  text(58,142,"Exact target: /dev/mmcblk0p3  UUID C49E-0225",1,C_GREEN);
  text(58,174,"R36OS backs up every UPDATE file to R36STATE first.",1,C_TEXT);
  text(58,202,"The partition is unmounted before fsck and checked read-only after.",1,C_TEXT);
  text(58,230,"K1 Boot Next Once markers must be absent.",1,C_TEXT);
  text(58,258,"A clean reboot is required before retrying K1.",1,C_YELLOW);
  button(112,326,176,"Repair",1);button(352,326,176,"Cancel",0);
  text(94,374,"A = bottom [printed B] Confirm     B = right [printed A] Cancel",1,C_MUTED);present();
  struct input_event ev;for(;;){long n=sc3(SYS_read,infd,(long)&ev,sizeof(ev));if(n==(long)sizeof(ev)&&ev.type==EV_KEY&&ev.value==1){if(ev.code==304)return 1;if(ev.code==305)return 0;}sleep_ms(20);}
}
static void run_r36update_repair_ui(){
  if(!confirm_r36update_repair()){logmsg("R36UPDATE repair cancelled by user");return;}
  run_sh("rm -f /run/r36os-r36update-repair.result /run/r36os-r36update-repair.progress");
  draw_r36update_repair_ui("RUNNING",1,"Starting repair","Verifying exact R36UPDATE identity and safety gates","",0);
  long pid=spawn_sh("/usr/local/bin/r36os-r36update-repair repair >/dev/null 2>&1");
  if(pid<=0){draw_r36update_repair_ui("FAIL",100,"Repair could not start","No filesystem write was attempted","Exporter/repair helper could not launch",1);wait_return_button();return;}
  s64 started=now_ms();char pb[512],stage[128],msg[192];int pct=1;memzero(stage,sizeof(stage));memzero(msg,sizeof(msg));
  while(!child_done(pid)){
    memzero(pb,sizeof(pb));if(read_file("/run/r36os-r36update-repair.progress",pb,sizeof(pb))>0){char*st;char*sg;char*mg;int pp;progress_fields(pb,&st,&pp,&sg,&mg);pct=pp;memzero(stage,sizeof(stage));memzero(msg,sizeof(msg));scopy_n(stage,sizeof(stage),sg,124);scopy_n(msg,sizeof(msg),mg,188);draw_r36update_repair_ui(st,pct,stage,msg,"",0);}
    if(now_ms()-started>600000){sc2(SYS_kill,pid,SIGTERM);sleep_ms(300);sc2(SYS_kill,pid,SIGKILL);draw_r36update_repair_ui("FAIL",100,"Repair timed out","R36OS stopped waiting after ten minutes","Reboot before further UPDATE/K1 work and export logs",1);logmsg("ERROR R36UPDATE repair timed out");wait_return_button();return;}
    sleep_ms(140);
  }
  char rr[1536],rs[64],rd[256],rb[256],fr[32],vr[32];memzero(rr,sizeof(rr));memzero(rs,sizeof(rs));memzero(rd,sizeof(rd));memzero(rb,sizeof(rb));memzero(fr,sizeof(fr));memzero(vr,sizeof(vr));
  read_file("/run/r36os-r36update-repair.result",rr,sizeof(rr));cfg_val(rr,"status",rs,sizeof(rs));cfg_val(rr,"detail",rd,sizeof(rd));cfg_val(rr,"backup",rb,sizeof(rb));cfg_val(rr,"repair_rc",fr,sizeof(fr));cfg_val(rr,"verify_rc",vr,sizeof(vr));
  if(contains(rs,"PASS_REBOOT_REQUIRED")){
    draw_r36update_repair_ui("PASS",100,"Repair and verification complete","R36UPDATE is intentionally unmounted until reboot","Restarting now; retry Boot Next Once only after the clean boot",0);
    logmsg("R36UPDATE FAT repair PASS; clean reboot required");
    sleep_ms(2200);
    request_power_handoff("reboot","r36update-repair","Restart");
    return;
  }
  draw_r36update_repair_ui("FAIL",100,"Repair did not complete",rd[0]?rd:"See R36UPDATE repair log",rb[0]?rb:"No repair was committed",1);
  logmsg("R36UPDATE FAT repair failed closed");
  wait_return_button();
}
'''
source_anchor='static void run_k1_boot_once_ui(){'
if source_anchor not in s:
    raise SystemExit("K1 UI function anchor missing")
s=s.replace(source_anchor,repair_funcs+'\\n'+source_anchor,1)

old_diag='text(246,406,"R1",1,C_BLUE);text(286,406,k1id[0]?"Arm verified K1 Boot Next Once":"K1 candidate unavailable",1,k1id[0]?C_TEXT:C_MUTED);'
new_diag='text(246,406,"R1",1,C_BLUE);text(286,406,k1id[0]?"Arm verified K1 Boot Next Once":"K1 candidate unavailable",1,k1id[0]?C_TEXT:C_MUTED);text(506,406,"R2",1,C_BLUE);text(546,406,"Repair UPDATE",1,C_YELLOW);'
if old_diag not in s:
    raise SystemExit("Diagnostics R1 line anchor missing")
s=s.replace(old_diag,new_diag,1)

old_action='else if(code==KEY_R1&&settingssel==9){run_k1_boot_once_ui();}'
new_action='else if(code==KEY_R2&&settingssel==9){run_r36update_repair_ui();}else if(code==KEY_R1&&settingssel==9){run_k1_boot_once_ui();}'
if old_action not in s:
    raise SystemExit("Diagnostics R1 action anchor missing")
s=s.replace(old_action,new_action,1)

old_label='text(246,270,"A(bottom)",1,C_BLUE);text(338,270,"Capture + export diagnostics",1,C_TEXT);'
new_label='text(246,270,"A(bottom)",1,C_BLUE);text(338,270,"Capture + upload logs",1,C_TEXT);'
if old_label not in s:
    raise SystemExit("Diagnostics menu label anchor missing")
s=s.replace(old_label,new_label,1)

p.write_text(s)
print("R40_UI_UPLOAD_LOGS_AND_FAT_REPAIR_PATCH=PASS")
