"""本地嵌入模型封装 — 基于 FlagEmbedding BGE-M3"""
from loguru import logger
from ..config import EMBEDDING_MODEL_PATH


class OllamaEmbedder:
    """本地嵌入模型封装，首次调用 embed() 时才加载模型"""

    def __init__(self, model_path: str | None = None):
        self._model_path = model_path or EMBEDDING_MODEL_PATH
        self.model = None

    def _ensure_loaded(self):
        if self.model is not None:
            return
        logger.info(f"加载嵌入模型: {self._model_path}")
        from FlagEmbedding import BGEM3FlagModel
        self.model = BGEM3FlagModel(self._model_path, use_fp16=False)
        logger.info("嵌入模型加载完成")

    def embed(self, texts: list[str]) -> list[dict]:
        """批量嵌入文本 → [{"dense": ..., "sparse": ...}, ...]"""
        self._ensure_loaded()
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
        return self.embed([text])[0]

    def embed_documents(self, texts: list[str]) -> list[dict]:
        return self.embed(texts)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None
