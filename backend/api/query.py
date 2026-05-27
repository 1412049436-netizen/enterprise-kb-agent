"""查询 API 路由"""
import time
from fastapi import APIRouter
from ..models.schemas import QueryRequest, QueryResponse, Source
from ..rag.embedder import OllamaEmbedder
from ..rag.vector_store import VectorStore
from ..rag.retriever import Retriever
from ..rag.generator import generate

router = APIRouter(prefix="/api")

# 全局实例（懒加载）
_embedder = None
_store = None
_retriever = None


def get_retriever():
    global _embedder, _store, _retriever
    if _retriever is None:
        _embedder = OllamaEmbedder()
        _store = VectorStore()
        _retriever = Retriever(_embedder, _store)
    return _retriever


@router.post("/query", response_model=QueryResponse)
def query_kb(req: QueryRequest):
    """知识库问答"""
    t0 = time.time()
    retriever = get_retriever()

    # 确定检索目标
    if req.mode == "auto":
        mode = _route(req.question)
    else:
        mode = req.mode

    # 检索
    collection = "error_logs" if mode == "error_logs" else "knowledge_base"
    sources = retriever.retrieve(req.question, collection, req.top_k)

    # 如果知识库没找到，尝试报错库
    if not sources and mode == "knowledge_base":
        sources = retriever.retrieve(req.question, "error_logs", req.top_k)
        mode = "error_logs" if sources else mode

    # 生成
    result = generate(req.question, sources, mode)
    latency = (time.time() - t0) * 1000

    return QueryResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        mode=mode,
        tokens=result["tokens"],
        latency_ms=round(latency, 1),
    )


@router.post("/query/error", response_model=QueryResponse)
def query_error(req: QueryRequest):
    """报错排查"""
    req.mode = "error_logs"
    return query_kb(req)


def _route(query: str) -> str:
    """自动识别查询类型"""
    error_kw = [
        "报错", "错误", "异常", "Error", "Exception",
        "失败", "502", "500", "timeout", "connect",
        "崩溃", "crash", "挂了", "不响应", "宕机",
    ]
    kb_kw = [
        "文档", "手册", "流程", "规范", "制度",
        "说明", "介绍", "如何使用", "配置", "API",
        "接口", "架构", "设计",
    ]

    q = query.lower()
    if any(k.lower() in q for k in error_kw):
        return "error_logs"
    if any(k.lower() in q or k in query for k in kb_kw):
        return "knowledge_base"
    return "knowledge_base"  # 默认知识库
