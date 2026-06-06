#!/bin/sh
#=============================================================================
# firewall.sh — OpenWrt 防火墙规则管理脚本
# 由 server.py 通过 SSH 远程调用
#
# 用法:
#   sh firewall.sh list                              # 列出所有规则
#   sh firewall.sh add <协议> <源IP> <目标IP> [端口] <动作>  # 添加规则
#   sh firewall.sh del <规则编号>                      # 删除规则
#   sh firewall.sh clear                             # 清空所有自定义规则
#=============================================================================

set -e

# ---- 配置 ----
CHAIN="FORWARD"                   # 默认操作链（路由器转发流量）
IPTABLES="/usr/sbin/iptables"     # iptables 路径

# ---- 工具函数 ----

# 检查 iptables 是否可用
check_iptables() {
    if [ ! -x "$IPTABLES" ]; then
        if [ -x "/usr/sbin/xtables-legacy-multi" ]; then
            IPTABLES="/usr/sbin/xtables-legacy-multi iptables"
        elif command -v iptables >/dev/null 2>&1; then
            IPTABLES="iptables"
        else
            echo "ERROR: iptables not found"
            exit 1
        fi
    fi
}

# 校验 IP 地址格式
is_valid_ip() {
    echo "$1" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || return 1
    local IFS='.'
    set -- $1
    [ $1 -le 255 ] && [ $2 -le 255 ] && [ $3 -le 255 ] && [ $4 -le 255 ]
}

# 校验端口号
is_valid_port() {
    echo "$1" | grep -Eq '^[0-9]{1,5}([-:][0-9]{1,5})?$' || return 1
}

# ---- 命令：列出规则 ----
cmd_list() {
    check_iptables
    echo "=== 防火墙规则列表 (链: $CHAIN) ==="
    if $IPTABLES -L "$CHAIN" -n --line-numbers -v 2>/dev/null; then
        :
    else
        echo "(链 $CHAIN 为空或不存在)"
    fi
    echo ""
    echo "=== 防火墙规则列表 (链: INPUT) ==="
    if $IPTABLES -L INPUT -n --line-numbers -v 2>/dev/null; then
        :
    else
        echo "(链 INPUT 为空或不存在)"
    fi
    echo ""
    echo "提示: 规则编号 (#num) 用于删除操作"
}

# ---- 命令：添加规则 ----
# 参数: <协议> <源IP> <目标IP> [端口] <动作>
cmd_add() {
    check_iptables

    local proto="$1"
    local src_addr="$2"
    local dst_addr="$3"
    local port="$4"
    local action="$5"

    # === 参数校验 ===
    if [ -z "$proto" ] || [ -z "$action" ]; then
        echo "ERROR: 缺少必填参数"
        echo "用法: firewall.sh add <协议> <源IP> <目标IP> [端口] <动作>"
        exit 1
    fi

    # 校验协议
    case "$proto" in
        tcp|udp|icmp) ;;
        *)
            echo "ERROR: 无效协议 '$proto'，支持: tcp, udp, icmp"
            exit 1
            ;;
    esac

    # 校验 IP
    if [ -n "$src_addr" ] && ! is_valid_ip "$src_addr"; then
        echo "ERROR: 无效源IP地址 '$src_addr'"
        exit 1
    fi
    if [ -n "$dst_addr" ] && ! is_valid_ip "$dst_addr"; then
        echo "ERROR: 无效目标IP地址 '$dst_addr'"
        exit 1
    fi

    # 校验端口（ICMP 不需要端口）
    if [ "$proto" != "icmp" ] && [ -n "$port" ]; then
        if ! is_valid_port "$port"; then
            echo "ERROR: 无效端口号 '$port'"
            exit 1
        fi
    fi

    # 校验动作
    case "$action" in
        ACCEPT|DROP|REJECT|accept|drop|reject) ;;
        *)
            echo "ERROR: 无效动作 '$action'，支持: ACCEPT, DROP, REJECT"
            exit 1
            ;;
    esac

    # 统一转为大写
    action=$(echo "$action" | tr 'a-z' 'A-Z')

    # === 构造 iptables 命令 ===
    local rule_args="-A $CHAIN"

    # 协议
    rule_args="$rule_args -p $proto"

    # 源地址
    if [ -n "$src_addr" ]; then
        rule_args="$rule_args -s $src_addr"
    fi

    # 目标地址
    if [ -n "$dst_addr" ]; then
        rule_args="$rule_args -d $dst_addr"
    fi

    # 端口（非 ICMP）
    if [ "$proto" != "icmp" ] && [ -n "$port" ]; then
        case "$port" in
            *-*)
                local start_port="${port%-*}"
                local end_port="${port#*-}"
                rule_args="$rule_args --dport ${start_port}:${end_port}"
                ;;
            *:*)
                rule_args="$rule_args --dport $port"
                ;;
            *)
                rule_args="$rule_args --dport $port"
                ;;
        esac
    fi

    # 动作
    rule_args="$rule_args -j $action"

    # === 执行 ===
    echo "执行: iptables $rule_args"
    if $IPTABLES $rule_args 2>&1; then
        echo "SUCCESS: 规则已添加到 $CHAIN 链"
        echo "规则详情: 协议=$proto 源=$src_addr 目标=$dst_addr 端口=${port:-任意} 动作=$action"
    else
        echo "ERROR: iptables 命令执行失败"
        exit 1
    fi
}

# ---- 命令：删除规则 ----
# 参数: <规则编号>
cmd_del() {
    check_iptables

    local rule_num="$1"

    if [ -z "$rule_num" ]; then
        echo "ERROR: 缺少规则编号"
        echo "用法: firewall.sh del <规则编号>"
        echo "提示: 使用 'firewall.sh list' 查看规则编号"
        exit 1
    fi

    # 校验是否为数字
    case "$rule_num" in
        ''|*[!0-9]*)
            echo "ERROR: 规则编号必须为数字"
            exit 1
            ;;
    esac

    # 检查规则是否存在
    local rule_count
    rule_count=$($IPTABLES -L "$CHAIN" -n --line-numbers 2>/dev/null | grep -c "^$rule_num ") || true

    if [ "$rule_count" -eq 0 ]; then
        echo "ERROR: $CHAIN 链中不存在编号为 $rule_num 的规则"
        echo "提示: 使用 'firewall.sh list' 查看当前规则"
        exit 1
    fi

    echo "删除 $CHAIN 链中的第 $rule_num 条规则..."
    if $IPTABLES -D "$CHAIN" "$rule_num" 2>&1; then
        echo "SUCCESS: 规则 #$rule_num 已删除"
    else
        echo "ERROR: 删除失败"
        exit 1
    fi
}

# ---- 命令：清空规则 ----
cmd_clear() {
    check_iptables

    echo "警告: 即将清空 $CHAIN 链中的所有规则"
    if $IPTABLES -F "$CHAIN" 2>&1; then
        echo "SUCCESS: $CHAIN 链已清空"
    else
        echo "ERROR: 清空失败"
        exit 1
    fi
}

# ---- 主入口 ----
ACTION="${1:-}"

case "$ACTION" in
    list)
        cmd_list
        ;;
    add)
        shift
        cmd_add "$@"
        ;;
    del|delete)
        shift
        cmd_del "$@"
        ;;
    clear|flush)
        cmd_clear
        ;;
    -h|--help|help|"")
        echo "防火墙规则管理脚本"
        echo ""
        echo "用法:"
        echo "  firewall.sh list                    列出所有规则"
        echo "  firewall.sh add <协议> <源IP> <目标IP> [端口] <动作>"
        echo "  firewall.sh del <规则编号>            删除规则"
        echo "  firewall.sh clear                   清空所有规则"
        echo ""
        echo "示例:"
        echo "  firewall.sh add tcp 192.168.6.1 192.168.6.100 80 DROP"
        echo "  firewall.sh add icmp 192.168.6.1 192.168.6.100 '' REJECT"
        echo "  firewall.sh del 3"
        echo "  firewall.sh list"
        ;;
    *)
        echo "ERROR: 未知命令 '$ACTION'"
        echo "支持的命令: list, add, del, clear"
        echo "使用 'firewall.sh help' 查看帮助"
        exit 1
        ;;
esac

exit 0
