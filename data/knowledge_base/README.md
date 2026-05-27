# 企业知识库

欢迎使用企业知识库问答系统。

## 快速开始

1. 将需要索引的文档放入 `data/knowledge_base/` 目录
2. 支持格式: PDF、Word (.docx)、Markdown (.md)、纯文本 (.txt)
3. 运行 `python scripts/ingest.py` 完成入库
4. 启动服务后访问 Web UI 进行问答

## 系统架构

本系统采用 RAG (检索增强生成) 架构：

- 文档 → 分块 → 向量化 → 存入 ChromaDB
- 用户提问 → 向量检索 → Rerank 重排序 → LLM 生成回答

所有模型和数据完全离线运行，无需互联网连接。

## 技术栈

- **LLM**: Ollama + Qwen2.5-3B (离线推理)
- **嵌入模型**: bge-m3 (中文语义检索)
- **向量数据库**: ChromaDB
- **API**: FastAPI
- **UI**: Gradio
