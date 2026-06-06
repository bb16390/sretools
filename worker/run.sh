#!/usr/bin/env bash

# Worker 启动脚本
# 两种用法：
#   1. 在项目根目录执行：./worker/run.sh
#   2. 进入 worker 目录执行：./run.sh
#
# 依赖：项目根目录下的 pyproject.toml，以及 uv（推荐）或 pip 环境。

set -euo pipefail

# 定位到脚本所在目录（worker/），然后上一层得到项目根
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[INFO] PROJECT_ROOT = ${PROJECT_ROOT}"
echo "[INFO] SCRIPT_DIR  = ${SCRIPT_DIR}"

# ---------------- 依赖安装 ----------------
if [[ -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
    if command -v uv >/dev/null 2>&1; then
        echo "[INFO] 使用 uv 同步依赖"
        (cd "${PROJECT_ROOT}" && uv sync --quiet)
    else
        echo "[WARN] 未检测到 uv，回退到 pip 安装"
        python3 -m pip install --quiet -e "${PROJECT_ROOT}"
    fi
fi

# ---------------- 启动方式 ----------------
# 关键：必须从 PROJECT_ROOT 启动，让 import worker.xxx 走标准路径；
# 否则从 worker/ 目录启动会因为 sys.path[0] 指向 worker/
# 导致 ``import grpc`` 命中本地 worker/grpc 包而失败。
cd "${PROJECT_ROOT}"

echo "[INFO] 启动 worker 主进程..."
if command -v uv >/dev/null 2>&1; then
    exec uv run python -m worker.main "$@"
else
    exec python3 -m worker.main "$@"
fi
