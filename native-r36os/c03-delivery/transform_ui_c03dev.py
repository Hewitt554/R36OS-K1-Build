from pathlib import Path
import hashlib,sys

if len(sys.argv)!=3:
    raise SystemExit("usage: transform_ui_c03dev.py <r58-source.c> <patched.c>")

src=Path(sys.argv[1]); out=Path(sys.argv[2])
BASE_SHA="657803bb2b4f60414d85775f86dae8d01d3cb46d631cfe2309e682dffd93289a"
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
actual=sha(src)
if actual!=BASE_SHA:
    raise SystemExit(f"R58 source sha mismatch: {actual}")

s=src.read_text()

old='static int controller_test=0,ct_keys=0,ct_axes=0,ct_last_type=0,ct_last_code=0,ct_last_value=0;static s64 controller_test_until=0;'
new=old+'static int native_c03_menu=0,native_c03_sel=0,native_c03_confirm=0;'
if s.count(old)!=1: raise SystemExit("controller globals anchor mismatch")
s=s.replace(old,new,1)

old='text(246,382,"Kernel Lab",1,C_MUTED);'
new=old+'text(246,406,"R1",1,C_BLUE);text(286,406,"Native C03 developer controls",1,C_TEXT);'
if s.count(old)!=1: raise SystemExit("diagnostics draw anchor mismatch")
s=s.replace(old,new,1)

anchor='static void draw_controller_test(){'
insert=r'''static void native_c03_refresh(){
  run_sh("/usr/local/bin/r36os-native-c03-control status >/run/r36os-native-c03-status 2>&1");
}
static void draw_native_c03_menu(){
  header("Native C03 developer");
  rect(28,64,W-56,H-108,C_PANEL);border(28,64,W-56,H-108,C_BLUE);
  text(50,84,"Native R36OS one-shot test",2,C_TEXT);
  text(50,112,"C03 remains separate from normal K1 Boot Once.",1,C_GREEN);
  char st[1024],bv[24],rs[24],rd[24],nid[48];
  memzero(st,sizeof(st));memzero(bv,sizeof(bv));memzero(rs,sizeof(rs));memzero(rd,sizeof(rd));memzero(nid,sizeof(nid));
  read_file("/run/r36os-native-c03-status",st,sizeof(st));
  cfg_val(st,"bundle_verify_code",bv,sizeof(bv));cfg_val(st,"root_staged",rs,sizeof(rs));cfg_val(st,"ready_staged",rd,sizeof(rd));cfg_val(st,"native_candidate",nid,sizeof(nid));
  text(50,140,"Candidate",1,C_MUTED);text(180,140,nid[0]?nid:"8f8eaa3bae6ad4352b4e01ef",1,C_BLUE);
  text(50,164,"Bundle",1,C_MUTED);text(180,164,bv[0]&&bv[0]=='0'?"Verified":"Check status",1,bv[0]&&bv[0]=='0'?C_GREEN:C_YELLOW);
  text(50,188,"Native root",1,C_MUTED);text(180,188,contains(rs,"yes")?"Staged":"Not staged",1,contains(rs,"yes")?C_GREEN:C_YELLOW);
  text(50,212,"Ready marker",1,C_MUTED);text(180,212,contains(rd,"yes")?"Present":"Not staged",1,contains(rd,"yes")?C_GREEN:C_YELLOW);
  const char*items[4]={"Status / refresh","Stage native root only","Arm Native Boot Once","Disarm native request"};
  for(int i=0;i<4;i++)button(50,246+i*38,W-100,items[i],i==native_c03_sel);
  text(50,406,"A(bottom)=Select   B(right)=Back   Up/Down=Move",1,C_MUTED);
  present();
}
static void draw_native_c03_confirm(){
  header("Confirm Native Boot Once");
  rect(46,94,W-92,264,C_PANEL);border(46,94,W-92,264,C_RED);
  text(72,120,"Arm Native C03 for ONE boot?",2,C_TEXT);
  text(72,156,"This writes the one-shot request only after",1,C_MUTED);
  text(72,178,"the staged root, hook and K1 payload verify.",1,C_MUTED);
  text(72,210,"A(bottom)",1,C_GREEN);text(180,210,"CONFIRM ARM ONCE",1,C_TEXT);
  text(72,240,"B(right)",1,C_BLUE);text(180,240,"Cancel",1,C_TEXT);
  text(72,284,"If the native boot fails, power-cycle once.",1,C_YELLOW);
  text(72,306,"The consumed guard prevents repeated attempts.",1,C_YELLOW);
  present();
}
static void native_c03_result_overlay(const char*label){
  char rr[512];memzero(rr,sizeof(rr));read_file("/run/r36os-native-c03-ui",rr,sizeof(rr));
  if(contains(rr,"status=PASS"))overlay_msg(label,C_GREEN);else overlay_msg("Native C03 action failed - export diagnostics",C_RED);
  overlay_until=now_ms()+3200;
  native_c03_refresh();
}
static void native_c03_action(){
  if(native_c03_sel==0){native_c03_refresh();overlay_msg("Native C03 status refreshed",C_BLUE);overlay_until=now_ms()+1600;return;}
  if(native_c03_sel==1){
    overlay_msg("Staging native root - please wait",C_BLUE);present();
    run_sh("/usr/local/bin/r36os-native-c03-control stage-only >/run/r36os-native-c03-ui 2>&1");
    native_c03_result_overlay("Native root staged - normal boot unchanged");return;
  }
  if(native_c03_sel==2){native_c03_confirm=1;return;}
  overlay_msg("Disarming Native C03 request",C_BLUE);present();
  run_sh("/usr/local/bin/r36os-native-c03-control disarm >/run/r36os-native-c03-ui 2>&1");
  native_c03_result_overlay("Native C03 request disarmed");
}
static void native_c03_arm_confirmed(){
  overlay_msg("Verifying and arming ONE native boot - please wait",C_YELLOW);present();
  run_sh("/usr/local/bin/r36os-native-c03-control arm-once >/run/r36os-native-c03-ui 2>&1");
  native_c03_result_overlay("Native C03 armed ONCE - reboot when ready");
}
'''
if s.count(anchor)!=1: raise SystemExit("controller test function anchor mismatch")
s=s.replace(anchor,insert+anchor,1)

old='static void redraw(){if(controller_test){draw_controller_test();return;}'
new='static void redraw(){if(native_c03_confirm){draw_native_c03_confirm();return;}if(native_c03_menu){draw_native_c03_menu();return;}if(controller_test){draw_controller_test();return;}'
if s.count(old)!=1: raise SystemExit("redraw anchor mismatch")
s=s.replace(old,new,1)

old='redraw();return;}if(prop_mode){'
new='''redraw();return;}if(native_c03_confirm){if(code==KEY_A){native_c03_confirm=0;native_c03_arm_confirmed();}else if(code==KEY_B){native_c03_confirm=0;logmsg("Native C03 arm cancelled");}redraw();return;}if(native_c03_menu){if(code==KEY_UP&&native_c03_sel>0)native_c03_sel--;else if(code==KEY_DOWN&&native_c03_sel<3)native_c03_sel++;else if(code==KEY_A)native_c03_action();else if(code==KEY_B){native_c03_menu=0;native_c03_confirm=0;logmsg("Native C03 developer menu closed");}redraw();return;}if(prop_mode){'''
if s.count(old)!=1: raise SystemExit("native menu input anchor mismatch")
s=s.replace(old,new,1)

old='else if(code==KEY_L1&&settingssel==9){logmsg("Kernel Lab baseline requested");run_kernel_baseline_ui();}'
new='else if(code==KEY_R1&&settingssel==9){native_c03_menu=1;native_c03_sel=0;native_c03_confirm=0;native_c03_refresh();logmsg("Native C03 developer menu opened");}'+old
if s.count(old)!=1: raise SystemExit("diagnostics R1 anchor mismatch")
s=s.replace(old,new,1)

out.write_text(s)
print(f"C03DEV_UI_TRANSFORM=PASS source_sha256={sha(out)}")
