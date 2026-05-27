"""retriever 模块单元测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from backend.rag.retriever import Retriever


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

    def test_empty_store_returns_empty(self):
        store = MockStore(docs=[])
        emb = MockEmbedder()
        retriever = Retriever(emb, store)
        result = retriever.retrieve("test query", "knowledge_base")
        assert result == []

    def test_single_doc_above_threshold(self):
        store = MockStore(
            docs=["企业知识库系统基于 RAG 架构"],
            dists=[0.1],
        )
        emb = MockEmbedder()
        retriever = Retriever(emb, store)
        result = retriever.retrieve("什么是 RAG", "knowledge_base")
        assert len(result) == 1
        assert "RAG" in result[0]["content"]

    def test_doc_below_threshold_filtered(self):
        store = MockStore(
            docs=["完全不相关的文档内容"],
            dists=[0.95],
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
        # 验证返回的是前两个高分文档（重排序后顺序可能变化）
        contents = {r["content"] for r in result}
        assert "最相关文档 A" in contents
        assert "次相关文档 B" in contents

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
