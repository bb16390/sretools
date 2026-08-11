#!/bin/bash

# 项目启停脚本 - 停止脚本
# 用法: ./stop.sh [master|worker|all] [-f|--force]
# 或:   ./stop.sh <stop|status|kill> [target] [options]
#
# 命令:
#   stop     停止服务 (默认)
#   status   查看服务状态
#   kill     强制终止服务 (SIGKILL)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# PID 文件目录
PID_DIR="$PROJECT_ROOT/.pids"
MASTER_PID_FILE="$PID_DIR/master.pid"
WORKER_PID_FILE="$PID_DIR/worker.pid"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"

# 颜色定义
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
NC=$'\033[0m'

# ------------------------------
# 日志辅助
# ------------------------------
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_ok() {
    echo -e "${GREEN}[ OK ]${NC} $1"
}

# ------------------------------
# 基础工具
# ------------------------------
setup_dirs() {
    mkdir -p "$PID_DIR" "$LOG_DIR"
}

is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

# 从 master/core/settings.py 读取 master 日志文件路径
get_master_log_file() {
    local python_cmd
    if command -v python3 &> /dev/null; then
        python_cmd="python3"
    elif command -v python &> /dev/null; then
        python_cmd="python"
    else
        echo "$PROJECT_ROOT/master/log/uvicorn.log"
        return 0
    fi
    local log_file
    if command -v uv &> /dev/null; then
        log_file=$(cd "$PROJECT_ROOT" && uv run python -c "from master.core.settings import settings; print(settings.log_dir)" 2>/dev/null || true)
    else
        log_file=$(cd "$PROJECT_ROOT" && PYTHONPATH="$PROJECT_ROOT" "$python_cmd" -c "from master.core.settings import settings; print(settings.log_dir)" 2>/dev/null || true)
    fi
    if [ -n "$log_file" ]; then
        echo "$log_file"
    else
        echo "$PROJECT_ROOT/master/log/uvicorn.log"
    fi
}

# 杀死主进程及其整个进程组
kill_process_tree() {
    local pid=$1
    local signal=$2

    if ! kill -0 "$pid" 2>/dev/null; then
        return 0
    fi

    # 优先按进程组杀
    local pgid
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    if [ -n "$pgid" ] && [ "$pgid" != "-1" ] && [ "$pgid" != "0" ]; then
        # 先给进程组发送信号
        kill "-$signal" -- "-$pgid" 2>/dev/null || true
    fi
    # 最后确保主进程收到信号
    kill "-$signal" "$pid" 2>/dev/null || true
}

# ------------------------------
# 停止单个服务
# ------------------------------
stop_service() {
    local name=$1
    local pid_file=$2
    local force=${3:-false}
    local timeout=${4:-30}

    log_info "停止 ${name} 服务..."

    if ! is_running "$pid_file"; then
        log_warn "${name} 服务未运行"
        rm -f "$pid_file"
        return 0
    fi

    local pid
    pid=$(cat "$pid_file")

    if [ "$force" = "true" ]; then
        log_warn "强制终止 ${name} (PID: $pid, SIGKILL)"
        kill_process_tree "$pid" "9"
        sleep 1
        # 再次清理残留
        kill -9 "$pid" 2>/dev/null || true
    else
        log_info "优雅停止 ${name} (PID: $pid, SIGTERM, 超时 ${timeout}s)"
        kill_process_tree "$pid" "TERM"

        # 轮询等待退出
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt "$timeout" ]; do
            sleep 1
            count=$((count + 1))
        done

        if kill -0 "$pid" 2>/dev/null; then
            log_warn "${name} ${timeout}s 内未退出，强制终止"
            kill_process_tree "$pid" "9"
            sleep 1
        fi
    fi

    # 最后确认清理
    kill -9 "$pid" 2>/dev/null || true

    rm -f "$pid_file"

    if kill -0 "$pid" 2>/dev/null; then
        log_error "${name} 进程 (PID: $pid) 仍在运行，请手动检查"
        return 1
    fi
    log_ok "${name} 服务已停止"
    return 0
}

stop_master() {
    stop_service "Master" "$MASTER_PID_FILE" "$1"
}

stop_worker() {
    stop_service "Worker" "$WORKER_PID_FILE" "$1"
}

stop_all() {
    local force=$1
    log_info "========== 停止所有服务 =========="
    # 先停 worker（子服务），再停 master
    stop_worker "$force" || true
    sleep 2
    stop_master "$force" || true
}

# ------------------------------
# 状态查看
# ------------------------------
print_status_line() {
    local name=$1
    local pid_file=$2
    local default_port=${3:-}
    local status="STOPPED"
    local color=$RED
    local pid=""
    local extra=""

    if is_running "$pid_file"; then
        pid=$(cat "$pid_file")
        status="RUNNING"
        color=$GREEN
        if command -v ps &> /dev/null; then
            local etime
            etime=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ' || echo "-")
            local pcpu
            pcpu=$(ps -o pcpu= -p "$pid" 2>/dev/null | tr -d ' ' || echo "-")
            local rss
            rss=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ' || echo "0")
            local rss_mb=$(( rss / 1024 ))
            extra="运行: ${etime} | CPU: ${pcpu}% | 内存: ${rss_mb}MB"
        fi
        if [ -n "$default_port" ]; then
            (echo > "/dev/tcp/127.0.0.1/${default_port}") 2>/dev/null \
                && extra="$extra | 端口 :${default_port} OK" \
                || extra="$extra | 端口 :${default_port} -"
        fi
    fi

    # 使用 %b 展开 ANSI 颜色转义码
    printf "  %-8s %b %s %b\n" \
        "$name" \
        "${color}$(printf '%-10s' "$status")${NC}" \
        "${pid:+PID:$pid}" \
        "${YELLOW}${extra}${NC}"
}

show_status() {
    echo ""
    echo "=========================================="
    echo "          服务运行状态"
    echo "=========================================="
    setup_dirs
    print_status_line "Master"  "$MASTER_PID_FILE" "5500"
    print_status_line "Worker"  "$WORKER_PID_FILE"
    echo "=========================================="
    echo ""
    echo "Master 日志: $(get_master_log_file)"
    echo "Worker 日志: $LOG_DIR/worker.log"
    echo "PID  目录: $PID_DIR"
    echo ""
}

# ------------------------------
# 帮助
# ------------------------------
usage() {
    cat <<EOF
用法: $0 [command] [target] [options]

命令:
  stop      停止服务 (默认命令，优雅停止)
  status    查看服务运行状态
  kill      强制停止服务 (直接 SIGKILL，慎用)

目标:
  master    仅停止 Master 服务
  worker    仅停止 Worker 服务
  all       停止所有服务 (默认)

选项:
  -f, --force    强制终止 (SIGKILL，立即停止，不等优雅退出)
  -t, --timeout N    优雅停止超时秒数 (默认 30)
  -h, --help     显示帮助

示例:
  $0                          # 优雅停止所有服务
  $0 stop all                  # 同上
  $0 stop worker -f           # 强制停止 worker
  $0 kill master           # 强制停止 master
  $0 status                # 查看状态
  $0 stop all -t 60         # 停止所有服务，超时 60s
EOF
}

# ------------------------------
# 主入口
# ------------------------------
main() {
    local command="stop"
    local target="all"
    local force=false
    local timeout=30

    local positional=()
    for arg in "$@"; do
        case "$arg" in
            stop|status|kill)
                command="$arg"
                ;;
            master|worker|all)
                target="$arg"
                ;;
            -f|--force)
                force=true
                ;;
            -t|--timeout)
                # 下一个参数是值，由位置参数里拿 (简单处理：让用户用等号)
                ;;
            --timeout=*)
                timeout="${arg#*=}"
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                positional+=("$arg")
                ;;
        esac
    done

    # kill 命令即强制
    if [ "$command" = "kill" ]; then
        force=true
        command="stop"
    fi

    setup_dirs

    case "$command" in
        stop)
            case "$target" in
                master)  stop_master  "$force" "$timeout" ;;
                worker)  stop_worker  "$force" "$timeout" ;;
                all)     stop_all     "$force" ;;
            esac
            ;;
        status)
            show_status
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
