"""企业知识库问答系统 — FastAPI 入口"""
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from .api.query import router as query_router
from .api.admin import router as admin_router
from .config import API_PORT

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.startup_time = datetime.datetime.now().isoformat()
    app.state.models_loaded = False
    logger.info(f"Backend starting at {app.state.startup_time} (models will load on first request)")
    yield


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
