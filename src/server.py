#!/usr/bin/env python3
"""流量监控 + 防火墙 Web 后端（Windows 版）
  - 读 OpenWrt stats.txt（优先 SSH，绕过 Samba 缓存；失败时回退 Samba）
  - 通过 SSH 调 OpenWrt 上的 firewall.sh
  - 对前端输入进行合法性校验，避免直接拼接用户输入形成系统命令
"""

import json, re, os, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ── 配置 ──────────────────────────────────────────────
STATS_FILE = r"\\192.168.6.100\share\traffic_monitor\stats.txt"
OPENWRT_HOST = "root@192.168.6.100"
FIREWALL_SCRIPT = "sh /mnt/p0/traffic_monitor/firewall.sh"

# ── 输入校验（指导书 3.3：避免直接拼接用户输入形成系统命令）──

IPV4_RE = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')

def is_valid_ipv4(addr):
    """校验 IPv4 地址格式：每段 0-255"""
    m = IPV4_RE.match(addr)
    if not m:
        return False
    return all(0 <= int(g) <= 255 for g in m.groups())

def is_valid_port(port):
    """校验端口号：1-65535 的整数 或 范围 start-end"""
    if not port:
        return True  # 端口可选
    # 单个端口
    if re.match(r'^\d{1,5}$', port):
        return 1 <= int(port) <= 65535
    # 范围 (start-end)
    if re.match(r'^\d{1,5}-\d{1,5}$', port):
        parts = port.split('-')
        return all(1 <= int(p) <= 65535 for p in parts)
    # 范围 (start:end)
    if re.match(r'^\d{1,5}:\d{1,5}$', port):
        parts = port.split(':')
        return all(1 <= int(p) <= 65535 for p in parts)
    return False

VALID_PROTOS = {'tcp', 'udp', 'icmp'}
VALID_ACTIONS = {'accept', 'drop', 'reject'}

def validate_firewall_add(data):
    """校验防火墙添加规则的参数，返回 (ok, error_message)"""
    proto = (data.get('proto', '') or '').strip().lower()
    src_addr = (data.get('src_addr', '') or '').strip()
    dst_addr = (data.get('dst_addr', '') or '').strip()
    port = (data.get('port', '') or '').strip()
    action = (data.get('action', '') or '').strip().lower()

    if not proto:
        return False, "协议类型不能为空"
    if proto not in VALID_PROTOS:
        return False, f"无效协议 '{proto}'，支持: {', '.join(sorted(VALID_PROTOS))}"

    if not src_addr:
        return False, "源 IP 地址不能为空"
    if not is_valid_ipv4(src_addr):
        return False, f"无效源 IP 地址: {src_addr}"

    if not dst_addr:
        return False, "目标 IP 地址不能为空"
    if not is_valid_ipv4(dst_addr):
        return False, f"无效目标 IP 地址: {dst_addr}"

    if proto != 'icmp' and not is_valid_port(port):
        return False, f"无效端口号: {port}（应为 1-65535 或范围如 8000-9000）"

    if not action:
        return False, "处理动作不能为空"
    if action not in VALID_ACTIONS:
        return False, f"无效动作 '{action}'，支持: {', '.join(sorted(VALID_ACTIONS))}"

    return True, ""

def validate_firewall_del(data):
    """校验防火墙删除规则的参数"""
    rule_id = (data.get('rule_id', '') or '').strip()
    if not rule_id:
        return False, "规则编号不能为空"
    if not rule_id.isdigit():
        return False, f"规则编号必须为数字，收到: {rule_id}"
    return True, ""

# ── 读 stats.txt ─────────────────────────────────────

FIELD_RE = re.compile(r'(\w+):([\w\s/]+)')

def _read_stats():
    """优先 SSH 直读（绕过 Samba 缓存），失败时回退 Samba"""
    try:
        r = subprocess.run(
            ["ssh", OPENWRT_HOST, "cat /mnt/p0/traffic_monitor/stats.txt"],
            capture_output=True, text=True, timeout=5, encoding="utf-8"
        )
        if r.returncode == 0:
            return r.stdout.splitlines()
    except Exception:
        pass
    # 回退到 Samba
    try:
        with open(STATS_FILE) as f:
            return f.readlines()
    except FileNotFoundError:
        return []

def parse_stats():
    flows = []
    for line in _read_stats():
        line = line.strip()
        if not line or '->' not in line:
            continue
        addr_part, _, stats_part = line.partition('|')
        src, _, dst = addr_part.partition(' -> ')
        src = src.strip()
        dst = dst.strip()
        fields = {}
        for m in FIELD_RE.finditer(stats_part):
            fields[m.group(1)] = m.group(2).strip()
        flows.append({
            "src": src,
            "dst": dst,
            "total": fields.get("total", "0"),
            "rate_2s": fields.get("2s", "0"),
            "rate_10s": fields.get("10s", "0"),
            "rate_40s": fields.get("40s", "0"),
            "max": fields.get("max", "0"),
        })
    return flows

# ── 防火墙 SSH 调用 ──────────────────────────────────

def run_firewall(action, params=None):
    cmd = ["ssh", OPENWRT_HOST, FIREWALL_SCRIPT, action]
    if params:
        # 过滤空字符串参数，避免传多余的空参数给 shell
        cmd.extend([p for p in params if p])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8")
        return {
            "ok": r.returncode == 0,
            "stdout": (r.stdout or "").strip(),
            "stderr": (r.stderr or "").strip()
        }
    except FileNotFoundError:
        return {"ok": False, "error": "ssh not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

# ── HTTP Handler ─────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._cors()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/stats":
            self._json({"flows": parse_stats()})
        elif path == "/api/firewall/list":
            self._json(run_firewall("list"))
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "请求体不是有效的 JSON"}, 400)
            return

        if path == "/api/firewall/add":
            ok, err = validate_firewall_add(data)
            if not ok:
                self._json({"ok": False, "error": err, "stderr": err}, 400)
                return
            params = [
                data.get("proto", "").strip().lower(),
                data.get("src_addr", "").strip(),
                data.get("dst_addr", "").strip(),
                data.get("port", "").strip(),
                data.get("action", "").strip().lower(),
            ]
            self._json(run_firewall("add", params))

        elif path == "/api/firewall/del":
            ok, err = validate_firewall_del(data)
            if not ok:
                self._json({"ok": False, "error": err, "stderr": err}, 400)
                return
            params = [data.get("rule_id", "").strip()]
            self._json(run_firewall("del", params))

        else:
            self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"API server running on http://localhost:{port}")
    server.serve_forever()
