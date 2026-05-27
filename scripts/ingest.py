#!/usr/bin/env python
"""一键入库脚本 — 扫描 data/ 目录，将文档导入向量库"""
import sys
sys.path.insert(0, ".")

from backend.ingestion.documents import DocumentParser
from backend.ingestion.error_logs import ErrorLogImporter
from backend.rag.embedder import OllamaEmbedder
from backend.rag.vector_store import VectorStore
from backend.config import KNOWLEDGE_BASE_DIR, ERROR_LOGS_DIR
from loguru import logger


def main(mode: str = "incremental"):
    parser = DocumentParser()
    importer = ErrorLogImporter()
    embedder = OllamaEmbedder()
    store = VectorStore()

    total_kb = 0
    total_err = 0

    # 知识库入库
    kb_coll = store.create_or_get("knowledge_base")
    if mode == "rebuild":
        store.delete_collection("knowledge_base")
        kb_coll = store.create_or_get("knowledge_base")

    if KNOWLEDGE_BASE_DIR.exists():
        chunks = parser.parse_directory(KNOWLEDGE_BASE_DIR)
        if chunks:
            texts = [c["content"] for c in chunks]
            metas = [c["metadata"] for c in chunks]
            ids = [c["metadata"]["chunk_id"] for c in chunks]

            batch = 20
            for i in range(0, len(texts), batch):
                b_texts = texts[i : i + batch]
                b_metas = metas[i : i + batch]
                b_ids = ids[i : i + batch]
                embs = embedder.embed_documents(b_texts)
                dense_vecs = [emb['dense'] for emb in embs]
                store.add(kb_coll, b_texts, dense_vecs, b_metas, b_ids)
                sparse_vecs = [emb['sparse'] for emb in embs]
                store.index_sparse(kb_coll, b_ids, sparse_vecs, b_texts)
                print(f"  进度: {min(i + batch, len(texts))}/{len(texts)}")

            total_kb = len(chunks)
    else:
        print(f"知识库目录不存在: {KNOWLEDGE_BASE_DIR}")

    # 报错库入库
    err_coll = store.create_or_get("error_logs")
    if mode == "rebuild":
        store.delete_collection("error_logs")
        err_coll = store.create_or_get("error_logs")

    if ERROR_LOGS_DIR.exists():
        all_chunks = []
        for f in sorted(ERROR_LOGS_DIR.iterdir()):
            try:
                if f.suffix == ".json":
                    all_chunks.extend(importer.from_json(f))
                elif f.suffix == ".csv":
                    all_chunks.extend(importer.from_csv(f))
                elif f.suffix == ".txt":
                    all_chunks.extend(importer.from_text(f))
            except Exception as e:
                print(f"  ⚠️ 跳过 {f.name}: {e}")

        if all_chunks:
            texts = [c["content"] for c in all_chunks]
            metas = [c["metadata"] for c in all_chunks]
            ids = [c["metadata"]["record_id"] for c in all_chunks]
            embs = embedder.embed_documents(texts)
            dense_vecs = [emb['dense'] for emb in embs]
            store.add(err_coll, texts, dense_vecs, metas, ids)
            sparse_vecs = [emb['sparse'] for emb in embs]
            store.index_sparse(err_coll, ids, sparse_vecs, texts)
            total_err = len(all_chunks)

    print(f"\n✅ 入库完成: 知识库 {total_kb} chunks · 报错库 {total_err} 条")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    print(f"启动批量入库 (模式: {mode})...")
    main(mode)
