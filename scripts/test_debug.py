"""Quick debug: test each component"""
import sys
sys.path.insert(0, "C:/Users/14120/enterprise-kb-agent")

from loguru import logger

print("=== 1. Testing Embedder (BGE-M3) ===")
try:
    from backend.rag.embedder import OllamaEmbedder
    e = OllamaEmbedder()
    q = e.embed_query("test query")
    print(f"  Dense dims: {len(q['dense'])}")
    print(f"  Sparse keys: {len(q['sparse'])}")
    print("  OK")
except Exception as ex:
    print(f"  FAILED: {ex}")

print("=== 2. Testing Retriever + Reranker ===")
try:
    from backend.rag.retriever import Retriever
    from backend.rag.vector_store import VectorStore
    embedder = OllamaEmbedder()
    store = VectorStore()
    retriever = Retriever(embedder, store)
    results = retriever.retrieve("GBT44261是什么", "knowledge_base", top_k=3)
    print(f"  Got {len(results)} results")
    for r in results:
        print(f"  - [{r['score']:.4f}] {r['title'][:40]}")
    print("  OK")
except Exception as ex:
    import traceback
    print(f"  FAILED: {ex}")
    traceback.print_exc()

print("=== 3. Testing Generator (llama-server) ===")
try:
    from backend.rag.generator import generate
    result = generate("GBT44261是什么", [], mode="knowledge_base")
    print(f"  Answer: {result['answer'][:200]}")
    print(f"  Tokens: {result.get('tokens', 0)}")
    print("  OK")
except Exception as ex:
    import traceback
    print(f"  FAILED: {ex}")
    traceback.print_exc()

print("=== DONE ===")
