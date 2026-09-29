typedef unsigned long u64;
#define SYS_WRITE 64
#define SYS_EXECVE 221
#define SYS_EXIT 93
static long sc3(long n,long a,long b,long c){register long x8 __asm__("x8")=n;register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;__asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x8):"memory");return x0;}
static u64 slen(const char*s){u64 n=0;while(s[n])n++;return n;}
static void out(const char*s){sc3(SYS_WRITE,1,(long)s,slen(s));}
static long ex(const char*p,char**envp){char*av[2];av[0]=(char*)p;av[1]=0;return sc3(SYS_EXECVE,(long)p,(long)av,(long)envp);}
int start_c(u64*sp){
  int argc=(int)sp[0];char**argv=(char**)&sp[1];char**envp=argv+argc+1;
  const char*paths[]={"/lib/systemd/systemd","/usr/lib/systemd/systemd","/bin/systemd","/usr/bin/systemd","/usr/sbin/init","/bin/init",0};
  out("\nR36OS-K1 userspace handoff\n");
  for(int i=0;paths[i];i++){
    out("R36OS-K1 handoff: trying ");out(paths[i]);out("\n");
    long r=ex(paths[i],envp);
    (void)r;
    out("R36OS-K1 handoff: not usable, trying next\n");
  }
  out("FAIL: no usable systemd/init executable found in R36OS root\n");
  out("Power-cycle to return to untouched legacy 4.4 boot.\n");
  for(;;)__asm__ volatile("wfe");
  return 111;
}
