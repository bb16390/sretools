#!/bin/bash

# 项目启停脚本 - 启动脚本
# 用法: ./start.sh [master|worker|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MASTER_DIR="$PROJECT_ROOT/master"
WORKER_DIR="$PROJECT_ROOT/worker"

# PID 文件目录
PID_DIR="$PROJECT_ROOT/.pids"
MASTER_PID_FILE="$PID_DIR/master.pid"
WORKER_PID_FILE="$PID_DIR/worker.pid"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
MASTER_LOG="$LOG_DIR/master.log"
WORKER_LOG="$LOG_DIR/worker.log"

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

# 创建必要的目录
setup_dirs() {
    mkdir -p "$PID_DIR" "$LOG_DIR"
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

# 启动 master 服务
start_master() {
    log_info "启动 Master 服务..."

    if is_running "$MASTER_PID_FILE"; then
        log_warn "Master 服务已在运行 (PID: $(cat $MASTER_PID_FILE))"
        return 0
    fi

    # 检查 Python 环境
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装"
        return 1
    fi

    # 检查依赖
    if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
        log_error "pyproject.toml 未找到"
        return 1
    fi

    # 安装依赖
    log_info "安装项目依赖..."
    cd "$PROJECT_ROOT" && pip3 install -e . -q 2>/dev/null || true

    # 启动服务
    cd "$MASTER_DIR"
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 5500 > "$MASTER_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$MASTER_PID_FILE"

    # 等待服务启动
    sleep 3

    if is_running "$MASTER_PID_FILE"; then
        log_info "Master 服务已启动 (PID: $pid)"
        log_info "日志文件: $MASTER_LOG"
    else
        log_error "Master 服务启动失败"
        return 1
    fi
}

# 启动 worker 服务
start_worker() {
    log_info "启动 Worker 服务..."

    if is_running "$WORKER_PID_FILE"; then
        log_warn "Worker 服务已在运行 (PID: $(cat $WORKER_PID_FILE))"
        return 0
    fi

    # 检查 Python 环境
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装"
        return 1
    fi

    # 检查依赖
    if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
        log_error "pyproject.toml 未找到"
        return 1
    fi

    # 安装依赖
    log_info "安装项目依赖..."
    cd "$PROJECT_ROOT" && pip3 install -e . -q 2>/dev/null || true

    # 启动服务
    cd "$WORKER_DIR"
    nohup python3 main.py > "$WORKER_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$WORKER_PID_FILE"

    # 等待服务启动
    sleep 3

    if is_running "$WORKER_PID_FILE"; then
        log_info "Worker 服务已启动 (PID: $pid)"
        log_info "日志文件: $WORKER_LOG"
    else
        log_error "Worker 服务启动失败"
        return 1
    fi
}

# 启动所有服务
start_all() {
    log_info "启动所有服务..."
    start_master
    if [ $? -eq 0 ]; then
        log_info "等待 Master 服务就绪..."
        sleep 5
    fi
    start_worker
}

# 主函数
main() {
    local cmd=${1:-all}

    setup_dirs

    case $cmd in
        master)
            start_master
            ;;
        worker)
            start_worker
            ;;
        all)
            start_all
            ;;
        *)
            echo "用法: $0 [master|worker|all]"
            exit 1
            ;;
    esac
}

main "$@"