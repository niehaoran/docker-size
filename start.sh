#!/bin/bash

# 打印环境信息，帮助调试
echo "环境信息:"
echo "Python 版本: $(python3 --version 2>&1)"
echo "Skopeo 版本: $(skopeo --version 2>&1)"
echo "当前工作目录: $(pwd)"
echo "Python 路径: $(which python3 2>&1)"

# 确保 skopeo 命令可用
if ! command -v skopeo &> /dev/null; then
    echo "错误: skopeo 命令不可用"
    exit 1
fi

# 确保 python3 命令可用
if ! command -v python3 &> /dev/null; then
    echo "错误: python3 命令不可用"
    exit 1
fi

# 启动 Flask 应用
echo "启动 Flask 应用..."
exec python3 app.py 