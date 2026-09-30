from pathlib import Path
import hashlib,sys

if len(sys.argv)!=3:
    raise SystemExit("usage: transform_ui.py <r37-source.c> <patched.c>")

src=Path(sys.argv[1]); out=Path(sys.argv[2])
BASE_SHA="25e2de1b49b31033176e45f9106d4509d715c31371ac2dee1b95e6edbb6c71bd"
PATCHED_SHA="657803bb2b4f60414d85775f86dae8d01d3cb46d631cfe2309e682dffd93289a"
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(src)!=BASE_SHA:
    raise SystemExit(f"source sha mismatch: {sha(src)}")

s=src.read_text()

old='static int fbfd=-1,infd=-1,logfd=-1; static int primary_event_index=-1; static int auxfds[32]; static int aux_count=0; static int power_event_grabbed=0; static int power_event_fd=-1; static u8*fb=0; static usize fblen=0; static struct fb_var_screeninfo vi; static struct fb_fix_screeninfo fi;'
new='static int fbfd=-1,infd=-1,k1_axisfd=-1,logfd=-1; static int primary_event_index=-1; static int k1_axis_event_index=-1; static int k1_split_input=0; static int auxfds[32]; static int aux_count=0; static int power_event_grabbed=0; static int power_event_fd=-1; static u8*fb=0; static usize fblen=0; static struct fb_var_screeninfo vi; static struct fb_fix_screeninfo fi;'
if s.count(old)!=1: raise SystemExit("globals anchor mismatch")
s=s.replace(old,new,1)

old='static int find_input(){char name[128];for(int i=0;i<32;i++){char p[32]="/dev/input/event";char n[8];itoa10(i,n);scat(p,sizeof(p),n);int fd=openf(p,O_RDONLY|O_NONBLOCK,0);if(fd<0)continue;memzero(name,sizeof(name));u32 req=(2u<<30)|((u32)sizeof(name)<<16)|((u32)\'E\'<<8)|0x06;long r=sc3(SYS_ioctl,fd,req,(long)name);if(r>=0&&(contains(name,"GO-Super")||contains(name,"Gamepad")||contains(name,"gamepad")||contains(name,"odroid"))){primary_event_index=i;char m[180]="Primary gamepad event";char q[8];itoa10(i,q);scat(m,sizeof(m),q);scat(m,sizeof(m)," name=");scat(m,sizeof(m),name);logmsg(m);return fd;}sc1(SYS_close,fd);}return -1;}'
new='''static int find_input(){
  char name[128];
  /* Preserve the proven legacy 4.4 single-gamepad path exactly and prefer it. */
  for(int i=0;i<32;i++){
    char p[32]="/dev/input/event";char n[8];itoa10(i,n);scat(p,sizeof(p),n);
    int fd=openf(p,O_RDONLY|O_NONBLOCK,0);if(fd<0)continue;
    memzero(name,sizeof(name));u32 req=(2u<<30)|((u32)sizeof(name)<<16)|((u32)'E'<<8)|0x06;
    long r=sc3(SYS_ioctl,fd,req,(long)name);
    if(r>=0&&(contains(name,"GO-Super")||contains(name,"Gamepad")||contains(name,"gamepad")||contains(name,"odroid"))){
      primary_event_index=i;char m[180]="Primary gamepad event";char q[8];itoa10(i,q);scat(m,sizeof(m),q);scat(m,sizeof(m)," name=");scat(m,sizeof(m),name);logmsg(m);return fd;
    }
    sc1(SYS_close,fd);
  }

  /* K1 6.12 exposes controls as gpio-keys + adc-joystick. */
  int keyfd=-1,keyidx=-1,axisfd=-1,axisidx=-1;
  for(int i=0;i<32;i++){
    char p[32]="/dev/input/event";char n[8];itoa10(i,n);scat(p,sizeof(p),n);
    int fd=openf(p,O_RDONLY|O_NONBLOCK,0);if(fd<0)continue;
    memzero(name,sizeof(name));u32 req=(2u<<30)|((u32)sizeof(name)<<16)|((u32)'E'<<8)|0x06;
    long r=sc3(SYS_ioctl,fd,req,(long)name);
    if(r>=0&&contains(name,"gpio-keys")&&keyfd<0){keyfd=fd;keyidx=i;fd=-1;}
    else if(r>=0&&contains(name,"adc-joystick")&&axisfd<0){axisfd=fd;axisidx=i;fd=-1;}
    if(fd>=0)sc1(SYS_close,fd);
  }
  if(keyfd>=0){
    primary_event_index=keyidx;k1_split_input=1;k1_axisfd=axisfd;k1_axis_event_index=axisidx;
    char m[192]="K1 split input: gpio-keys event";char q[8];itoa10(keyidx,q);scat(m,sizeof(m),q);
    if(axisidx>=0){scat(m,sizeof(m)," + adc-joystick event");itoa10(axisidx,q);scat(m,sizeof(m),q);}else scat(m,sizeof(m),"; adc-joystick missing");
    logmsg(m);return keyfd;
  }
  if(axisfd>=0)sc1(SYS_close,axisfd);
  return -1;
}'''
if s.count(old)!=1: raise SystemExit("find_input anchor mismatch")
s=s.replace(old,new,1)

old='static void open_aux_inputs(){char name[128];aux_count=0;power_event_grabbed=0;power_event_fd=-1;for(int i=0;i<32&&aux_count<32;i++){if(i==primary_event_index)continue;char p[32]="/dev/input/event";char n[8];itoa10(i,n);scat(p,sizeof(p),n);int fd=openf(p,O_RDONLY|O_NONBLOCK,0);if(fd<0)continue;memzero(name,sizeof(name));u32 req=(2u<<30)|((u32)sizeof(name)<<16)|((u32)\'E\'<<8)|0x06;sc3(SYS_ioctl,fd,req,(long)name);if(contains(name,"rk8xx_pwrkey")){power_event_fd=fd;long gr=sc3(SYS_ioctl,fd,0x40044590,1);if(gr==0){power_event_grabbed=1;logmsg("Power input EVIOCGRAB acquired - logind can no longer consume KEY_POWER");}else{logmsg("WARN Power input EVIOCGRAB failed - suspend masks remain fallback");}}auxfds[aux_count++]=fd;char m[190]="Aux input event";char q[8];itoa10(i,q);scat(m,sizeof(m),q);scat(m,sizeof(m)," name=");scat(m,sizeof(m),name[0]?name:"unknown");logmsg(m);}lognum("aux_input_count",aux_count);lognum("power_event_grabbed",power_event_grabbed);}'
new='static void open_aux_inputs(){char name[128];aux_count=0;power_event_grabbed=0;power_event_fd=-1;for(int i=0;i<32&&aux_count<32;i++){if(i==primary_event_index||i==k1_axis_event_index)continue;char p[32]="/dev/input/event";char n[8];itoa10(i,n);scat(p,sizeof(p),n);int fd=openf(p,O_RDONLY|O_NONBLOCK,0);if(fd<0)continue;memzero(name,sizeof(name));u32 req=(2u<<30)|((u32)sizeof(name)<<16)|((u32)\'E\'<<8)|0x06;sc3(SYS_ioctl,fd,req,(long)name);if(contains(name,"rk8xx_pwrkey")){power_event_fd=fd;long gr=sc3(SYS_ioctl,fd,0x40044590,1);if(gr==0){power_event_grabbed=1;logmsg("Power input EVIOCGRAB acquired - logind can no longer consume KEY_POWER");}else{logmsg("WARN Power input EVIOCGRAB failed - suspend masks remain fallback");}}auxfds[aux_count++]=fd;char m[190]="Aux input event";char q[8];itoa10(i,q);scat(m,sizeof(m),q);scat(m,sizeof(m)," name=");scat(m,sizeof(m),name[0]?name:"unknown");logmsg(m);}lognum("aux_input_count",aux_count);lognum("power_event_grabbed",power_event_grabbed);}'
if s.count(old)!=1: raise SystemExit("aux anchor mismatch")
s=s.replace(old,new,1)

anchor='#define KEY_POWER 116\n'
insert='''#define KEY_POWER 116
static int map_k1_key_code(int code){
  if(!k1_split_input)return code;
  if(code==314)return KEY_SELECT;
  if(code==315)return KEY_START;
  if(code==317)return KEY_L3;
  if(code==318)return KEY_R3;
  if(code==316)return KEY_FN;
  return code;
}
'''
if s.count(anchor)!=1: raise SystemExit("key-map anchor mismatch")
s=s.replace(anchor,insert,1)

old='''    if(n==(long)sizeof(ev)){
      if(controller_test){ct_last_type=ev.type;ct_last_code=ev.code;ct_last_value=ev.value;if(ev.type==EV_KEY)ct_keys++;else if(ev.type==EV_ABS)ct_axes++;redraw();}
      else if(ev.type==EV_KEY){
        if(ev.value==1)handle_press(ev.code);
        else if(ev.value==0)handle_release(ev.code);
      }
    }
    for(int i=0;i<aux_count;i++){'''
new='''    if(n==(long)sizeof(ev)){
      if(ev.type==EV_KEY)ev.code=(u16)map_k1_key_code(ev.code);
      if(controller_test){ct_last_type=ev.type;ct_last_code=ev.code;ct_last_value=ev.value;if(ev.type==EV_KEY)ct_keys++;else if(ev.type==EV_ABS)ct_axes++;redraw();}
      else if(ev.type==EV_KEY){
        if(ev.value==1)handle_press(ev.code);
        else if(ev.value==0)handle_release(ev.code);
      }
    }
    if(k1_axisfd>=0){
      for(int k=0;k<8;k++){
        struct input_event ae;
        long an=sc3(SYS_read,k1_axisfd,(long)&ae,sizeof(ae));
        if(an!=(long)sizeof(ae))break;
        if(controller_test){ct_last_type=ae.type;ct_last_code=ae.code;ct_last_value=ae.value;if(ae.type==EV_KEY)ct_keys++;else if(ae.type==EV_ABS)ct_axes++;redraw();}
      }
    }
    for(int i=0;i<aux_count;i++){'''
if s.count(old)!=1: raise SystemExit("mainloop anchor mismatch")
s=s.replace(old,new,1)

old='if(infd>=0)sc1(SYS_close,infd);for(int i=0;i<aux_count;i++)'
new='if(infd>=0)sc1(SYS_close,infd);if(k1_axisfd>=0)sc1(SYS_close,k1_axisfd);for(int i=0;i<aux_count;i++)'
if s.count(old)!=1: raise SystemExit("close anchor mismatch")
s=s.replace(old,new,1)

out.write_text(s)
if sha(out)!=PATCHED_SHA:
    raise SystemExit(f"patched sha mismatch: {sha(out)}")
print(f"R58_UI_TRANSFORM=PASS sha256={PATCHED_SHA}")
