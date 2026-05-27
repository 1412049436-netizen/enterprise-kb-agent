# Production Readiness Optimization — Design Spec

> 2026-05-27 | enterprise-kb-agent | v0.6 → v1.0

## Goal

Make the enterprise-kb-agent production-ready for 50+ concurrent users on current hardware (GTX 1650 Ti 4GB), with a clean upgrade path to future GPUs.

## Constraints

- C: drive must keep ≥ 5GB free (currently 12.8GB, no writes planned)
- D: drive has 26.3GB free, additional 12GB reclaimable (deprecated Qwen2.5-3B-Instruct)
- GTX 1650 Ti 4GB VRAM — only the 1.96GB GGUF LLM fits; embedding/reranker models stay on CPU
- No system-level CUDA Toolkit installation — use Vulkan backend or self-contained CUDA wheel

---

## Phase 1: Performance Breakthrough

### 1.1 LLM Inference: CPU → GPU via Vulkan

**Current**: llama.cpp CPU binary, 5.9 tok/s.
**Target**: llama.cpp Vulkan binary, estimated 15-25 tok/s on GTX 1650 Ti.

The Vulkan backend requires no CUDA Toolkit — Windows ships Vulkan drivers for NVIDIA GPUs. The GGUF model (1.96GB) fits in 4GB VRAM with room for KV cache.

**Fallback**: If Vulkan underperforms, use `llama-cpp-python` with pre-built CUDA wheel (bundles its own CUDA DLLs).

**Files changed**: `backend/rag/generator.py` (point LLAMA_SERVER_URL to Vulkan binary), download new llama.cpp Vulkan binary to `D:\llama-cpp-vulkan\`.

### 1.2 Streaming Output

**Current**: `generator.py` uses `"stream": false`, waits for full generation.
**Target**: SSE streaming via FastAPI `StreamingResponse`.

- `generator.py`: add `generate_stream()` generator function, yields tokens as they arrive
- `backend/api/query.py`: new `/api/query/stream` endpoint returning `text/event-stream`
- `frontend/app.py`: Gradio chatbot consumes stream, renders tokens incrementally

**Perceived latency**: first token in < 1s instead of waiting for all 200 tokens.

### 1.3 Lazy Model Loading

**Current**: BGE-M3 (8.6GB) + Reranker (4.3GB) load at FastAPI import time → ~30s startup.
**Target**: Load on first request.

- `OllamaEmbedder`: defer `BGEM3FlagModel()` init to first `embed()` call
- `Retriever._get_reranker()`: already lazy, no change needed
- `backend/main.py`: lifespan startup reduced to config validation only

**Startup time**: 30s → 2-3s. First query pays the model-loading cost (~30s), subsequent queries instant.

### Performance Targets

| Metric | Before | After |
|--------|--------|-------|
| Backend startup | ~30s | 2-3s |
| Inference speed | 5.9 tok/s (CPU) | 15-25 tok/s (Vulkan) |
| End-to-end answer | 20-64s | 4-12s |
| Time-to-first-token | N/A (batch) | < 1s |

---

## Phase 2: One-Click Deploy

### 2.1 Create `scripts/ingest.py`

README references `python scripts/ingest.py` but the file doesn't exist. Create it by extracting the ingestion logic from `admin.py`'s `/api/admin/ingest` endpoint into a shared function, callable from both CLI and API.

### 2.2 Docker Compose with Vulkan

Update `docker-compose.yml` llama-server service to use Vulkan-enabled image. Add device passthrough for GPU.

### 2.3 Startup Script

`start.bat` (Windows): starts llama-server → waits → starts FastAPI → starts Gradio. One double-click instead of three terminals.

---

## Phase 3: Dead Code Removal

### 3.1 Delete `scripts/check_ollama.py`

References `_load_llm()` function that no longer exists (generator was rewritten to llama-server HTTP API in v0.6).

### 3.2 Delete `D:\Qwen2.5-3B-Instruct` (12GB)

Marked deprecated in PROGRESS.md. Replaced by GGUF version.

### 3.3 Deduplicate Ingestion Logic

`admin.py:ingest()` (~60 lines) duplicates what `scripts/ingest.py` should do. Extract shared `ingest_knowledge_base()` and `ingest_error_logs()` functions into `backend/ingestion/__init__.py`. Both the API endpoint and the CLI script call the same functions.

---

## Phase 4: Configuration + Testing

### 4.1 Centralize Config

Move hardcoded values into `config.py`:

| Location | Hardcoded Value | New Config Key |
|----------|----------------|----------------|
| `retriever.py:64` | `0.20` threshold | Already exists: `SIMILARITY_THRESHOLD` — use it |
| `retriever.py:57` | `0.7/0.3` fusion weights | `DENSE_WEIGHT`, `SPARSE_WEIGHT` |
| `generator.py:39` | `max_tokens=256` (error) | `ERROR_MAX_TOKENS` |
| `generator.py:42` | `max_tokens=200` (kb) | `KB_MAX_TOKENS` |

### 4.2 Unit Tests

Add `tests/` directory with pytest:

- `tests/test_retriever.py`: dense/sparse fusion math, threshold filtering, rerank result ordering
- `tests/test_documents.py`: chunk splitting, overlap, Markdown header parsing

Target: 80% coverage on `rag/` and `ingestion/` modules.

---

## Phase 5: Production Hardening

### 5.1 Request Queue

`asyncio.Queue` with max concurrency = 1 (single model can't parallelize). Returns 503 if queue full. Prevents OOM from concurrent embedding + generation.

### 5.2 Enhanced Health Check

`/api/admin/health` returns:
```json
{
  "status": "ok",
  "models_loaded": true,
  "queue_depth": 3,
  "uptime_seconds": 3600
}
```

### 5.3 Structured Logging

Add request_id to each log line. JSON format for log aggregation. Log latency per phase (embed, retrieve, rerank, generate).

---

## What We're NOT Doing

- **Not switching embedding/reranker models to GPU**: 4GB VRAM is too small for 8.6GB + 4.3GB models. These stay on CPU until hardware upgrade.
- **Not adding authentication**: out of scope for this optimization round.
- **Not migrating away from ChromaDB**: it works for the current scale. Revisit at 100K+ documents.
- **Not rewriting in another language**: Python + FastAPI is appropriate for this workload.

---

## File Change Summary

| Phase | Files |
|-------|-------|
| 1 | `backend/rag/generator.py`, `backend/main.py`, `backend/api/query.py`, `frontend/app.py` |
| 2 | `scripts/ingest.py` (new), `start.bat` (new), `docker-compose.yml`, `backend/ingestion/__init__.py` |
| 3 | Delete: `scripts/check_ollama.py`, `D:\Qwen2.5-3B-Instruct`; Refactor: `backend/api/admin.py` |
| 4 | `backend/config.py`, `backend/rag/retriever.py`, `tests/` (new) |
| 5 | `backend/api/query.py`, `backend/api/admin.py`, `backend/main.py` |
