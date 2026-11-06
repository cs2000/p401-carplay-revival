#!/bin/sh
set -eu
ws=/opt/p401-workspace
vendor=/opt/p401-build/candidate-r1/root
clang --target=arm-linux-gnueabihf -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard \
  -isystem /opt/p401-r4-arm/usr/include -fuse-ld=lld -fPIC -shared -nostdlib \
  -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -Wl,--hash-style=both -O2 -Wall -Wextra -Werror \
  "$ws/work/visual_emulator/framebuffer.c" "$vendor/lib/libc.so.6" "$vendor/lib/libdl.so.2" \
  -o "$ws/work/visual_emulator/libp401-pc-fb.so"
