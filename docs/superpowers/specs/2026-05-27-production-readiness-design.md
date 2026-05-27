# 生产就绪优化 — 设计规范

> 2026-05-27 | enterprise-kb-agent | v0.6 → v1.0

## 目标

将 enterprise-kb-agent 优化到可在 GTX 1650 Ti 4GB 上支撑 50+ 用户的生产就绪水平，并为后续 GPU 升级留好接口。

## 约束条件

- C 盘必须保持 ≥ 5GB 空闲（当前 12.8GB，本次优化不往 C 盘写入）
- D 盘当前 26.3GB 空闲，另可回收 12GB（已废弃的 Qwen2.5-3B-Instruct）
- GTX 1650 Ti 仅 4GB 显存 — 只有 1.96GB 的 GGUF 大模型放得进去；嵌入模型和 Reranker 继续用 CPU
- 不安装系统级 CUDA Toolkit — 使用 Vulkan 后端或自带 DLL 的 CUDA wheel

---

## 阶段 1：性能突破

### 1.1 LLM 推理：CPU → GPU（Vulkan）

**现状**：llama.cpp 纯 CPU 版，5.9 tok/s。
**目标**：llama.cpp Vulkan 版，预计 GTX 1650 Ti 上 15-25 tok/s。

Vulkan 后端无需安装 CUDA Toolkit — Windows 自带 NVIDIA Vulkan 驱动。GGUF 模型（1.96GB）放进 4GB 显存后还有余量给 KV cache。

**备用方案**：如果 Vulkan 效果不理想，改用 `llama-cpp-python` 的预编译 CUDA wheel（自带所需 CUDA DLL，无需系统安装）。

**涉及文件**：`backend/rag/generator.py`（LLAMA_SERVER_URL 指向 Vulkan 版二进制），下载新的 llama.cpp Vulkan 二进制到 `D:\llama-cpp-vulkan\`。

### 1.2 流式输出

**现状**：`generator.py` 使用 `"stream": false`，等模型生成完 200 tokens 才一次性返回。
**目标**：通过 FastAPI `StreamingResponse` 实现 SSE 流式输出。

- `generator.py`：新增 `generate_stream()` 生成器函数，逐 token yield
- `backend/api/query.py`：新增 `/api/query/stream` 端点，返回 `text/event-stream`
- `frontend/app.py`：Gradio 前端实时消费流，逐 token 显示

**体感延迟**：首 token < 1 秒出字，不用干等全部生成完毕。

### 1.3 模型懒加载

**现状**：BGE-M3（8.6GB）+ Reranker（4.3GB）在 FastAPI import 时就加载 → 启动约 30s。
**目标**：首次请求时才加载。

- `OllamaEmbedder`：把 `BGEM3FlagModel()` 初始化推迟到第一次 `embed()` 调用
- `Retriever._get_reranker()`：已经是懒加载，无需改动
- `backend/main.py`：启动流程精简为只做配置校验

**启动时间**：30s → 2-3s。第一个请求承担模型加载成本（约 30s），后续请求即时响应。

### 性能目标

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 后端启动 | ~30s | 2-3s |
| 推理速度 | 5.9 tok/s（CPU） | 15-25 tok/s（Vulkan） |
| 端到端回答 | 20-64s | 4-12s |
| 首字延迟 | 无（等全部） | < 1s |

---

## 阶段 2：一键部署

### 2.1 补 `scripts/ingest.py`

README 写明了 `python scripts/ingest.py` 但这个文件不存在。将 `admin.py` 的 `/api/admin/ingest` 端点中的入库逻辑提取为共享函数，CLI 脚本和 API 端点共用。

### 2.2 Docker Compose 适配 Vulkan

更新 `docker-compose.yml`，llama-server 服务改用 Vulkan 版镜像，添加 GPU 设备直通。

### 2.3 启动脚本

`start.bat`（Windows）：一键启动 llama-server → 等待就绪 → 启动 FastAPI → 启动 Gradio。一个双击代替三个终端。

---

## 阶段 3：死代码清理

### 3.1 删除 `scripts/check_ollama.py`

引用的 `_load_llm()` 函数在 v0.6 重写后已不存在，脚本直接跑不起来。

### 3.2 删除 `D:\Qwen2.5-3B-Instruct`（12GB）

PROGRESS.md 已标注"已废弃"，已被 GGUF 量化版替代。

### 3.3 消除入库逻辑重复

`admin.py:ingest()`（约 60 行）和本该存在的 `scripts/ingest.py` 是同一件事。提取 `ingest_knowledge_base()` 和 `ingest_error_logs()` 到 `backend/ingestion/__init__.py`，API 端点和 CLI 脚本共用。

---

## 阶段 4：配置 + 测试

### 4.1 配置统一

将散落的硬编码值收敛到 `config.py`：

| 位置 | 硬编码值 | 新配置键 |
|------|---------|---------|
| `retriever.py:64` | `0.20` 阈值 | 已存在 `SIMILARITY_THRESHOLD` — 直接用 |
| `retriever.py:57` | `0.7/0.3` 融合权重 | `DENSE_WEIGHT`、`SPARSE_WEIGHT` |
| `generator.py:39` | `max_tokens=256`（报错模式） | `ERROR_MAX_TOKENS` |
| `generator.py:42` | `max_tokens=200`（知识库模式） | `KB_MAX_TOKENS` |

### 4.2 单元测试

新建 `tests/` 目录，使用 pytest：

- `tests/test_retriever.py`：dense/sparse 融合计算、阈值过滤、rerank 排序结果
- `tests/test_documents.py`：chunk 切分、重叠处理、Markdown 标题解析

目标：`rag/` 和 `ingestion/` 模块 80% 覆盖率。

---

## 阶段 5：生产加固

### 5.1 请求队列

`asyncio.Queue` + 最大并发数 = 1（单模型无法并行推理）。队列满时返回 503，防止并发请求导致 OOM。

### 5.2 增强健康检查

`/api/admin/health` 返回：
```json
{
  "status": "ok",
  "models_loaded": true,
  "queue_depth": 3,
  "uptime_seconds": 3600
}
```

### 5.3 结构化日志

每条日志带 request_id。JSON 格式输出，方便后续对接日志聚合系统。记录每个阶段（embed、retrieve、rerank、generate）的耗时。

---

## 不做什么

- **不把嵌入/Reranker 模型搬上 GPU**：4GB 显存放不下 8.6GB + 4.3GB 的模型组合，等硬件升级后再做
- **不加认证系统**：本轮优化不涉及
- **不换向量数据库**：当前 ChromaDB 够用，文档量到 10 万级别再考虑换
- **不换编程语言**：Python + FastAPI 适合这个规模的负载

---

## 文件变更总览

| 阶段 | 涉及文件 |
|------|---------|
| 1 | `backend/rag/generator.py`、`backend/main.py`、`backend/api/query.py`、`frontend/app.py` |
| 2 | `scripts/ingest.py`（新）、`start.bat`（新）、`docker-compose.yml`、`backend/ingestion/__init__.py` |
| 3 | 删除：`scripts/check_ollama.py`、`D:\Qwen2.5-3B-Instruct`；重构：`backend/api/admin.py` |
| 4 | `backend/config.py`、`backend/rag/retriever.py`、`tests/`（新目录） |
| 5 | `backend/api/query.py`、`backend/api/admin.py`、`backend/main.py` |
