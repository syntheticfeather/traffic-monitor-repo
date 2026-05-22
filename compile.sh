#!/bin/bash
# 快速重编（libpcap 已装到 toolchain，先跑过 build.sh）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
T="$SCRIPT_DIR/../openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64/toolchain-x86_64_gcc-13.3.0_musl"
export PATH="$T/bin:/usr/bin:/bin"
export STAGING_DIR="$T"
cd "$SCRIPT_DIR/src"
x86_64-openwrt-linux-musl-gcc -static -o monitor monitor.c hash.c -lpcap -lpthread
echo "=== DONE ==="
ls -la monitor
file monitor
