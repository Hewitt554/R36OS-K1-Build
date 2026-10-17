/* R36OS Alpha 6 CP15 - tiny read-only ext4 identity probe.
 * Exit 0: matching UUID, ext4 extents and R36SYS label.
 * Exit 1: different UUID/device. Exit 3: UUID matches but unsafe format/label.
 * Exit 2: bad invocation. Never writes files or device bytes.
 *
 * CI test-build -DCP15_ALLOW_REGULAR_FIXTURE permits temporary ext4 files.
 * Production binary permits /dev/mmcblkNpM block devices only.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static int is_valid_uuid(const char *s) {
    if (strlen(s) != 36) return 0;
    for (int i=0; i<36; ++i) {
        if (i==8 || i==13 || i==18 || i==23) { if (s[i]!='-') return 0; }
        else if (!((s[i]>='0'&&s[i]<='9') || (s[i]>='a'&&s[i]<='f'))) return 0;
    }
    return 1;
}
static void print_uuid(char out[37], const uint8_t u[16]) {
    static const char hex[]="0123456789abcdef";
    int k=0;
    for (int i=0;i<16;i++) {
        if (i==4 || i==6 || i==8 || i==10) out[k++]='-';
        out[k++]=hex[u[i]>>4];out[k++]=hex[u[i]&15];
    }
    out[36]='\0';
}
#ifndef CP15_ALLOW_REGULAR_FIXTURE
static int is_mmc_partition_path(const char *p) {
    if (strncmp(p,"/dev/mmcblk",11) != 0) return 0;
    p+=11;
    if (!(*p >= '0' && *p <= '9')) return 0;
    while (*p >= '0' && *p <= '9') p++;
    if (*p++ != 'p') return 0;
    if (!(*p >= '0' && *p <= '9')) return 0;
    while (*p >= '0' && *p <= '9') p++;
    return *p == '\0';
}
#endif
int main(int argc, char **argv) {
    if (argc != 3 || !is_valid_uuid(argv[2])) return 2;
#ifndef CP15_ALLOW_REGULAR_FIXTURE
    if (!is_mmc_partition_path(argv[1])) return 2;
#endif
    struct stat st;
    if (lstat(argv[1],&st) != 0 || S_ISLNK(st.st_mode)) return 1;
#ifdef CP15_ALLOW_REGULAR_FIXTURE
    if (!S_ISBLK(st.st_mode) && !S_ISREG(st.st_mode)) return 1;
#else
    if (!S_ISBLK(st.st_mode)) return 1;
#endif
    int fd=open(argv[1],O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    if (fd<0) return 1;
    uint8_t sb[1024];
    ssize_t size=pread(fd,sb,sizeof sb,1024);
    close(fd);
    if (size!=(ssize_t)sizeof(sb)) return 1;
    char uuid[37];
    print_uuid(uuid,sb+0x68);
    if (strcmp(uuid,argv[2]) != 0) return 1;
    /* Superblock offsets per Linux ext2/ext4 on-disk format. */
    if (sb[0x38]!=0x53 || sb[0x39]!=0xef) return 3;
    uint32_t incompat=(uint32_t)sb[0x60] | (uint32_t)sb[0x61]<<8 |
       (uint32_t)sb[0x62]<<16 | (uint32_t)sb[0x63]<<24;
    if (!(incompat&0x40)) return 3; /* EXTENTS feature required for ext4 */
    if (memcmp(sb+0x78,"R36SYS",6)!=0 || sb[0x78+6]!='\0') return 3;
    return 0;
}