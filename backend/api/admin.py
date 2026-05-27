"""管理 API 路由 — 文档入库、统计"""
from fastapi import APIRouter, Request, UploadFile, File
from ..models.schemas import StatsResponse, IngestResponse
from ..rag.vector_store import VectorStore
from ..ingestion import ingest_knowledge_base, ingest_error_logs
from ..rag.embedder import OllamaEmbedder
from ..config import KNOWLEDGE_BASE_DIR, ERROR_LOGS_DIR
from pathlib import Path
from loguru import logger

router = APIRouter(prefix="/api/admin")


@router.post("/ingest", response_model=IngestResponse)
def ingest(mode: str = "incremental"):
    """批量入库所有文档"""
    embedder = OllamaEmbedder()
    store = VectorStore()

    kb_chunks, kb_errors = ingest_knowledge_base(embedder, store, mode)
    error_chunks, err_errors = ingest_error_logs(embedder, store, mode)

    all_errors = kb_errors + err_errors
    return IngestResponse(
        status="ok" if not all_errors else "partial",
        mode=mode,
        kb_chunks=kb_chunks,
        error_chunks=error_chunks,
        errors=all_errors,
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
