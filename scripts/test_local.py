#!/usr/bin/env python
"""端到端测试：嵌入 -> 入库 -> 检索 -> 生成"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.rag.embedder import OllamaEmbedder
from backend.rag.vector_store import VectorStore
from backend.rag.retriever import Retriever
from backend.rag.generator import generate

print("1. Init embedder...")
emb = OllamaEmbedder()
store = VectorStore()
rtr = Retriever(emb, store)

print("2. Indexing documents...")
coll = store.create_or_get("knowledge_base")
docs = [
    "企业知识库系统基于 RAG 架构，使用向量检索和 LLM 生成回答",
    "员工请假流程：填写请假申请表 -> 直属领导审批 -> HR 备案",
    "系统部署在 Docker 容器中，使用 FastAPI 提供 API 服务",
]
vecs = emb.embed_documents(docs)
metas = [{"source": f"doc_{i}", "title": f"文档{i}"} for i in range(3)]
ids = [f"chunk_{i}" for i in range(3)]
coll.add(ids=ids, embeddings=vecs, documents=docs, metadatas=metas)
print(f"   Indexed {store.count(coll)} documents")

print("3. Retrieving...")
sources = rtr.retrieve("请假流程是什么", "knowledge_base", top_k=2)
print(f"   Retrieved {len(sources)} sources:")
for s in sources:
    print(f"   [{s['score']}] {s['content'][:60]}...")

print("4. Generating...")
result = generate("请假流程是什么", sources, "knowledge_base")
print(f"   Answer: {result['answer'][:200]}")
print(f"   Tokens: {result['tokens']}")

print("\n=== ALL TESTS PASSED ===")
