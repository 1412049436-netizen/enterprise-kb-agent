#!/bin/bash
# 重启 FastAPI 后端：先 kill 旧进程，再启动新进程
# 用法: bash scripts/restart_backend.sh

set -e

PORT=8000
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[restart_backend] 检查端口 ${PORT} 占用..."

# 查找并 kill 所有占用 8000 的进程
PID=$(netstat -ano 2>/dev/null | grep ":${PORT}" | grep LISTENING | awk '{print $NF}' | head -1)
if [ -n "$PID" ]; then
    echo "[restart_backend] kill PID=${PID}"
    taskkill //F //PID "$PID" 2>/dev/null || true
    sleep 1
fi

# 验证端口已释放
REMAIN=$(netstat -ano 2>/dev/null | grep ":${PORT}" | grep LISTENING | awk '{print $NF}' | head -1)
if [ -n "$REMAIN" ]; then
    echo "[restart_backend] 警告: 端口 ${PORT} 仍被 PID=${REMAIN} 占用，强制继续"
fi

echo "[restart_backend] 调用 start_backend.sh..."
bash "${SCRIPT_DIR}/start_backend.sh"
