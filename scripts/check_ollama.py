#!/usr/bin/env python
"""验证本地模型和依赖可用性"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import LLM_MODEL_PATH, EMBEDDING_MODEL_PATH


def check_models():
    print("📁 模型文件检查")
    llm_ok = Path(LLM_MODEL_PATH).exists()
    emb_ok = Path(EMBEDDING_MODEL_PATH).exists()
    print(f"   LLM  ({LLM_MODEL_PATH}): {'✅' if llm_ok else '❌ 未找到'}")
    print(f"   嵌入 ({EMBEDDING_MODEL_PATH}): {'✅' if emb_ok else '❌ 未找到'}")
    return llm_ok and emb_ok


def test_embedding():
    print("\n🔢 测试嵌入模型...")
    try:
        from backend.rag.embedder import OllamaEmbedder
        emb = OllamaEmbedder()
        vec = emb.embed_query("企业知识库系统")
        print(f"   ✅ 正常，维度: {len(vec)}")
        return True
    except Exception as e:
        print(f"❌ 嵌入测试失败: {e}")
        return False


def test_llm():
    print("\n🧠 测试 LLM 生成...")
    try:
        from backend.rag.generator import _load_llm
        model, tokenizer = _load_llm()
        prompt = "用一句话介绍什么是 RAG 检索增强生成"
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        import torch
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=50, do_sample=False)
        answer = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        print(f"   回答: {answer[:100]}...")
        return True
    except Exception as e:
        print(f"❌ LLM 测试失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("  本地模型环境检测")
    print("=" * 50)
    if check_models():
        test_embedding()
        test_llm()
    print("\n" + "=" * 50)
