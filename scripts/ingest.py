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
