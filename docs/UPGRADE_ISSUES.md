# 企业内部知识库 — 升级踩坑记录

> 记录 2026-05-26 从 v0.5 (dense-only) → v0.6 (dense+sparse+reranker) 的完整升级过程。

---

## 一、升级目标

```
v0.5: Query → BGE-M3 dense → ChromaDB cosine → 距离排序 → Qwen2.5-3B 生成
v0.6: Query → BGE-M3 dense+sparse → ChromaDB + 稀疏融合 → CrossEncoder Rerank → Qwen2.5-3B 生成
```

---

## 二、Phase 1: embedder 改造 (dense → dense+sparse)

### 问题 1: 嵌入返回值类型不兼容

**现象**: `embedder.embed_query()` 原本返回 `list[float]`，改成 BGE-M3 的 `encode(return_sparse=True)` 后返回 `{"dense": [...], "sparse": {...}}`。`retriever.py` 和 `vector_store.py` 直接把 dict 当 list 传给 ChromaDB，炸了。

**修复**: 需要同步改三个文件：
- `embedder.py`: 返回 `{"dense": list[float], "sparse": {int: float}}`
- `retriever.py`: 取 `q_emb["dense"]` 传给 ChromaDB
- `vector_store.py`: 新增 `search_sparse()` 处理稀疏向量

**教训**: 改了接口返回值就要全链路检查所有调用方，不能只改一个文件。

---

## 三、Phase 2: 稀疏检索实现 (sparse index)

### 问题 2: 旧索引没有 sparse 数据

**现象**: 加完 `index_sparse()` 和 `search_sparse()` 后，检索时 `sparse_index` 为空，sparse 分支完全不生效。

**根因**: 旧文档入库时只存了 dense 向量到 ChromaDB，稀疏权重没有存。`VectorStore.sparse_index` 是内存字典，进程重启就丢。

**修复**: 
1. 修改 `scripts/ingest.py rebuild` 逻辑，入库时间时调用 `store.index_sparse()` 存稀疏索引
2. 重建索引：65 条旧文档 + 4 条报错日志 = 69 chunks

**教训**: 新增存储结构时必须考虑已有数据的迁移/重建路径。

---

### 问题 3: Dense+Sparse 融合后 Recall 毫无提升

**现象**: 双路融合后跑 7 个测试 query 的 Recall 对比：

```
        旧(dense-only)  新(dense+sparse)
Recall@1    71%             71%
Recall@3    71%             71%
Recall@5    86%             86%
Recall@8   100%            100%
```

一字不差，0 提升。

**根因分析**:
1. **bge-m3 的 sparse 不是传统 BM25**。它的 `lexical_weights` 是从同一个 transformer 学出来的，和 dense 向量高度相关。dense 分高的文档 sparse 分也高 — 双路没有带来新信息，只是重复打分。
2. **知识库太小（69 chunks）**。dense 已经 100% 能召回到正确答案（Recall@8=100%）。sparse 在几百/几千条的大库里才有增量价值 — 当 dense 漏掉的东西 sparse 能补回来。

**真正的瓶颈**: Recall@1=71% vs Recall@8=100%，说明问题不是"找不到"而是"排不准"。dense 把正确答案召回来了但排在后面。

**决策**: 代码保留（正确实现了，大库时有用），继续推进 Phase 3 的 CrossEncoder Rerank 解决排序问题。

**教训**:
- Sparse 不是万能药，要先分析数据规模决定是否值得
- bge-m3 的 dual-vector 不等于互补 — lexical_weights 是 "learned token importance"，不是 BM25 的词频匹配
- 先看 Recall@K 曲线定位瓶颈（召回 vs 排序），再选技术方案

---

## 四、Phase 3: CrossEncoder Rerank

### 问题 4: 模型下载与加载

**现象**: `bge-reranker-v2-m3` 需要 4.3GB，放在 `D:/bge-reranker-v2-m3/`。

**注意**: 
- `sentence-transformers` 的 `CrossEncoder` 加载时需要 `model.safetensors` 和 `config.json`
- 首次加载需要 30-60s（CPU 上加载 4.3GB 权重）
- 加载后常驻内存，首次查询慢后续快

---

### 问题 5: retriever.py 硬编码阈值

**现象**: `retriever.py` 第 64 行：

```python
candidates = [c for c in candidates if 1.0 - c["distance"] >= 0.20]
```

应该用 `config.SIMILARITY_THRESHOLD`，虽然是同一个值但改配置不会生效。

**修复方向**: 改为 `>= SIMILARITY_THRESHOLD`。

---

## 五、Phase 4: 后端崩溃/启动问题

### 问题 6: 后端持续崩溃，新代码不生效

**现象**: 改了代码后，API 测试结果和没改一样。后端一直崩溃重启，启动的是旧进程。

**根因链**:
1. 旧 Python 进程残留，占着端口 8000
2. 新进程启动时 `[Errno 10048]` 端口冲突，启动失败
3. 旧的崩溃进程自动重启，加载的还是旧代码
4. 用户看到的结果来自旧进程

**修复步骤**:
```bash
# 1. 杀干净所有 Python
taskkill /F /IM python.exe

# 2. 确认端口释放
netstat -ano | findstr :8000

# 3. 重新启动（注意 workdir！）
cd C:\Users\14120\enterprise-kb-agent
D:\Anaconda3\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**教训**:
- 修改代码后必须确认进程已重启并加载了新代码
- 验证方法：加一个 log 标记或版本号到启动日志里
- Windows 上 `taskkill /F /IM python.exe` 是原子弹，但比慢慢排查快

---

### 问题 7: uvicorn 启动时缺少 workdir

**现象**: 
```
Error: No module named 'backend'
```

**根因**: 从非项目目录启动 uvicorn 时，Python 找不到 `backend` 包。

**修复**: 必须 `cd C:\Users\14120\enterprise-kb-agent` 再启动，或用 `-WorkingDirectory` 参数（PowerShell 的 `Start-Process`）。

**教训**: uvicorn 的模块导入依赖于当前工作目录在项目根。

---

### 问题 8: Hermes 的终端环境混乱

**现象**: 用户在 PowerShell 终端里粘贴中文消息，被当成 PowerShell 命令执行：

```
PS> [，重新设计一下如果我们的嵌入模型加上一个spare...
"[" 后面缺少类型名称。  ← PowerShell 报错

PS> ，变为混合检索，然后用llm
无法将"变为混合检索"识别为 cmdlet  ← PowerShell 报错

PS> what happen
无法将"what"识别为 cmdlet  ← PowerShell 报错
```

所有发给 Hermes 的消息都被 PowerShell 当命令解析了。

**根因**: Hermes 在 Windows 上默认使用 git-bash (MSYS)，但用户的终端窗口是 PowerShell。当用户在 PowerShell 窗口里粘贴内容时，PowerShell 先尝试解析，导致乱码和命令错误。

**Hermes 实际的 shell 环境**: bash (git-bash / MSYS)，不是 PowerShell。所有 `terminal` 工具调用都走 bash。

**教训**: 
- Windows 用户要注意当前终端类型 — PowerShell 窗口 ≠ Hermes 的 shell
- 粘贴中文到 PowerShell 可能乱码
- Hermes 内部命令用 POSIX 语法（`ls`、`grep`、单引号），不是 PowerShell 语法

---

## 六、最终结果

### 管线架构

```
Query
  → BGE-M3 embed → dense[1024] + sparse[lexical_weights]
  → ChromaDB cosine dense 召回 Top-16
  → sparse 增强: 0.7*dense_score + 0.3*sparse_score
  → bge-reranker-v2-m3 CrossEncoder 重排 → Top-4
  → llama-server Qwen2.5-3B GGUF q4_k_m 生成回答
```

### Reranker 效果验证

```
Query: "GBT44261.1标准什么时候发布的"

融合排序:  合规文件 > 合规文件 > 标准解读 > 标准解读 > 合规文件
                      ↑ 正确答案在第 7 位

Rerank后:  正式发布(0.9958) > 标准解读(0.9912) > 合规文件(0.0004)
           ↑ 正确答案升到第 1 位！
```

### 端到端性能

- 首次查询：~64s（含 embedder 加载 + reranker 加载）
- 后续查询：~20-30s（模型已缓存）
- 回答质量：Recall@1 从 71% → 预期应有提升（需跑完整 benchmark 确认）

---

## 七、技术债务 & 后续 TODO

| # | 问题 | 优先级 |
|---|------|--------|
| 1 | retriever.py 硬编码阈值 0.20，应改用 config | P2 |
| 2 | 回答截断 (128 tokens → 256) | P1 |
| 3 | 首次查询慢 (60s+)，应考虑模型预热 | P2 |
| 4 | 无请求队列，并发不安全 | P2 |
| 5 | sparse_index 内存存储，重启丢失（需持久化） | P3 |
| 6 | 三服务手动启动，无一键脚本 | P1 |
| 7 | 缺少系统的 Recall/MRR benchmark 脚本 | P2 |
| 8 | PROGRESS.md 已过时，需更新到 v0.6 状态 | P1 |

---

## 八、经验总结

1. **改接口先查全链路调用方** — embedder 返回值变了，retriever/vector_store/ingestion 全要改
2. **新结构要配迁移路径** — sparse index 是新增的，旧数据必须重建
3. **先定位瓶颈再选方案** — sparse 解决召回，reranker 解决排序，我们这个规模的问题是排序
4. **改完代码要验证新进程** — Windows 端口冲突导致旧代码常驻是最隐蔽的 bug
5. **模型加载慢不可怕，可以预热** — 首次 64s 是 embedder+reranker 加载，后续 20-30s 可以接受
6. **Windows 混合终端是坑** — PowerShell 窗口 ≠ bash shell，中文粘贴会乱码
