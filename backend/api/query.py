"""查询 API 路由"""
import os
import time
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..models.schemas import QueryRequest, QueryStreamRequest, QueryResponse, Source
from ..rag.embedder import OllamaEmbedder
from ..rag.vector_store import VectorStore
from ..rag.retriever import Retriever
from ..rag.generator import generate, generate_stream
from ..auth.dependencies import get_current_user

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


# 请求队列（单模型串行推理）
_queue: asyncio.Queue | None = None
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "10"))


def _get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    return _queue


async def _enqueue_request(question: str, mode: str, top_k: int) -> dict:
    """将请求加入队列并等待执行结果"""
    queue = _get_queue()
    loop = asyncio.get_event_loop()
    result_future: asyncio.Future = loop.create_future()

    try:
        queue.put_nowait((question, mode, top_k, result_future))
    except asyncio.QueueFull:
        raise HTTPException(status_code=503, detail="服务器繁忙，请稍后重试")

    return await result_future


async def _process_queue():
    """后台协程：消费请求队列"""
    queue = _get_queue()
    retriever = get_retriever()  # 触发模型加载
    while True:
        question, mode, top_k, future = await queue.get()
        try:
            collection = "error_logs" if mode == "error_logs" else "knowledge_base"
            sources = retriever.retrieve(question, collection, top_k)
            if not sources and mode == "knowledge_base":
                sources = retriever.retrieve(question, "error_logs", top_k)
                mode = "error_logs" if sources else mode
            result = generate(question, sources, mode)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)


@router.post("/query", response_model=QueryResponse)
async def query_kb(req: QueryRequest, user = Depends(get_current_user)):
    """知识库问答"""
    t0 = time.time()

    if req.mode == "auto":
        mode = _route(req.question)
    else:
        mode = req.mode

    result = await _enqueue_request(req.question, mode, req.top_k)
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


@router.post("/query/stream")
async def query_kb_stream(req: QueryStreamRequest, user = Depends(get_current_user)):
    """知识库问答 — SSE 流式输出"""
    import json as json_module
    from loguru import logger
    t_start = time.time()

    retriever = get_retriever()
    t_get_retriever = time.time()

    if req.mode == "auto":
        mode = _route(req.question)
    else:
        mode = req.mode

    collection = "error_logs" if mode == "error_logs" else "knowledge_base"
    sources = retriever.retrieve(req.question, collection, req.top_k)
    t_retrieve = time.time()

    if not sources and mode == "knowledge_base":
        sources = retriever.retrieve(req.question, "error_logs", req.top_k)
        mode = "error_logs" if sources else mode

    logger.info(f"[TIMING] get_retriever={t_get_retriever - t_start:.1f}s, "
                f"retrieve={t_retrieve - t_get_retriever:.1f}s, "
                f"total_before_stream={t_retrieve - t_start:.1f}s, "
                f"sources={len(sources)}")

    async def event_stream():
        full_answer = ""
        t_stream_start = time.time()
        first_token = None
        try:
            for token in generate_stream(req.question, sources, mode):
                if first_token is None:
                    first_token = time.time()
                    logger.info(f"[TIMING] first_token_after={first_token - t_stream_start:.1f}s")
                full_answer += token
                yield f"data: {json_module.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json_module.dumps({'error': str(e)})}\n\n"
        finally:
            t_done = time.time()
            logger.info(f"[TIMING] stream_total={t_done - t_stream_start:.1f}s, "
                        f"total_request={t_done - t_start:.1f}s")
            from ..rag.generator import _clean_response
            cleaned = _clean_response(full_answer)
            yield f"data: {json_module.dumps({'done': True, 'full_answer': cleaned, 'sources': [s['title'] for s in sources]})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def get_queue_status() -> dict:
    """返回当前队列和模型状态，供 admin.py 健康检查调用"""
    return {
        "embedder_loaded": _embedder is not None and _embedder.is_loaded,
        "reranker_loaded": _retriever is not None and Retriever._reranker is not None,
        "queue_depth": _get_queue().qsize(),
    }
