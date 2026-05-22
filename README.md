# 流量监控系统 — 计算机网络实验二

基于 OpenWrt 的网络流量实时监控与防火墙管理系统。

## 文件说明

| 文件 | 说明 |
|------|------|
| `src/monitor.c` | C 程序主文件 — libpcap 抓包 + 线程管理 |
| `src/hash.c` | 哈希表 + 流结点管理 |
| `src/hash.h` | 数据结构定义 + 函数声明 |
| `src/server.py` | Python 后端 — HTTP API |
| `compile.sh` | 交叉编译脚本 |
| `前端API文档.md` | 前端接口文档 |
| `实验环境配置记录.md` | OpenWrt 部署配置记录 |
| `AI使用记录-完整交互.md` | AI 辅助开发过程记录 |
| `测试记录-traffic-monitor.md` | 功能测试记录 |

## 运行环境

- **C 程序**：OpenWrt 24.10 (x86_64)，通过交叉编译部署
- **后端**：Python 3.11+，Windows / Linux，端口 8080
- **编译**：WSL Ubuntu + OpenWrt Toolchain

## 架构

```
OpenWrt 虚拟机
  ├── monitor (C) — libpcap 抓包 → stats.txt
  ├── Samba 共享 /mnt/p0
  └── firewall.sh — 防火墙脚本

Windows 宿主机
  ├── server.py — 读 Samba stats.txt → JSON API
  └── 编译：WSL + OpenWrt Toolchain

前端（队友开发）
  └── 调 /api/stats + /api/firewall/*
```

## 编译

```bash
bash compile.sh
# 输出：src/monitor（静态链接 musl 二进制）
```

## 启动后端

```cmd
python src/server.py
```

浏览器访问 `http://localhost:8080/api/stats`。
