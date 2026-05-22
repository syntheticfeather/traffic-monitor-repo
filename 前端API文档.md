# 流量监控与防火墙 — 前端 API 文档

## 基础信息

| 项 | 值 |
|----|-----|
| 后端地址 | `http://localhost:8080` |
| 数据格式 | JSON |
| 跨域 | 已开启 CORS（`Access-Control-Allow-Origin: *`） |

---

## 一、GET /api/stats

获取实时流量监控数据。

### 请求

```
GET http://localhost:8080/api/stats
```

无需参数。

### 响应

```json
{
  "flows": [
    {
      "src": "192.168.6.100:445",
      "dst": "192.168.6.1:58958",
      "total": "397931",
      "rate_2s": "642 B/s",
      "rate_10s": "538 B/s",
      "rate_40s": "0 B/s",
      "max": "1328 B/s"
    },
    {
      "src": "192.168.6.100:22",
      "dst": "192.168.6.1:63311",
      "total": "1824",
      "rate_2s": "0 B/s",
      "rate_10s": "0 B/s",
      "rate_40s": "0 B/s",
      "max": "456 B/s"
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 含义 |
|------|------|------|
| `src` | string | 源 IP:端口（例 `192.168.6.100:445`，ICMP 包端口为 0） |
| `dst` | string | 目的 IP:端口 |
| `total` | string | 累计流量（字节） |
| `rate_2s` | string | 最近 2 秒平均速率 |
| `rate_10s` | string | 最近 10 秒平均速率 |
| `rate_40s` | string | 最近 40 秒平均速率 |
| `max` | string | 历史峰值速率 |

### 方向判断

- 源 IP 为 OpenWrt 路由器地址 → **出站**
- 目的 IP 为 OpenWrt 路由器地址 → **入站**

### 前端轮询建议

`stats.txt` 每 2 秒更新一次。建议前端每 **2~3 秒** 调用一次此接口实现实时监控。

---

## 二、GET /api/firewall/list

获取当前防火墙规则列表。

### 请求

```
GET http://localhost:8080/api/firewall/list
```

### 响应

```json
{
  "ok": true,
  "stdout": "规则1: ...\n规则2: ...",
  "stderr": ""
}
```

| 字段 | 类型 | 含义 |
|------|------|------|
| `ok` | bool | 是否执行成功 |
| `stdout` | string | 脚本标准输出（规则列表文本） |
| `stderr` | string | 脚本错误输出（为空表示无错误） |

> `firewall.sh` 由队员编写，输出格式待队友确定后更新此文档。

---

## 三、POST /api/firewall/add

新增一条防火墙规则。

### 请求

```
POST http://localhost:8080/api/firewall/add
Content-Type: application/json

{
  "proto": "tcp",
  "src_addr": "192.168.6.1",
  "dst_addr": "192.168.6.100",
  "port": "80",
  "action": "accept"
}
```

### 参数说明

| 参数 | 类型 | 必填 | 含义 |
|------|------|------|------|
| `proto` | string | 是 | 协议类型：`tcp` / `udp` / `icmp` |
| `src_addr` | string | 是 | 源 IP 地址 |
| `dst_addr` | string | 是 | 目的 IP 地址 |
| `port` | string | 是 | 端口号 |
| `action` | string | 是 | 动作：`accept` / `drop` / `reject` |

### 响应

```json
{
  "ok": true,
  "stdout": "规则已添加",
  "stderr": ""
}
```

---

## 四、POST /api/firewall/del

删除一条防火墙规则。

### 请求

```
POST http://localhost:8080/api/firewall/del
Content-Type: application/json

{
  "rule_id": "1"
}
```

| 参数 | 类型 | 必填 | 含义 |
|------|------|------|------|
| `rule_id` | string | 是 | 要删除的规则编号 |

### 响应

```json
{
  "ok": true,
  "stdout": "规则已删除",
  "stderr": ""
}
```

---

## 五、前端调用示例

### 轮询获取流量数据

```javascript
// 每 2 秒拉一次
setInterval(async () => {
  const res = await fetch('http://localhost:8080/api/stats');
  const data = await res.json();
  // data.flows → 渲染表格 / 图表
  renderTable(data.flows);
}, 2000);
```

### 添加防火墙规则

```javascript
const res = await fetch('http://localhost:8080/api/firewall/add', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    proto: 'tcp',
    src_addr: '192.168.6.1',
    dst_addr: '192.168.6.100',
    port: '80',
    action: 'drop'
  })
});
const result = await res.json();
// result.ok → 成功 / 失败
```

---

## 六、错误响应

```json
{
  "error": "not found"
}
```

HTTP 状态码 404，当访问未定义的路径时返回。

---

## 七、架构图

```
 ┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
 │  前端 (HTML/JS)       │     │  后端 (server.py)     │     │  OpenWrt 虚拟机   │
 │                      │────→│  Windows 上运行       │────→│                  │
 │  轮询 GET /api/stats │     │  :8080              │     │  monitor (C程序)  │
 │  提交防火墙规则      │     │  读 Samba: stats.txt │     │  firewall.sh     │
 │                      │←────│  SSH 调 firewall.sh │←────│  Samba 共享       │
 └──────────────────────┘     └──────────────────────┘     └──────────────────┘
```
