#define _POSIX_C_SOURCE 200809L
/* CP17 read-only hardware *disk* diagnostic. Paints framebuffer VRAM only.
 * This is optional: missing /dev/fb0 is reported but never treated as a pass.
 * No block device is ever opened. No persistent logs are written.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

/* Minimal 5x7 glyphs; only the text used on the framebuffer is included. */
static const struct { char c; unsigned char row[7]; } FONT[] = {
 {' ',{0,0,0,0,0,0,0}}, {'0',{14,17,19,21,25,17,14}},
 {'1',{4,12,4,4,4,4,14}}, {'2',{14,17,1,2,4,8,31}},
 {'3',{30,1,1,14,1,1,30}}, {'4',{2,6,10,18,31,2,2}},
 {'5',{31,16,30,1,1,17,14}}, {'6',{6,8,16,30,17,17,14}},
 {'7',{31,1,2,4,8,8,8}}, {'8',{14,17,17,14,17,17,14}},
 {'9',{14,17,17,15,1,2,12}},
 {'A',{14,17,17,31,17,17,17}}, {'B',{30,17,17,30,17,17,30}},
 {'C',{14,17,16,16,16,17,14}}, {'D',{30,17,17,17,17,17,30}},
 {'E',{31,16,16,30,16,16,31}}, {'F',{31,16,16,30,16,16,16}},
 {'G',{14,17,16,23,17,17,14}}, {'H',{17,17,17,31,17,17,17}},
 {'I',{14,4,4,4,4,4,14}}, {'J',{7,2,2,2,18,18,12}},
 {'K',{17,18,20,24,20,18,17}}, {'L',{16,16,16,16,16,16,31}},
 {'M',{17,27,21,21,17,17,17}}, {'N',{17,25,21,19,17,17,17}},
 {'O',{14,17,17,17,17,17,14}}, {'P',{30,17,17,30,16,16,16}},
 {'Q',{14,17,17,17,21,18,13}}, {'R',{30,17,17,30,20,18,17}},
 {'S',{15,16,16,14,1,1,30}}, {'T',{31,4,4,4,4,4,4}},
 {'U',{17,17,17,17,17,17,14}}, {'V',{17,17,17,17,17,10,4}},
 {'W',{17,17,17,21,21,21,10}}, {'X',{17,17,10,4,10,17,17}},
 {'Y',{17,17,10,4,4,4,4}}, {'Z',{31,1,2,4,8,16,31}},
 {'-',{0,0,0,31,0,0,0}}, {':',{0,4,4,0,4,4,0}},
 {'/',{1,2,2,4,8,8,16}}, {'.',{0,0,0,0,0,12,12}}
};

static uint32_t scaled_channel(unsigned val, const struct fb_bitfield *bit) {
    if (bit->length == 0) return 0;
    if (bit->length > 8 || bit->offset > 31 || bit->offset + bit->length > 32) return UINT32_MAX;
    unsigned max = (1U << bit->length) - 1;
    return ((val * max + 127U) / 255U) << bit->offset;
}
static uint32_t pack_color(const struct fb_var_screeninfo *v, unsigned r,unsigned g,unsigned b) {
    uint32_t a=scaled_channel(r,&v->red),c=scaled_channel(g,&v->green),d=scaled_channel(b,&v->blue);
    if (a == UINT32_MAX || c == UINT32_MAX || d == UINT32_MAX) return 0;
    return a|c|d;
}
static void dot(uint8_t *map, size_t length, const struct fb_fix_screeninfo *f,
                const struct fb_var_screeninfo *v, unsigned x,unsigned y,
                unsigned r,unsigned g,unsigned b) {
    if (x>=v->xres || y>=v->yres) return;
    const unsigned bytes=v->bits_per_pixel / 8;
    size_t yy=(size_t)y+v->yoffset, xx=(size_t)x+v->xoffset;
    if (xx > SIZE_MAX/bytes || yy > SIZE_MAX/f->line_length) return;
    size_t ofs=yy*f->line_length+xx*bytes;
    if (ofs>length || bytes>length-ofs) return;
    uint32_t color=pack_color(v,r,g,b);
    for(unsigned i=0;i<bytes;i++) map[ofs+i]=(uint8_t)(color>>(8*i));
}
static void glyph(uint8_t *map,size_t len,const struct fb_fix_screeninfo *f,
                  const struct fb_var_screeninfo *v,unsigned x,unsigned y,char letter,
                  unsigned scale) {
    const unsigned char *g=FONT[0].row;
    for(size_t i=0;i<sizeof(FONT)/sizeof(FONT[0]);i++) if (FONT[i].c==letter){g=FONT[i].row;break;}
    for(unsigned row=0;row<7;row++) for(unsigned col=0;col<5;col++) if(g[row]&(16>>col))
        for(unsigned sy=0;sy<scale;sy++) for(unsigned sx=0;sx<scale;sx++)
            dot(map,len,f,v,x+col*scale+sx,y+row*scale+sy,255,255,255);
}
static void title(uint8_t *map,size_t len,const struct fb_fix_screeninfo *f,
                  const struct fb_var_screeninfo *v,unsigned y,const char *t,unsigned scale) {
    unsigned width=(unsigned)strlen(t)*6*scale;
    unsigned x=width<v->xres?(v->xres-width)/2:4;
    for(;*t;t++,x+=6*scale) glyph(map,len,f,v,x,y,*t,scale);
}
int main(void) {
    int fd=open("/dev/fb0",O_RDWR|O_CLOEXEC);
    if(fd<0){perror("CP17 framebuffer open");return 2;}
    struct fb_var_screeninfo v;
    struct fb_fix_screeninfo f;
    if(ioctl(fd,FBIOGET_VSCREENINFO,&v)<0 || ioctl(fd,FBIOGET_FSCREENINFO,&f)<0) {
        perror("CP17 framebuffer geometry"); close(fd);return 3;
    }
    printf("CP17 framebuffer: %ux%u bpp=%u stride=%u\n",v.xres,v.yres,v.bits_per_pixel,f.line_length);
    if (v.xres<160 || v.yres<120 || v.xres>4096 || v.yres>2160 ||
        (v.bits_per_pixel!=16 && v.bits_per_pixel!=32) ||
        v.red.msb_right || v.green.msb_right || v.blue.msb_right ||
        f.line_length==0 || f.smem_len==0 || f.smem_len>64*1024*1024) {
        fprintf(stderr,"CP17 framebuffer unsupported geometry; no writes attempted\n");close(fd);return 4;
    }
    const unsigned bytes=v.bits_per_pixel/8;
    if ((size_t)(v.xoffset+v.xres)*bytes>f.line_length ||
        (size_t)(v.yoffset+v.yres) > f.smem_len/f.line_length) {
        fprintf(stderr,"CP17 framebuffer offsets invalid\n"); close(fd);return 5;
    }
    void *ptr=mmap(NULL,f.smem_len,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if(ptr==MAP_FAILED){perror("CP17 framebuffer mmap");close(fd);return 6;}
    uint8_t *p=ptr;
    const unsigned xres=v.xres,yres=v.yres;
    /* Seven coloured vertical bars make correct channel mapping visible. */
    const unsigned char bars[7][3]={{255,255,255},{255,255,0},{0,255,255},{0,255,0},
                                    {255,0,255},{255,0,0},{0,0,255}};
    for(unsigned y=0;y<yres;y++) for(unsigned x=0;x<xres;x++) {
        unsigned band=(x*7U)/xres;if(band>6)band=6;
        unsigned r=bars[band][0],g=bars[band][1],b=bars[band][2];
        if(y<yres/6 || y>yres*5/6){r/=5;g/=5;b/=5;}
        dot(p,f.smem_len,&f,&v,x,y,r,g,b);
    }
    unsigned scale=(xres>=600 && yres>=400)?3:2;
    title(p,f.smem_len,&f,&v,yres/16,"R36OS CP17",scale);
    title(p,f.smem_len,&f,&v,yres*6/7,"DISPLAY TEST",scale);
    if(msync(ptr,f.smem_len,MS_SYNC)<0) fprintf(stderr,"CP17 framebuffer flush unknown\n");
    munmap(ptr,f.smem_len);close(fd);
    printf("CP17 FB_PATTERN_SENT: human must verify colours/orientation; not proof of Panel4\n");
    return 0;
}