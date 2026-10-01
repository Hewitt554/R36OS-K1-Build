/* SPDX-License-Identifier: MIT
 * R36OS Native C03 one-shot initramfs /init.
 * Freestanding AArch64: no libc, no BusyBox, no dynamic loader.
 *
 * Safety:
 * - only accepts r36os.kernel_attempt=NATIVE_C03;
 * - discovers the exact R36STATE ext4 UUID rather than trusting device names;
 * - never formats/fscks/repartitions or writes boot media;
 * - enters only a pre-staged, candidate-bound native root under R36STATE;
 * - leaves the U-Boot one-shot consumed marker intact so the next power cycle
 *   returns to the legacy path automatically.
 */
typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef long i64;

#define AT_FDCWD (-100)
#define O_RDONLY 0
#define O_WRONLY 1
#define O_RDWR 2
#define O_CREAT 0100
#define O_TRUNC 01000
#define SEEK_SET 0
#define MS_NOATIME 1024
#define MS_BIND 4096
#define MS_MOVE 8192
#define SYS_dup3 24
#define SYS_mkdirat 34
#define SYS_mount 40
#define SYS_chdir 49
#define SYS_chroot 51
#define SYS_openat 56
#define SYS_close 57
#define SYS_lseek 62
#define SYS_read 63
#define SYS_write 64
#define SYS_sync 81
#define SYS_nanosleep 101
#define SYS_execve 221

struct timespec64 { i64 tv_sec; i64 tv_nsec; };

static inline long sc1(long n,long a){
    register long x8 __asm__("x8")=n; register long x0 __asm__("x0")=a;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x8):"memory"); return x0;
}
static inline long sc2(long n,long a,long b){
    register long x8 __asm__("x8")=n; register long x0 __asm__("x0")=a,x1 __asm__("x1")=b;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x8):"memory"); return x0;
}
static inline long sc3(long n,long a,long b,long c){
    register long x8 __asm__("x8")=n; register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x8):"memory"); return x0;
}
static inline long sc4(long n,long a,long b,long c,long d){
    register long x8 __asm__("x8")=n; register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c,x3 __asm__("x3")=d;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x8):"memory"); return x0;
}
static inline long sc5(long n,long a,long b,long c,long d,long e){
    register long x8 __asm__("x8")=n; register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c,x3 __asm__("x3")=d,x4 __asm__("x4")=e;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x8):"memory"); return x0;
}

static u64 slen(const char *s){u64 n=0; while(s && s[n]) n++; return n;}
static int streqn(const char*a,const char*b,u64 n){for(u64 i=0;i<n;i++) if(a[i]!=b[i]) return 0; return 1;}
static int streq(const char*a,const char*b){u64 i=0;while(a[i]&&b[i]&&a[i]==b[i])i++;return a[i]==b[i];}
static void copy(char*d,const char*s,u64 cap){u64 i=0;if(!cap)return;for(;i+1<cap&&s[i];i++)d[i]=s[i];d[i]=0;}
static long openf(const char*p,int f,int m){return sc4(SYS_openat,AT_FDCWD,(long)p,f,m);}
static long rd(int f,void*b,u64 n){return sc3(SYS_read,f,(long)b,(long)n);}
static long wr(int f,const void*b,u64 n){return sc3(SYS_write,f,(long)b,(long)n);}
static void cls(int f){sc1(SYS_close,f);}
static void mkdirp1(const char*p){sc3(SYS_mkdirat,AT_FDCWD,(long)p,0755);}
static void pause_ms(long ms){struct timespec64 ts;ts.tv_sec=0;ts.tv_nsec=ms*1000000L;sc2(SYS_nanosleep,(long)&ts,0);}
static void attach_console(void){
    int f=(int)openf("/dev/console",O_RDWR,0);
    if(f<0)return;
    if(f!=0)sc3(SYS_dup3,f,0,0);
    if(f!=1)sc3(SYS_dup3,f,1,0);
    if(f!=2)sc3(SYS_dup3,f,2,0);
    if(f>2)cls(f);
}
static void msg(const char*s){
    wr(1,s,slen(s));
    int f=(int)openf("/dev/kmsg",O_WRONLY,0);
    if(f>=0){wr(f,"<6>R36OS-NATIVE: ",18);wr(f,s,slen(s));cls(f);}
}
static void fail_forever(const char*s){
    msg("FAIL: ");msg(s);msg("\nPower-cycle to return to the untouched legacy boot path.\n");
    for(;;)pause_ms(1000);
}

static int hexv(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static int uuid_parse(const char*s,u8 out[16]){
    int oi=0,hi=-1;
    for(u64 i=0;s[i]&&oi<16;i++){
        if(s[i]=='-'||s[i]=='\''||s[i]=='"')continue;
        int v=hexv(s[i]);if(v<0)return 0;
        if(hi<0)hi=v;else{out[oi++]=(u8)((hi<<4)|v);hi=-1;}
    }
    return oi==16&&hi<0;
}
static int uuid_equal(const u8*a,const u8*b){for(int i=0;i<16;i++)if(a[i]!=b[i])return 0;return 1;}
static const char *EXPECTED_STATE_UUID="a25488c6-742d-4555-82d1-e28ffc848af3";
static const char *EXPECTED_KREL="6.12.94-r36os-k1";
static const char *EXPECTED_K1_CID="9d7bd2334f315d98b482f850";

static int cmdline_value(const char*key,char*out,u64 cap){
    char b[2048];int f=(int)openf("/proc/cmdline",O_RDONLY,0);if(f<0)return 0;
    long n=rd(f,b,sizeof(b)-1);cls(f);if(n<=0)return 0;b[n]=0;
    u64 klen=slen(key);
    for(long i=0;i<=n-(long)klen;i++){
        if((i==0||b[i-1]==' ')&&streqn(&b[i],key,klen)){
            i+=(long)klen;u64 o=0;
            while(i<n&&b[i]!=' '&&o+1<cap){if(b[i]!='\''&&b[i]!='"')out[o++]=b[i];i++;}
            out[o]=0;return o>0;
        }
    }
    return 0;
}
static int valid_candidate_id(const char*s){
    if(slen(s)!=24)return 0;
    for(int i=0;i<24;i++){char c=s[i];if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return 0;}
    return 1;
}
static int valid_sha256(const char*s){
    if(slen(s)!=64)return 0;
    for(int i=0;i<64;i++){char c=s[i];if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return 0;}
    return 1;
}
static int ext4_uuid_matches(const char*dev,const u8 expected[16]){
    u8 sb[2048];int f=(int)openf(dev,O_RDONLY,0);if(f<0)return 0;
    if(sc3(SYS_lseek,f,1024,SEEK_SET)<0){cls(f);return 0;}
    long n=rd(f,sb,sizeof(sb));cls(f);if(n<0x78)return 0;
    if(sb[0x38]!=0x53||sb[0x39]!=0xEF)return 0;
    return uuid_equal(&sb[0x68],expected);
}
static int find_state(char*out,u64 cap,const u8 expected[16]){
    static const char *devs[]={
        "/dev/mmcblk0p1","/dev/mmcblk0p2","/dev/mmcblk0p3","/dev/mmcblk0p4",
        "/dev/mmcblk0p5","/dev/mmcblk0p6","/dev/mmcblk0p7","/dev/mmcblk0p8",
        "/dev/mmcblk1p1","/dev/mmcblk1p2","/dev/mmcblk1p3","/dev/mmcblk1p4",0};
    for(int round=0;round<160;round++){
        for(int i=0;devs[i];i++)if(ext4_uuid_matches(devs[i],expected)){copy(out,devs[i],cap);return 1;}
        pause_ms(100);
    }
    return 0;
}

static int read_key(const char*path,const char*key,char*out,u64 cap){
    char b[4096];int f=(int)openf(path,O_RDONLY,0);if(f<0)return 0;
    long n=rd(f,b,sizeof(b)-1);cls(f);if(n<=0)return 0;b[n]=0;
    u64 klen=slen(key);
    for(long i=0;i<n;i++){
        if((i==0||b[i-1]=='\n')&&i+(long)klen<n&&streqn(&b[i],key,klen)&&b[i+(long)klen]=='='){
            i+=(long)klen+1;u64 o=0;
            while(i<n&&b[i]!='\n'&&b[i]!='\r'&&o+1<cap)out[o++]=b[i++];
            out[o]=0;return o>0;
        }
    }
    return 0;
}
static int exists_readable(const char*path){int f=(int)openf(path,O_RDONLY,0);if(f<0)return 0;cls(f);return 1;}
static void write_early_marker(const char*state_dev,const char*nid){
    mkdirp1("/state/logs");mkdirp1("/state/logs/native-boot");
    int f=(int)openf("/state/logs/native-boot/C03_EARLY.conf",O_WRONLY|O_CREAT|O_TRUNC,0644);
    if(f<0)return;
    const char*a="format=R36OS_NATIVE_C03_EARLY_V1\nstatus=SWITCH_ROOT_READY\nnative_candidate=";
    wr(f,a,slen(a));wr(f,nid,slen(nid));
    wr(f,"\nstate_device=",14);wr(f,state_dev,slen(state_dev));
    wr(f,"\nstate_uuid=",12);wr(f,EXPECTED_STATE_UUID,slen(EXPECTED_STATE_UUID));
    wr(f,"\nkernel_release=",16);wr(f,EXPECTED_KREL,slen(EXPECTED_KREL));
    wr(f,"\nk1_candidate=",14);wr(f,EXPECTED_K1_CID,slen(EXPECTED_K1_CID));
    wr(f,"\nlegacy_boot_untouched=yes\n",27);cls(f);sc1(SYS_sync,0);
}

int k1_main(void){
    mkdirp1("/dev");mkdirp1("/proc");mkdirp1("/sys");mkdirp1("/state");mkdirp1("/newroot");
    if(sc5(SYS_mount,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",0,(long)"mode=0755")<0)fail_forever("mount devtmpfs failed");
    attach_console();
    if(sc5(SYS_mount,(long)"proc",(long)"/proc",(long)"proc",0,0)<0)fail_forever("mount proc failed");
    if(sc5(SYS_mount,(long)"sysfs",(long)"/sys",(long)"sysfs",0,0)<0)fail_forever("mount sysfs failed");
    msg("stage=native-initramfs-start\n");

    char slot[16],attempt[32],kcid[32],nid[32],state_uuid[64],rootfs_sha[80];
    if(!cmdline_value("r36os.kernel_slot=",slot,sizeof(slot))||!streq(slot,"next"))fail_forever("missing r36os.kernel_slot=next");
    if(!cmdline_value("r36os.kernel_attempt=",attempt,sizeof(attempt))||!streq(attempt,"NATIVE_C03"))fail_forever("missing r36os.kernel_attempt=NATIVE_C03");
    if(!cmdline_value("r36os.kernel_candidate=",kcid,sizeof(kcid))||!streq(kcid,EXPECTED_K1_CID))fail_forever("wrong K1 candidate identity");
    if(!cmdline_value("r36os.native_candidate=",nid,sizeof(nid))||!valid_candidate_id(nid))fail_forever("invalid native candidate identity");
    if(!cmdline_value("r36os.native_state_uuid=",state_uuid,sizeof(state_uuid))||!streq(state_uuid,EXPECTED_STATE_UUID))fail_forever("wrong R36STATE identity");
    if(!cmdline_value("r36os.native_rootfs_sha=",rootfs_sha,sizeof(rootfs_sha))||!valid_sha256(rootfs_sha))fail_forever("invalid native rootfs SHA identity");

    u8 want[16];if(!uuid_parse(EXPECTED_STATE_UUID,want))fail_forever("compiled R36STATE UUID invalid");
    char statedev[64];msg("stage=state-discovery\n");
    if(!find_state(statedev,sizeof(statedev),want))fail_forever("R36STATE ext4 UUID not found");
    if(sc5(SYS_mount,(long)statedev,(long)"/state",(long)"ext4",MS_NOATIME,(long)"errors=remount-ro")<0)fail_forever("mount R36STATE failed");
    msg("stage=state-mounted\n");

    char staged_nid[32],staged_krel[64],staged_kcid[32],staged_rootfs_sha[80],root_nid[32];
    if(!read_key("/state/r36os-next/C03_READY.conf","native_candidate",staged_nid,sizeof(staged_nid))||!streq(staged_nid,nid))fail_forever("staged native candidate mismatch");
    if(!read_key("/state/r36os-next/C03_READY.conf","kernel_release",staged_krel,sizeof(staged_krel))||!streq(staged_krel,EXPECTED_KREL))fail_forever("staged kernel release mismatch");
    if(!read_key("/state/r36os-next/C03_READY.conf","k1_candidate",staged_kcid,sizeof(staged_kcid))||!streq(staged_kcid,EXPECTED_K1_CID))fail_forever("staged K1 candidate mismatch");
    if(!read_key("/state/r36os-next/C03_READY.conf","rootfs_sha256",staged_rootfs_sha,sizeof(staged_rootfs_sha))||!streq(staged_rootfs_sha,rootfs_sha))fail_forever("staged rootfs SHA mismatch");
    if(!read_key("/state/r36os-next/rootfs/etc/r36os-native-c03.conf","native_candidate",root_nid,sizeof(root_nid))||!streq(root_nid,nid))fail_forever("native root candidate mismatch");
    if(!exists_readable("/state/r36os-next/rootfs/sbin/init"))fail_forever("native /sbin/init missing");
    if(!exists_readable("/state/r36os-next/rootfs/etc/r36os-release"))fail_forever("native release identity missing");
    if(!exists_readable("/state/kernel-next/modules/6.12.94-r36os-k1/modules.dep"))fail_forever("K1 module tree missing from R36STATE");

    if(sc5(SYS_mount,(long)"/state/r36os-next/rootfs",(long)"/newroot",0,MS_BIND,0)<0)fail_forever("bind native root failed");
    mkdirp1("/newroot/r36state");mkdirp1("/newroot/dev");mkdirp1("/newroot/proc");mkdirp1("/newroot/sys");
    mkdirp1("/newroot/usr/lib/modules/6.12.94-r36os-k1");
    if(sc5(SYS_mount,(long)"/state",(long)"/newroot/r36state",0,MS_BIND,0)<0)fail_forever("bind R36STATE into native root failed");
    if(sc5(SYS_mount,(long)"/state/kernel-next/modules/6.12.94-r36os-k1",(long)"/newroot/usr/lib/modules/6.12.94-r36os-k1",0,MS_BIND,0)<0)fail_forever("bind K1 modules into native root failed");

    write_early_marker(statedev,nid);
    msg("stage=native-root-ready\n");

    if(sc5(SYS_mount,(long)"/dev",(long)"/newroot/dev",0,MS_MOVE,0)<0)fail_forever("move /dev failed");
    if(sc5(SYS_mount,(long)"/proc",(long)"/newroot/proc",0,MS_MOVE,0)<0)fail_forever("move /proc failed");
    if(sc5(SYS_mount,(long)"/sys",(long)"/newroot/sys",0,MS_MOVE,0)<0)fail_forever("move /sys failed");
    if(sc1(SYS_chdir,(long)"/newroot")<0)fail_forever("chdir native root failed");
    if(sc5(SYS_mount,(long)".",(long)"/",0,MS_MOVE,0)<0)fail_forever("switch_root mount move failed");
    if(sc1(SYS_chroot,(long)".")<0)fail_forever("switch_root chroot failed");
    if(sc1(SYS_chdir,(long)"/")<0)fail_forever("chdir after switch_root failed");
    msg("stage=exec-native-systemd\n");
    char *argv[]={(char*)"/sbin/init",0};
    char *envp[]={(char*)"PATH=/usr/sbin:/usr/bin:/sbin:/bin",(char*)"R36OS_NATIVE_C03=1",0};
    sc3(SYS_execve,(long)argv[0],(long)argv,(long)envp);
    fail_forever("exec native /sbin/init failed");
    return 111;
}
