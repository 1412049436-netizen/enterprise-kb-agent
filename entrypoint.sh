#!/bin/bash
# 容器入口: 同时启动 FastAPI 和 Gradio
set -e

echo "=== 企业知识库问答系统 v0.6 (Docker) ==="
echo "MODEL_ROOT=$MODEL_ROOT"
echo "LLAMA_SERVER_URL=$LLAMA_SERVER_URL"

# 等 llama-server 就绪
echo "Waiting for llama-server..."
for i in $(seq 1 30); do
    if curl -s "$LLAMA_SERVER_URL" > /dev/null 2>&1; then
        echo "llama-server ready (waited ${i}s)"
        break
    fi
    sleep 1
done

# 启动 FastAPI (后台)
echo "Starting FastAPI on :8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

# 等 FastAPI 就绪
for i in $(seq 1 20); do
    if curl -s http://localhost:8000/api/admin/health > /dev/null 2>&1; then
        echo "FastAPI ready (waited ${i}s)"
        break
    fi
    sleep 2
done

# 启动 Gradio (前台，容器主进程)
echo "Starting Gradio on :7860..."
exec python frontend/app.py
