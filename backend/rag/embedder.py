"""本地嵌入模型封装 — 基于 FlagEmbedding BGE-M3"""
from loguru import logger
from FlagEmbedding import BGEM3FlagModel
from ..config import EMBEDDING_MODEL_PATH


class OllamaEmbedder:
    """本地嵌入模型封装，兼容原有接口名"""

    def __init__(self, model_path: str | None = None):
        path = model_path or EMBEDDING_MODEL_PATH
        logger.info(f"加载嵌入模型: {path}")
        self.model = BGEM3FlagModel(path, use_fp16=False)

    def embed(self, texts: list[str]) -> list[dict]:
        """批量嵌入文本 → [{"dense": ..., "sparse": ...}, ...]"""
        results = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            batch_size=12,
        )
        output = []
        for i in range(len(texts)):
            output.append({
                "dense": results["dense_vecs"][i].tolist()
                    if results.get("dense_vecs") is not None
                    else None,
                "sparse": results["lexical_weights"][i]
                    if results.get("lexical_weights") is not None
                    else None,
            })
        return output

    def embed_query(self, text: str) -> dict:
        """嵌入单个查询文本 → {"dense": ..., "sparse": ...}"""
        return self.embed([text])[0]

    def embed_documents(self, texts: list[str]) -> list[dict]:
        """嵌入文档列表 → [{"dense": ..., "sparse": ...}, ...]"""
        return self.embed(texts)
