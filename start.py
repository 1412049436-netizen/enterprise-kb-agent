#!/usr/bin/env python
"""一键启动脚本 — 启动 llama-server + FastAPI + Gradio"""
import subprocess
import time
import sys
import urllib.request
from pathlib import Path

PYTHON = r"D:\Anaconda3\python.exe"
LLAMA_SERVER = r"D:\llama-cpp-vulkan\llama-server.exe"
MODEL = r"D:\Qwen2.5-3B-Instruct-GGUF\qwen2.5-3b-instruct-q4_k_m.gguf"
PROJECT = Path(__file__).resolve().parent


def wait_for_health(url: str, name: str, timeout: int = 60):
    print(f"  等待 {name} 就绪...", end="", flush=True)
    for _ in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=2)
            print(" 就绪!")
            return True
        except Exception:
            time.sleep(1)
            print(".", end="", flush=True)
    print(f"\n  {name} 启动超时!")
    return False


def main():
    print("=" * 50)
    print("  企业知识库问答系统 v1.0")
    print("=" * 50)

    # 1. 启动 llama-server
    print("\n[1/3] 启动 LLM 推理服务 (Vulkan)...")
    llama_proc = subprocess.Popen(
        [
            LLAMA_SERVER,
            "-m", MODEL,
            "--host", "127.0.0.1",
            "--port", "8080",
            "-c", "4096",
            "-ngl", "99",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_health("http://127.0.0.1:8080/health", "llama-server"):
        print("  无法启动 llama-server，请检查 Vulkan 二进制和模型路径")
        sys.exit(1)

    # 2. 启动 FastAPI
    print("\n[2/3] 启动 FastAPI 后端...")
    api_proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(PROJECT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_health("http://127.0.0.1:8000/api/admin/health", "FastAPI"):
        print("  无法启动 FastAPI，请检查依赖和端口占用")
        llama_proc.terminate()
        sys.exit(1)

    # 3. 启动 Gradio
    print("\n[3/3] 启动 Gradio 前端...")
    gradio_proc = subprocess.Popen(
        [PYTHON, "frontend/app.py"],
        cwd=str(PROJECT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(3)
    print("\n" + "=" * 50)
    print("  全部启动完成!")
    print(f"  Web UI:  http://localhost:7860")
    print(f"  API文档: http://localhost:8000/docs")
    print("=" * 50)
    print("\n按 Ctrl+C 停止所有服务...")

    try:
        llama_proc.wait()
    except KeyboardInterrupt:
        print("\n正在停止所有服务...")
        gradio_proc.terminate()
        api_proc.terminate()
        llama_proc.terminate()
        print("已停止。")


if __name__ == "__main__":
    main()
