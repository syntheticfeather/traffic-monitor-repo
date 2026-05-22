#!/bin/bash
T=/mnt/d/Study/paper/CS/lab/lab2/openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64/toolchain-x86_64_gcc-13.3.0_musl
export PATH="$T/bin:/usr/bin:/bin"
export STAGING_DIR="$T"
cd /mnt/d/Study/paper/CS/lab/lab2/resources/src
x86_64-openwrt-linux-musl-gcc -static -o monitor monitor.c hash.c -lpcap -lpthread
echo "=== DONE ==="
ls -la monitor
file monitor
