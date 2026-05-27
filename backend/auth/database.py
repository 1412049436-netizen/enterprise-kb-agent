"""SQLite 数据库连接 + 用户表管理"""
import sqlite3
from pathlib import Path
from loguru import logger

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = str(DB_DIR / "users.db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def create_users_table():
    """创建用户表（如果不存在）"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def init_admin_user():
    """首次启动时创建默认管理员账号"""
    create_users_table()
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if row["cnt"] == 0:
        from .security import hash_password
        pw_hash = hash_password("admin123")
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", pw_hash, "admin"),
        )
        conn.commit()
        logger.warning("=" * 50)
        logger.warning("默认管理员账号已创建: admin / admin123")
        logger.warning("请尽快修改密码!")
        logger.warning("=" * 50)
    conn.close()
