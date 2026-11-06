/* LOCAL PC LAB ONLY. Supplies an 800x480 memory framebuffer, no device access. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/syscall.h>
#include <sys/ioctl.h>
#include <linux/fb.h>

static int framebuffer_fd(int fd) {
    char path[64], target[256];
    snprintf(path, sizeof(path), "/proc/self/fd/%d", fd);
    ssize_t n = readlink(path, target, sizeof(target)-1);
    if (n < 0) return 0;
    target[n] = 0;
    return strcmp(target, "/dev/fb0") == 0;
}

int ioctl(int fd, int request, ...) {
    va_list ap; va_start(ap, request); void *arg = va_arg(ap, void *); va_end(ap);
    static int (*real_ioctl)(int, int, ...);
    if (!real_ioctl) real_ioctl = dlsym(RTLD_NEXT, "ioctl");
    if (!framebuffer_fd(fd)) return real_ioctl(fd, request, arg);
    if (request == FBIOGET_VSCREENINFO) {
        struct fb_var_screeninfo *v = arg;
        memset(v, 0, sizeof(*v));
        v->xres = v->xres_virtual = 800; v->yres = v->yres_virtual = 480;
        v->bits_per_pixel = 32; v->width = 154; v->height = 87;
        v->red.offset = 16; v->red.length = 8;
        v->green.offset = 8; v->green.length = 8;
        v->blue.offset = 0; v->blue.length = 8;
        v->transp.offset = 24; v->transp.length = 8;
        return 0;
    }
    if (request == FBIOGET_FSCREENINFO) {
        struct fb_fix_screeninfo *f = arg;
        memset(f, 0, sizeof(*f));
        strcpy(f->id, "P401-PC-LAB");
        f->smem_start = 0x10000000; f->smem_len = 800*480*4;
        f->line_length = 800*4; f->type = FB_TYPE_PACKED_PIXELS;
        f->visual = FB_VISUAL_TRUECOLOR;
        return 0;
    }
    if (request == FBIOPUT_VSCREENINFO || request == FBIOPAN_DISPLAY || request == FBIOBLANK) return 0;
    return real_ioctl(fd, request, arg);
}

/* Avoid vendor recursive crash-reporting when a hardware dependency is absent. */
void abort(void) {
    const char msg[] = "PC LAB: native application aborted; stopping probe.\n";
    write(2, msg, sizeof(msg)-1);
    _exit(134);
}

/* Inject pointer events through Qt's own server on the GUI thread. */
/* The vendor glibc uses time32; modern musl headers redirect select to time64. */
struct vendor_timeval { long tv_sec, tv_usec; };
int vendor_select(int, void *, void *, void *, struct vendor_timeval *) __asm__("select");
int vendor_select(int nfds, void *rd, void *wr, void *ex, struct vendor_timeval *timeout) {
    static int (*real_select)(int, void *, void *, void *, struct vendor_timeval *);
    static void (*send_mouse)(const void *, int, int);
    static int input_fd = -1, injecting;
    if (!real_select) real_select = dlsym(RTLD_NEXT, "select");
    if (syscall(SYS_gettid) != getpid() || injecting) return real_select(nfds, rd, wr, ex, timeout);
    injecting = 1;
    if (!send_mouse) send_mouse = dlsym(RTLD_DEFAULT, "_ZN9QWSServer14sendMouseEventERK6QPointii");
    if (input_fd < 0) input_fd = open("/lab/control/input.bin", O_RDONLY | O_NONBLOCK);
    struct { int x, y, buttons; } event;
    if (send_mouse && input_fd >= 0 && read(input_fd, &event, sizeof(event)) == sizeof(event)) {
        if (event.x >= 0 && event.x < 800 && event.y >= 0 && event.y < 480 && (event.buttons == 0 || event.buttons == 1)) {
            int point[2] = {event.x, event.y};
            send_mouse(point, event.buttons, 0);
        }
    }
    injecting = 0;
    struct vendor_timeval tick = {0, 25000};
    if (timeout && timeout->tv_sec == 0 && timeout->tv_usec < tick.tv_usec) tick = *timeout;
    return real_select(nfds, rd, wr, ex, &tick);
}
