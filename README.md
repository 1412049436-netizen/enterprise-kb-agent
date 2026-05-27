# 企业知识库问答系统

基于 RAG 的离线企业知识库问答 + 报错排查系统。

## 快速启动

### 1. 启动 Ollama
```bash
ollama serve
```

### 2. 安装依赖
```bash
cd enterprise-kb-agent
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 入库文档
将文档放入 `data/knowledge_base/`，报错记录放入 `data/error_logs/`，然后：
```bash
python scripts/ingest.py
```

### 4. 启动服务
```bash
# 终端1: 启动后端API
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 终端2: 启动Web UI
cd frontend && python app.py
```

### 5. 访问
- Web UI: http://localhost:7860
- API 文档: http://localhost:8000/docs

## 项目结构
```
enterprise-kb-agent/
├── backend/
│   ├── main.py          # FastAPI 入口
│   ├── config.py        # 配置管理
│   ├── models/schemas.py # 数据模型
│   ├── rag/             # RAG 核心
│   │   ├── embedder.py  # 嵌入模型
│   │   ├── vector_store.py # ChromaDB
│   │   ├── retriever.py # 检索+重排序
│   │   └── generator.py # LLM 生成
│   ├── ingestion/       # 数据导入
│   │   ├── documents.py # 文档解析
│   │   └── error_logs.py # 报错日志导入
│   └── api/
│       ├── query.py     # 问答API
│       └── admin.py     # 管理API
├── frontend/
│   └── app.py           # Gradio Web UI
├── data/
│   ├── knowledge_base/  # 原始文档
│   ├── error_logs/      # 报错记录
│   └── chroma_db/       # 向量库持久化
├── scripts/
│   ├── ingest.py        # 批量入库
│   └── check_ollama.py  # 环境检测
└── requirements.txt
```
