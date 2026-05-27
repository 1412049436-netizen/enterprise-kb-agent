# 企业内部知识库搭建 — 问题记录

> 项目路径: `C:\Users\14120\enterprise-kb-agent\`
> 搭建日期: 2025-05-25

---

## 1. C 盘空间不足

**现象**: C 盘 100G 只剩 5.2G，无法装模型。

**解决**: 清理了以下内容，释放 15.8G → 剩 21G：

| 删除项 | 大小 |
|--------|------|
| Docker WSL vhdx 数据盘 | 12.5G |
| npm 全局包 (openclaw/claude-code 等) | 2.7G |
| npm 缓存 | 464M |
| Temp 临时文件 | 588M |

**遗留**: Docker vhdx 被 WSL 锁定，`rm` 和 `cmd del` 均无效，最终用 Python `os.remove()` 才删掉。

---

## 2. Ollama 下载失败

**现象**: 
- `winget install Ollama.Ollama` 报错 "file being used by another process"（WinGet 缓存被锁）
- `curl` 从 ollama.com 下载速度极慢（<1MB/min），2GB 安装包无法完成

**最终方案**: 放弃 Ollama，改为从 ModelScope 直接下载模型文件，用 transformers 本地加载：

```bash
git lfs install
git clone https://www.modelscope.cn/Qwen/Qwen2.5-3B-Instruct.git → D:\Qwen2.5-3B-Instruct (5.7G)
git clone https://www.modelscope.cn/BAAI/bge-m3.git               → D:\bge-m3 (4.3G)
```

---

## 3. 架构从 Ollama API 改为本地模型加载

**原始设计**: 所有推理通过 Ollama HTTP API (`localhost:11434`)
**改为**: transformers + sentence-transformers 直接加载本地模型文件

| 模块 | 原来 | 现在 |
|------|------|------|
| 嵌入 | Ollama `/api/embed` | sentence-transformers + bge-m3 (CPU) |
| 生成 | Ollama `/api/generate` | transformers + Qwen2.5-3B (CUDA) |
| Rerank | Ollama LLM | 复用已加载的 Qwen2.5-3B |

**关键配置** (`backend/config.py`):
```python
LLM_MODEL_PATH = "D:/Qwen2.5-3B-Instruct"
EMBEDDING_MODEL_PATH = "D:/bge-m3"
```

---

## 4. 必须用 Anaconda Python

**现象**: 系统 `python` 命令指向 Hermes Agent 自带的 venv，缺少 `torch`、`transformers` 等依赖。

**解决**: 所有启动命令必须用完整路径 `D:\Anaconda3\python.exe`

```bash
# ✅ 正确
D:\Anaconda3\python.exe scripts\ingest.py
D:\Anaconda3\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
D:\Anaconda3\python.exe frontend\app.py

# ❌ 错误 — 会走 Hermes 的 Python
python scripts\ingest.py
```

---

## 5. API 启动后端口被旧进程占用

**现象**: 多次重启 uvicorn 后，旧进程未完全退出，新进程报 `[winerror 10048] 端口只允许使用一次`

**解决**: 每次重启前手动清理端口：
```bash
netstat -ano | grep ":8000 " | awk '{print $5}' | while read pid; do
  taskkill //F //PID $pid
done
```

---

## 6. Qwen2.5-3B 生成速度慢

**现象**: 128 tokens 需要 ~92 秒，约 1.4 tok/s

**原因**: 
- Qwen2.5-3B 虽然是 3B 小模型，但 `device_map="cuda"` 可能未完全利用 GPU
- 部分层可能 offload 到 CPU

**缓解**:
- 知识库 `max_tokens=128`（从 256 降下来）
- 报错模式 `max_tokens=256`（从 512 降下来）

**建议**: 如果有多余显存，可关闭 CPU offload：
```python
model = AutoModelForCausalLM.from_pretrained(path, device_map="cuda", ...)
# 不要用 device_map="auto"，它会自动把部分层放 CPU
```

---

## 7. Qwen2.5-3B 小模型幻觉（重复续写）

**现象**: 回答完正确内容后，模型会自己扮演 "Human:" 开始提问，然后继续回答，循环直到 max_tokens 用完。示例：

```
员工的请假流程为：填写请假申请表 -> 直属领导审批 -> HR备案。 
根据[来源1]中的文档1描述。 ... Human: 请续写以下文案: 品牌故事: ...
```

**缓解措施** (已实施):

1. **Prompt 精简** — 系统提示从多行规则压缩为一句话
2. **repetition_penalty=1.15** — 惩罚重复 token
3. **幻觉截断正则** — post-processing 检测并截断：
   ```python
   cut = re.search(r"(Human|Assistant|User|用户)[：:] ", response)
   if cut:
       response = response[:cut.start()].strip()
   ```

**根本原因**: 3B 模型在长上下文 RAG 场景下 prompt 遵循能力不足。**建议后续升级到 7B 或更大模型**（需 8GB+ 显存）。

---

## 8. 回答自相矛盾

**现象**: 模型先说"文档库中未找到相关信息"然后又列出文档中的流程步骤。

**原因**: prompt 中"没有就说未找到"对 3B 小模型形成错误触发。

**修复**: 去掉该指令，改为仅强调"不要编造"，让 post-processing 来处理无结果情况。

---

## 9. Gradio 6.0 API 不兼容

**现象**: 代码按 Gradio 4.x 编写，实际安装了 6.0，启动报错：
- `TypeError: Chatbot.__init__() got an unexpected keyword argument 'show_copy_button'`
- `TypeError: Chatbot.__init__() got an unexpected keyword argument 'bubble_full_width'`
- `theme` 和 `css` 参数从 `Blocks()` 移到了 `launch()`

**修复**: 已适配 Gradio 6.0 API。

---

## 10. API 响应超时

**现象**: 用 `httpx.post(timeout=120)` 发请求，生成 256 tokens 需要 ~155 秒，直接超时。

**修复**: 
- 生成 `max_tokens` 从 256 降到 128
- 前端 httpx timeout 设为 180 秒

---

## 当前系统极限

| 指标 | 值 |
|------|-----|
| 单次问答耗时 | ~92 秒 |
| CUDA 显存占用 | ~4GB |
| 系统内存占用 | ~2GB |
| 模型磁盘占用 | ~10GB (3B LLM + bge-m3) |
| 最大并发 | 1（模型未做并发优化） |

**改进方向**: 
- 升级到 Qwen2.5-7B（需 7-8GB 显存，速度约 2-3 tok/s）
- 或换用 vLLM / llama.cpp 提升推理吞吐
- 加请求队列支持多用户排队

---

## 11. ChromaDB 距离度量错误（已修复）

**现象**: 检索始终返回 0 条结果，导致模型完全靠猜测回答（幻觉）。

**原因**: ChromaDB 默认使用 l2（欧氏距离），范围 0~2，但 `retriever.py` 中 `1.0 - distance` 按余弦距离（范围 0~1）计算相似度。最佳匹配实际余弦相似度 0.74 被错误算成 0.28，低于阈值 0.35 被过滤。

**修复**: 
- `vector_store.py`: 创建 collection 时指定 `metadata={"hnsw:space": "cosine"}`
- `config.py`: `SIMILARITY_THRESHOLD` 从 0.35 降到 0.20

---

## 12. LLM Rerank 内存溢出

**现象**: Rerank 阶段报错 `页面文件太小，无法完成操作 (os error 1455)`，自动回退距离排序。

**原因**: 检索时已加载 bge-m3 嵌入模型（~4GB），再加载 Qwen2.5-3B（~6GB）做 rerank 超出可用内存。

**缓解**: Rerank 失败自动回退距离排序，不影响最终结果。但会丢失 LLM 重排序的精度提升。

**建议**: 换用 Cross-Encoder reranker（如 bge-reranker-v2-m3），模型小得多（~2GB）且速度快 100x。

---

## 13. 回答末尾截断

**现象**: 回答到一半被截断，如 "解析如下：1. **标准编号及名称**" 之后无内容。

**原因**: 知识库模式 `max_tokens=128` 不够用。对于有多个来源的复杂问题，128 tokens 在列出第 1 点后就耗尽了。

**建议**: `max_tokens` 提升到 200-256，或改用流式输出，或后处理截断时按句子边界切分。

---

## 14. 端到端响应 173 秒（已修复 → 20-32s）

**现象**: 单次查询从提问到回答耗时 173 秒（近 3 分钟）。

**原因**: Qwen2.5-3B 用 transformers 原生推理，未做任何优化。1.4 tok/s × 128 tokens ≈ 91s 纯推理时间。

**修复**: 替换推理引擎为 llama.cpp（GGUF 量化版）。
- 下载 Qwen2.5-3B q4_k_m GGUF 量化模型（1.96GB）
- 使用 llama-server 二进制（b9330 CPU版）作为 OpenAI 兼容 HTTP API
- generator.py 改为 httpx 调用 `localhost:8080/v1/completions`
- 速度从 1.4 tok/s → 5.9 tok/s（CPU），端到端从 173s → 20-32s（5.5x-8.5x）

---

## 15. llama.cpp 迁移过程踩坑记录

### 15a. pip 安装 llama-cpp-python 失败（Windows 长路径）

**现象**: `pip install llama-cpp-python` 报错 `[Errno 2] No such file or directory`，路径超过 260 字符。

**原因**: vendor/llama.cpp/tools/server/webui 目录嵌套太深。

**尝试的方案**:
- ❌ 设置 `TMP=C:\tmp` — pip 不认
- ❌ 开 `LongPathsEnabled` 注册表 — 还是不够
- ❌ `conda install` — Python 版本错乱（装成 3.14）
- ❌ GitHub Release wheel — cp313 wheel 不存在
- ❌ 旧版 `==0.2.90` — 缺 MSVC 编译器

**最终方案**: 放弃 pip，直接用 llama.cpp 预编译的 server 二进制。
- 下载 `llama-b9330-bin-win-cpu-x64.zip`（GitHub Releases）
- 解压到 `D:\llama-b9330\`
- 启动 `llama-server.exe -m <gguf模型> --port 8080`
- generator.py 改为 HTTP 调用，完全绕开编译/Python绑定问题

### 15b. CUDA 版二进制 DLL 缺失

**现象**: `llama-server.exe` 启动即崩溃，exit code 127 / 0xC0000135。

**原因**: CUDA 11.7/12.4 版本需要系统安装对应 CUDA Toolkit DLL（cudart64_xxx.dll），而 PyTorch 自带 CUDA 库不代表系统有。

**解决**: 改为纯 CPU 版二进制（`llama-b9330-bin-win-cpu-x64.zip`）。3B 小模型 CPU 推理足够快（5.9 tok/s），且无 DLL 依赖。

### 15c. llama-server 中文 UTF-8 编码

**现象**: curl 发中文 prompt 报 JSON parse error（ill-formed UTF-8 byte）。

**原因**: git-bash 的 curl 对中文编码处理有问题。

**解决**: 用 Python `httpx` 代替 curl 做测试。
