"""企业知识库问答系统 — 配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── 本地模型路径 ───────────────────────────────────
MODEL_ROOT = Path(os.getenv("MODEL_ROOT", "D:/"))
LLM_MODEL_PATH = str(MODEL_ROOT / os.getenv("LLM_MODEL_DIR", "Qwen2.5-3B-Instruct"))
# GGUF 量化版路径（llama.cpp 使用）
LLM_GGUF_PATH = str(MODEL_ROOT / os.getenv("LLM_GGUF_DIR", "Qwen2.5-3B-Instruct-GGUF/qwen2.5-3b-instruct-q4_k_m.gguf"))
EMBEDDING_MODEL_PATH = str(MODEL_ROOT / os.getenv("EMBEDDING_MODEL_DIR", "bge-m3"))
RERANKER_MODEL_PATH = str(MODEL_ROOT / os.getenv("RERANKER_MODEL_DIR", "bge-reranker-v2-m3"))
DEVICE = os.getenv("DEVICE", None)  # None=auto, or "cpu"/"cuda"

# ── Chunking 参数 ────────────────────────────────────
# 文档解析时的核心参数
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))        # 每个chunk的字符数（中文600字≈1200 tokens边距）
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))   # 相邻chunk重叠区域
MD_HEADER_LEVEL = int(os.getenv("MD_HEADER_LEVEL", "3")) # Markdown按H1-H3标题拆分

# ── 检索参数 ─────────────────────────────────────────
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "8"))           # 向量检索初步召回
TOP_K_FINAL = int(os.getenv("TOP_K_FINAL", "4"))                   # Rerank后最终保留
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.20"))

# ── 数据路径 ─────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
ERROR_LOGS_DIR = DATA_DIR / "error_logs"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"

# ── 服务端口 ─────────────────────────────────────────
API_PORT = int(os.getenv("API_PORT", "8000"))
UI_PORT = int(os.getenv("UI_PORT", "7860"))

# ── 确保目录存在 ─────────────────────────────────────
for d in [DATA_DIR, KNOWLEDGE_BASE_DIR, ERROR_LOGS_DIR, CHROMA_DB_DIR]:
    d.mkdir(parents=True, exist_ok=True)
