"""向量检索 + Rerank 重排序"""
from loguru import logger
from sentence_transformers import CrossEncoder
from .embedder import OllamaEmbedder
from .vector_store import VectorStore
from ..config import TOP_K_RETRIEVAL, TOP_K_FINAL, SIMILARITY_THRESHOLD, RERANKER_MODEL_PATH


class Retriever:
    """向量召回 → Rerank → 返回最佳结果"""

    _reranker = None

    def __init__(self, embedder: OllamaEmbedder, vector_store: VectorStore):
        self.embedder = embedder
        self.store = vector_store

    def retrieve(
        self,
        query: str,
        collection_name: str = "knowledge_base",
        top_k: int | None = None,
    ) -> list[dict]:
        top_k = top_k or TOP_K_FINAL
        fetch_k = max(top_k * 2, TOP_K_RETRIEVAL)

        coll = self.store.create_or_get(collection_name)
        if self.store.count(coll) == 0:
            return []

        q_emb = self.embedder.embed_query(query)
        raw = self.store.search(coll, q_emb['dense'], top_k=fetch_k)

        docs = raw.get("documents", [[]])[0] or []
        metas = raw.get("metadatas", [[]])[0] or []
        dists = raw.get("distances", [[]])[0] or []

        # 建立 dense 候选 Map，key 为 content 前 100 字符
        dense_map = {}
        candidates = []
        for d, m, dist in zip(docs, metas, dists):
            if 1.0 - dist >= SIMILARITY_THRESHOLD:
                content_key = d[:100] if d else ""
                entry = {"content": d, "metadata": m or {}, "distance": dist}
                dense_map[content_key] = entry
                candidates.append(entry)

        # 稀疏检索，作为 dense 结果的分数增强
        sparse_results = self.store.search_sparse(q_emb['sparse'], top_k=fetch_k)

        for doc_id, score, content in sparse_results:
            content_key = content[:100] if content else ""
            if content_key in dense_map:
                entry = dense_map[content_key]
                dense_score = 1.0 - entry["distance"]
                sparse_score = score
                final_score = 0.7 * dense_score + 0.3 * sparse_score
                entry["distance"] = 1.0 - final_score

        if not candidates:
            return []

        # 过滤低分候选
        candidates = [c for c in candidates if 1.0 - c["distance"] >= 0.20]

        candidates.sort(key=lambda x: x["distance"])

        reranked = self._rerank(query, candidates, top_k)
        return reranked

    @classmethod
    def _get_reranker(cls):
        if cls._reranker is None:
            cls._reranker = CrossEncoder(RERANKER_MODEL_PATH)
        return cls._reranker

    def _rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        if len(candidates) <= 1:
            return self._format_results(candidates[:top_k])

        reranker = self._get_reranker()
        pairs = [(query, c["content"]) for c in candidates]
        scores = reranker.predict(pairs, show_progress_bar=False)

        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)

        logger.info(f"Rerank: {len(candidates)} candidates, scores range {min(scores):.4f}-{max(scores):.4f}")
        logger.info(f"  Best: {candidates[0].get('metadata',{}).get('title','?')[:30]} rerank={candidates[0].get('rerank_score',0):.4f}")

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return self._format_results(candidates[:top_k])

    def _format_results(self, candidates: list[dict]) -> list[dict]:
        results = []
        for c in candidates:
            score = round(c.get("rerank_score", 1.0 - c["distance"]), 4)
            results.append({
                "content": c["content"],
                "source": c["metadata"].get("source", "未知来源"),
                "title": c["metadata"].get("title", ""),
                "section": c["metadata"].get("section", ""),
                "score": score,
            })
        return results
