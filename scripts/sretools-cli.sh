#!/bin/bash

# 项目启停脚本 - 启动脚本
# 用法: ./start.sh [master|worker|all] [--skip-deps|--force-deps|--no-wait]
#
# 命令:
#   start    - 启动服务 (默认)
#   stop     - 停止服务
#   restart  - 重启服务
#   status   - 查看服务状态

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MASTER_DIR="$PROJECT_ROOT/master"
WORKER_DIR="$PROJECT_ROOT/worker"

# PID 文件目录
PID_DIR="$PROJECT_ROOT/.pids"
MASTER_PID_FILE="$PID_DIR/master.pid"
WORKER_PID_FILE="$PID_DIR/worker.pid"

# 日志目录
MASTER_LOG="$MASTER_DIR/logs/master.log"
WORKER_LOG="$WORKER_DIR/logs/worker.log"

# 颜色定义
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
NC=$'\033[0m'

# ------------------------------
# 日志辅助函数
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

log_ok() {
    echo -e "${GREEN}[ OK ]${NC} $1"
}

# ------------------------------
# 环境检测
# ------------------------------
detect_python_cmd() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo ""
    fi
}

detect_pkg_manager() {
    if command -v uv &> /dev/null; then
        echo "uv"
    elif command -v pip3 &> /dev/null; then
        echo "pip3"
    elif command -v pip &> /dev/null; then
        echo "pip"
    else
        echo ""
    fi
}

# ------------------------------
# 目录与环境变量
# ------------------------------
setup_dirs() {
    mkdir -p "$PID_DIR" "$MASTER_DIR/logs" "$WORKER_DIR/logs"
}

# 加载 .env 文件（如果存在）
load_env_file() {
    local env_file="$1"
    if [ -f "$env_file" ]; then
        # 导出变量，但不覆盖已设置的环境变量
        while IFS='=' read -r key value; do
            # 跳过注释和空行
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            # 去除两端引号
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            # 只在变量未设置时导出
            if [ -z "${!key:-}" ]; then
                export "$key=$value"
            fi
        done < "$env_file"
        return 0
    fi
    return 1
}

load_project_envs() {
    load_env_file "$PROJECT_ROOT/.env" 2>/dev/null || true
    load_env_file "$MASTER_DIR/.env" 2>/dev/null || true
    load_env_file "$WORKER_DIR/.env" 2>/dev/null || true
}


# ------------------------------
# 进程管理辅助
# ------------------------------
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        # PID 存在但进程不存，清理文件
        rm -f "$pid_file"
    fi
    return 1
}

# 获取进程启动时间，用于区分是否新进程
get_pid_start_time() {
    local pid=$1
    if command -v ps &> /dev/null; then
        # Linux: ps -o lstart=
        local start
        start=$(ps -o lstart= -p "$pid" 2>/dev/null || echo "")
        if [ -n "$start" ]; then
            echo "$start"
            return 0
        fi
    fi
    # 回退方案：使用 /proc
    if [ -d "/proc/$pid" ]; then
        stat -c %Y "/proc/$pid" 2>/dev/null || echo "$(date +%s)"
        return 0
    fi
    echo "unknown"
}

# 健康检查：通过 HTTP 端口探测
health_check_http() {
    local port=$1
    local timeout=${2:-10}
    local url="http://127.0.0.1:${port}/"
    local count=0
    while [ $count -lt "$timeout" ]; do
        if command -v curl &> /dev/null; then
            if curl -fsS --max-time 2 "$url" &>/dev/null; then
                return 0
            fi
        else
            # 使用 /dev/tcp 回退
            (echo > "/dev/tcp/127.0.0.1/${port}") 2>/dev/null && return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    return 1
}

# ------------------------------
# 依赖安装（带缓存机制）
# ------------------------------
DEPS_CHECK_MARKER="$PROJECT_ROOT/.deps_installed"

install_dependencies() {
    local force=${1:-false}
    local pkg_manager
    local python_cmd
    pkg_manager=$(detect_pkg_manager)
    python_cmd=$(detect_python_cmd)

    if [ -z "$python_cmd" ]; then
        log_error "未找到 Python，请先安装 Python 3.12+"
        return 1
    fi

    if [ "$force" != "true" ] && [ -f "$DEPS_CHECK_MARKER" ]; then
        # 简单检查 pyproject.toml 是否比 marker 新
        if [ "$PROJECT_ROOT/pyproject.toml" -ot "$DEPS_CHECK_MARKER" ]; then
            # 同时检查 uv.lock 是否更新（如果存在）
            if [ ! -f "$PROJECT_ROOT/uv.lock" ] || [ "$PROJECT_ROOT/uv.lock" -ot "$DEPS_CHECK_MARKER" ]; then
                log_info "依赖已是最新，跳过安装 (使用 --force-deps 强制重新安装)"
                return 0
            fi
        fi
    fi

    log_step "检查并安装项目依赖..."

    if [ "$pkg_manager" = "uv" ]; then
        log_info "使用 uv 同步依赖 (推荐)"
        if (cd "$PROJECT_ROOT" && uv sync --quiet); then
            touch "$DEPS_CHECK_MARKER"
            log_ok "依赖安装完成"
            return 0
        else
            log_warn "uv sync 失败，回退到 pip"
        fi
    fi

    if [ -n "$pkg_manager" ]; then
        log_info "使用 $pkg_manager 安装依赖..."
        if (cd "$PROJECT_ROOT" && "$python_cmd" -m "$pkg_manager" install -e . -q); then
            touch "$DEPS_CHECK_MARKER"
            log_ok "依赖安装完成"
            return 0
        fi
    fi

    log_error "依赖安装失败，请手动执行: cd $PROJECT_ROOT && pip install -e ."
    return 1
}

# ------------------------------
# Master 启停
# ------------------------------
start_master() {
    local skip_deps=${1:-false}
    local wait_ready=${2:-true}

    log_info "启动 Master 服务..."

    if is_running "$MASTER_PID_FILE"; then
        local pid
        pid=$(cat "$MASTER_PID_FILE")
        log_warn "Master 服务已在运行 (PID: $pid)"
        return 0
    fi

    # 依赖检查
    if [ "$skip_deps" != "true" ]; then
        install_dependencies || return 1
    fi

    local python_cmd
    python_cmd=$(detect_python_cmd)
    if [ -z "$python_cmd" ]; then
        log_error "Python 3 未安装"
        return 1
    fi

    # 读取配置（从 .env 或 settings 默认值）
    local master_host="${HOST:-0.0.0.0}"
    local master_port="${PORT:-5500}"

    log_info "Master 监听地址: ${master_host}:${master_port}"

    # 通过 python -c 启动 uvicorn，传入与项目日志格式一致的 log_config
    # 使访问日志格式与 aiosqlite 等业务日志保持一致
    local actual_cmd
    if command -v uv &> /dev/null; then
        actual_cmd="cd '$MASTER_DIR' && uv run python main.py"
    else
        actual_cmd="cd '$MASTER_DIR' && PYTHONPATH='${MASTER_DIR}:${PROJECT_ROOT}' '${python_cmd}' main.py"
    fi

    nohup bash -c "$actual_cmd" > /dev/null 2>&1 &
    local pid=$!
    echo "$pid" > "$MASTER_PID_FILE"
    disown "$pid" 2>/dev/null || true

    # 快速检测是否立即崩溃
    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
        log_error "Master 服务启动失败 (进程已退出)"
        log_error "请查看日志: tail -n 50 $MASTER_LOG"
        if [ -f "$MASTER_LOG" ]; then
            echo "----- 最近日志 -----"
            tail -n 20 "$MASTER_LOG" || true
            echo "-------------------"
        fi
        rm -f "$MASTER_PID_FILE"
        return 1
    fi

    if [ "$wait_ready" = "true" ]; then
        log_info "等待 Master HTTP 服务就绪 (最多 30s)..."
        if health_check_http "$master_port" 30; then
            log_ok "Master 服务已启动 (PID: $pid) -> http://${master_host}:${master_port}"
        else
            log_warn "Master 进程运行中 (PID: $pid)，但 HTTP 端口尚未就绪"
            log_warn "日志文件: $MASTER_LOG"
        fi
    else
        log_ok "Master 服务已启动 (PID: $pid)"
    fi
    log_info "日志文件: $MASTER_LOG"
    return 0
}

# ------------------------------
# Worker 启停
# ------------------------------
start_worker() {
    local skip_deps=${1:-false}
    local wait_ready=${2:-true}

    log_info "启动 Worker 服务..."

    if is_running "$WORKER_PID_FILE"; then
        local pid
        pid=$(cat "$WORKER_PID_FILE")
        log_warn "Worker 服务已在运行 (PID: $pid)"
        return 0
    fi

    if [ "$skip_deps" != "true" ]; then
        install_dependencies || return 1
    fi

    local python_cmd
    python_cmd=$(detect_python_cmd)
    if [ -z "$python_cmd" ]; then
        log_error "Python 3 未安装"
        return 1
    fi

    local actual_cmd
    if command -v uv &> /dev/null; then
        # 从项目根运行，避免 worker/grpc 名称冲突
        actual_cmd="cd '$PROJECT_ROOT' && uv run python -m worker.main"
    else
        actual_cmd="cd '$PROJECT_ROOT' && '${python_cmd}' -m worker.main"
    fi

    nohup bash -c "$actual_cmd" > "$WORKER_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$WORKER_PID_FILE"
    disown "$pid" 2>/dev/null || true

    # 快速检测
    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
        log_error "Worker 服务启动失败 (进程已退出)"
        log_error "请查看日志: tail -n 50 $WORKER_LOG"
        if [ -f "$WORKER_LOG" ]; then
            echo "----- 最近日志 -----"
            tail -n 20 "$WORKER_LOG" || true
            echo "-------------------"
        fi
        rm -f "$WORKER_PID_FILE"
        return 1
    fi

    if [ "$wait_ready" = "true" ]; then
        # worker 是常驻进程，没有 HTTP 端口，额外等待几秒确认稳定
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 5 ]; do
            sleep 1
            count=$((count + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            log_ok "Worker 服务已启动 (PID: $pid)"
        else
            log_error "Worker 服务启动后异常退出"
            rm -f "$WORKER_PID_FILE"
            return 1
        fi
    else
        log_ok "Worker 服务已启动 (PID: $pid)"
    fi
    log_info "日志文件: $WORKER_LOG"
    return 0
}

# ------------------------------
# 批量操作
# ------------------------------
start_all() {
    local skip_deps=$1
    local wait_ready=$2
    log_info "========== 启动所有服务 =========="
    start_master "$skip_deps" "$wait_ready" || true
    # 给 Master 留点时间启动 gRPC
    sleep 3
    start_worker "$skip_deps" "$wait_ready" || true
}

# 停止 Master
stop_master() {
    local force=${1:-false}
    log_info "停止 Master 服务..."

    if ! is_running "$MASTER_PID_FILE"; then
        log_warn "Master 服务未运行"
        rm -f "$MASTER_PID_FILE"
        return 0
    fi

    local pid
    pid=$(cat "$MASTER_PID_FILE")

    # 优雅停止
    if [ "$force" = "true" ]; then
        log_warn "强制终止 Master (PID: $pid)"
        kill -9 "$pid" 2>/dev/null || true
    else
        log_info "发送 SIGTERM 至 Master (PID: $pid)"
        kill -TERM "$pid" 2>/dev/null || true

        # 等待最多 30s
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 30 ]; do
            sleep 1
            count=$((count + 1))
        done

        if kill -0 "$pid" 2>/dev/null; then
            log_warn "优雅停止超时 (30s)，强制终止..."
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi

    # 清理 PID 和可能的子进程（通过进程组）
    local pgid
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    if [ -n "$pgid" ] && [ "$pgid" != "-1" ]; then
        kill -TERM -- "-$pgid" 2>/dev/null || true
        sleep 1
        kill -9 -- "-$pgid" 2>/dev/null || true
    fi

    rm -f "$MASTER_PID_FILE"
    log_ok "Master 服务已停止"
}

# 停止 Worker
stop_worker() {
    local force=${1:-false}
    log_info "停止 Worker 服务..."

    if ! is_running "$WORKER_PID_FILE"; then
        log_warn "Worker 服务未运行"
        rm -f "$WORKER_PID_FILE"
        return 0
    fi

    local pid
    pid=$(cat "$WORKER_PID_FILE")

    if [ "$force" = "true" ]; then
        log_warn "强制终止 Worker (PID: $pid)"
        kill -9 "$pid" 2>/dev/null || true
    else
        log_info "发送 SIGTERM 至 Worker (PID: $pid)"
        kill -TERM "$pid" 2>/dev/null || true

        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 30 ]; do
            sleep 1
            count=$((count + 1))
        done

        if kill -0 "$pid" 2>/dev/null; then
            log_warn "优雅停止超时 (30s)，强制终止..."
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi

    # 清理进程组
    local pgid
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    if [ -n "$pgid" ] && [ "$pgid" != "-1" ]; then
        kill -TERM -- "-$pgid" 2>/dev/null || true
        sleep 1
        kill -9 -- "-$pgid" 2>/dev/null || true
    fi

    rm -f "$WORKER_PID_FILE"
    log_ok "Worker 服务已停止"
}

stop_all() {
    local force=$1
    log_info "========== 停止所有服务 =========="
    # 先停 worker，再停 master
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
        # 获取运行时长
        if command -v ps &> /dev/null; then
            local etime
            etime=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ' || echo "unknown")
            extra="运行时长: ${etime}"
        fi
        if [ -n "$default_port" ]; then
            # 端口检测
            (echo > "/dev/tcp/127.0.0.1/${default_port}") 2>/dev/null && extra="$extra | 端口 :${default_port} OK" || extra="$extra | 端口 :${default_port} ?"
        fi
    fi

    echo -e "  ${CYAN}$name${NC}  ${color}${status}${NC}  ${pid:+PID: $pid}  ${YELLOW}$extra${NC}"
}

show_status() {
    echo ""
    echo "=========================================="
    echo "          服务运行状态"
    echo "=========================================="
    print_status_line "Master" "$MASTER_PID_FILE" "5500"
    print_status_line "Worker" "$WORKER_PID_FILE"
    echo "=========================================="
    echo ""
    echo "Master 日志: $MASTER_LOG"
    echo "Worker 日志: $WORKER_LOG"
    echo "PID 目录: $PID_DIR"
    echo ""
}

# ------------------------------
# 帮助与参数解析
# ------------------------------
usage() {
    cat <<EOF
用法: $0 <command> [target] [options]

命令:
  start      启动服务 (默认命令)
  stop       停止服务
  restart    重启服务
  status     查看服务运行状态

目标:
  master     仅操作 Master 服务
  worker     仅操作 Worker 服务
  all        操作所有服务 (默认)

选项 (仅 start / restart):
  --skip-deps    跳过依赖检查与安装
  --force-deps   强制重新安装依赖
  --no-wait      启动后不等待服务就绪
  -f, --force    stop/restart 时强制终止 (SIGKILL)

示例:
  $0 start all                     # 启动所有服务
  $0 start master --skip-deps      # 跳过依赖安装启动 master
  $0 restart all                   # 重启所有服务
  $0 stop worker -f                # 强制停止 worker
  $0 status                        # 查看状态
EOF
}

# ------------------------------
# 主入口
# ------------------------------
main() {
    local command="start"
    local target="all"
    local skip_deps=false
    local force_deps=false
    local no_wait=false
    local force=false

    # 解析参数
    local positional=()
    for arg in "$@"; do
        case "$arg" in
            start|stop|restart|status|help|-h|--help)
                command=${arg/-h/help}
                command=${command/--help/help}
                ;;
            master|worker|all)
                target="$arg"
                ;;
            --skip-deps)
                skip_deps=true
                ;;
            --force-deps)
                force_deps=true
                ;;
            --no-wait)
                no_wait=true
                ;;
            -f|--force)
                force=true
                ;;
            -h|--help)
                command="help"
                ;;
            *)
                positional+=("$arg")
                ;;
        esac
    done

    if [ "$command" = "help" ]; then
        usage
        exit 0
    fi

    # 处理遗留参数：如果第一个位置参数是目标
    if [ ${#positional[@]} -gt 0 ]; then
        case "${positional[0]}" in
            master|worker|all)
                target="${positional[0]}"
                ;;
        esac
    fi

    setup_dirs
    load_project_envs

    local wait_ready=true
    if [ "$no_wait" = "true" ]; then
        wait_ready=false
    fi
    local real_skip_deps="$skip_deps"
    if [ "$force_deps" = "true" ]; then
        # 强制重新安装：删除 marker
        rm -f "$DEPS_CHECK_MARKER"
        real_skip_deps=false
    fi

    case "$command" in
        start)
            case "$target" in
                master)  start_master  "$real_skip_deps" "$wait_ready" ;;
                worker)  start_worker  "$real_skip_deps" "$wait_ready" ;;
                all)     start_all     "$real_skip_deps" "$wait_ready" ;;
            esac
            ;;
        stop)
            case "$target" in
                master)  stop_master  "$force" ;;
                worker)  stop_worker  "$force" ;;
                all)     stop_all     "$force" ;;
            esac
            ;;
        restart)
            log_info "执行重启操作..."
            case "$target" in
                master)
                    stop_master  "$force" || true
                    sleep 2
                    start_master "$real_skip_deps" "$wait_ready"
                    ;;
                worker)
                    stop_worker  "$force" || true
                    sleep 2
                    start_worker "$real_skip_deps" "$wait_ready"
                    ;;
                all)
                    stop_all     "$force" || true
                    sleep 3
                    start_all    "$real_skip_deps" "$wait_ready"
                    ;;
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
