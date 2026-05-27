# 企业知识库问答系统 — Docker 镜像
# CPU 专用版，无 CUDA 依赖

FROM python:3.11-slim

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先装 PyTorch CPU 版（单独装，快很多）
RUN pip install --no-cache-dir \
    torch==2.5.1 \
    --index-url https://download.pytorch.org/whl/cpu

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 额外依赖（requirements 里缺的）
RUN pip install --no-cache-dir \
    FlagEmbedding>=1.3.0

# 应用代码
WORKDIR /app
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/
COPY scripts/ ./scripts/

# 入口脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 环境变量默认值（docker-compose 可覆盖）
ENV MODEL_ROOT=/models
ENV LLAMA_SERVER_URL=http://llama-server:8080/v1/completions
ENV API_BASE=http://localhost:8000
ENV DEVICE=cpu

EXPOSE 8000 7860

CMD ["/entrypoint.sh"]
