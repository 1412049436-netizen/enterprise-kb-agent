"""用户管理 CLI — 注册、改密码、查看、删除用户"""
import argparse
import sys
from pathlib import Path
from getpass import getpass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.auth.database import get_connection, create_users_table
from backend.auth.security import hash_password


def cmd_list():
    create_users_table()
    conn = get_connection()
    rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    conn.close()

    if not rows:
        print("(暂无用户)")
        return

    print(f"{'ID':<6}{'用户名':<20}{'角色':<10}{'创建时间'}")
    print("-" * 56)
    for r in rows:
        print(f"{r['id']:<6}{r['username']:<20}{r['role']:<10}{r['created_at']}")


def cmd_add(username: str, password: str, role: str = "user"):
    if role not in ("admin", "user"):
        print(f"错误: 角色必须是 admin 或 user，不能是 '{role}'")
        sys.exit(1)

    create_users_table()
    conn = get_connection()

    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        print(f"错误: 用户 '{username}' 已存在")
        conn.close()
        sys.exit(1)

    pw_hash = hash_password(password)
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, pw_hash, role),
    )
    conn.commit()
    conn.close()
    print(f"用户 '{username}' (角色: {role}) 创建成功")


def cmd_change_password(username: str, password: str):
    create_users_table()
    conn = get_connection()

    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        print(f"错误: 用户 '{username}' 不存在")
        conn.close()
        sys.exit(1)

    pw_hash = hash_password(password)
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pw_hash, username))
    conn.commit()
    conn.close()
    print(f"用户 '{username}' 密码已更新")


def cmd_delete(username: str, force: bool = False):
    create_users_table()
    conn = get_connection()

    row = conn.execute("SELECT id, role FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        print(f"错误: 用户 '{username}' 不存在")
        conn.close()
        sys.exit(1)

    if not force:
        conn.close()
        confirm = input(f"确认删除用户 '{username}' ({row['role']})? [y/N]: ")
        if confirm.lower() != "y":
            print("已取消")
            return

    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    print(f"用户 '{username}' 已删除")


def main():
    parser = argparse.ArgumentParser(description="企业知识库 — 用户管理工具")
    sub = parser.add_subparsers(dest="command", help="可用命令")

    p_list = sub.add_parser("list", help="查看所有用户")

    p_add = sub.add_parser("add", help="注册新用户")
    p_add.add_argument("username", help="用户名")
    p_add.add_argument("password", nargs="?", help="密码（不填则交互输入）")
    p_add.add_argument("--role", "-r", default="user", choices=["admin", "user"], help="角色 (默认: user)")

    p_pw = sub.add_parser("change-password", aliases=["chpw"], help="修改用户密码")
    p_pw.add_argument("username", help="用户名")
    p_pw.add_argument("password", nargs="?", help="新密码（不填则交互输入）")

    p_del = sub.add_parser("delete", aliases=["del"], help="删除用户")
    p_del.add_argument("username", help="用户名")
    p_del.add_argument("--force", "-f", action="store_true", help="跳过确认")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        cmd_list()
    elif args.command == "add":
        password = args.password or getpass("密码: ")
        cmd_add(args.username, password, args.role)
    elif args.command in ("change-password", "chpw"):
        password = args.password or getpass("新密码: ")
        cmd_change_password(args.username, password)
    elif args.command in ("delete", "del"):
        cmd_delete(args.username, args.force)


if __name__ == "__main__":
    main()
