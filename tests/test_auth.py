"""认证模块单元测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ["JWT_SECRET"] = "test-secret-key"

# 初始化测试数据库
from backend.auth.database import create_users_table, get_connection
from backend.auth.security import hash_password

create_users_table()
conn = get_connection()
conn.execute("DELETE FROM users")
conn.execute(
    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
    ("admin", hash_password("admin123"), "admin"),
)
conn.execute(
    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
    ("user1", hash_password("user123"), "user"),
)
conn.commit()
conn.close()

from backend.main import app

# --- 在创建 TestClient (触发 lifespan) 之前，mock 模型依赖 ---
import backend.api.query as query_module
from unittest.mock import MagicMock

# Mock get_retriever: 避免 lifespan 中的 _process_queue 启动时加载模型
_mock_retriever = MagicMock()
_mock_retriever.retrieve.return_value = []
query_module.get_retriever = lambda: _mock_retriever

# 绕过异步队列，直接返回假结果
async def _mock_enqueue_request(question, mode, top_k):
    return {
        "answer": "test answer",
        "sources": [],
        "mode": mode,
        "tokens": 2,
        "latency_ms": 1.0,
    }

query_module._enqueue_request = _mock_enqueue_request

# 绕过 lifespan 状态污染：直接在 app 状态中设置必要字段
import datetime as _dt
app.state.startup_time = _dt.datetime.now().isoformat()
app.state.models_loaded = False

from fastapi.testclient import TestClient
client = TestClient(app)


class TestAuthLogin:

    def test_login_success_returns_token(self):
        resp = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self):
        resp = client.post("/api/auth/login", json={
            "username": "admin", "password": "wrong"
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user_returns_401(self):
        resp = client.post("/api/auth/login", json={
            "username": "nobody", "password": "xxx"
        })
        assert resp.status_code == 401


class TestAuthDependencies:

    def test_no_token_returns_401(self):
        resp = client.post("/api/query", json={
            "question": "test", "mode": "knowledge_base"
        })
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        resp = client.post("/api/query", json={
            "question": "test", "mode": "knowledge_base"
        }, headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_valid_token_access_query(self):
        login_resp = client.post("/api/auth/login", json={
            "username": "user1", "password": "user123"
        })
        token = login_resp.json()["access_token"]
        resp = client.post("/api/query", json={
            "question": "test", "mode": "knowledge_base"
        }, headers={"Authorization": f"Bearer {token}"})
        # 返回 200 即可（可能无检索结果但不影响）
        assert resp.status_code == 200

    def test_normal_user_cannot_access_admin(self):
        login_resp = client.post("/api/auth/login", json={
            "username": "user1", "password": "user123"
        })
        token = login_resp.json()["access_token"]
        resp = client.get("/api/admin/stats", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 403

    def test_admin_can_access_admin(self):
        login_resp = client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        token = login_resp.json()["access_token"]
        resp = client.get("/api/admin/stats", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 200

    def test_health_check_is_public(self):
        resp = client.get("/api/admin/health")
        assert resp.status_code == 200
