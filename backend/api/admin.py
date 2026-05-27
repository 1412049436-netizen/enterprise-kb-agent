"""管理 API 路由 — 文档入库、统计"""
from fastapi import APIRouter, Request, UploadFile, File
from ..models.schemas import StatsResponse, IngestResponse
from ..rag.vector_store import VectorStore
from ..ingestion.documents import DocumentParser
from ..ingestion.error_logs import ErrorLogImporter
from ..rag.embedder import OllamaEmbedder
from ..config import KNOWLEDGE_BASE_DIR, ERROR_LOGS_DIR
from pathlib import Path
from loguru import logger

router = APIRouter(prefix="/api/admin")


@router.post("/ingest", response_model=IngestResponse)
def ingest(mode: str = "incremental"):
    """批量入库所有文档"""
    parser = DocumentParser()
    importer = ErrorLogImporter()
    embedder = OllamaEmbedder()
    store = VectorStore()

    kb_chunks = 0
    error_chunks = 0
    errors = []

    # 知识库
    kb_coll = store.create_or_get("knowledge_base")
    if mode == "rebuild":
        store.delete_collection("knowledge_base")
        kb_coll = store.create_or_get("knowledge_base")

    if KNOWLEDGE_BASE_DIR.exists():
        try:
            chunks = parser.parse_directory(KNOWLEDGE_BASE_DIR)
            if chunks:
                texts = [c["content"] for c in chunks]
                metas = [c["metadata"] for c in chunks]
                ids = [c["metadata"]["chunk_id"] for c in chunks]

                # 分批嵌入（避免一次发太多）
                batch = 20
                for i in range(0, len(texts), batch):
                    b_texts = texts[i : i + batch]
                    b_metas = metas[i : i + batch]
                    b_ids = ids[i : i + batch]
                    embs = embedder.embed_documents(b_texts)
                    store.add(kb_coll, b_texts, embs, b_metas, b_ids)

                kb_chunks = len(chunks)
                logger.info(f"知识库入库: {kb_chunks} chunks")
        except Exception as e:
            errors.append(f"KB入库失败: {e}")
            logger.error(f"KB入库失败: {e}")

    # 报错库
    err_coll = store.create_or_get("error_logs")
    if mode == "rebuild":
        store.delete_collection("error_logs")
        err_coll = store.create_or_get("error_logs")

    if ERROR_LOGS_DIR.exists():
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
                store.add(err_coll, texts, embs, metas, ids)
                error_chunks = len(all_chunks)
                logger.info(f"报错库入库: {error_chunks} 条")
        except Exception as e:
            errors.append(f"报错入库失败: {e}")
            logger.error(f"报错入库失败: {e}")

    return IngestResponse(
        status="ok" if not errors else "partial",
        mode=mode,
        kb_chunks=kb_chunks,
        error_chunks=error_chunks,
        errors=errors,
    )


@router.get("/stats", response_model=StatsResponse)
def stats():
    """知识库统计"""
    store = VectorStore()
    kb = store.create_or_get("knowledge_base")
    err = store.create_or_get("error_logs")

    # 统计文件数
    kb_files = 0
    err_files = 0
    if KNOWLEDGE_BASE_DIR.exists():
        kb_files = len(list(KNOWLEDGE_BASE_DIR.rglob("*")))
    if ERROR_LOGS_DIR.exists():
        err_files = len(list(ERROR_LOGS_DIR.rglob("*")))

    return StatsResponse(
        knowledge_base_chunks=store.count(kb),
        error_logs_chunks=store.count(err),
        knowledge_base_files=kb_files,
        error_logs_files=err_files,
    )


@router.get("/health")
def health(request: Request):
    return {"status": "ok", "startup_time": request.app.state.startup_time}
