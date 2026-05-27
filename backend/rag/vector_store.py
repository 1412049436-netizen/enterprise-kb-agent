"""ChromaDB 向量存储封装"""
import chromadb
from chromadb.config import Settings
from loguru import logger
from ..config import CHROMA_DB_DIR


class VectorStore:
    """ChromaDB 持久化向量存储"""

    def __init__(self, persist_dir: str | None = None):
        persist_dir = persist_dir or str(CHROMA_DB_DIR)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.sparse_index = {}
        logger.info(f"ChromaDB 已连接: {persist_dir}")

    def create_or_get(self, name: str) -> chromadb.Collection:
        """获取或创建 collection"""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def delete_collection(self, name: str):
        """删除 collection（用于重建索引）"""
        try:
            self.client.delete_collection(name)
            logger.info(f"已删除 collection: {name}")
        except Exception:
            pass

    def add(
        self,
        collection: chromadb.Collection,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[str],
    ):
        """批量添加文档到向量库"""
        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def search(
        self,
        collection: chromadb.Collection,
        query_embedding: list[float],
        top_k: int = 8,
    ) -> dict:
        """语义检索，返回文档 + 元数据 + 距离"""
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def index_sparse(self, collection, ids, sparse_vectors, texts=None):
        """建立稀疏索引：{doc_id: {vector, content}}"""
        texts = texts or [""] * len(ids)
        for doc_id, sv, text in zip(ids, sparse_vectors, texts):
            self.sparse_index[doc_id] = {"vector": sv, "content": text}
        logger.info(f"稀疏索引已更新，共 {len(self.sparse_index)} 个文档")

    def search_sparse(self, query_sparse, top_k=16):
        """稀疏检索，返回 top_k 个 (doc_id, score, content) 元组"""
        scores = []
        for doc_id, entry in self.sparse_index.items():
            doc_sparse = entry["vector"]
            score = sum(
                query_sparse.get(token_id, 0.0) * weight
                for token_id, weight in doc_sparse.items()
            )
            if score > 0:
                scores.append((doc_id, score, entry["content"]))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def count(self, collection: chromadb.Collection) -> int:
        """返回 collection 中的文档数"""
        return collection.count()
