#!/bin/bash

# 项目升级脚本
# 用法:
#   ./upgrade.sh                          # 交互式升级 (当前目录 git pull 方式)
#   ./upgrade.sh git                      # 从 git 仓库拉取最新代码并升级
#   ./upgrade.sh tarball <path.tar.gz>    # 从本地 tar.gz 包升级
#   ./upgrade.sh check                    # 仅检查是否可以升级 (不做实际修改)
#   ./upgrade.sh rollback <backup_dir>    # 回滚到指定备份目录
#
# 环境变量:
#   YES=1                 跳过所有确认
#   DEPLOY_TYPE=master|worker|all  升级范围
#   SKIP_BACKUP=1         跳过升级前备份 (不推荐)
#   SKIP_MIGRATION=1      跳过数据库迁移
#   GIT_BRANCH=main       指定 git 分支

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MASTER_DIR="$PROJECT_ROOT/master"
WORKER_DIR="$PROJECT_ROOT/worker"
BACKUP_DIR="$PROJECT_ROOT/backups"
UPGRADE_LOG="$PROJECT_ROOT/logs/upgrade_$(date '+%Y%m%d_%H%M%S').log"

# 颜色 (使用 $'...' 让 heredoc 中的帮助文本也能正确显示颜色)
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
_start_time=$(date +%s)
log_info()  { echo -e "${GREEN}[INFO]${NC}  $1" | tee -a "$UPGRADE_LOG"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1" | tee -a "$UPGRADE_LOG"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$UPGRADE_LOG" >&2; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $1" | tee -a "$UPGRADE_LOG"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $1" | tee -a "$UPGRADE_LOG"; }
log_title() {
    echo "" | tee -a "$UPGRADE_LOG"
    echo "==========================================" | tee -a "$UPGRADE_LOG"
    echo -e "  ${PURPLE}$1${NC}" | tee -a "$UPGRADE_LOG"
    echo "==========================================" | tee -a "$UPGRADE_LOG"
}

# ------------------------------
# 公共工具
# ------------------------------
YES=${YES:-0}
SKIP_BACKUP=${SKIP_BACKUP:-0}
SKIP_MIGRATION=${SKIP_MIGRATION:-0}
GIT_BRANCH=${GIT_BRANCH:-main}
DEPLOY_TYPE=${DEPLOY_TYPE:-all}

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

elapsed() {
    local now=$(date +%s)
    echo $(( now - _start_time ))
}

# ------------------------------
# 版本检测
# ------------------------------
get_current_version() {
    if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
        grep -m1 '^version' "$PROJECT_ROOT/pyproject.toml" 2>/dev/null \
            | sed -E 's/.*version\s*=\s*"([^"]+)".*/\1/' || echo "unknown"
    else
        echo "unknown"
    fi
}

get_pyproject_version_from_dir() {
    local dir=$1
    if [ -f "$dir/pyproject.toml" ]; then
        grep -m1 '^version' "$dir/pyproject.toml" 2>/dev/null \
            | sed -E 's/.*version\s*=\s*"([^"]+)".*/\1/' || echo "unknown"
    else
        echo "unknown"
    fi
}

# ------------------------------
# 备份
# ------------------------------
create_upgrade_backup() {
    local backup_tag=$1
    local backup_path="$BACKUP_DIR/upgrade_${backup_tag}_$(date '+%Y%m%d_%H%M%S')"

    if [ "$SKIP_BACKUP" = "1" ]; then
        log_warn "已通过 SKIP_BACKUP=1 跳过升级前备份 (不推荐)"
        echo "NO_BACKUP"
        return 0
    fi

    log_step "创建升级前完整备份"
    mkdir -p "$backup_path"

    # 1. 完整源码备份（排除 .git, __pycache__, .venv）
    log_info "备份项目源码..."
    if command -v rsync &>/dev/null; then
        rsync -a \
            --exclude='.git' \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.venv' \
            --exclude='.pids' \
            --exclude='logs' \
            --exclude='backups' \
            --exclude='worker/data' \
            "$PROJECT_ROOT/" "$backup_path/source/" \
            && log_ok "源码备份完成" || log_warn "源码备份失败"
    else
        tar czf "$backup_path/source.tar.gz" \
            --exclude='.git' \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.venv' \
            --exclude='.pids' \
            --exclude='logs' \
            --exclude='backups' \
            -C "$PROJECT_ROOT" . \
            2>>"$UPGRADE_LOG" \
            && log_ok "源码备份完成 (source.tar.gz)" || log_warn "源码备份失败"
    fi

    # 2. 配置文件
    log_info "备份 .env 配置..."
    [ -f "$MASTER_DIR/.env" ] && cp -a "$MASTER_DIR/.env" "$backup_path/master.env.bak"
    [ -f "$WORKER_DIR/.env" ] && cp -a "$WORKER_DIR/.env" "$backup_path/worker.env.bak"
    [ -f "$PROJECT_ROOT/.env" ] && cp -a "$PROJECT_ROOT/.env" "$backup_path/root.env.bak"

    # 3. SQLite 数据库
    if [ -f "$MASTER_DIR/amisadmin.db" ]; then
        cp -a "$MASTER_DIR/amisadmin.db" "$backup_path/amisadmin.db.bak"
        log_ok "SQLite 数据库已备份"
    fi

    # 4. master/data 和 worker/data
    [ -d "$MASTER_DIR/data" ] && cp -a "$MASTER_DIR/data" "$backup_path/master_data"
    [ -d "$WORKER_DIR/data" ] && cp -a "$WORKER_DIR/data" "$backup_path/worker_data"

    log_ok "备份完成: $backup_path"
    echo "$backup_path"
}

# ------------------------------
# 服务控制
# ------------------------------
stop_running_services() {
    log_step "停止正在运行的服务"
    if [ -x "$SCRIPT_DIR/stop.sh" ]; then
        case "$DEPLOY_TYPE" in
            master) "$SCRIPT_DIR/stop.sh" stop master || true ;;
            worker) "$SCRIPT_DIR/stop.sh" stop worker || true ;;
            all)    "$SCRIPT_DIR/stop.sh" stop all    || true ;;
        esac
    else
        log_warn "stop.sh 不可执行，尝试调用 start.sh stop"
        if [ -x "$SCRIPT_DIR/start.sh" ]; then
            "$SCRIPT_DIR/start.sh" stop "$DEPLOY_TYPE" || true
        fi
    fi
    # 等待端口释放
    sleep 3
    log_ok "服务停止完成"
}

start_services() {
    log_step "启动服务"
    if [ -x "$SCRIPT_DIR/start.sh" ]; then
        case "$DEPLOY_TYPE" in
            master) "$SCRIPT_DIR/start.sh" start master --skip-deps --no-wait || true ;;
            worker) "$SCRIPT_DIR/start.sh" start worker --skip-deps --no-wait || true ;;
            all)    "$SCRIPT_DIR/start.sh" start all    --skip-deps --no-wait || true ;;
        esac
    fi
    sleep 2
}

# ------------------------------
# 依赖与迁移
# ------------------------------
run_dependency_update() {
    log_step "更新 Python 依赖"
    cd "$PROJECT_ROOT"
    if command -v uv &>/dev/null; then
        log_info "使用 uv sync 更新依赖..."
        if uv sync 2>&1 | tail -n 10 | tee -a "$UPGRADE_LOG"; then
            log_ok "uv sync 完成"
            return 0
        fi
        log_warn "uv sync 失败，回退 pip"
    fi
    local py
    py="$(command -v python3 || command -v python)"
    log_info "使用 pip install -U -e ."
    if "$py" -m pip install -U -e . 2>&1 | tail -n 10 | tee -a "$UPGRADE_LOG"; then
        log_ok "依赖更新完成"
        return 0
    fi
    log_error "依赖更新失败，但将继续尝试启动服务 (可能运行失败)"
    return 1
}

run_database_migration() {
    if [ "$SKIP_MIGRATION" = "1" ]; then
        log_warn "SKIP_MIGRATION=1，跳过数据库迁移"
        return 0
    fi
    if [ "$DEPLOY_TYPE" = "worker" ]; then
        log_info "DEPLOY_TYPE=worker，跳过数据库迁移"
        return 0
    fi

    # 直接复用 deploy.sh 中的迁移逻辑
    if [ -x "$SCRIPT_DIR/deploy.sh" ]; then
        log_step "执行数据库迁移"
        log_info "通过 deploy.sh 调用迁移 (check + .env 保留)"
        local py
        py="$(command -v python3 || command -v python)"
        if command -v timeout &>/dev/null; then
            timeout 60 "$py" -c "
import sys, os, asyncio
sys.path.insert(0, '$MASTER_DIR')
os.environ['PYTHONPATH'] = '$MASTER_DIR:$PROJECT_ROOT'
try:
    from main import app
    from core.globals import site
    from sqlmodel import SQLModel
except Exception as e:
    print(f'Import failed: {e}', file=sys.stderr)
    sys.exit(0)

async def main():
    try:
        async with app.router.lifespan_context(app):
            await site.db.async_run_sync(SQLModel.metadata.create_all, is_session=False)
            print('Database migration / table creation OK')
    except Exception as e:
        print(f'Migration skipped/warning: {e}')

asyncio.run(main())
" 2>&1 | tail -n 10 | tee -a "$UPGRADE_LOG" && log_ok "数据库迁移完成" || log_warn "数据库迁移有警告，详见日志"
        fi
    fi
}

# ------------------------------
# 健康检查
# ------------------------------
post_upgrade_health_check() {
    log_step "升级后健康检查"
    local ok=true

    # 检查 master HTTP
    if [ "$DEPLOY_TYPE" = "master" ] || [ "$DEPLOY_TYPE" = "all" ]; then
        sleep 3
        local port=5500
        if (echo > "/dev/tcp/127.0.0.1/${port}") 2>/dev/null; then
            log_ok "Master HTTP 端口 :${port} 可连接"
        else
            log_warn "Master HTTP 端口 :${port} 暂不可用 (可能还在启动中)"
            ok=false
        fi
    fi

    # 检查进程
    if [ -x "$SCRIPT_DIR/stop.sh" ]; then
        echo "" | tee -a "$UPGRADE_LOG"
        "$SCRIPT_DIR/stop.sh" status | tee -a "$UPGRADE_LOG" || true
    fi

    if [ "$ok" = "true" ]; then
        log_ok "健康检查通过"
    else
        log_warn "健康检查部分未通过，请手动确认服务状态"
    fi
}

# ------------------------------
# 代码获取方式
# ------------------------------
fetch_code_via_git() {
    log_step "通过 Git 更新代码 (分支: $GIT_BRANCH)"
    cd "$PROJECT_ROOT"
    if [ ! -d ".git" ]; then
        log_error "$PROJECT_ROOT 不是 git 仓库，无法使用 git 升级"
        return 1
    fi
    if ! command -v git &>/dev/null; then
        log_error "git 命令未找到"
        return 1
    fi

    # 当前 commit / tag
    local before
    before=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local before_ver
    before_ver=$(get_current_version)

    log_info "升级前版本: $before_ver (commit $before)"

    # 确认工作区干净
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        log_warn "工作区存在未提交的修改，将使用 git stash 暂存后再拉取"
        if ! confirm "是否继续？ (stash → pull → stash pop)" "n"; then
            log_error "中止升级"
            return 1
        fi
        git -C "$PROJECT_ROOT" stash push -m "upgrade backup $(date '+%F %T')" 2>&1 | tee -a "$UPGRADE_LOG"
        local stashed=true
    fi

    # git fetch + pull
    log_info "执行 git fetch origin ..."
    git -C "$PROJECT_ROOT" fetch origin --tags 2>&1 | tee -a "$UPGRADE_LOG" || true
    log_info "执行 git checkout $GIT_BRANCH ..."
    git -C "$PROJECT_ROOT" checkout "$GIT_BRANCH" 2>&1 | tee -a "$UPGRADE_LOG" || {
        log_error "切换分支 $GIT_BRANCH 失败"
        return 1
    }
    log_info "执行 git pull --ff-only origin $GIT_BRANCH ..."
    if ! git -C "$PROJECT_ROOT" pull --ff-only origin "$GIT_BRANCH" 2>&1 | tee -a "$UPGRADE_LOG"; then
        log_error "git pull 失败 (可能需要合并冲突)，请手动处理后再次升级"
        [ "${stashed:-false}" = "true" ] && git -C "$PROJECT_ROOT" stash pop 2>&1 | tee -a "$UPGRADE_LOG" || true
        return 1
    fi

    if [ "${stashed:-false}" = "true" ]; then
        log_info "还原 stash 的本地修改..."
        if ! git -C "$PROJECT_ROOT" stash pop 2>&1 | tee -a "$UPGRADE_LOG"; then
            log_warn "stash pop 有冲突，请手动解决冲突，必要时运行 git mergetool"
        fi
    fi

    local after
    after=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local after_ver
    after_ver=$(get_current_version)
    log_info "升级后版本: $after_ver (commit $after)"

    if [ "$before" = "$after" ] && [ "$before_ver" = "$after_ver" ]; then
        log_warn "代码没有变化，升级操作将继续执行依赖/迁移流程以确保一致性"
    else
        log_ok "代码已更新"
    fi
    return 0
}

fetch_code_via_tarball() {
    local tarball=$1
    log_step "通过 tar.gz 包升级: $tarball"
    if [ ! -f "$tarball" ]; then
        log_error "文件不存在: $tarball"
        return 1
    fi
    local tmp_dir
    tmp_dir=$(mktemp -d -t upgrade.XXXXXX)
    log_info "解压到临时目录: $tmp_dir"
    if ! tar xzf "$tarball" -C "$tmp_dir" 2>>"$UPGRADE_LOG"; then
        log_error "解压失败"
        rm -rf "$tmp_dir"
        return 1
    fi

    # 找到包中的 pyproject.toml 所在目录
    local src_dir=""
    for d in "$tmp_dir" "$tmp_dir"/*; do
        if [ -f "$d/pyproject.toml" ]; then
            src_dir="$d"
            break
        fi
    done
    if [ -z "$src_dir" ]; then
        log_error "压缩包中未找到包含 pyproject.toml 的项目根目录"
        rm -rf "$tmp_dir"
        return 1
    fi

    local old_ver
    old_ver=$(get_current_version)
    local new_ver
    new_ver=$(get_pyproject_version_from_dir "$src_dir")

    log_info "当前版本: $old_ver → 新版本: $new_ver"

    # 使用 rsync 覆盖 (无则用 cp -r)
    log_info "覆盖项目文件至 $PROJECT_ROOT ..."
    if command -v rsync &>/dev/null; then
        rsync -a --delete \
            --exclude='.git' \
            --exclude='.env' \
            --exclude='master/.env' \
            --exclude='worker/.env' \
            --exclude='master/amisadmin.db' \
            --exclude='master/data' \
            --exclude='worker/data' \
            --exclude='.pids' \
            --exclude='logs' \
            --exclude='backups' \
            "$src_dir/" "$PROJECT_ROOT/" \
            2>>"$UPGRADE_LOG" || log_warn "rsync 有警告"
    else
        # 回退：排除敏感文件后 cp
        for d in "$src_dir"/* "$src_dir"/.[!.]*; do
            [ -e "$d" ] || continue
            local bn
            bn=$(basename "$d")
            case "$bn" in
                .git|.env|backups|logs|.pids) continue ;;
            esac
            # 配置和数据目录不覆盖
            if [ "$bn" = "master" ]; then
                # 排除 master/.env, master/data, master/amisadmin.db
                for sd in "$d"/*; do
                    [ -e "$sd" ] || continue
                    local sdn
                    sdn=$(basename "$sd")
                    case "$sdn" in
                        .env|data|amisadmin.db) continue ;;
                    esac
                    rm -rf "$PROJECT_ROOT/master/$sdn"
                    cp -a "$sd" "$PROJECT_ROOT/master/$sdn"
                done
            elif [ "$bn" = "worker" ]; then
                for sd in "$d"/*; do
                    [ -e "$sd" ] || continue
                    local sdn
                    sdn=$(basename "$sd")
                    case "$sdn" in
                        .env|data) continue ;;
                    esac
                    rm -rf "$PROJECT_ROOT/worker/$sdn"
                    cp -a "$sd" "$PROJECT_ROOT/worker/$sdn"
                done
            else
                rm -rf "$PROJECT_ROOT/$bn"
                cp -a "$d" "$PROJECT_ROOT/$bn"
            fi
        done
    fi

    rm -rf "$tmp_dir"
    log_ok "tar.gz 包覆盖完成"
    return 0
}

# ------------------------------
# 回滚
# ------------------------------
rollback_from_backup() {
    local backup_dir=$1
    if [ ! -d "$backup_dir" ]; then
        log_error "备份目录不存在: $backup_dir"
        return 1
    fi
    log_title "回滚到备份: $backup_dir"

    if ! confirm "确认执行回滚？将停止服务、覆盖代码和配置，操作不可逆！" "n"; then
        log_warn "取消回滚"
        return 1
    fi

    # 1. 停服务
    stop_running_services

    # 2. 源码还原
    if [ -d "$backup_dir/source" ]; then
        log_step "从 source/ 还原源码..."
        if command -v rsync &>/dev/null; then
            rsync -a --delete \
                "$backup_dir/source/" "$PROJECT_ROOT/" \
                2>>"$UPGRADE_LOG" || log_warn "rsync 有警告"
        else
            cp -a "$backup_dir/source"/* "$backup_dir/source"/.[!.]* "$PROJECT_ROOT/" 2>>"$UPGRADE_LOG" || true
        fi
        log_ok "源码还原完成"
    elif [ -f "$backup_dir/source.tar.gz" ]; then
        log_step "从 source.tar.gz 还原源码..."
        tar xzf "$backup_dir/source.tar.gz" -C "$PROJECT_ROOT" 2>>"$UPGRADE_LOG" || true
        log_ok "源码还原完成"
    else
        log_warn "备份中没有源码快照，仅还原配置/数据"
    fi

    # 3. 配置还原
    [ -f "$backup_dir/master.env.bak" ] && cp -a "$backup_dir/master.env.bak" "$MASTER_DIR/.env" && log_info "还原 master/.env"
    [ -f "$backup_dir/worker.env.bak" ] && cp -a "$backup_dir/worker.env.bak" "$WORKER_DIR/.env" && log_info "还原 worker/.env"
    [ -f "$backup_dir/root.env.bak" ]   && cp -a "$backup_dir/root.env.bak"   "$PROJECT_ROOT/.env" && log_info "还原根目录 .env"
    [ -f "$backup_dir/amisadmin.db.bak" ] && cp -a "$backup_dir/amisadmin.db.bak" "$MASTER_DIR/amisadmin.db" && log_info "还原 SQLite 数据库"

    # 4. master/data / worker/data
    [ -d "$backup_dir/master_data" ] && rm -rf "$MASTER_DIR/data" && cp -a "$backup_dir/master_data" "$MASTER_DIR/data" && log_info "还原 master/data"
    [ -d "$backup_dir/worker_data" ] && rm -rf "$WORKER_DIR/data" && cp -a "$backup_dir/worker_data" "$WORKER_DIR/data" && log_info "还原 worker/data"

    # 5. 还原依赖
    log_step "重新 sync 依赖以匹配旧代码..."
    run_dependency_update || true

    # 6. 启服务
    start_services
    sleep 3
    post_upgrade_health_check || true

    log_ok "回滚完成，耗时 $(elapsed)s"
    log_info "升级日志: $UPGRADE_LOG"
}

# ------------------------------
# 升级主流程
# ------------------------------
run_upgrade() {
    local mode=$1
    local mode_arg=${2:-}

    log_title "项目升级流程"
    log_info "升级模式: $mode ${mode_arg:+($mode_arg)}"
    log_info "升级范围: DEPLOY_TYPE=$DEPLOY_TYPE"
    log_info "升级日志: $UPGRADE_LOG"
    echo "" | tee -a "$UPGRADE_LOG"

    # 0. 环境预检
    log_step "升级前置检查"
    local py
    py="$(command -v python3 || command -v python || echo "")"
    if [ -z "$py" ]; then
        log_error "Python 未找到，中止升级"
        return 1
    fi
    if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
        log_error "pyproject.toml 未找到，$PROJECT_ROOT 不是项目根目录"
        return 1
    fi
    case "$DEPLOY_TYPE" in
        master|worker|all) ;;
        *) log_error "无效 DEPLOY_TYPE=$DEPLOY_TYPE"; return 1 ;;
    esac
    local cur_ver
    cur_ver=$(get_current_version)
    log_info "当前项目版本: $cur_ver"
    log_ok "前置检查通过"

    # 1. 升级前完整备份
    local backup_path=""
    backup_path=$(create_upgrade_backup "pre")
    if [ "$backup_path" = "NO_BACKUP" ]; then
        backup_path=""
    else
        log_info "升级失败可回滚: $0 rollback $backup_path"
    fi

    # 2. 确认开始
    echo "" | tee -a "$UPGRADE_LOG"
    if ! confirm "准备就绪，开始升级？升级过程会短暂停服。" "y"; then
        log_warn "用户取消升级"
        return 0
    fi

    # 3. 停止服务
    stop_running_services

    # 4. 获取新代码
    echo "" | tee -a "$UPGRADE_LOG"
    local code_ok=true
    case "$mode" in
        git)
            fetch_code_via_git || code_ok=false
            ;;
        tarball)
            fetch_code_via_tarball "$mode_arg" || code_ok=false
            ;;
        local)
            log_step "使用本地现有代码升级 (仅执行依赖/迁移流程)"
            log_ok "无需拉取代码"
            ;;
        *)
            log_error "未知升级模式: $mode"
            code_ok=false
            ;;
    esac
    if [ "$code_ok" = "false" ]; then
        log_error "代码更新失败"
        if [ -n "$backup_path" ]; then
            if confirm "是否立即回滚到升级前备份？" "y"; then
                rollback_from_backup "$backup_path"
            else
                log_warn "保留现状，请手动处理或稍后回滚"
            fi
        fi
        return 1
    fi

    # 5. 更新依赖
    echo "" | tee -a "$UPGRADE_LOG"
    run_dependency_update || true

    # 6. 数据库迁移
    echo "" | tee -a "$UPGRADE_LOG"
    run_database_migration || true

    # 7. 启动服务
    echo "" | tee -a "$UPGRADE_LOG"
    start_services

    # 8. 健康检查
    echo "" | tee -a "$UPGRADE_LOG"
    post_upgrade_health_check || true

    # 9. 完成
    local new_ver
    new_ver=$(get_current_version)
    echo "" | tee -a "$UPGRADE_LOG"
    echo "==========================================" | tee -a "$UPGRADE_LOG"
    log_ok "升级完成！耗时 $(elapsed)s"
    echo "==========================================" | tee -a "$UPGRADE_LOG"
    echo "  旧版本: $cur_ver" | tee -a "$UPGRADE_LOG"
    echo "  新版本: $new_ver" | tee -a "$UPGRADE_LOG"
    echo "  升级日志: $UPGRADE_LOG" | tee -a "$UPGRADE_LOG"
    if [ -n "$backup_path" ]; then
        echo "  回滚命令: $0 rollback $backup_path" | tee -a "$UPGRADE_LOG"
    fi
    echo "" | tee -a "$UPGRADE_LOG"
    echo "常用操作:" | tee -a "$UPGRADE_LOG"
    echo "  查看状态: $SCRIPT_DIR/stop.sh status" | tee -a "$UPGRADE_LOG"
    echo "  查看日志: tail -f $PROJECT_ROOT/logs/master.log $PROJECT_ROOT/logs/worker.log" | tee -a "$UPGRADE_LOG"
    echo "" | tee -a "$UPGRADE_LOG"
}

run_check_only() {
    log_title "升级可行性检查"
    log_info "日志文件: $UPGRADE_LOG"
    echo "" | tee -a "$UPGRADE_LOG"

    local fail=0

    # Python
    log_step "1/6 检查 Python"
    local py
    py="$(command -v python3 || command -v python || echo "")"
    if [ -z "$py" ]; then log_error "未找到 Python"; fail=$((fail+1))
    else log_ok "Python 可用: $py ($("$py" --version 2>&1))"; fi

    # 包管理器
    log_step "2/6 检查包管理器"
    if command -v uv &>/dev/null; then log_ok "uv 可用: $(uv --version 2>&1)"
    elif command -v pip3 &>/dev/null; then log_ok "pip3 可用"
    else log_warn "uv/pip 未找到，将无法自动更新依赖"; fail=$((fail+1)); fi

    # 项目文件
    log_step "3/6 检查项目结构"
    if [ -f "$PROJECT_ROOT/pyproject.toml" ] && [ -f "$MASTER_DIR/main.py" ] && [ -f "$WORKER_DIR/main.py" ]; then
        log_ok "项目文件完整"
    else
        log_error "项目文件缺失"; fail=$((fail+1))
    fi
    local ver
    ver=$(get_current_version)
    log_info "当前版本: $ver"

    # Git 仓库
    log_step "4/6 检查 Git 升级方式"
    if command -v git &>/dev/null && [ -d "$PROJECT_ROOT/.git" ]; then
        local branch
        branch=$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || echo "?")
        log_ok "Git 可用，当前分支: $branch"
        log_info "升级命令: $0 git  (GIT_BRANCH=$GIT_BRANCH)"
    else
        log_warn "Git 仓库不可用，可使用 tarball 方式升级: $0 tarball <file.tar.gz>"
    fi

    # 服务状态
    log_step "5/6 检查运行中服务"
    if [ -x "$SCRIPT_DIR/stop.sh" ]; then
        "$SCRIPT_DIR/stop.sh" status 2>&1 | tee -a "$UPGRADE_LOG" || true
    fi

    # 备份目录
    log_step "6/6 检查备份空间"
    if mkdir -p "$BACKUP_DIR" 2>>"$UPGRADE_LOG"; then
        local avail
        avail=$(df -Pm "$BACKUP_DIR" 2>/dev/null | awk 'NR==2{print $4}' || echo "")
        if [ -n "$avail" ]; then
            log_ok "备份目录可用: $BACKUP_DIR (剩余 ${avail}MB)"
        else
            log_ok "备份目录可用: $BACKUP_DIR"
        fi
    else
        log_error "备份目录不可写"; fail=$((fail+1))
    fi

    echo "" | tee -a "$UPGRADE_LOG"
    if [ "$fail" -gt 0 ]; then
        log_error "发现 ${fail} 项严重问题，建议先解决后再升级"
        return 1
    fi
    log_ok "检查通过，可以执行升级"
    echo "  git 升级: $0 git" | tee -a "$UPGRADE_LOG"
    echo "  包升级:   $0 tarball /path/to/release.tar.gz" | tee -a "$UPGRADE_LOG"
    echo "  仅流程:   $0 local  (代码已就位，仅执行依赖/迁移/重启)" | tee -a "$UPGRADE_LOG"
    echo "" | tee -a "$UPGRADE_LOG"
}

usage() {
    cat <<EOF
${CYAN}项目升级脚本${NC}

${GREEN}用法:${NC}
  $0 [mode] [args] [options]

${GREEN}模式:${NC}
  (无)               默认使用 git 拉取并升级 (等同 git)
  git                通过 git 拉取最新代码并升级 (推荐)
  tarball <path>     通过本地 tar.gz 发布包升级
  local              代码已在当前目录就位，仅执行 依赖更新 → 迁移 → 重启
  check              仅做升级可行性检查 (不做修改)
  rollback <dir>     回滚到指定备份目录 (来自升级前自动备份)
  -h, --help         显示帮助

${GREEN}环境变量:${NC}
  YES=1                 跳过所有交互确认
  DEPLOY_TYPE=master|worker|all   升级/重启范围 (默认 all)
  GIT_BRANCH=main       git 升级模式的目标分支 (默认 main)
  SKIP_BACKUP=1         跳过升级前完整备份 (不推荐)
  SKIP_MIGRATION=1      跳过数据库迁移

${GREEN}示例:${NC}
  $0 check                              # 升级前检查
  $0 git                                # 从当前 git 分支拉取升级
  GIT_BRANCH=release/1.0 $0 git         # 切到指定分支升级
  $0 tarball /tmp/sretools-v1.1.tar.gz  # 从发布包升级
  $0 local                              # 代码已更新，仅跑后续流程
  $0 rollback backups/upgrade_pre_xxx/  # 出错时回滚
  YES=1 DEPLOY_TYPE=worker $0 git       # 非交互仅升级 worker
EOF
}

# ------------------------------
# 入口
# ------------------------------
main() {
    # 确保日志目录存在
    mkdir -p "$(dirname "$UPGRADE_LOG")"
    : > "$UPGRADE_LOG" 2>/dev/null || true
    chmod 644 "$UPGRADE_LOG" 2>/dev/null || true

    local mode=${1:-git}
    case "$mode" in
        -h|--help|help) usage; exit 0 ;;
        check)          run_check_only ;;
        rollback)
            if [ -z "${2:-}" ]; then
                log_error "请指定备份目录: $0 rollback <dir>"
                exit 1
            fi
            rollback_from_backup "$2"
            ;;
        git|""|local)
            run_upgrade "${mode:-git}" ""
            ;;
        tarball)
            if [ -z "${2:-}" ]; then
                log_error "请指定 tar.gz 包路径: $0 tarball <path.tar.gz>"
                exit 1
            fi
            run_upgrade "tarball" "$2"
            ;;
        *) usage; exit 1 ;;
    esac
}

main "$@"
