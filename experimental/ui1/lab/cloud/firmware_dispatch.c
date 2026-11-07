/* Test-only host dispatcher for QEMU child execs, without host binfmt changes.
 * The production runner is unchanged. Every verifier call executes the real
 * ARM verifier; MsnCoreApp remains at its original ABI-pinned path.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

static const char *leaf(const char *p) {
    const char *s = strrchr(p, '/');
    return s ? s + 1 : p;
}

int main(int argc, char **argv) {
    const char *command = leaf(argv[0]);
    int first = 1;
    if (!strcmp(command, "dispatch")) {
        if (argc < 2) return 64;
        command = argv[1]; first = 2;
    }
    char **args = calloc((size_t)argc + 12, sizeof(char *));
    if (!args) return 70;
    int n = 0;
    args[n++] = "/qemu-arm";
    args[n++] = "-cpu";
    args[n++] = "cortex-a7";
    char *preload = getenv("LD_PRELOAD");
    preload = preload ? strdup(preload) : NULL;
    unsetenv("LD_PRELOAD");
    if (!strcmp(command, "MsnCoreApp")) {
        int custom = preload && strstr(preload, "/libp401-ui.so");
        fprintf(stderr, "LAB_DISPATCH: %s real ARM MsnCoreApp\n", custom ? "custom" : "stock");
        fflush(stderr);
        if (custom) {
            char mode[32] = {0};
            FILE *f = fopen("/lab/control/dispatch-case.txt", "r");
            if (f) { (void)fgets(mode, sizeof(mode), f); fclose(f); }
            if (!strncmp(mode, "crash", 5)) return 139;
            if (!strncmp(mode, "timeout", 7)) for (;;) pause();
        }
        char *guest_preload = NULL;
        if (asprintf(&guest_preload, "LD_PRELOAD=%s%s%s/lab/libp401-pc-fb.so",
                     custom ? "/lab/libp401-test-probe.so:" : "",
                     custom ? preload : "", custom ? ":" : "") < 0) return 70;
        args[n++] = "-E";
        args[n++] = guest_preload;
        args[n++] = "/usr/bin/MsnCoreApp";
    } else if (!strcmp(command, "verify")) {
        FILE *f = fopen("/lab/control/verify-calls.txt", "a");
        if (f) {
            for (int i = first; i < argc; i++) fprintf(f, "%s%s", i == first ? "" : " ", argv[i]);
            fputc('\n', f); fclose(f);
        }
        args[n++] = "/lab/verify.arm";
    } else {
        args[n++] = "/lab/busybox.arm";
        if (strcmp(command, "busybox")) args[n++] = (char *)command;
    }
    for (int i = first; i < argc; i++) {
        /* The production manifest pins its verifier too. Its entry point is
         * the dispatcher only in this lab, so verify the preserved exact ARM
         * original for that one path. All other targets remain unchanged. */
        if (!strcmp(command, "verify") && i == first + 1 &&
            !strcmp(argv[first], "verify") &&
            !strcmp(argv[i], "/usr/libexec/carplay-revival/verify")) {
            fprintf(stderr, "LAB_DISPATCH: verifier self-pin reads exact preserved /lab/verify.arm\n");
            args[n++] = "/lab/verify.arm";
        } else args[n++] = argv[i];
    }
    args[n] = NULL;
    execv(args[0], args);
    fprintf(stderr, "LAB_DISPATCH: exec failed: %s\n", strerror(errno));
    return 126;
}
