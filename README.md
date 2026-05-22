# 流量监控系统 — 计算机网络实验二

基于 OpenWrt 的网络流量实时监控与防火墙管理系统。

## 项目结构

```
├── src/
│   ├── monitor.c     # C 主程序（libpcap 抓包 + 线程管理）
│   ├── hash.c / .h   # 哈希表 + 流结点管理
│   └── server.py     # Python Web 后端（HTTP API）
├── libpcap-1.10.5.tar.gz  # libpcap 源码（编译依赖）
├── build.sh          # 首次完整构建（交叉编译 libpcap + monitor）
├── compile.sh        # 快速重编（只编 monitor）
├── 前端API文档.md
├── 实验环境配置记录.md
├── AI使用记录-完整交互.md
└── 测试记录-traffic-monitor.md
```

## 环境准备

### 交叉编译工具链（WSL / Linux）

下载到本项目**上级目录**：

```bash
wget https://downloads.openwrt.org/releases/24.10.0/targets/x86/64/openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst
tar --zstd -xf openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst -C ..
```

WSL 中安装构建依赖：

```bash
sudo apt install bison flex zstd build-essential
```

### OpenWrt 运行环境

- OpenWrt 24.10 (x86_64) 虚拟机
- `opkg install luci-app-samba4` — 文件共享
- `opkg install libpcap` — 运行时依赖

## 构建

```bash
# 首次（含 libpcap 交叉编译）
bash build.sh

# 只修改 C 代码后
bash compile.sh
```

输出：`src/monitor`（静态链接 musl 二进制，可直接在 OpenWrt 上运行）

## 运行

1. 部署到 OpenWrt：`cat src/monitor | ssh root@192.168.6.100 'cat > /mnt/p0/traffic_monitor/monitor && chmod +x /mnt/p0/traffic_monitor/monitor'`
2. OpenWrt 上：`cd /mnt/p0/traffic_monitor && ./monitor &`
3. Windows 上：`python src/server.py`
4. 接口：`http://localhost:8080/api/stats`

## API

详见 [前端API文档.md](前端API文档.md)

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/stats` | GET | 流量数据 JSON |
| `/api/firewall/list` | GET | 防火墙规则列表 |
| `/api/firewall/add` | POST | 添加规则 |
| `/api/firewall/del` | POST | 删除规则 |
