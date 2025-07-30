#!/bin/bash

# 打印环境信息，帮助调试
echo "环境信息:"
echo "Python 版本: $(python3 --version 2>&1)"
echo "Skopeo 版本: $(skopeo --version 2>&1)"
echo "当前工作目录: $(pwd)"
echo "Python 路径: $(which python3 2>&1)"

# 检查API认证配置
if [ -n "$API_KEY" ]; then
    echo "API认证: 已启用 (API_KEY已设置)"
else
    echo "API认证: 未启用 (API_KEY未设置)"
fi

# 输出缓存配置信息
CACHE_TYPE=${CACHE_TYPE:-simple}
CACHE_TIMEOUT=${CACHE_TIMEOUT:-3600}

echo "缓存配置:"
echo "  类型: $CACHE_TYPE"
echo "  超时: ${CACHE_TIMEOUT}秒"
if [ "$CACHE_TYPE" = "redis" ]; then
    if [ -n "$CACHE_REDIS_URL" ]; then
        echo "  Redis URL: $CACHE_REDIS_URL"
    else
        echo "  警告: CACHE_TYPE设置为redis但CACHE_REDIS_URL未设置"
    fi
fi

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