@echo off
chcp 65001 >nul
title 企业知识库问答系统 v1.0

set PYTHON=D:\Anaconda3\python.exe
set LLAMA_SERVER=D:\llama-cpp-vulkan\llama-server.exe
set MODEL=D:\Qwen2.5-3B-Instruct-GGUF\qwen2.5-3b-instruct-q4_k_m.gguf
set PROJECT=C:\Users\14120\enterprise-kb-agent

echo ========================================
echo   企业知识库问答系统 v1.0
echo   启动中...
echo ========================================

echo.
echo [1/3] 启动 LLM 推理服务 (Vulkan)...
start "llama-server" "%LLAMA_SERVER%" -m "%MODEL%" --host 127.0.0.1 --port 8080 -c 4096 -ngl 99

echo 等待 llama-server 就绪...
:wait_llama
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:8080/v1/completions >nul 2>&1
if errorlevel 1 goto wait_llama
echo llama-server 就绪!

echo.
echo [2/3] 启动 FastAPI 后端...
start "FastAPI" "%PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

echo 等待 FastAPI 就绪...
:wait_api
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:8000/api/admin/health >nul 2>&1
if errorlevel 1 goto wait_api
echo FastAPI 就绪!

echo.
echo [3/3] 启动 Gradio 前端...
cd /d "%PROJECT%"
start "Gradio" "%PYTHON%" frontend/app.py

echo.
echo ========================================
echo   全部启动完成!
echo   Web UI:  http://localhost:7860
echo   API文档: http://localhost:8000/docs
echo ========================================
pause
