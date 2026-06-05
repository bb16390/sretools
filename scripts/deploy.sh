#!/bin/bash

# 项目部署配置向导脚本
# 用法: ./deploy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MASTER_DIR="$PROJECT_ROOT/master"
WORKER_DIR="$PROJECT_ROOT/worker"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 读取用户输入（带默认值）
read_input() {
    local prompt=$1
    local default=$2
    local var_name=$3

    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " value
        value=${value:-$default}
    else
        read -p "$prompt: " value
    fi

    eval "$var_name='$value'"
}

# 选择部署类型
select_deploy_type() {
    echo ""
    echo "=========================================="
    echo "        项目部署配置向导"
    echo "=========================================="
    echo ""
    echo "请选择部署类型:"
    echo "  1) 仅部署 Master"
    echo "  2) 仅部署 Worker"
    echo "  3) 同时部署 Master 和 Worker"
    echo ""
    read -p "请输入选项 [1-3]: " choice

    case $choice in
        1)
            DEPLOY_TYPE="master"
            ;;
        2)
            DEPLOY_TYPE="worker"
            ;;
        3)
            DEPLOY_TYPE="all"
            ;;
        *)
            log_error "无效选项"
            exit 1
            ;;
    esac

    log_info "已选择: $DEPLOY_TYPE"
}

# 配置 Master
configure_master() {
    log_step "配置 Master 服务..."

    echo ""
    echo "--- Master 配置 ---"

    # 数据库类型
    echo ""
    echo "数据库类型:"
    echo "  1) SQLite (默认，适合开发)"
    echo "  2) PostgreSQL"
    read -p "请选择 [1-2]: " db_choice

    case $db_choice in
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
    read_input "日志级别 (DEBUG/INFO/WARNING/ERROR)" "INFO" LOG_LEVEL
    read_input "秘钥 (secret_key)" "$(openssl rand -base64 32 2>/dev/null || echo 'your-secret-key-here')" SECRET_KEY
}

# 生成 Master .env 文件
generate_master_env() {
    log_info "生成 Master 配置文件..."

    cat > "$MASTER_DIR/.env" << EOF
# Master 服务配置
# 由 deploy.sh 脚本生成

# 数据库配置
DATABASE_URL=${DATABASE_URL}

# 服务配置
HOST=${MASTER_HOST}
PORT=${MASTER_PORT}
DEBUG=false

# 日志配置
LOG_LEVEL=${LOG_LEVEL}

# 安全配置
SECRET_KEY=${SECRET_KEY}

# 允许的来源
ALLOW_ORIGINS=*

# 语言
LANGUAGE=zh_CN
EOF

    log_info "Master 配置文件已生成: $MASTER_DIR/.env"
}

# 配置 Worker
configure_worker() {
    log_step "配置 Worker 服务..."

    echo ""
    echo "--- Worker 配置 ---"

    read_input "Master 服务地址 (gRPC)" "localhost:50051" GRPC_SERVER_ADDRESS
    read_input "Worker ID" "worker_1" WORKER_ID
    read_input "日志级别 (DEBUG/INFO/WARNING/ERROR)" "INFO" LOG_LEVEL
    read_input "日志收集间隔 (秒)" "5" LOG_COLLECT_INTERVAL
    read_input "指标收集间隔 (秒)" "10" METRIC_COLLECT_INTERVAL
    read_input "本地存储路径" "${WORKER_DIR}/data" LOCAL_STORAGE_PATH
}

# 生成 Worker .env 文件
generate_worker_env() {
    log_info "生成 Worker 配置文件..."

    cat > "$WORKER_DIR/.env" << EOF
# Worker 服务配置
# 由 deploy.sh 脚本生成

# 中心端配置
CENTRAL_SERVERS=http://localhost:5500
CENTRAL_TIMEOUT=10
CENTRAL_RETRY_TIMES=3

# gRPC 配置
GRPC_ENABLED=true
GRPC_SERVER_ADDRESS=${GRPC_SERVER_ADDRESS}
GRPC_ONLY=false

# Worker 配置
WORKER_ID=${WORKER_ID}

# 日志配置
LOG_LEVEL=${LOG_LEVEL}
LOG_DIR=${WORKER_DIR}/log/worker.log

# 日志收集配置
LOG_COLLECT_INTERVAL=${LOG_COLLECT_INTERVAL}
LOG_BATCH_SIZE=1000
LOG_QUEUE_SIZE=10000

# 指标配置
METRIC_COLLECT_INTERVAL=${METRIC_COLLECT_INTERVAL}
METRIC_BATCH_SIZE=500

# 存储配置
LOCAL_STORAGE_PATH=${LOCAL_STORAGE_PATH}
MAX_LOCAL_STORAGE_SIZE=1024

# 网络配置
ALLOW_ORIGINS=*

# 安全配置
API_KEY=
SECRET_KEY=your-secret-key-here
EOF

    log_info "Worker 配置文件已生成: $WORKER_DIR/.env"
}

# 主函数
main() {
    select_deploy_type

    case $DEPLOY_TYPE in
        master)
            configure_master
            generate_master_env
            ;;
        worker)
            configure_worker
            generate_worker_env
            ;;
        all)
            configure_master
            generate_master_env
            echo ""
            configure_worker
            generate_worker_env
            ;;
    esac

    echo ""
    echo "=========================================="
    log_info "部署配置完成!"
    echo "=========================================="
    echo ""
    echo "下一步操作:"
    echo "  1. 启动服务: ./scripts/start.sh all"
    echo "  2. 停止服务: ./scripts/stop.sh all"
    echo ""
}

main "$@"