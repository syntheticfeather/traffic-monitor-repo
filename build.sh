#!/bin/bash
# 首次构建：编译 libpcap + monitor
# 前提：需先下载 OpenWrt Toolchain 到 ../openwrt-toolchain/
#   wget https://downloads.openwrt.org/releases/24.10.0/targets/x86/64/openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst
#   tar --zstd -xf openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst -C ..
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
T="$SCRIPT_DIR/../openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64/toolchain-x86_64_gcc-13.3.0_musl"
export PATH="$T/bin:/usr/bin:/bin"
export STAGING_DIR="$T"

# 1. Build libpcap
echo "=== Building libpcap ==="
cd /tmp
rm -rf libpcap-1.10.5
tar xf "$SCRIPT_DIR/libpcap-1.10.5.tar.gz"
cd libpcap-1.10.5
./configure --host=x86_64-openwrt-linux-musl --prefix="$T" --disable-shared --disable-dbus
make -j$(nproc)
make install
echo "=== libpcap DONE ==="

# 2. Build monitor
echo "=== Building monitor ==="
cd "$SCRIPT_DIR/src"
x86_64-openwrt-linux-musl-gcc -static -o monitor monitor.c hash.c -lpcap -lpthread
echo "=== monitor DONE ==="
ls -la monitor
file monitor
