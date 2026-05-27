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
) -> tuple:
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
) -> tuple:
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

            sparse_vecs = [e["sparse"] for e in embedder.embed_documents(texts)]
            store.index_sparse(coll, ids, sparse_vecs, texts)

            logger.info(f"报错库入库: {len(all_chunks)} 条")
            return len(all_chunks), []
    except Exception as e:
        errors.append(f"报错入库失败: {e}")
        logger.error(f"报错入库失败: {e}")
        return 0, errors
