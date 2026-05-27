"""LLM 生成模块 — 通过 llama-server HTTP API 调用 (OpenAI 兼容)"""
import os
import re
import httpx
from loguru import logger
from ..config import LLAMA_SERVER_URL, KB_MAX_TOKENS, ERROR_MAX_TOKENS, GENERATION_TIMEOUT

# ── 提示词模板 ───────────────────────────────────────

KB_SYSTEM_PROMPT = "你是企业知识库助手。严格基于提供的文档内容回答，不要编造。用中文简洁回答。"

ERROR_SYSTEM_PROMPT = "你是技术报错排查助手。基于错误记录回答。匹配就给出解决方案+步骤，类似就说明'参考方案'，无匹配就说'未找到该错误记录'。用中文。"

def build_context(sources: list[dict]) -> str:
    """将检索结果拼接为上下文"""
    parts = []
    for i, s in enumerate(sources, 1):
        title = s.get("title") or s.get("source", "文档")
        section = s.get("section", "")
        header = f"[来源{i}] {title}" + (f" > {section}" if section else "")
        parts.append(f"{header}\n{s['content']}\n")
    return "\n---\n".join(parts)


def generate(
    query: str,
    sources: list[dict],
    mode: str = "knowledge_base",
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> dict:
    ctx = build_context(sources)

    if mode == "error_logs":
        system_prompt = ERROR_SYSTEM_PROMPT
        temperature = 0.2
        max_tokens = ERROR_MAX_TOKENS
    else:
        system_prompt = KB_SYSTEM_PROMPT
        max_tokens = KB_MAX_TOKENS

    user_prompt = f"""文档：
{ctx}

问题：{query}

回答："""

    full_prompt = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    try:
        resp = httpx.post(
            LLAMA_SERVER_URL,
            json={
                "prompt": full_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
                "stop": ["<|im_end|>", "<|im_start|>"],
                "stream": False,
            },
            timeout=GENERATION_TIMEOUT,
        )
        data = resp.json()
        response = data["choices"][0]["text"].strip()

        # 截断自问自答幻觉
        cut = re.search(r"(Human|Assistant|User|用户)[：:] ", response)
        if not cut:
            cut = re.search(r"\n(问题|提问|文档：|根据\[来源)", response)
        if cut:
            response = response[: cut.start()].strip()

        usage = data.get("usage", {})
        return {
            "answer": response,
            "sources": sources,
            "tokens": usage.get("completion_tokens", 0),
            "tokens_per_second": round(
                usage.get("completion_tokens", 0)
                / max(usage.get("total_time", 1) / 1e9, 0.01),
                1,
            ),
        }
    except Exception as e:
        logger.error(f"生成失败: {e}")
        return {
            "answer": f"回答生成失败: {str(e)}",
            "sources": sources,
            "tokens": 0,
            "tokens_per_second": 0,
        }
