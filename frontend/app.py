"""企业知识库问答系统 — Gradio Web UI (Gradio 6.0)"""
import gradio as gr
import httpx
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def query_api(message: str, mode: str, top_k: int, history: list):
    api_mode = {"知识库问答": "knowledge_base", "报错排查": "error_logs", "自动识别": "auto"}[mode]
    try:
        resp = httpx.post(
            f"{API_BASE}/api/query",
            json={"question": message, "mode": api_mode, "top_k": top_k},
            timeout=180,
        )
        data = resp.json()
        answer = data["answer"]
        if data.get("sources"):
            answer += "\n\n---\n**参考来源：**\n"
            for s in data["sources"]:
                title = s.get("title") or s.get("source", "未知")
                answer += f"- {title} (相关度: {s.get('score', 0):.0%})\n"
        answer += f"\n\n*{data.get('tokens', 0)} tokens · {data.get('latency_ms', 0):.0f}ms*"
        return answer
    except Exception as e:
        return f"请求失败: {e}"


with gr.Blocks(title="企业知识库助手") as demo:
    gr.Markdown("""# 📚 企业知识库问答系统\n完全离线运行 · 基于 RAG 架构 · 支持知识库问答和报错排查""")

    with gr.Row():
        with gr.Column(scale=1):
            mode = gr.Radio(["自动识别", "知识库问答", "报错排查"], label="问答模式", value="自动识别")
            top_k = gr.Slider(1, 10, value=4, step=1, label="检索数量")
            gr.Markdown("### 使用说明\n- **知识库问答**: 查询文档中的信息\n- **报错排查**: 匹配历史错误解决方案\n- **自动识别**: 系统自动判断查询类型")
            stats_btn = gr.Button("检查状态")
            stats_box = gr.Markdown("")

        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话", height=500)
            msg = gr.Textbox(label="输入你的问题", placeholder="例如：请假流程是什么？", lines=2)
            with gr.Row():
                send_btn = gr.Button("发送", variant="primary")
                clear_btn = gr.Button("清空对话")

    def respond(message, chat_history, mode, top_k):
        if not message.strip():
            return "", chat_history
        answer = query_api(message, mode, top_k, chat_history)
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": answer})
        return "", chat_history

    send_btn.click(respond, [msg, chatbot, mode, top_k], [msg, chatbot])
    msg.submit(respond, [msg, chatbot, mode, top_k], [msg, chatbot])
    clear_btn.click(lambda: [], None, chatbot)

    def check_stats():
        try:
            r = httpx.get(f"{API_BASE}/api/admin/stats", timeout=5)
            d = r.json()
            return f"**知识库:** {d['knowledge_base_chunks']} chunks · **报错库:** {d['error_logs_chunks']} 条"
        except:
            return "后端未连接"

    stats_btn.click(check_stats, None, stats_box)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
        css="footer {display: none !important;}",
    )
