#!/bin/bash

# 项目部署脚本
# 用法:
#   ./deploy.sh              # 交互式部署向导 (默认)
#   ./deploy.sh install      # 全新安装 (非交互，可用 --yes 跳过确认)
#   ./deploy.sh config       # 仅生成/更新 .env 配置文件
#   ./deploy.sh check        # 仅做环境检查
#   ./deploy.sh backup [dir] # 备份配置与数据 (默认备份到 backups/YYYYmmdd_HHMM/)
#
# 环境变量可覆盖交互:
#   DEPLOY_TYPE=master|worker|all
#   YES=1 跳过所有确认

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MASTER_DIR="$PROJECT_ROOT/master"
WORKER_DIR="$PROJECT_ROOT/worker"
BACKUP_DIR="$PROJECT_ROOT/backups"
LOG_DIR="$PROJECT_ROOT/logs"

# 颜色定义 (使用 $'...' 形式让 heredoc 中也能正确输出颜色)
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
PURPLE=$'\033[0;35m'
CYAN=$'\033[0;36m'
NC=$'\033[0m'

# ------------------------------
# 日志辅助
# ------------------------------
log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $1"; }
log_title() {
    echo ""
    echo "=========================================="
    echo -e "  ${PURPLE}$1${NC}"
    echo "=========================================="
}

# ------------------------------
# 公共工具
# ------------------------------
YES=${YES:-0}
confirm() {
    local prompt=$1
    local default=${2:-y}
    if [ "$YES" = "1" ] || [ "$YES" = "true" ]; then
        return 0
    fi
    local hint
    [ "$default" = "y" ] && hint="[Y/n]" || hint="[y/N]"
    read -rp "$prompt $hint " ans
    ans=${ans:-$default}
    [[ "$ans" =~ ^[Yy] ]] && return 0 || return 1
}

read_input() {
    local prompt=$1
    local default=$2
    local var_name=$3
    local value
    if [ -n "$default" ]; then
        read -rp "$prompt [$default]: " value
        value=${value:-$default}
    else
        read -rp "$prompt: " value
    fi
    # 通过引用赋值
    printf -v "$var_name" "%s" "$value"
}

detect_python_cmd() {
    if command -v python3 &>/dev/null; then echo "python3"
    elif command -v python &>/dev/null; then echo "python"
    else echo ""; fi
}

detect_pkg_manager() {
    if command -v uv &>/dev/null; then echo "uv"
    elif command -v pip3 &>/dev/null; then echo "pip3"
    elif command -v pip &>/dev/null; then echo "pip"
    else echo ""; fi
}

# ------------------------------
# 环境检查
# ------------------------------
check_python_env() {
    log_step "检查 Python 环境"
    local python_cmd
    python_cmd=$(detect_python_cmd)
    if [ -z "$python_cmd" ]; then
        log_error "未找到 Python，请先安装 Python 3.12+"
        return 1
    fi
    log_ok "Python 命令: $python_cmd"

    local version
    version=$("$python_cmd" -c 'import sys; print(".".join(map(str,sys.version_info[:2])))' 2>/dev/null || echo "0.0")
    log_info "Python 版本: $version"

    if ! "$python_cmd" -c 'import sys; assert sys.version_info >= (3,12)' 2>/dev/null; then
        log_error "Python 版本过低，需要 3.12+ (当前: $version)"
        return 1
    fi
    export PYTHON_CMD="$python_cmd"
    log_ok "Python 环境检查通过"
}

check_package_manager() {
    log_step "检查包管理器"
    local pkg
    pkg=$(detect_pkg_manager)
    if [ -z "$pkg" ]; then
        log_error "未找到包管理器 (uv 或 pip)，请先安装"
        log_info "推荐安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        return 1
    fi
    log_ok "包管理器: $pkg"
    export PKG_MANAGER="$pkg"
}

check_project_files() {
    log_step "检查项目文件"
    local required=(
        "$PROJECT_ROOT/pyproject.toml"
        "$MASTER_DIR/main.py"
        "$WORKER_DIR/main.py"
    )
    for f in "${required[@]}"; do
        if [ ! -f "$f" ]; then
            log_error "缺少必要文件: $f"
            return 1
        fi
    done
    log_ok "项目文件完整"
}

check_disk_space() {
    log_step "检查磁盘空间"
    local min_mb=500
    local avail
    avail=$(df -Pm "$PROJECT_ROOT" 2>/dev/null | awk 'END{print $4}')
    if [ -n "$avail" ] && [ "$avail" -ge "$min_mb" ] 2>/dev/null; then
        log_ok "可用空间: ${avail}MB"
    elif [ -z "$avail" ]; then
        log_warn "无法获取磁盘空间信息，继续..."
    else
        log_warn "磁盘空间不足 ${min_mb}MB (可用: ${avail}MB)，但继续尝试..."
    fi
}

preflight_check() {
    log_title "部署前置检查"
    check_python_env || return 1
    check_package_manager || return 1
    check_project_files || return 1
    check_disk_space || true
    log_ok "所有前置检查通过"
}

# ------------------------------
# 依赖安装
# ------------------------------
install_dependencies() {
    log_step "安装项目依赖"
    local python_cmd=${PYTHON_CMD:-$(detect_python_cmd)}
    local pkg=${PKG_MANAGER:-$(detect_pkg_manager)}

    if [ -z "$python_cmd" ]; then
        log_error "Python 未找到，无法安装依赖"
        return 1
    fi

    if [ "$pkg" = "uv" ]; then
        log_info "使用 uv sync 同步依赖 (推荐)"
        if (cd "$PROJECT_ROOT" && uv sync); then
            log_ok "uv sync 完成"
            return 0
        fi
        log_warn "uv sync 失败，回退 pip"
    fi

    log_info "使用 pip 安装 (pip install -e .)"
    if (cd "$PROJECT_ROOT" && "$python_cmd" -m pip install -e .); then
        log_ok "依赖安装完成"
        return 0
    fi
    log_error "依赖安装失败"
    return 1
}

# ------------------------------
# 目录结构初始化
# ------------------------------
setup_directories() {
    log_step "创建必要目录"
    mkdir -p \
        "$LOG_DIR" \
        "$PROJECT_ROOT/.pids" \
        "$BACKUP_DIR" \
        "$MASTER_DIR/log" \
        "$MASTER_DIR/data/gateways/install" \
        "$MASTER_DIR/data/gateways/backup" \
        "$WORKER_DIR/log" \
        "$WORKER_DIR/data"
    log_ok "目录结构已创建"
}

# ------------------------------
# 配置文件生成 (Master)
# ------------------------------
generate_random_secret() {
    if command -v openssl &>/dev/null; then
        openssl rand -base64 32 2>/dev/null || tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48
    else
        tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48
    fi
}

configure_master_interactive() {
    log_title "Master 服务配置"
    echo ""

    echo "数据库类型:"
    echo "  1) SQLite (默认，适合开发/单机)"
    echo "  2) PostgreSQL (推荐生产环境)"
    read -rp "请选择 [1-2]: " db_choice
    case "${db_choice:-1}" in
        2)
            read_input "  PostgreSQL 主机" "localhost" DB_HOST
            read_input "  PostgreSQL 端口" "5432" DB_PORT
            read_input "  PostgreSQL 用户名" "postgres" DB_USER
            read_input "  PostgreSQL 密码" "" DB_PASSWORD
            read_input "  PostgreSQL 数据库名" "sre_tools" DB_NAME
            DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            ;;
        *)
            DATABASE_URL="sqlite:///${MASTER_DIR}/amisadmin.db?check_same_thread=False"
            ;;
    esac

    read_input "服务监听地址" "0.0.0.0" MASTER_HOST
    read_input "服务端口" "5500" MASTER_PORT
    read_input "日志级别 (DEBUG/INFO/WARNING/ERROR)" "INFO" MASTER_LOG_LEVEL
    read_input "管理员秘钥 (secret_key)" "$(generate_random_secret)" SECRET_KEY
}

write_master_env() {
    local env_file="$MASTER_DIR/.env"
    log_info "生成 Master 配置文件: $env_file"
    cat > "$env_file" <<EOF
# ============================================================
# Master 服务配置文件
# 由 deploy.sh 生成于 $(date '+%Y-%m-%d %H:%M:%S')
# 修改后需要重启 Master 服务生效: ./scripts/start.sh restart master
# ============================================================

# ----- 数据库 -----
DATABASE_URL=${DATABASE_URL}

# ----- 服务 -----
HOST=${MASTER_HOST:-0.0.0.0}
PORT=${MASTER_PORT:-5500}
DEBUG=false

# ----- 站点 -----
SITE_TITLE=SRE Tools
LANGUAGE=zh_CN

# ----- 日志 -----
LOG_LEVEL=${MASTER_LOG_LEVEL:-INFO}
LOG_FILE=${PROJECT_ROOT}/logs/master.log
ERROR_LOG_FILE=${PROJECT_ROOT}/logs/master-error.log

# ----- 安全 -----
SECRET_KEY=${SECRET_KEY}
ALLOW_ORIGINS=*

# ----- 网关 -----
GATEWAY_INSTALL_ROOT=${MASTER_DIR}/data/gateways/install
GATEWAY_BACKUP_ROOT=${MASTER_DIR}/data/gateways/backup
EOF
    chmod 600 "$env_file"
    log_ok "Master 配置已写入"
}

# ------------------------------
# 配置文件生成 (Worker)
# ------------------------------
configure_worker_interactive() {
    log_title "Worker 服务配置"
    echo ""

    read_input "Master HTTP 地址" "http://localhost:5500" CENTRAL_SERVERS
    read_input "Master gRPC 地址 (host:port)" "localhost:50051" GRPC_SERVER_ADDRESS
    read_input "本 Worker ID (唯一标识)" "worker_$(hostname 2>/dev/null || echo 1)" WORKER_ID
    read_input "日志级别" "INFO" WORKER_LOG_LEVEL
    read_input "日志收集间隔(秒)" "5" LOG_COLLECT_INTERVAL
    read_input "指标收集间隔(秒)" "10" METRIC_COLLECT_INTERVAL
    read_input "本地存储路径" "${WORKER_DIR}/data" LOCAL_STORAGE_PATH
}

write_worker_env() {
    local env_file="$WORKER_DIR/.env"
    log_info "生成 Worker 配置文件: $env_file"
    cat > "$env_file" <<EOF
# ============================================================
# Worker 服务配置文件
# 由 deploy.sh 生成于 $(date '+%Y-%m-%d %H:%M:%S')
# 修改后需要重启 Worker 服务生效: ./scripts/start.sh restart worker
# ============================================================

# ----- Master 端 -----
CENTRAL_SERVERS=${CENTRAL_SERVERS:-http://localhost:5500}
CENTRAL_TIMEOUT=10
CENTRAL_RETRY_TIMES=3

# ----- gRPC -----
GRPC_ENABLED=true
GRPC_SERVER_ADDRESS=${GRPC_SERVER_ADDRESS:-localhost:50051}
GRPC_ONLY=false

# ----- Worker 标识 -----
WORKER_ID=${WORKER_ID:-worker_1}

# ----- 日志 -----
LOG_LEVEL=${WORKER_LOG_LEVEL:-INFO}
LOG_FILE=${PROJECT_ROOT}/logs/worker.log
ERROR_LOG_FILE=${PROJECT_ROOT}/logs/worker-error.log

# ----- 日志收集 -----
LOG_COLLECT_INTERVAL=${LOG_COLLECT_INTERVAL:-5}
LOG_BATCH_SIZE=1000
LOG_QUEUE_SIZE=10000

# ----- 指标收集 -----
METRIC_COLLECT_INTERVAL=${METRIC_COLLECT_INTERVAL:-10}
METRIC_BATCH_SIZE=500

# ----- 存储 -----
LOCAL_STORAGE_PATH=${LOCAL_STORAGE_PATH:-${WORKER_DIR}/data}
MAX_LOCAL_STORAGE_SIZE=1024

# ----- 网络 -----
ALLOW_ORIGINS=*

# ----- 安全 -----
API_KEY=
SECRET_KEY=$(generate_random_secret)
EOF
    chmod 600 "$env_file"
    log_ok "Worker 配置已写入"
}

# ------------------------------
# 数据库迁移 (Master)
# ------------------------------
run_database_migrations() {
    log_step "执行数据库初始化/Migration"
    local python_cmd=${PYTHON_CMD:-$(detect_python_cmd)}
    if [ -z "$python_cmd" ]; then
        log_warn "Python 不可用，跳过数据库初始化"
        return 0
    fi

    # 优先使用 alembic（如果配置了）
    if [ -f "$MASTER_DIR/alembic.ini" ] && command -v alembic &>/dev/null; then
        log_info "使用 Alembic 升级数据库..."
        if (cd "$MASTER_DIR" && alembic upgrade head); then
            log_ok "Alembic migration 完成"
            return 0
        fi
        log_warn "Alembic 执行失败，回退到 ORM 自动建表"
    fi

    # 回退：直接运行 main.py lifespan 创建表
    log_info "通过 Master 的 FastAPI lifespan 自动建表..."
    if command -v timeout &>/dev/null; then
        timeout 30 "$python_cmd" -c "
import sys, os, asyncio
sys.path.insert(0, '$MASTER_DIR')
os.environ.setdefault('PYTHONPATH', '$MASTER_DIR:$PROJECT_ROOT')
from main import app
from core.globals import site
from sqlmodel import SQLModel
# 触发 lifespan 中的建表逻辑
import asyncio
from contextlib import asynccontextmanager

async def main():
    async with app.router.lifespan_context(app):
        await site.db.async_run_sync(SQLModel.metadata.create_all, is_session=False)
        print('Database tables created/verified')

asyncio.run(main())
" 2>&1 | tail -n 20 && log_ok "数据库初始化完成" || log_warn "数据库初始化可能未完成 (详见日志)"
    else
        log_warn "缺少 timeout 命令，跳过自动建表"
    fi
}

# ------------------------------
# 备份
# ------------------------------
create_backup() {
    local target_dir=${1:-}
    if [ -z "$target_dir" ]; then
        target_dir="$BACKUP_DIR/backup_$(date '+%Y%m%d_%H%M%S')"
    fi
    log_step "备份配置与数据到: $target_dir"
    mkdir -p "$target_dir"

    # 备份 .env 文件
    [ -f "$MASTER_DIR/.env" ] && cp -a "$MASTER_DIR/.env" "$target_dir/master.env.bak" && log_info "已备份 master/.env"
    [ -f "$WORKER_DIR/.env" ] && cp -a "$WORKER_DIR/.env" "$target_dir/worker.env.bak" && log_info "已备份 worker/.env"
    [ -f "$PROJECT_ROOT/.env" ] && cp -a "$PROJECT_ROOT/.env" "$target_dir/root.env.bak" && log_info "已备份根目录 .env"

    # 备份数据库 (SQLite)
    local sqlite_db="$MASTER_DIR/amisadmin.db"
    if [ -f "$sqlite_db" ]; then
        cp -a "$sqlite_db" "$target_dir/amisadmin.db.bak"
        log_info "已备份 SQLite 数据库 ($(du -h "$sqlite_db" | cut -f1))"
    fi

    # 备份 worker 数据目录
    if [ -d "$WORKER_DIR/data" ] && [ -n "$(ls -A "$WORKER_DIR/data" 2>/dev/null)" ]; then
        tar czf "$target_dir/worker_data.tgz" -C "$WORKER_DIR" data 2>/dev/null \
            && log_info "已备份 worker/data (worker_data.tgz)" \
            || log_warn "worker/data 备份失败"
    fi

    # 备份配置脚本
    [ -d "$MASTER_DIR/data" ] && [ -n "$(ls -A "$MASTER_DIR/data" 2>/dev/null)" ] && \
        tar czf "$target_dir/master_data.tgz" -C "$MASTER_DIR" data 2>/dev/null \
        && log_info "已备份 master/data (master_data.tgz)"

    log_ok "备份完成: $target_dir"
    echo "  $(du -sh "$target_dir" 2>/dev/null | cut -f1)"
    echo ""
}

restore_from_backup() {
    local backup_dir=$1
    if [ ! -d "$backup_dir" ]; then
        log_error "备份目录不存在: $backup_dir"
        return 1
    fi
    log_step "从备份恢复: $backup_dir"
    confirm "确认要恢复备份吗？当前 .env 和数据将被覆盖！" "n" || return 1

    [ -f "$backup_dir/master.env.bak" ] && cp -a "$backup_dir/master.env.bak" "$MASTER_DIR/.env" && log_info "已恢复 master/.env"
    [ -f "$backup_dir/worker.env.bak" ] && cp -a "$backup_dir/worker.env.bak" "$WORKER_DIR/.env" && log_info "已恢复 worker/.env"
    [ -f "$backup_dir/root.env.bak" ] && cp -a "$backup_dir/root.env.bak" "$PROJECT_ROOT/.env" && log_info "已恢复根目录 .env"
    [ -f "$backup_dir/amisadmin.db.bak" ] && cp -a "$backup_dir/amisadmin.db.bak" "$MASTER_DIR/amisadmin.db" && log_info "已恢复 SQLite 数据库"

    if [ -f "$backup_dir/worker_data.tgz" ]; then
        tar xzf "$backup_dir/worker_data.tgz" -C "$WORKER_DIR" && log_info "已恢复 worker/data"
    fi
    if [ -f "$backup_dir/master_data.tgz" ]; then
        tar xzf "$backup_dir/master_data.tgz" -C "$MASTER_DIR" && log_info "已恢复 master/data"
    fi
    log_ok "恢复完成，请重启服务"
}

# ------------------------------
# 部署模式选择
# ------------------------------
select_deploy_type() {
    # 环境变量优先
    if [ -n "${DEPLOY_TYPE:-}" ]; then
        case "$DEPLOY_TYPE" in
            master|worker|all)
                log_info "通过环境变量 DEPLOY_TYPE=$DEPLOY_TYPE 选择部署类型"
                return 0
                ;;
        esac
    fi

    echo ""
    echo "请选择部署类型:"
    echo "  1) 仅部署 Master (控制中心 + Web)"
    echo "  2) 仅部署 Worker (采集/执行节点)"
    echo "  3) 同时部署 Master 和 Worker (单机全量，默认)"
    echo ""
    read -rp "请输入选项 [1-3]: " choice
    case "${choice:-3}" in
        1) DEPLOY_TYPE="master" ;;
        2) DEPLOY_TYPE="worker" ;;
        3) DEPLOY_TYPE="all" ;;
        *) log_error "无效选项"; exit 1 ;;
    esac
    log_info "已选择部署类型: $DEPLOY_TYPE"
}

# ------------------------------
# 核心流程
# ------------------------------
do_install() {
    log_title "项目部署: 全新安装"

    # 0. 运行中服务提前停
    if [ -x "$SCRIPT_DIR/stop.sh" ]; then
        echo ""
        if confirm "是否先停止正在运行的 Master/Worker 服务？" "y"; then
            log_info "停止现有服务..."
            "$SCRIPT_DIR/stop.sh" stop all || true
        fi
    fi

    # 1. 前置检查
    preflight_check || exit 1

    # 2. 目录结构
    setup_directories

    # 3. 备份（已有配置）
    local has_old_config=false
    if [ -f "$MASTER_DIR/.env" ] || [ -f "$WORKER_DIR/.env" ]; then
        has_old_config=true
    fi
    if [ "$has_old_config" = "true" ]; then
        echo ""
        if confirm "检测到已有配置，是否备份？" "y"; then
            create_backup
        fi
    fi

    # 4. 依赖安装
    echo ""
    if confirm "是否安装 Python 依赖？" "y"; then
        install_dependencies || {
            log_error "依赖安装失败，部署中止"
            exit 1
        }
    fi

    # 5. 选择部署类型
    select_deploy_type

    # 6. 配置引导
    case "$DEPLOY_TYPE" in
        master)
            if [ "$has_old_config" = "true" ] && [ -f "$MASTER_DIR/.env" ]; then
                echo ""
                if ! confirm "检测到已有 master/.env，是否重新生成配置？" "n"; then
                    log_info "保留现有 master 配置"
                else
                    configure_master_interactive
                    write_master_env
                fi
            else
                configure_master_interactive
                write_master_env
            fi
            ;;
        worker)
            if [ "$has_old_config" = "true" ] && [ -f "$WORKER_DIR/.env" ]; then
                echo ""
                if ! confirm "检测到已有 worker/.env，是否重新生成配置？" "n"; then
                    log_info "保留现有 worker 配置"
                else
                    configure_worker_interactive
                    write_worker_env
                fi
            else
                configure_worker_interactive
                write_worker_env
            fi
            ;;
        all)
            if [ -f "$MASTER_DIR/.env" ]; then
                echo ""
                if ! confirm "检测到已有 master/.env，是否重新生成 Master 配置？" "n"; then
                    log_info "保留现有 master 配置"
                else
                    configure_master_interactive
                    write_master_env
                fi
            else
                configure_master_interactive
                write_master_env
            fi
            echo ""
            if [ -f "$WORKER_DIR/.env" ]; then
                if ! confirm "检测到已有 worker/.env，是否重新生成 Worker 配置？" "n"; then
                    log_info "保留现有 worker 配置"
                else
                    configure_worker_interactive
                    write_worker_env
                fi
            else
                configure_worker_interactive
                write_worker_env
            fi
            ;;
    esac

    # 7. 数据库迁移 (仅 master/all)
    if [ "$DEPLOY_TYPE" = "master" ] || [ "$DEPLOY_TYPE" = "all" ]; then
        echo ""
        if confirm "是否初始化/升级 Master 数据库？" "y"; then
            run_database_migrations || true
        fi
    fi

    # 8. 设置脚本可执行权限
    chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true
    chmod +x "$WORKER_DIR/run.sh" 2>/dev/null || true

    # 9. 完成
    echo ""
    echo "=========================================="
    log_ok "部署完成！"
    echo "=========================================="
    echo ""
    echo "下一步操作:"
    case "$DEPLOY_TYPE" in
        master)
            echo "  启动 Master:  $SCRIPT_DIR/start.sh start master"
            echo "  查看状态:    $SCRIPT_DIR/start.sh status"
            echo "  访问地址:    http://<host>:${MASTER_PORT:-5500}/admin"
            echo "               默认管理员账号: admin / admin"
            ;;
        worker)
            echo "  先确认 Master 已启动且 gRPC 端口 ${GRPC_SERVER_ADDRESS:-localhost:50051} 可连通"
            echo "  启动 Worker: $SCRIPT_DIR/start.sh start worker"
            echo "  查看状态:   $SCRIPT_DIR/start.sh status"
            ;;
        all)
            echo "  一键启动:    $SCRIPT_DIR/start.sh start all"
            echo "  单独启动:    $SCRIPT_DIR/start.sh start master  (先启 Master)"
            echo "               $SCRIPT_DIR/start.sh start worker  (再启 Worker)"
            echo "  查看状态:    $SCRIPT_DIR/start.sh status"
            echo "  Web 访问:    http://<host>:${MASTER_PORT:-5500}/admin  (admin/admin)"
            ;;
    esac
    echo ""
    echo "其他常用命令:"
    echo "  停止服务:    $SCRIPT_DIR/stop.sh"
    echo "  重启服务:    $SCRIPT_DIR/start.sh restart all"
    echo "  查看日志:    tail -f $LOG_DIR/master.log  $LOG_DIR/worker.log"
    echo ""
}

do_config_only() {
    log_title "仅生成/更新配置文件"
    setup_directories
    select_deploy_type
    case "$DEPLOY_TYPE" in
        master) configure_master_interactive; write_master_env ;;
        worker) configure_worker_interactive; write_worker_env ;;
        all)
            configure_master_interactive; write_master_env
            echo ""
            configure_worker_interactive; write_worker_env
            ;;
    esac
    log_ok "配置生成完成"
}

usage() {
    cat <<EOF
${CYAN}项目部署脚本${NC}

${GREEN}用法:${NC}
  $0 [command] [options]

${GREEN}命令:${NC}
  (无)         交互式部署向导 (默认执行 install 流程)
  install      全新安装部署 (前置检查 → 依赖 → 目录 → 配置 → 数据库)
  config       仅生成/更新 .env 配置文件
  check        仅做部署环境前置检查 (不修改任何文件)
  backup [dir] 备份配置与数据到指定目录 (默认 backups/backup_时间戳/)
  restore <dir>  从指定备份目录恢复配置与数据
  -h, --help   显示本帮助

${GREEN}环境变量:${NC}
  DEPLOY_TYPE=master|worker|all   跳过部署类型选择
  YES=1                           跳过所有交互确认 (非交互部署)

${GREEN}示例:${NC}
  $0                                # 交互式向导
  $0 install                       # 全新安装
  DEPLOY_TYPE=worker YES=1 $0 install   # 非交互仅部署 worker
  $0 config                         # 只写配置文件
  $0 check                          # 环境预检
  $0 backup                         # 备份
  $0 restore backups/backup_20250101_120000
EOF
}

# ------------------------------
# 主入口
# ------------------------------
main() {
    local cmd=${1:-install}
    case "$cmd" in
        -h|--help|help)
            usage
            exit 0
            ;;
        install|"")
            shift 2>/dev/null || true
            do_install
            ;;
        config)
            do_config_only
            ;;
        check)
            preflight_check
            ;;
        backup)
            setup_directories
            create_backup "${2:-}"
            ;;
        restore)
            if [ -z "${2:-}" ]; then
                log_error "请指定备份目录: $0 restore <backup_dir>"
                exit 1
            fi
            restore_from_backup "$2"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
