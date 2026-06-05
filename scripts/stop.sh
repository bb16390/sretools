#!/bin/bash

# 项目启停脚本 - 停止脚本
# 用法: ./stop.sh [master|worker|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# PID 文件目录
PID_DIR="$PROJECT_ROOT/.pids"
MASTER_PID_FILE="$PID_DIR/master.pid"
WORKER_PID_FILE="$PID_DIR/worker.pid"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查进程是否运行
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

# 停止 master 服务
stop_master() {
    log_info "停止 Master 服务..."

    if ! is_running "$MASTER_PID_FILE"; then
        log_warn "Master 服务未运行"
        return 0
    fi

    local pid=$(cat "$MASTER_PID_FILE")

    # 尝试优雅停止
    if kill -TERM "$pid" 2>/dev/null; then
        # 等待进程停止
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 30 ]; do
            sleep 1
            count=$((count + 1))
        done

        # 如果进程还在运行，强制终止
        if kill -0 "$pid" 2>/dev/null; then
            log_warn "优雅停止超时，强制终止..."
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi

    rm -f "$MASTER_PID_FILE"
    log_info "Master 服务已停止"
}

# 停止 worker 服务
stop_worker() {
    log_info "停止 Worker 服务..."

    if ! is_running "$WORKER_PID_FILE"; then
        log_warn "Worker 服务未运行"
        return 0
    fi

    local pid=$(cat "$WORKER_PID_FILE")

    # 尝试优雅停止
    if kill -TERM "$pid" 2>/dev/null; then
        # 等待进程停止
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 30 ]; do
            sleep 1
            count=$((count + 1))
        done

        # 如果进程还在运行，强制终止
        if kill -0 "$pid" 2>/dev/null; then
            log_warn "优雅停止超时，强制终止..."
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi

    rm -f "$WORKER_PID_FILE"
    log_info "Worker 服务已停止"
}

# 停止所有服务
stop_all() {
    log_info "停止所有服务..."
    stop_worker
    sleep 2
    stop_master
}

# 主函数
main() {
    local cmd=${1:-all}

    case $cmd in
        master)
            stop_master
            ;;
        worker)
            stop_worker
            ;;
        all)
            stop_all
            ;;
        *)
            echo "用法: $0 [master|worker|all]"
            exit 1
            ;;
    esac
}

main "$@"