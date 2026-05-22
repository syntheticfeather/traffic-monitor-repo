# 计算机网络实验二 — AI 交互完整记录

## 阶段一：OpenWrt 部署

### 1.1 镜像选择

**我**：下载哪个 img？
**AI**：`generic-ext4-combined-efi.img.gz`。解释：ext4 可读写、efi 兼容 VMware UEFI 引导、combined 内核+根文件系统打包。

### 1.2 镜像格式转换

**我**：StarWind V2V 显示 "not initialized"，需要公司邮箱注册。
**AI**：换免费方案 — 用 `qemu-img`：
```cmd
qemu-img.exe convert -f raw -O vmdk generic-ext4-combined-efi.img openwrt.vmdk
```

### 1.3 VMware 创建虚拟机

**AI** 指导：自定义 → Linux 5.x 64 位 → 1GB 内存 / 1 核 → NAT 网络 → 使用现有 vmdk 磁盘。

### 1.4 开机弹窗 "无法连接虚拟设备 sata0:1"

**AI**：选"否"，编辑虚拟机设置 → 移除报错的 SATA 磁盘 → 重新添加硬盘 → 浏览选中 vmdk。

---

## 阶段二：网络配置

### 2.1 误用 firstboot

**我**：`vi /etc/config/network` 误删了内容，能不能 undo？
**AI**：vi 内按 `u` 撤销。如果已 `:wq` 保存，检查 `ls /etc/config/*~` 备份。

### 2.2 firstboot 后 network 清空

**我**：`firstboot` 后 network 全空了。
**AI**：这是重置到出厂的行为。需要重新写入配置。

### 2.3 网关配置错误（关键踩坑）

**我**：VMnet8 是 `192.168.6.1`，我设 `gateway '192.168.6.1'`，ping 不通。
**AI**：`192.168.6.1` 是宿主机在虚拟网络中的地址，不负责转发。VMware NAT 的内置网关是 `192.168.6.2`。改后通了。

**关键认知**：
```
192.168.6.1 = 宿主机 VMnet8 接口地址（仅通信，不转发）
192.168.6.2 = VMware NAT 虚拟网关（实际转发数据包）
```

---

## 阶段三：Samba 文件共享

### 3.1 安装配置

**AI** 指导步骤：
```bash
opkg update
opkg install luci-app-samba4
mkdir -p /mnt/p0 && chmod -R 777 /mnt/p0
```

`/etc/config/samba4` 添加：
```
config sambashare
    option name 'share'
    option path '/mnt/p0'
    option read_only 'no'
    option guest_ok 'yes'
    option create_mask '0777'
    option dir_mask '0777'
    option browseable 'yes'
```

Windows 访问 `\\192.168.6.100` 验证通过。

---

## 阶段四：流量监控程序 — 数据结构设计

### 4.1 设计讨论（费曼学习法）

**AI** 通过提问引导我自主设计：
- Q: "流的键是什么？"
- A: 源 IP + 目的 IP 对
- Q: "值应该存什么？"
- A: 累计字节数、峰值速率、平均值
- Q: "怎么处理碰撞？"
- A: 链式存储
- Q: "满了怎么淘汰？"
- A: FIFO

### 4.2 最终设计

| 决策 | 方案 |
|------|------|
| 哈希表槽数 | 1999（质数） |
| 结点池大小 | 2000（预分配数组） |
| 哨兵 | 独立数组 `sentinel_pool[HASH_SIZE]`，不被 FIFO 覆盖 |
| 锁 | `pthread_mutex_t` 保护结点池，`flock` 保护文件 |

### 4.3 哨兵设计的迭代

**我** 最初用 `malloc` 创建哨兵。
**AI**：全局数组已经预分配，不需要 `malloc`。哨兵从独立数组出，和流结点池分离，防止 FIFO 绕回覆盖哨兵。

### 4.4 锁的优化

**我** 注意到 `stats_thread` 在锁内做 `fprintf` 会长时间占锁。
**AI**：锁内只做快照（微秒级），锁外写文件（毫秒级），不阻塞抓包线程。

---

## 阶段五：交叉编译（7 次失败 → 1 次成功）

### 5.1 失败路径记录

| # | 尝试 | 失败原因 |
|---|------|---------|
| 1 | WSL `gcc -static` | libpcap 静态库依赖 dbus/rdma/infiniband |
| 2 | WSL 动态编译 + 拷 .so | glibc vs musl ABI 不兼容 |
| 3 | OpenWrt 本地 `opkg install gcc` | overlay 仅 30MB |
| 4 | 扩磁盘 + fdisk | GPT 备份表损坏，VM 变砖 |
| 5 | `musl-gcc` 交叉编译 | 缺内核头文件 |
| 6 | OpenWrt SDK | 缺 feeds 和 toolchain |
| 7 | qemu-img resize + parted 扩分区 | GPT 顽固损坏无法修复 |

### 5.2 最终成功方案

**我**：上网搜索交叉编译。
**AI**：搜索到关键信息 — 应该下载 **OpenWrt Toolchain**（~100MB），而非 SDK（~300MB）。

**Toolchain 交叉编译步骤**：
1. 下载：`openwrt-toolchain-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst`
2. 下载 libpcap 源码（tcpdump.org 官方版，非 GitHub 版）
3. `sudo apt install bison`（libpcap configure 需要）
4. 用 Toolchain 编译 libpcap：
```bash
./configure --host=x86_64-openwrt-linux-musl --prefix="$T" --disable-shared --disable-dbus
make -j$(nproc) && make install
```
5. 编译监控程序：
```bash
x86_64-openwrt-linux-musl-gcc -static -o monitor monitor.c hash.c -lpcap -lpthread
```

输出：`ELF 64-bit LSB executable, statically linked`

### 5.3 编译脚本化

**AI** 创建 `compile.sh`（快速重编）和 `build.sh`（首次完整构建），后续修改代码只需一行 `bash compile.sh`。

### 5.4 上传到 OpenWrt

```bash
cat monitor | wsl -e bash -c "ssh root@192.168.6.100 'cat > /mnt/p0/traffic_monitor/monitor && chmod +x /mnt/p0/traffic_monitor/monitor'"
```

---

## 阶段六：功能测试

### 6.1 测试方法

**AI** 通过 SSH 直接执行：
```bash
ssh root@192.168.6.100 "
ping -c 10 8.8.8.8 &
ping -c 10 114.114.114.114 &
sleep 5
cat /mnt/p0/traffic_monitor/stats.txt
"
```

### 6.2 测试结果

16 条流记录成功生成。累计字节、瞬时速率、峰值速率均正常计算。

IP 显示格式：当前以 32 位整数输出（如 `1678158016`），Web 前端需通过 `inet_ntop` 转换为点分十进制（`192.168.1.100`）。

---

## 关键 AI 提示词与回复摘要

| 场景 | 我的提问 | AI 核心回复 |
|------|---------|------------|
| 镜像选择 | "应该下载哪个 img？" | 选 ext4-combined-efi，解释每个后缀含义 |
| 格式转换 | "StarWind 要注册" | 换 qemu-img，一行命令 |
| 网络不通 | "ping 全部 loss" | 网关 `.1` 改 `.2`，解释 NAT 网关 vs 宿主机接口 |
| network 清空 | "firstboot 后啥都没了" | firstboot 行为说明，手动重写配置 |
| 哈希表设计 | "直接 mod 作为 hash 函数" | 碰撞处理、哨兵、FIFO 细节追问 |
| 静态编译失败 | "gcc -static 报 dbus 错误" | 逐项排查，最终找到 Toolchain 方案 |
| GPT 损坏 | "fdisk 后 VM 打不开了" | GPT 修复尝试，最终放弃扩磁盘走交叉编译 |
| 编译脚本 | "改了代码怎么快速重编" | 创建 `compile.sh`，一行重新编译+上传 |

---

## AI 使用评价

- **正面**：交叉编译 7 次失败中每次给出新方案不放弃，最终 Toolchain 方案可行；设计讨论阶段使用费曼学习法通过提问引导自主思考
- **局限**：初期对 WSL/Git Bash 环境的 PATH 处理（`Program Files (x86)` 括号问题）缺乏预判，多次命令执行失败后才适配
- **收获**：理解了 glibc 与 musl 的 ABI 差异、OpenWrt SDK 与 Toolchain 的区别、GPT 分区表修复的基本方法