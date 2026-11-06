#!/bin/sh
# Requires an ARM hard-float toolchain suitable for Linux 3.4.
set -eu
: "${CROSS_COMPILE:?Set CROSS_COMPILE to the ARM toolchain prefix}"
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out=${1:?Give a NEW build directory}
[ ! -e "$out" ] || { echo 'Build directory already exists' >&2; exit 1; }
mkdir -p "$out"
tar -xjf "$repo/third_party/busybox/busybox-1.38.0.tar.bz2" -C "$out"
src=$out/busybox-1.38.0
cp "$repo/third_party/busybox/busybox.config" "$src/.config"
make -C "$src" ARCH=arm CROSS_COMPILE="$CROSS_COMPILE" oldconfig
make -C "$src" ARCH=arm CROSS_COMPILE="$CROSS_COMPILE" \
  EXTRA_CFLAGS='-march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard' -j2
cp "$src/busybox" "$out/udhcpd"
echo 'Rebuilt udhcpd. A different toolchain may produce a different hash; validate before use.'
