#!/usr/bin/env python3
"""流量监控 + 防火墙 Web 后端（Windows 版）
  - 读 OpenWrt Samba 共享的 stats.txt
  - 通过 SSH 调 OpenWrt 上的 firewall.sh
"""

import json, re, os, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Windows UNC 路径：Samba 共享
STATS_FILE = r"\\192.168.6.100\share\traffic_monitor\stats.txt"
OPENWRT_HOST = "root@192.168.6.100"
FIREWALL_SCRIPT = "sh /mnt/p0/traffic_monitor/firewall.sh"

FIELD_RE = re.compile(r'(\w+):([\w\s/]+)')

def parse_stats():
    flows = []
    try:
        with open(STATS_FILE) as f:
            for line in f:
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
    except FileNotFoundError:
        pass
    return flows


def run_firewall(action, params=None):
    cmd = ["ssh", OPENWRT_HOST, FIREWALL_SCRIPT, action]
    if params:
        cmd.extend(params)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return {
            "ok": r.returncode == 0,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip()
        }
    except FileNotFoundError:
        return {"ok": False, "error": "ssh not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}


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
            data = {}

        if path == "/api/firewall/add":
            params = [
                data.get("proto", ""),
                data.get("src_addr", ""),
                data.get("dst_addr", ""),
                data.get("port", ""),
                data.get("action", ""),
            ]
            self._json(run_firewall("add", params))
        elif path == "/api/firewall/del":
            params = [data.get("rule_id", "")]
            self._json(run_firewall("del", params))
        else:
            self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"API server running on http://localhost:{port}")
    server.serve_forever()
