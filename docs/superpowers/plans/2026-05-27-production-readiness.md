# 生产就绪优化 — 实现计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来逐任务实现此计划。步骤使用 `- [ ]` 复选框语法跟踪。

**目标：** 将 enterprise-kb-agent 从 v0.6 优化到生产就绪 v1.0，实现 GPU 推理（Vulkan）、流式输出、一键部署、配置统一、测试覆盖和生产加固。

**架构：** llama.cpp Vulkan 版在 GPU 上跑 Qwen2.5-3B GGUF 推理 → FastAPI SSE 流式输出 → Gradio 前端逐 token 渲染。嵌入模型和 Reranker 保持 CPU 懒加载。asyncio.Queue 控制并发。

**技术栈：** Python 3.11, FastAPI, Gradio 6.0, ChromaDB, llama.cpp (Vulkan), BGE-M3, bge-reranker-v2-m3, httpx, pytest

---

## 阶段 1：性能突破

### Task 1: 下载并部署 llama.cpp Vulkan 版

- [ ] **Step 1: 下载 Vulkan 二进制包**

在浏览器或 PowerShell 中执行：
```powershell
Invoke-WebRequest -Uri "https://github.com/ggml-org/llama.cpp/releases/download/b8864/llama-b8864-bin-win-vulkan-x64.zip" -OutFile "D:\llama-b8864-bin-win-vulkan-x64.zip"
```

- [ ] **Step 2: 解压到 D 盘**

```powershell
Expand-Archive -Path "D:\llama-b8864-bin-win-vulkan-x64.zip" -DestinationPath "D:\llama-cpp-vulkan" -Force
```

- [ ] **Step 3: 验证解压结果**

```bash
ls -la "D:/llama-cpp-vulkan/" | head -20
```

预期：看到 `llama-server.exe` 和相关的 DLL 文件。

- [ ] **Step 4: 快速冒烟测试 Vulkan 二进制能否启动**

```bash
"D:/llama-cpp-vulkan/llama-server.exe" --help 2>&1 | head -5
```

预期：显示 help 信息，不报 DLL 缺失错误。

- [ ] **Step 5: Commit**

```bash
# 这是纯下载操作，不需要 commit。更新 PROGRESS.md 记录新二进制路径。
```

---

### Task 2: 更新 config.py 和 generator.py 配置

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/rag/generator.py`

- [ ] **Step 1: 在 config.py 添加 Vulkan 路径和 tokens 配置**

编辑 `backend/config.py`，在 LLM 配置区域（第 12 行附近）修改：

```python
# ── LLM 推理服务 (llama.cpp) ─────────────────────────
LLAMA_SERVER_BIN = str(MODEL_ROOT / os.getenv("LLAMA_SERVER_BIN", "llama-cpp-vulkan/llama-server.exe"))
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8080/v1/completions")

# ── 生成参数 ─────────────────────────────────────────
KB_MAX_TOKENS = int(os.getenv("KB_MAX_TOKENS", "200"))
ERROR_MAX_TOKENS = int(os.getenv("ERROR_MAX_TOKENS", "256"))
GENERATION_TIMEOUT = int(os.getenv("GENERATION_TIMEOUT", "180"))
```

注意：原来的 `LLM_GGUF_PATH` 和 `LLAMA_SERVER_URL` 的旧定义需要替换掉。`LLM_GGUF_PATH` 保留（给启动脚本用），但 `LLAMA_SERVER_URL` 移到新位置。

实际需要修改的具体行：

```diff
-# LLM_MODEL_PATH 和 LLM_GGUF_PATH 保持不变
+LLAMA_SERVER_BIN = str(MODEL_ROOT / os.getenv("LLAMA_SERVER_BIN", "llama-cpp-vulkan/llama-server.exe"))
+# LLAMA_SERVER_URL 移到下面
+
+KB_MAX_TOKENS = int(os.getenv("KB_MAX_TOKENS", "200"))
+ERROR_MAX_TOKENS = int(os.getenv("ERROR_MAX_TOKENS", "256"))
+GENERATION_TIMEOUT = int(os.getenv("GENERATION_TIMEOUT", "180"))
```
注意：原有的 `LLM_GGUF_PATH` 保留不动（start.bat 需要引用它），原来的 `LLAMA_SERVER_URL` 移到此处统一管理。

- [ ] **Step 2: 更新 generator.py 使用新配置**

编辑 `backend/rag/generator.py`，将文件顶部硬编码的 `LLAMA_SERVER_URL` 替换为从 config 导入：

```diff
-import os
 import re
 import httpx
 from loguru import logger
+from ..config import LLAMA_SERVER_URL, KB_MAX_TOKENS, ERROR_MAX_TOKENS, GENERATION_TIMEOUT

 # ── 提示词模板 ───────────────────────────────────────

 KB_SYSTEM_PROMPT = "你是企业知识库助手。严格基于提供的文档内容回答，不要编造。用中文简洁回答。"

 ERROR_SYSTEM_PROMPT = "你是技术报错排查助手。基于错误记录回答。匹配就给出解决方案+步骤，类似就说明'参考方案'，无匹配就说'未找到该错误记录'。用中文。"

-LLAMA_SERVER_URL = os.environ.get("LLAMA_SERVER_URL", "http://127.0.0.1:8080/v1/completions")
-
```

然后更新 `generate()` 函数中的硬编码 max_tokens：

```diff
     if mode == "error_logs":
         system_prompt = ERROR_SYSTEM_PROMPT
         temperature = 0.2
-        max_tokens = 256
+        max_tokens = ERROR_MAX_TOKENS
     else:
         system_prompt = KB_SYSTEM_PROMPT
-        max_tokens = 200
+        max_tokens = KB_MAX_TOKENS
```

并把 timeout 也改用配置：

```diff
-            timeout=180,
+            timeout=GENERATION_TIMEOUT,
```

- [ ] **Step 3: 验证 import 正常**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "from backend.config import LLAMA_SERVER_URL, KB_MAX_TOKENS, ERROR_MAX_TOKENS; print(f'OK: {LLAMA_SERVER_URL=} {KB_MAX_TOKENS=} {ERROR_MAX_TOKENS=}')"
```

预期：`OK: LLAMA_SERVER_URL='http://127.0.0.1:8080/v1/completions' KB_MAX_TOKENS=200 ERROR_MAX_TOKENS=256`

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/config.py backend/rag/generator.py
git commit -m "feat: add Vulkan path config and centralized token limits"
```

---

### Task 3: 添加流式生成支持

**Files:**
- Modify: `backend/rag/generator.py`

- [ ] **Step 1: 在 generator.py 添加 generate_stream() 函数**

在 `generate()` 函数之后添加：

```python
def generate_stream(
    query: str,
    sources: list[dict],
    mode: str = "knowledge_base",
    temperature: float = 0.1,
    max_tokens: int | None = None,
):
    """流式生成，逐 token yield 字符串"""
    ctx = build_context(sources)

    if mode == "error_logs":
        system_prompt = ERROR_SYSTEM_PROMPT
        temperature = 0.2
        max_tokens = max_tokens or ERROR_MAX_TOKENS
    else:
        system_prompt = KB_SYSTEM_PROMPT
        max_tokens = max_tokens or KB_MAX_TOKENS

    user_prompt = f"""文档：
{ctx}

问题：{query}

回答："""

    full_prompt = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    full_response = ""

    try:
        with httpx.stream(
            "POST",
            LLAMA_SERVER_URL,
            json={
                "prompt": full_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
                "stop": ["<|im_end|>", "<|im_start|>"],
                "stream": True,
            },
            timeout=GENERATION_TIMEOUT,
        ) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data_str)
                        token = chunk["choices"][0].get("text", "")
                        full_response += token
                        yield token
                    except Exception:
                        continue

        # 后处理：cut hallucination on full response
        cleaned = _clean_response(full_response)
        # If cleaning changed the response, we can't "un-yield" tokens,
        # but the full cleaned version is what the caller should use.
        # The caller is responsible for final display.

    except Exception as e:
        logger.error(f"流式生成失败: {e}")
        yield f"\n[生成失败: {str(e)}]"


def _clean_response(response: str) -> str:
    """截断自问自答幻觉"""
    import re
    cut = re.search(r"(Human|Assistant|User|用户)[：:] ", response)
    if not cut:
        cut = re.search(r"\n(问题|提问|文档：|根据\[来源)", response)
    if cut:
        response = response[:cut.start()].strip()
    return response
```

同时更新 `generate()` 函数复用 `_clean_response`：

把 `generate()` 中的这一段（约第 75-78 行）：
```python
        # 截断自问自答幻觉
        cut = re.search(r"(Human|Assistant|User|用户)[：:] ", response)
        if not cut:
            cut = re.search(r"\n(问题|提问|文档：|根据\[来源)", response)
        if cut:
            response = response[: cut.start()].strip()
```

替换为：
```python
        response = _clean_response(response)
```

- [ ] **Step 2: 验证模块 import**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "from backend.rag.generator import generate, generate_stream, _clean_response; print('OK')"
```

预期：`OK`

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/rag/generator.py
git commit -m "feat: add streaming generation and refactor hallucination cleanup"
```

---

### Task 4: 添加流式 API 端点

**Files:**
- Modify: `backend/api/query.py`
- Modify: `backend/models/schemas.py`

- [ ] **Step 1: 在 schemas.py 添加流式请求模型**

编辑 `backend/models/schemas.py`，在 `QueryRequest` 后面添加：

```python
class QueryStreamRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    mode: Literal["knowledge_base", "error_logs", "auto"] = "auto"
    top_k: int = Field(default=4, ge=1, le=10)
```

- [ ] **Step 2: 在 query.py 添加流式端点**

编辑 `backend/api/query.py`，在文件顶部导入区添加：

```python
from fastapi.responses import StreamingResponse
from ..rag.generator import generate, generate_stream
from ..models.schemas import QueryRequest, QueryResponse, Source, QueryStreamRequest
```

在文件末尾（`_route` 函数之后）添加：

```python
@router.post("/query/stream")
async def query_kb_stream(req: QueryStreamRequest):
    """知识库问答 — SSE 流式输出"""
    import json as json_module

    retriever = get_retriever()

    if req.mode == "auto":
        mode = _route(req.question)
    else:
        mode = req.mode

    collection = "error_logs" if mode == "error_logs" else "knowledge_base"
    sources = retriever.retrieve(req.question, collection, req.top_k)

    if not sources and mode == "knowledge_base":
        sources = retriever.retrieve(req.question, "error_logs", req.top_k)
        mode = "error_logs" if sources else mode

    async def event_stream():
        full_answer = ""
        try:
            for token in generate_stream(req.question, sources, mode):
                full_answer += token
                yield f"data: {json_module.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json_module.dumps({'error': str(e)})}\n\n"
        finally:
            yield f"data: {json_module.dumps({'done': True, 'full_answer': full_answer, 'sources': [s['title'] for s in sources]})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 3: 验证端点注册成功**（无需启动完整服务，只检查语法）

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "from backend.api.query import router; print('OK, routes:', [r.path for r in router.routes])"
```

预期：看到包含 `/query/stream` 的路由列表。

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/api/query.py backend/models/schemas.py
git commit -m "feat: add SSE streaming endpoint for query"
```

---

### Task 5: 前端接入流式输出

**Files:**
- Modify: `frontend/app.py`

- [ ] **Step 1: 添加流式请求函数**

编辑 `frontend/app.py`，在 `query_api()` 函数之后添加：

```python
def query_api_stream(message: str, mode: str, top_k: int, history: list):
    """流式查询 API，逐 token yield 累积回答"""
    api_mode = {"知识库问答": "knowledge_base", "报错排查": "error_logs", "自动识别": "auto"}[mode]
    answer = ""
    sources_info = ""

    try:
        with httpx.stream(
            "POST",
            f"{API_BASE}/api/query/stream",
            json={"question": message, "mode": api_mode, "top_k": top_k},
            timeout=180,
        ) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("done"):
                        sources = data.get("sources", [])
                        if sources:
                            sources_info = "\n\n---\n**参考来源：**\n" + "\n".join(f"- {s}" for s in sources)
                        yield answer + sources_info
                        return
                    elif data.get("error"):
                        yield f"请求失败: {data['error']}"
                        return
                    else:
                        answer += data.get("token", "")
                        yield answer
    except Exception as e:
        yield f"请求失败: {e}"
```

在文件顶部添加 `import json`（如果还没有的话 — 当前只有 `import os` 和 `import httpx` 和 `import gradio as gr`）。

- [ ] **Step 2: 修改 respond 函数为生成器**

将现有的 `respond()` 函数（第 48-54 行）替换为：

```python
def respond(message, chat_history, mode, top_k):
    if not message.strip():
        yield "", chat_history
        return

    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": ""})

    for partial_answer in query_api_stream(message, mode, top_k, chat_history):
        chat_history[-1]["content"] = partial_answer
        yield "", chat_history
```

- [ ] **Step 3: 验证语法**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "import ast; ast.parse(open('frontend/app.py').read()); print('Syntax OK')"
```

预期：`Syntax OK`

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add frontend/app.py
git commit -m "feat: add streaming support to frontend"
```

---

### Task 6: 模型懒加载

**Files:**
- Modify: `backend/rag/embedder.py`
- Modify: `backend/main.py`

- [ ] **Step 1: 重构 OllamaEmbedder 为懒加载**

编辑 `backend/rag/embedder.py`：

```python
"""本地嵌入模型封装 — 基于 FlagEmbedding BGE-M3"""
from loguru import logger
from ..config import EMBEDDING_MODEL_PATH


class OllamaEmbedder:
    """本地嵌入模型封装，兼容原有接口名。首次调用 embed() 时才加载模型。"""

    def __init__(self, model_path: str | None = None):
        self._model_path = model_path or EMBEDDING_MODEL_PATH
        self.model = None

    def _ensure_loaded(self):
        if self.model is not None:
            return
        logger.info(f"加载嵌入模型: {self._model_path}")
        from FlagEmbedding import BGEM3FlagModel
        self.model = BGEM3FlagModel(self._model_path, use_fp16=False)
        logger.info("嵌入模型加载完成")

    def embed(self, texts: list[str]) -> list[dict]:
        """批量嵌入文本 → [{"dense": ..., "sparse": ...}, ...]"""
        self._ensure_loaded()
        results = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            batch_size=12,
        )
        output = []
        for i in range(len(texts)):
            output.append({
                "dense": results["dense_vecs"][i].tolist()
                    if results.get("dense_vecs") is not None
                    else None,
                "sparse": results["lexical_weights"][i]
                    if results.get("lexical_weights") is not None
                    else None,
            })
        return output

    def embed_query(self, text: str) -> dict:
        """嵌入单个查询文本 → {"dense": ..., "sparse": ...}"""
        return self.embed([text])[0]

    def embed_documents(self, texts: list[str]) -> list[dict]:
        """嵌入文档列表 → [{"dense": ..., "sparse": ...}, ...]"""
        return self.embed(texts)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None
```

- [ ] **Step 2: 简化 main.py 的 lifespan**

编辑 `backend/main.py`，将 lifespan 改为（去掉不必要逻辑）：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    import datetime
    app.state.startup_time = datetime.datetime.now().isoformat()
    app.state.models_loaded = False  # 懒加载，首次请求时才会变 True
    logger.info(f"Backend starting at {app.state.startup_time} (models will load on first request)")
    yield
```

注意需要检查当前代码中 `import datetime` 是否在文件顶部 — 当前在函数内部 import，保持不变即可。

- [ ] **Step 3: 验证懒加载行为**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "
from backend.rag.embedder import OllamaEmbedder
emb = OllamaEmbedder()
print(f'Before embed: model is None = {emb.model is None}')
# 不做 embed 调用，模型不应加载
"
```

预期：`Before embed: model is None = True`

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/rag/embedder.py backend/main.py
git commit -m "feat: lazy-load embedding model on first request"
```

---

## 阶段 2：一键部署

### Task 7: 提取共享入库函数

**Files:**
- Modify: `backend/ingestion/__init__.py`

- [ ] **Step 1: 将共享入库逻辑写入 ingestion/__init__.py**

当前 `backend/ingestion/__init__.py` 是空的。写入以下内容：

```python
"""数据入库 — 共享函数，供 CLI 脚本和 API 端点共用"""
from loguru import logger
from pathlib import Path
from ..rag.embedder import OllamaEmbedder
from ..rag.vector_store import VectorStore
from ..config import KNOWLEDGE_BASE_DIR, ERROR_LOGS_DIR


def ingest_knowledge_base(
    embedder: OllamaEmbedder,
    store: VectorStore,
    mode: str = "incremental",
) -> tuple[int, list[str]]:
    """入库知识库文档 → (chunk_count, errors)"""
    from .documents import DocumentParser
    parser = DocumentParser()

    coll = store.create_or_get("knowledge_base")
    if mode == "rebuild":
        store.delete_collection("knowledge_base")
        coll = store.create_or_get("knowledge_base")

    errors = []
    if not KNOWLEDGE_BASE_DIR.exists():
        return 0, ["知识库目录不存在"]

    try:
        chunks = parser.parse_directory(KNOWLEDGE_BASE_DIR)
        if chunks:
            texts = [c["content"] for c in chunks]
            metas = [c["metadata"] for c in chunks]
            ids = [c["metadata"]["chunk_id"] for c in chunks]

            batch = 20
            for i in range(0, len(texts), batch):
                b_texts = texts[i:i + batch]
                b_metas = metas[i:i + batch]
                b_ids = ids[i:i + batch]
                embs = embedder.embed_documents(b_texts)
                store.add(coll, b_texts, embs, b_metas, b_ids)

            # 建立稀疏索引
            sparse_vecs = [e["sparse"] for e in embedder.embed_documents(texts)]
            store.index_sparse(coll, ids, sparse_vecs, texts)

            logger.info(f"知识库入库: {len(chunks)} chunks")
            return len(chunks), []
    except Exception as e:
        errors.append(f"KB入库失败: {e}")
        logger.error(f"KB入库失败: {e}")
        return 0, errors


def ingest_error_logs(
    embedder: OllamaEmbedder,
    store: VectorStore,
    mode: str = "incremental",
) -> tuple[int, list[str]]:
    """入库报错日志 → (chunk_count, errors)"""
    from .error_logs import ErrorLogImporter
    importer = ErrorLogImporter()

    coll = store.create_or_get("error_logs")
    if mode == "rebuild":
        store.delete_collection("error_logs")
        coll = store.create_or_get("error_logs")

    errors = []
    if not ERROR_LOGS_DIR.exists():
        return 0, ["报错日志目录不存在"]

    try:
        all_chunks = []
        for f in ERROR_LOGS_DIR.iterdir():
            if f.suffix == ".json":
                all_chunks.extend(importer.from_json(f))
            elif f.suffix == ".csv":
                all_chunks.extend(importer.from_csv(f))
            elif f.suffix == ".txt":
                all_chunks.extend(importer.from_text(f))

        if all_chunks:
            texts = [c["content"] for c in all_chunks]
            metas = [c["metadata"] for c in all_chunks]
            ids = [c["metadata"]["record_id"] for c in all_chunks]
            embs = embedder.embed_documents(texts)
            store.add(coll, texts, embs, metas, ids)

            # 建立稀疏索引
            sparse_vecs = [e["sparse"] for e in embedder.embed_documents(texts)]
            store.index_sparse(coll, ids, sparse_vecs, texts)

            logger.info(f"报错库入库: {len(all_chunks)} 条")
            return len(all_chunks), []
    except Exception as e:
        errors.append(f"报错入库失败: {e}")
        logger.error(f"报错入库失败: {e}")
        return 0, errors
```

- [ ] **Step 2: 验证语法**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "import ast; ast.parse(open('backend/ingestion/__init__.py').read()); print('Syntax OK')"
```

预期：`Syntax OK`

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/ingestion/__init__.py
git commit -m "refactor: extract shared ingestion functions"
```

---

### Task 8: 创建 scripts/ingest.py

**Files:**
- Create: `scripts/ingest.py`

- [ ] **Step 1: 编写 CLI 入库脚本**

```python
#!/usr/bin/env python
"""知识库入库脚本 — CLI 入口

用法:
  D:/Anaconda3/python.exe scripts/ingest.py            # 增量入库
  D:/Anaconda3/python.exe scripts/ingest.py rebuild    # 重建索引
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from backend.rag.embedder import OllamaEmbedder
from backend.rag.vector_store import VectorStore
from backend.ingestion import ingest_knowledge_base, ingest_error_logs


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    if mode not in ("incremental", "rebuild"):
        print(f"用法: python scripts/ingest.py [incremental|rebuild]")
        sys.exit(1)

    print(f"=== 入库模式: {mode} ===")
    embedder = OllamaEmbedder()
    store = VectorStore()

    kb_count, kb_errors = ingest_knowledge_base(embedder, store, mode)
    err_count, err_errors = ingest_error_logs(embedder, store, mode)

    print(f"\n=== 入库完成 ===")
    print(f"知识库: {kb_count} chunks")
    print(f"报错库: {err_count} 条")
    for e in kb_errors + err_errors:
        print(f"  错误: {e}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证脚本语法**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "import ast; ast.parse(open('scripts/ingest.py').read()); print('Syntax OK')"
```

预期：`Syntax OK`

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add scripts/ingest.py
git commit -m "feat: add CLI ingestion script"
```

---

### Task 9: 重构 admin.py 使用共享入库函数

**Files:**
- Modify: `backend/api/admin.py`

- [ ] **Step 1: 简化 ingest 端点**

将 `admin.py` 的 `ingest()` 函数（约第 15-91 行）替换为：

```python
@router.post("/ingest", response_model=IngestResponse)
def ingest(mode: str = "incremental"):
    """批量入库所有文档"""
    embedder = OllamaEmbedder()
    store = VectorStore()

    kb_chunks, kb_errors = ingest_knowledge_base(embedder, store, mode)
    error_chunks, err_errors = ingest_error_logs(embedder, store, mode)

    all_errors = kb_errors + err_errors
    return IngestResponse(
        status="ok" if not all_errors else "partial",
        mode=mode,
        kb_chunks=kb_chunks,
        error_chunks=error_chunks,
        errors=all_errors,
    )
```

更新文件顶部的 import，把原来的：
```python
from ..ingestion.documents import DocumentParser
from ..ingestion.error_logs import ErrorLogImporter
```

替换为：
```python
from ..ingestion import ingest_knowledge_base, ingest_error_logs
```

并确保 `OllamaEmbedder` 和 `VectorStore` 的 import 保留（它们还在用）。

- [ ] **Step 2: 验证语法**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "import ast; ast.parse(open('backend/api/admin.py').read()); print('Syntax OK')"
```

预期：`Syntax OK`

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/api/admin.py
git commit -m "refactor: use shared ingestion functions in admin API"
```

---

### Task 10: 创建启动脚本 start.bat

**Files:**
- Create: `start.bat`

- [ ] **Step 1: 编写 Windows 启动脚本**

```batch
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
```

- [ ] **Step 2: 验证批处理语法**

```bash
# 验证文件存在
ls -la "C:/Users/14120/enterprise-kb-agent/start.bat"
```

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add start.bat
git commit -m "feat: add one-click startup script for Windows"
```

---

### Task 11: 更新 docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 适配 Vulkan 和流式输出**

当前 `docker-compose.yml` 的 llama-server 使用 CPU 镜像。由于 Vulkan 需要 GPU 直通，更新配置：

```yaml
services:
  llama-server:
    image: ghcr.io/ggerganov/llama.cpp:server-vulkan
    container_name: kb-llama
    ports:
      - "8080:8080"
    volumes:
      - D:/Qwen2.5-3B-Instruct-GGUF:/models:ro
    devices:
      - /dev/dri:/dev/dri  # GPU 设备直通 (Linux)
    command:
      - "-m"
      - "/models/qwen2.5-3b-instruct-q4_k_m.gguf"
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "8080"
      - "-c"
      - "4096"
      - "-ngl"
      - "99"
    restart: unless-stopped
    # Windows 不支持 devices，需要 deploy.resources 方式（见下方注释）
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  backend:
    build: .
    container_name: kb-backend
    ports:
      - "8000:8000"
      - "7860:7860"
    volumes:
      - D:/bge-m3:/models/bge-m3:ro
      - D:/bge-reranker-v2-m3:/models/bge-reranker-v2-m3:ro
      - ./data:/app/data
    environment:
      - MODEL_ROOT=/models
      - LLAMA_SERVER_URL=http://llama-server:8080/v1/completions
      - EMBEDDING_MODEL_DIR=bge-m3
      - RERANKER_MODEL_DIR=bge-reranker-v2-m3
      - DEVICE=cpu
    depends_on:
      - llama-server
    restart: unless-stopped
```

- [ ] **Step 2: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add docker-compose.yml
git commit -m "feat: update docker-compose for Vulkan GPU support"
```

---

## 阶段 3：死代码清理

### Task 12: 删除过期文件

- [ ] **Step 1: 删除 check_ollama.py**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git rm scripts/check_ollama.py
```

- [ ] **Step 2: 删除已废弃的 12GB 模型（需要确认）**

```bash
# 先确认路径存在
ls -la "D:/Qwen2.5-3B-Instruct/" | head -5
# 确认后删除
rm -rf "D:/Qwen2.5-3B-Instruct"
```

- [ ] **Step 3: 更新 PROGRESS.md 记录清理**

```bash
# 这一步手动在 PROGRESS.md 中标注 Qwen2.5-3B-Instruct 已删除、check_ollama.py 已删除
```

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add scripts/check_ollama.py PROGRESS.md
git commit -m "chore: remove deprecated check_ollama.py and update progress"
```

---

## 阶段 4：配置 + 测试

### Task 13: 配置统一 — retriever.py 熵值收敛

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/rag/retriever.py`

- [ ] **Step 1: 在 config.py 添加融合权重配置**

```python
# ── Dense + Sparse 融合 ──────────────────────────────
DENSE_WEIGHT = float(os.getenv("DENSE_WEIGHT", "0.7"))
SPARSE_WEIGHT = float(os.getenv("SPARSE_WEIGHT", "0.3"))
```

- [ ] **Step 2: 更新 retriever.py 消除硬编码**

编辑 `backend/rag/retriever.py`：

将 import 从：
```python
from ..config import TOP_K_RETRIEVAL, TOP_K_FINAL, SIMILARITY_THRESHOLD, RERANKER_MODEL_PATH
```

改为：
```python
from ..config import TOP_K_RETRIEVAL, TOP_K_FINAL, SIMILARITY_THRESHOLD, DENSE_WEIGHT, SPARSE_WEIGHT, RERANKER_MODEL_PATH
```

将第 57 行的：
```python
final_score = 0.7 * dense_score + 0.3 * sparse_score
```

改为：
```python
final_score = DENSE_WEIGHT * dense_score + SPARSE_WEIGHT * sparse_score
```

将第 64 行的：
```python
candidates = [c for c in candidates if 1.0 - c["distance"] >= 0.20]
```

改为：
```python
candidates = [c for c in candidates if 1.0 - c["distance"] >= SIMILARITY_THRESHOLD]
```

- [ ] **Step 3: 验证 import**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "from backend.rag.retriever import Retriever; print('OK')"
```

预期：`OK`

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/config.py backend/rag/retriever.py
git commit -m "refactor: centralize retriever config values"
```

---

### Task 14: 编写 retriever 单元测试

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_retriever.py`

- [ ] **Step 1: 创建测试目录和空 __init__.py**

```bash
mkdir -p "C:\Users\14120\enterprise-kb-agent\tests"
```

```python
# tests/__init__.py — empty
```

- [ ] **Step 2: 编写 retriever 测试**

```python
"""retriever 模块单元测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from backend.rag.retriever import Retriever
from backend.rag.embedder import OllamaEmbedder
from backend.rag.vector_store import VectorStore


class MockEmbedder:
    """模拟嵌入器，避免加载 8.6GB 模型"""
    def embed_query(self, text):
        return {
            "dense": [0.1] * 1024,
            "sparse": {"1": 0.5, "2": 0.3, "3": 0.1},
        }

    def embed_documents(self, texts):
        return [
            {"dense": [0.1] * 1024, "sparse": {"1": 0.5, "2": 0.3}}
        ] * len(texts)


class MockStore:
    """模拟向量库"""
    def __init__(self, docs=None, metas=None, dists=None):
        self._docs = docs or []
        self._metas = metas or [{}] * len(self._docs)
        self._dists = dists or [0.3] * len(self._docs)

    def create_or_get(self, name):
        return self

    def count(self, coll=None):
        return len(self._docs)

    def search(self, coll, q_emb, top_k=8):
        k = min(top_k, len(self._docs))
        return {
            "documents": [self._docs[:k]],
            "metadatas": [self._metas[:k]],
            "distances": [self._dists[:k]],
        }

    def search_sparse(self, q_sparse, top_k=16):
        return [(f"id_{i}", 0.6, doc) for i, doc in enumerate(self._docs[:top_k])]


class TestRetriever:
    """检索器测试套件"""

    def test_empty_store_returns_empty(self):
        store = MockStore(docs=[])
        emb = MockEmbedder()
        retriever = Retriever(emb, store)
        result = retriever.retrieve("test query", "knowledge_base")
        assert result == []

    def test_single_doc_above_threshold(self):
        store = MockStore(
            docs=["企业知识库系统基于 RAG 架构"],
            dists=[0.1],  # similarity = 0.9 > 0.20
        )
        emb = MockEmbedder()
        retriever = Retriever(emb, store)
        result = retriever.retrieve("什么是 RAG", "knowledge_base")
        assert len(result) == 1
        assert "RAG" in result[0]["content"]

    def test_doc_below_threshold_filtered(self):
        store = MockStore(
            docs=["完全不相关的文档内容"],
            dists=[0.95],  # similarity = 0.05 < 0.20
        )
        emb = MockEmbedder()
        retriever = Retriever(emb, store)
        result = retriever.retrieve("企业知识库", "knowledge_base")
        assert result == []

    def test_multiple_docs_ranked_by_score(self):
        store = MockStore(
            docs=["最相关文档 A", "次相关文档 B", "不太相关 C"],
            dists=[0.15, 0.30, 0.80],
        )
        emb = MockEmbedder()
        retriever = Retriever(emb, store)
        result = retriever.retrieve("查询", "knowledge_base", top_k=2)
        assert len(result) == 2
        # 第一个结果的分数应该最高（距离最小）
        assert result[0]["content"] == "最相关文档 A"


class TestRetrieverFormatResults:
    """结果格式化测试"""

    def test_format_includes_required_fields(self):
        emb = MockEmbedder()
        store = MockStore(
            docs=["测试文档"],
            metas=[{"source": "test.md", "title": "测试", "section": "概述"}],
            dists=[0.2],
        )
        retriever = Retriever(emb, store)
        result = retriever.retrieve("查询", "knowledge_base", top_k=1)
        assert len(result) == 1
        for key in ["content", "source", "title", "score"]:
            assert key in result[0], f"Missing field: {key}"
```

- [ ] **Step 3: 运行测试（此时不需要加载真实模型）**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -m pytest tests/test_retriever.py -v
```

预期：5 tests passed

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add tests/ tests/test_retriever.py
git commit -m "test: add retriever unit tests"
```

---

### Task 15: 编写 documents 单元测试

**Files:**
- Create: `tests/test_documents.py`

- [ ] **Step 1: 编写文档解析测试**

```python
"""documents 模块单元测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import tempfile
from backend.ingestion.documents import DocumentParser


class TestDocumentParser:
    """文档解析器测试套件"""

    def setup_method(self):
        self.parser = DocumentParser()

    def test_parse_txt_file(self):
        content = "这是第一段内容。\n\n这是第二段内容，用于测试分块功能。"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp = f.name

        try:
            chunks = self.parser.parse(tmp)
            assert len(chunks) >= 1
            assert all("content" in c for c in chunks)
            assert all("metadata" in c for c in chunks)
            assert all("chunk_id" in c["metadata"] for c in chunks)
        finally:
            Path(tmp).unlink()

    def test_chunk_has_required_metadata(self):
        content = "测试文档。" * 500  # 确保足够大触发 chunking
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp = f.name

        try:
            chunks = self.parser.parse(tmp)
            for chunk in chunks:
                meta = chunk["metadata"]
                assert "source" in meta
                assert "title" in meta
                assert "chunk_id" in meta
                assert len(meta["chunk_id"]) == 16  # MD5 前 16 位
        finally:
            Path(tmp).unlink()

    def test_parse_markdown_with_headers(self):
        md_content = """# 第一章
这是第一章的内容。这是关于系统架构的说明。

## 1.1 系统组件
系统由前端和后端组成。

# 第二章
这是第二章的内容。
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(md_content)
            tmp = f.name

        try:
            chunks = self.parser.parse(tmp)
            assert len(chunks) >= 1
            # Markdown 解析应该保留 section 信息
            sections = [
                c["metadata"].get("section", "")
                for c in chunks
                if c["metadata"].get("section")
            ]
            assert len(sections) >= 1
        finally:
            Path(tmp).unlink()

    def test_rejects_unsupported_extension(self):
        with pytest.raises(ValueError, match="不支持的文件类型"):
            self.parser.parse("test.xyz")

    def test_parse_directory_finds_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "doc1.txt").write_text("内容1", encoding="utf-8")
            (Path(tmpdir) / "doc2.txt").write_text("内容2", encoding="utf-8")
            (Path(tmpdir) / "ignore.jpg").write_text("图片")

            chunks = self.parser.parse_directory(tmpdir)
            assert len(chunks) >= 2  # 只解析 .txt 文件
```

- [ ] **Step 2: 运行测试**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -m pytest tests/test_documents.py -v
```

预期：5 tests passed（不需要加载任何模型）

- [ ] **Step 3: 运行全部测试**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -m pytest tests/ -v
```

预期：10 tests passed

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add tests/test_documents.py
git commit -m "test: add document parser unit tests"
```

---

## 阶段 5：生产加固

### Task 16: 添加请求队列

**Files:**
- Modify: `backend/api/query.py`

- [ ] **Step 1: 实现 asyncio 请求队列**

编辑 `backend/api/query.py`。首先在文件顶部已有的 import 区域添加 `import os` 和 `import asyncio`：

```diff
+import os
+import asyncio
 import time
 from fastapi import APIRouter
+from fastapi import HTTPException
 from fastapi.responses import StreamingResponse
```

然后在 `get_retriever()` 之后添加队列管理：

```python

# 请求队列（单模型串行推理）
_queue: asyncio.Queue | None = None
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "10"))


def _get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    return _queue


async def _enqueue_request(question: str, mode: str, top_k: int) -> dict:
    """将请求加入队列并等待执行结果"""
    queue = _get_queue()
    result_future: asyncio.Future = asyncio.get_event_loop().create_future()

    try:
        queue.put_nowait((question, mode, top_k, result_future))
    except asyncio.QueueFull:
        raise HTTPException(status_code=503, detail="服务器繁忙，请稍后重试")

    return await result_future


async def _process_queue():
    """后台协程：消费请求队列"""
    queue = _get_queue()
    retriever = get_retriever()  # 触发模型加载
    while True:
        question, mode, top_k, future = await queue.get()
        try:
            collection = "error_logs" if mode == "error_logs" else "knowledge_base"
            sources = retriever.retrieve(question, collection, top_k)
            if not sources and mode == "knowledge_base":
                sources = retriever.retrieve(question, "error_logs", top_k)
                mode = "error_logs" if sources else mode
            result = generate(question, sources, mode)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
```

注意：需要在文件顶部添加 `import os`。

- [ ] **Step 2: 修改 /api/query 端点使用队列**

将 `query_kb()` 函数改为 async，使用队列：

```python
@router.post("/query", response_model=QueryResponse)
async def query_kb(req: QueryRequest):
    """知识库问答"""
    t0 = time.time()

    if req.mode == "auto":
        mode = _route(req.question)
    else:
        mode = req.mode

    result = await _enqueue_request(req.question, mode, req.top_k)
    latency = (time.time() - t0) * 1000

    return QueryResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        mode=mode,
        tokens=result["tokens"],
        latency_ms=round(latency, 1),
    )
```

- [ ] **Step 3: 在 lifespan 中启动后台队列处理器**

编辑 `backend/main.py`，在 lifespan 中启动队列处理器：

```python
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    import datetime
    app.state.startup_time = datetime.datetime.now().isoformat()
    app.state.models_loaded = False
    logger.info(f"Backend starting at {app.state.startup_time}")

    # 启动后台队列处理器
    from .api.query import _process_queue
    queue_task = asyncio.create_task(_process_queue())
    app.state.queue_task = queue_task

    yield

    # 关闭时取消后台任务
    queue_task.cancel()
    try:
        await queue_task
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 4: 验证语法**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "import ast; ast.parse(open('backend/api/query.py').read()); print('Syntax OK')"
D:/Anaconda3/python.exe -c "import ast; ast.parse(open('backend/main.py').read()); print('Syntax OK')"
```

预期：`Syntax OK`（两行）

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/api/query.py backend/main.py
git commit -m "feat: add asyncio request queue for concurrent safety"
```

---

### Task 17: 增强健康检查

**Files:**
- Modify: `backend/api/query.py`
- Modify: `backend/api/admin.py`

- [ ] **Step 1: 在 query.py 中添加状态查询函数**

编辑 `backend/api/query.py`，在文件末尾添加：

```python
def get_queue_status() -> dict:
    """返回当前队列和模型状态，供 admin.py 健康检查调用"""
    return {
        "embedder_loaded": _embedder is not None and _embedder.is_loaded,
        "reranker_loaded": _retriever is not None and Retriever._reranker is not None,
        "queue_depth": _get_queue().qsize(),
    }
```

- [ ] **Step 2: 更新 admin.py 的 health 端点**

编辑 `backend/api/admin.py`，在文件顶部添加：

```python
import time
_start_time = time.time()
```

然后将 `health()` 函数（约第 117-119 行）替换为：

```python
@router.get("/health")
def health(request: Request):
    from ..api.query import get_queue_status

    qs = get_queue_status()
    return {
        "status": "ok",
        "startup_time": request.app.state.startup_time,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "models_loaded": qs["embedder_loaded"] and qs["reranker_loaded"],
        "queue_depth": qs["queue_depth"],
    }
```

- [ ] **Step 3: 验证语法**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "import ast; ast.parse(open('backend/api/query.py').read()); print('Syntax OK')"
D:/Anaconda3/python.exe -c "import ast; ast.parse(open('backend/api/admin.py').read()); print('Syntax OK')"
```

预期：两行 `Syntax OK`
    return {
        "status": "ok",
        "startup_time": request.app.state.startup_time,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "models_loaded": qs["embedder_loaded"] and qs["reranker_loaded"],
        "queue_depth": qs["queue_depth"],
    }
```

- [ ] **Step 2: 验证语法**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "import ast; ast.parse(open('backend/api/admin.py').read()); print('Syntax OK')"
```

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/api/admin.py backend/api/query.py
git commit -m "feat: enhance health check with model/queue status"
```

---

### Task 18: 结构化日志

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 添加请求 ID 中间件**

编辑 `backend/main.py`，在 `app = FastAPI(...)` 之后、中间件之前添加：

```python
import uuid
import time as time_module
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time_module.time()

        # 注入 request_id 到 request state
        request.state.request_id = request_id

        response = await call_next(request)

        elapsed_ms = (time_module.time() - start) * 1000
        logger.info(
            "request completed | "
            f"request_id={request_id} "
            f"method={request.method} "
            f"path={request.url.path} "
            f"status={response.status_code} "
            f"elapsed_ms={elapsed_ms:.0f}"
        )
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLogMiddleware)
```

注意：`app.add_middleware(RequestLogMiddleware)` 必须在 `app.add_middleware(CORSMiddleware, ...)` 之后。

需要添加 import：从 loguru 导入 logger（它已经在用了）。

- [ ] **Step 2: 验证完整启动**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -c "from backend.main import app; print(f'OK: {len(app.routes)} routes')"
```

预期：打印路由数量并正常退出。

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add backend/main.py
git commit -m "feat: add structured request logging with request IDs"
```

---

## 最终验证

### Task 19: 端到端测试

- [ ] **Step 1: 启动 Vulkan 版 llama-server**

```bash
# 终端 1：启动 Vulkan 推理服务
D:/llama-cpp-vulkan/llama-server.exe -m D:/Qwen2.5-3B-Instruct-GGUF/qwen2.5-3b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8080 -c 4096 -ngl 99
```

预期：服务启动，显示 Vulkan 初始化信息和模型加载成功。

- [ ] **Step 2: 启动后端**

```bash
# 终端 2：启动 FastAPI
D:/Anaconda3/python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

预期：2-3 秒内启动完成，显示"models will load on first request"

- [ ] **Step 3: 测试健康检查**

```bash
curl -s http://127.0.0.1:8000/api/admin/health | python -m json.tool
```

预期：`{"status": "ok", "models_loaded": false, ...}`

- [ ] **Step 4: 测试查询 API**

```bash
curl -s -X POST http://127.0.0.1:8000/api/query -H "Content-Type: application/json" -d "{\"question\": \"请假流程是什么\", \"mode\": \"knowledge_base\"}" | python -m json.tool
```

预期：返回 answer、sources、tokens、latency_ms。

- [ ] **Step 5: 测试流式端点**

```bash
curl -s -X POST http://127.0.0.1:8000/api/query/stream -H "Content-Type: application/json" -d "{\"question\": \"你好\", \"mode\": \"knowledge_base\"}" --no-buffer
```

预期：SSE 流式返回 token。

- [ ] **Step 6: 运行全部单元测试**

```bash
cd C:/Users/14120/enterprise-kb-agent && D:/Anaconda3/python.exe -m pytest tests/ -v
```

预期：All tests pass.

- [ ] **Step 7: 最终 Commit**

```bash
cd "C:\Users\14120\enterprise-kb-agent"
git add .
git commit -m "chore: final integration validation"
```

---

## 文件变更总览

| 任务 | 创建 | 修改 | 删除 |
|------|------|------|------|
| 1 | — | — | —（下载二进制） |
| 2 | — | `config.py`, `generator.py` | — |
| 3 | — | `generator.py` | — |
| 4 | — | `query.py`, `schemas.py` | — |
| 5 | — | `frontend/app.py` | — |
| 6 | — | `embedder.py`, `main.py` | — |
| 7 | `ingestion/__init__.py` | — | — |
| 8 | `scripts/ingest.py` | — | — |
| 9 | — | `admin.py` | — |
| 10 | `start.bat` | — | — |
| 11 | — | `docker-compose.yml` | — |
| 12 | — | — | `check_ollama.py`, `D:\Qwen2.5-3B-Instruct` |
| 13 | — | `config.py`, `retriever.py` | — |
| 14 | `tests/__init__.py`, `test_retriever.py` | — | — |
| 15 | `tests/test_documents.py` | — | — |
| 16 | — | `query.py`, `main.py` | — |
| 17 | — | `admin.py`, `query.py` | — |
| 18 | — | `main.py` | — |
| 19 | — | — | —（验证） |
