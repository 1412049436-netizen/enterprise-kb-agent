"""企业知识库问答系统 — Gradio Web UI (Gradio 6.0)"""
import gradio as gr
import httpx
import json
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

# 全局 token（单用户部署够用）
_token: str | None = None


def _headers() -> dict:
    """返回带 token 的请求头"""
    if _token:
        return {"Authorization": f"Bearer {_token}"}
    return {}


def login_api(username: str, password: str) -> str:
    """登录并返回状态消息"""
    global _token
    try:
        resp = httpx.post(
            f"{API_BASE}/api/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            _token = resp.json()["access_token"]
            return f"✅ 登录成功: {username}"
        else:
            detail = resp.json().get("detail", "未知错误")
            return f"❌ 登录失败: {detail}"
    except Exception as e:
        return f"❌ 连接失败: {e}"


def logout_api() -> str:
    """退出登录"""
    global _token
    _token = None
    return "已退出登录"


def query_api(message: str, mode: str, top_k: int, history: list) -> str:
    api_mode = {"知识库问答": "knowledge_base", "报错排查": "error_logs", "自动识别": "auto"}[mode]
    try:
        resp = httpx.post(
            f"{API_BASE}/api/query",
            json={"question": message, "mode": api_mode, "top_k": top_k},
            headers=_headers(),
            timeout=180,
        )
        if resp.status_code == 401:
            return "⚠️ 请先登录（左侧输入账号密码）"
        if resp.status_code == 403:
            return "⛔ 权限不足"
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
    gr.Markdown("""# 📚 企业知识库问答系统
完全离线运行 · 基于 RAG 架构 · 支持知识库问答和报错排查""")

    with gr.Row():
        # ── 左侧：登录 + 设置 ──
        with gr.Column(scale=1):
            gr.Markdown("### 🔐 登录")
            login_user = gr.Textbox(label="用户名", value="admin")
            login_pass = gr.Textbox(label="密码", type="password", value="admin123")
            with gr.Row():
                login_btn = gr.Button("登录", variant="primary", size="sm")
                logout_btn = gr.Button("退出", size="sm")
            login_status = gr.Markdown("")

            gr.Markdown("---")

            mode = gr.Radio(["自动识别", "知识库问答", "报错排查"], label="问答模式", value="自动识别")
            top_k = gr.Slider(1, 10, value=4, step=1, label="检索数量")
            stats_btn = gr.Button("检查状态")
            stats_box = gr.Markdown("")

        # ── 右侧：对话区 ──
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话", height=450)
            msg = gr.Textbox(label="输入你的问题", placeholder="例如：请假流程是什么？", lines=2)
            with gr.Row():
                send_btn = gr.Button("发送", variant="primary")
                clear_btn = gr.Button("清空对话")

    # ── 事件绑定 ──

    login_btn.click(login_api, [login_user, login_pass], [login_status])
    logout_btn.click(logout_api, None, [login_status])

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
            r = httpx.get(
                f"{API_BASE}/api/admin/stats",
                headers=_headers(),
                timeout=5,
            )
            if r.status_code == 401:
                return "⚠️ 请先登录（需要管理员权限）"
            if r.status_code == 403:
                return "⛔ 需要管理员权限"
            d = r.json()
            return f"**知识库:** {d['knowledge_base_chunks']} chunks · **报错库:** {d['error_logs_chunks']} 条"
        except Exception:
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
