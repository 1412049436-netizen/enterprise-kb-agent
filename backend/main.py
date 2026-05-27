"""企业知识库问答系统 — FastAPI 入口"""
import asyncio
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time as time_module
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from loguru import logger
from .api.query import router as query_router
from .api.admin import router as admin_router
from .config import API_PORT

@asynccontextmanager
async def lifespan(app: FastAPI):
    import datetime
    app.state.startup_time = datetime.datetime.now().isoformat()
    app.state.models_loaded = False
    logger.info(f"Backend starting at {app.state.startup_time} (models will load on first request)")

    # 启动后台队列处理器
    from .api.query import _process_queue
    queue_task = asyncio.create_task(_process_queue())
    app.state.queue_task = queue_task

    yield

    # 关闭时取消后台任务
    queue_task.cancel()
    try:
        await queue_task
    except asyncio.CancelledError:
        pass


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time_module.time()

        request.state.request_id = request_id

        response = await call_next(request)

        elapsed_ms = (time_module.time() - start) * 1000
        logger.info(
            "request completed | "
            f"request_id={request_id} "
            f"method={request.method} "
            f"path={request.url.path} "
            f"status={response.status_code} "
            f"elapsed_ms={elapsed_ms:.0f}"
        )
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title="企业知识库问答系统",
    description="基于 RAG 的离线企业知识库问答 + 报错排查",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLogMiddleware)

app.include_router(query_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {
        "service": "企业知识库问答系统",
        "docs": "/docs",
        "health": "/api/admin/health",
    }


def main():
    import uvicorn
    logger.info(f"启动 FastAPI 服务: http://0.0.0.0:{API_PORT}")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
