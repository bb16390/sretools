#!/bin/bash

# 启动worker服务
echo "Starting worker service..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# 检查依赖
if [ ! -f "../pyproject.toml" ]; then
    echo "Error: pyproject.toml not found"
    exit 1
fi

# 安装依赖
echo "Installing dependencies..."
python3 -m pip install -e ..

# 运行worker
echo "Running worker..."
python3 main.py
