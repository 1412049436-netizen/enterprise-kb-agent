#!/bin/bash
# 健壮的 FastAPI 后端启动脚本（git-bash / MSYS 兼容）
# 用法: bash scripts/start_backend.sh

set -e

PORT=8000
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="D:/Anaconda3/python.exe"
HEALTH_URL="http://localhost:${PORT}/api/admin/health"

echo "[start_backend] 检查端口 ${PORT} 占用..."

# 1. 检查端口是否被占用
PID=$(netstat -ano 2>/dev/null | grep ":${PORT}" | grep LISTENING | awk '{print $NF}' | head -1)

if [ -n "$PID" ]; then
    echo "[start_backend] 端口 ${PORT} 被 PID=${PID} 占用，正在 kill..."
    taskkill //F //PID "$PID" 2>/dev/null || true
    sleep 1

    # 2. 等待端口释放（最多等 10 秒）
    waited=0
    while [ $waited -lt 10 ]; do
        REMAIN=$(netstat -ano 2>/dev/null | grep ":${PORT}" | grep LISTENING | awk '{print $NF}' | head -1)
        if [ -z "$REMAIN" ]; then
            echo "[start_backend] 端口 ${PORT} 已释放 (等待 ${waited}s)"
            break
        fi
        sleep 1
        waited=$((waited + 1))
    done

    if [ $waited -ge 10 ]; then
        echo "[start_backend] 错误: 端口 ${PORT} 在 ${waited}s 后仍未释放"
        exit 1
    fi
else
    echo "[start_backend] 端口 ${PORT} 空闲"
fi

# 3. 启动 uvicorn
cd "$PROJECT_DIR"
echo "[start_backend] 启动 uvicorn (pid=$$) ..."
START_TS=$(date -u +"%Y-%m-%dT%H:%M:%S")
$PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} >> server_out.log 2>> server_err.log &
UVICORN_PID=$!
echo "[start_backend] uvicorn PID=${UVICORN_PID}, 启动时间=${START_TS}"

# 4. 轮询 health 接口（最多等 30 秒）
echo "[start_backend] 等待后端就绪..."
elapsed=0
while [ $elapsed -lt 30 ]; do
    if curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null | grep -q "200"; then
        echo "[start_backend] Backend ready (${elapsed}s)"
        exit 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

echo "[start_backend] Backend failed to start (waited ${elapsed}s)"
exit 1
