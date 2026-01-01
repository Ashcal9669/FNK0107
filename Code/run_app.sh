#!/bin/bash

# 获取脚本所在目录（兼容性更好的写法）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 切换到脚本所在目录
cd "$SCRIPT_DIR"

# 优先使用虚拟环境的 Python
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -x "${SCRIPT_DIR}/.venv/bin/python" ]; then
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
fi

# 检查是否为无桌面环境
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    if [ ! -f "web_server.py" ]; then
        echo "Error: web_server.py not found"
        exit 1
    fi
    HOST="${FREENOVE_HOST:-0.0.0.0}"
    PORT="${FREENOVE_PORT:-8080}"
    RUN_PREFIX=""
    if [ "${FREENOVE_USE_SUDO:-0}" = "1" ]; then
        RUN_PREFIX="sudo"
    fi
    echo "Headless mode detected. Starting web UI on ${HOST}:${PORT}"
    $RUN_PREFIX "$PYTHON_BIN" web_server.py --host "$HOST" --port "$PORT"
    exit 0
fi

# 检查 app_ui.py 文件是否存在
if [ ! -f "app_ui.py" ]; then
    echo "错误: app_ui.py 文件未找到"
    exit 1
fi

# 以管理员权限运行 app_ui.py
RUN_PREFIX=""
if [ "${FREENOVE_USE_SUDO:-1}" = "1" ]; then
    RUN_PREFIX="sudo"
fi
$RUN_PREFIX "$PYTHON_BIN" app_ui.py
