#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define CID "4c70486f70ba16acf7437403"
#define LOGDIR "/r36state/logs/kernel-next"
#define RUNLOG "/run/r36os-k1-input-compat.status"
#define READY "/run/r36os-k1-input-compat.ready"
#define MAXEV 32
#define BITS_PER_LONG (sizeof(unsigned long)*8)
#define NBITS(x) ((((x)-1)/BITS_PER_LONG)+1)
#define TESTBIT(a,b) (((a)[(b)/BITS_PER_LONG] >> ((b)%BITS_PER_LONG)) & 1UL)

static volatile sig_atomic_t stop_flag;
static FILE *logf;
static void sigstop(int s){(void)s;stop_flag=1;}
static void logline(const char *fmt,...){
  va_list ap; va_start(ap,fmt); if(logf){vfprintf(logf,fmt,ap);fputc('\n',logf);fflush(logf);} va_end(ap);
}
static int get_name(int fd,char *buf,size_t n){memset(buf,0,n);return ioctl(fd,EVIOCGNAME((int)n),buf)>=0?0:-1;}
static int get_bits(int fd,int ev,unsigned long *bits,size_t bytes){memset(bits,0,bytes);return ioctl(fd,EVIOCGBIT(ev,(int)bytes),bits)>=0?0:-1;}
static int open_event(int i,int flags,char *path,size_t n){snprintf(path,n,"/dev/input/event%d",i);return open(path,flags|O_NONBLOCK|O_CLOEXEC);}
static int named_old_gamepad(const char *n){return strstr(n,"GO-Super")||strstr(n,"Gamepad")||strstr(n,"gamepad")||strstr(n,"odroid");}
static int count_face(unsigned long *key){int c=0; int v[]={BTN_SOUTH,BTN_EAST,BTN_NORTH,BTN_WEST}; for(unsigned i=0;i<4;i++)c+=TESTBIT(key,v[i])?1:0; return c;}
static int axis_candidate(int fd){
  unsigned long ev[NBITS(EV_MAX+1)], ab[NBITS(ABS_MAX+1)];
  if(get_bits(fd,0,ev,sizeof(ev))<0||!TESTBIT(ev,EV_ABS))return 0;
  if(get_bits(fd,EV_ABS,ab,sizeof(ab))<0)return 0;
  return TESTBIT(ab,ABS_X)&&TESTBIT(ab,ABS_Y);
}
static int key_candidate(int fd){
  unsigned long ev[NBITS(EV_MAX+1)], key[NBITS(KEY_MAX+1)];
  if(get_bits(fd,0,ev,sizeof(ev))<0||!TESTBIT(ev,EV_KEY))return 0;
  if(get_bits(fd,EV_KEY,key,sizeof(key))<0)return 0;
  int dpad=TESTBIT(key,BTN_DPAD_UP)+TESTBIT(key,BTN_DPAD_DOWN)+TESTBIT(key,BTN_DPAD_LEFT)+TESTBIT(key,BTN_DPAD_RIGHT);
  return count_face(key)>=2 && dpad>=2;
}
static int has_ci(const char *s,const char *needle){
  size_t n=strlen(needle); if(!n)return 1; for(;*s;s++){size_t i=0;while(i<n&&s[i]){char a=s[i],b=needle[i];if(a>='A'&&a<='Z')a+=32;if(b>='A'&&b<='Z')b+=32;if(a!=b)break;i++;}if(i==n)return 1;}return 0;
}
static int axis_score(int fd,const char *name){if(!axis_candidate(fd))return 0;return (has_ci(name,"adc")||has_ci(name,"joy"))?20:1;}
static int key_score(int fd,const char *name){if(!key_candidate(fd))return 0;return (has_ci(name,"gpio")||has_ci(name,"key"))?20:1;}
static int copy_keys(int src,int ui){
  unsigned long key[NBITS(KEY_MAX+1)]; if(get_bits(src,EV_KEY,key,sizeof(key))<0)return -1;
  if(ioctl(ui,UI_SET_EVBIT,EV_KEY)<0)return -1;
  for(int c=0;c<=KEY_MAX;c++) if(TESTBIT(key,c)) ioctl(ui,UI_SET_KEYBIT,c);
  return 0;
}
static int copy_abs(int src,int ui){
  unsigned long ab[NBITS(ABS_MAX+1)]; if(get_bits(src,EV_ABS,ab,sizeof(ab))<0)return -1;
  if(ioctl(ui,UI_SET_EVBIT,EV_ABS)<0)return -1;
  for(int c=0;c<=ABS_MAX;c++) if(TESTBIT(ab,c)){
    struct input_absinfo ai; if(ioctl(src,EVIOCGABS(c),&ai)<0)continue;
    ioctl(ui,UI_SET_ABSBIT,c);
    struct uinput_abs_setup as; memset(&as,0,sizeof(as)); as.code=(uint16_t)c; as.absinfo=ai;
    if(ioctl(ui,UI_ABS_SETUP,&as)<0){ logline("abs_setup_fail code=%d errno=%d",c,errno); return -1; }
  }
  return 0;
}
static void write_status(const char *status,const char *detail,const char *axis_name,const char *key_name){
  FILE *f=fopen(RUNLOG,"w"); if(!f)return;
  fprintf(f,"format=R36OS_K1_INPUT_COMPAT_V1\nstatus=%s\ndetail=%s\ncandidate_id=%s\naxis_name=%s\nkey_name=%s\npid=%ld\n",status,detail,CID,axis_name?axis_name:"",key_name?key_name:"",(long)getpid()); fclose(f);
}
static void mark_ready(const char *detail){FILE *f=fopen(READY,"w");if(f){fprintf(f,"%s\n",detail);fclose(f);}}
static int mirror_loop(int a,int k,int ui){
  int same=(a==k);
  struct pollfd p[2]={{.fd=a,.events=POLLIN},{.fd=k,.events=POLLIN}};
  int np=same?1:2;
  while(!stop_flag){int r=poll(p,np,500);if(r<0){if(errno==EINTR)continue;return 2;}for(int i=0;i<np;i++)if(p[i].revents&POLLIN){struct input_event ev[32];ssize_t n=read(p[i].fd,ev,sizeof(ev));if(n<=0)continue;ssize_t cnt=n/(ssize_t)sizeof(ev[0]);for(ssize_t q=0;q<cnt;q++){if(ev[q].type==EV_SYN||ev[q].type==EV_KEY||ev[q].type==EV_ABS)write(ui,&ev[q],sizeof(ev[q]));}}}
  return 0;
}
int main(int argc,char **argv){
  if(argc>1 && strcmp(argv[1],"--selftest")==0){
    if(BTN_SOUTH!=304||BTN_EAST!=305||BTN_NORTH!=307||BTN_WEST!=308||
       BTN_DPAD_UP!=544||BTN_DPAD_DOWN!=545||BTN_DPAD_LEFT!=546||BTN_DPAD_RIGHT!=547||
       ABS_X!=0||ABS_Y!=1||ABS_RX!=3||ABS_RY!=4){
      fprintf(stderr,"R57_INPUT_COMPAT_SELFTEST=FAIL linux-input-code-mismatch\n");
      return 90;
    }
    printf("R57_INPUT_COMPAT_SELFTEST=PASS\n");
    return 0;
  }
  signal(SIGTERM,sigstop);signal(SIGINT,sigstop);signal(SIGHUP,sigstop);
  mkdir(LOGDIR,0755); char lp[256];snprintf(lp,sizeof(lp),LOGDIR "/K1-INPUT-COMPAT-%s.conf",CID); logf=fopen(lp,"w");
  logline("format=R36OS_K1_INPUT_COMPAT_LOG_V1");logline("candidate_id=%s",CID);unlink(READY);
  int axis=-1,key=-1;char an[128]="",kn[128]="",path[64],name[128];
  for(int attempt=0;attempt<80&&!stop_flag;attempt++){
    int best_a=0,best_k=0;axis=key=-1;an[0]=kn[0]=0;
    for(int i=0;i<MAXEV;i++){
      int fd=open_event(i,O_RDONLY,path,sizeof(path));if(fd<0)continue;get_name(fd,name,sizeof(name));
      int as=axis_score(fd,name), ks=key_score(fd,name), both=as&&ks;
      logline("scan attempt=%d event=%d name=%s axis_score=%d key_score=%d combined=%d",attempt,i,name,as,ks,both);
      if(both && named_old_gamepad(name)){
        write_status("PASS","existing-combined-gamepad",name,name);mark_ready("existing-combined-gamepad");close(fd);if(logf)fclose(logf);return 0;
      }
      if(as>best_a){best_a=as;axis=i;snprintf(an,sizeof(an),"%s",name);}
      if(ks>best_k){best_k=ks;key=i;snprintf(kn,sizeof(kn),"%s",name);}
      close(fd);
    }
    if(axis>=0&&key>=0)break;
    usleep(100000);
  }
  if(axis<0||key<0){logline("result=no-compatible-sources axis=%d key=%d",axis,key);write_status("FAIL","no-compatible-sources",an,kn);if(logf)fclose(logf);return 2;}
  char ap[64],kp[64];int same_source=(axis==key);int afd=open_event(axis,O_RDONLY,ap,sizeof(ap));int kfd=same_source?afd:open_event(key,O_RDONLY,kp,sizeof(kp));
  if(afd<0||kfd<0){if(afd>=0)close(afd);write_status("FAIL","source-open-failed",an,kn);return 3;}
  if(same_source)logline("source_mode=combined event=%d name=%s",axis,an);else logline("source_mode=split axis_event=%d key_event=%d",axis,key);
  int ui=open("/dev/uinput",O_WRONLY|O_NONBLOCK|O_CLOEXEC); if(ui<0)ui=open("/dev/input/uinput",O_WRONLY|O_NONBLOCK|O_CLOEXEC); if(ui<0){logline("uinput_open_fail errno=%d",errno);write_status("FAIL","uinput-open-failed",an,kn);return 4;}
  ioctl(ui,UI_SET_EVBIT,EV_SYN); if(copy_keys(kfd,ui)<0||copy_abs(afd,ui)<0){write_status("FAIL","uinput-capability-copy-failed",an,kn);return 5;}
  struct uinput_setup us;memset(&us,0,sizeof(us));snprintf(us.name,UINPUT_MAX_NAME_SIZE,"R36OS K1 Gamepad");us.id.bustype=BUS_VIRTUAL;us.id.vendor=0x5233;us.id.product=0x3601;us.id.version=1;
  if(ioctl(ui,UI_DEV_SETUP,&us)<0||ioctl(ui,UI_DEV_CREATE)<0){logline("uinput_create_fail errno=%d",errno);write_status("FAIL","uinput-create-failed",an,kn);return 6;}
  int visible=0;
  for(int w=0;w<40&&!visible;w++){
    for(int i=0;i<MAXEV;i++){char vp[64],vn[128]="";int vfd=open_event(i,O_RDONLY,vp,sizeof(vp));if(vfd<0)continue;get_name(vfd,vn,sizeof(vn));close(vfd);if(strstr(vn,"R36OS K1 Gamepad")){visible=1;break;}}
    if(!visible)usleep(50000);
  }
  logline("result=bridge-ready virtual_event_visible=%d axis_event=%d axis_name=%s key_event=%d key_name=%s",visible,axis,an,key,kn);
  write_status(visible?"PASS":"WARN",visible?"bridge-ready":"bridge-created-event-node-not-yet-visible",an,kn);mark_ready(visible?"bridge-ready":"bridge-created");
  int rc=mirror_loop(afd,kfd,ui);ioctl(ui,UI_DEV_DESTROY);close(ui);close(afd);if(!same_source)close(kfd);if(logf)fclose(logf);unlink(READY);return rc;
}
