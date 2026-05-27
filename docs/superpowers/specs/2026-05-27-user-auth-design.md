# 用户认证系统 — 设计规范

> 2026-05-27 | enterprise-kb-agent | v1.0 → v1.1

## 目标

为知识库问答系统添加用户认证：内部员工和管理员可用，支持后期公网部署。不引入外部服务依赖。

## 约束

- 数据库用 SQLite（项目已有，零额外部署）
- 密码 bcrypt 哈希存储
- FastAPI 原生 OAuth2 + JWT，Swagger 自动集成
- 管理员能入库/管理，普通用户只能查询
- 首次启动自动创建默认管理员账号

---

## 数据模型

### 用户表（SQLite）

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',  -- 'admin' | 'user'
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Pydantic 模型

```python
class User(BaseModel):
    username: str
    role: str

class UserInDB(User):
    password_hash: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    username: str
    password: str
```

---

## 认证流程

```
1. POST /api/auth/login  {"username": "admin", "password": "xxx"}
   → 查用户表 → 验证 bcrypt 哈希 → 生成 JWT
   → 返回 {"access_token": "eyJ...", "token_type": "bearer"}

2. 后续请求: Header Authorization: Bearer eyJ...
   → FastAPI OAuth2PasswordBearer 自动解析
   → get_current_user() 依赖注入 → 返回 User 对象
```

---

## JWT 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| JWT_SECRET | `change-me-in-production` | 生产环境必须覆盖 |
| JWT_ALGORITHM | HS256 | 签名算法 |
| JWT_EXPIRE_MINUTES | 480 | 8 小时过期 |

---

## 权限规则

| 接口 | 权限 |
|------|------|
| `POST /api/auth/login` | 公开 |
| `GET /api/admin/health` | 公开 |
| `GET /api/admin/stats` | **admin** |
| `POST /api/admin/ingest` | **admin** |
| `POST /api/query` | 登录即可 |
| `POST /api/query/stream` | 登录即可 |
| `POST /api/query/error` | 登录即可 |

---

## 文件结构

```
backend/auth/                    # 新增模块
├── __init__.py                  # 空
├── models.py                    # User, UserInDB, Token, LoginRequest
├── database.py                  # SQLite 连接, init_admin_user()
├── security.py                  # hash_password, verify_password, create_token, decode_token
└── dependencies.py              # get_current_user, require_admin

backend/api/auth.py              # 新增: POST /api/auth/login

backend/api/query.py             # 修改: 加认证依赖
backend/api/admin.py             # 修改: ingest/stats 加 admin 依赖
backend/main.py                  # 修改: lifespan 中调用 init_admin_user()
backend/config.py                # 修改: 加 JWT 配置项
```

---

## 首次初始化

`database.py` 中 `init_admin_user()`：
- 查询用户表是否为空
- 如果为空，创建默认 admin 账号：用户名 `admin`，密码 `admin123`
- 日志提示：`管理员账号已创建: admin / admin123，请尽快修改密码`
- 如果用户表非空，跳过

---

## 不做什么

- 不实现用户注册（由管理员手动添加或通过脚本管理）
- 不实现密码重置/修改功能（v1.1 阶段不做）
- 不实现 SSO/OIDC/LDAP 集成（预留扩展点）
- 不加密整个 SQLite 数据库
- 不引入 Redis 做 token 黑名单

---

## 文件变更总览

| 操作 | 文件 |
|------|------|
| 新建 | `backend/auth/__init__.py`, `models.py`, `database.py`, `security.py`, `dependencies.py` |
| 新建 | `backend/api/auth.py` |
| 修改 | `backend/api/query.py`（加认证依赖） |
| 修改 | `backend/api/admin.py`（加 admin 权限） |
| 修改 | `backend/main.py`（lifespan 初始化用户表） |
| 修改 | `backend/config.py`（JWT 配置项） |
| 新建 | `tests/test_auth.py`（认证单元测试） |

## 测试范围

- 登录成功返回 token
- 错误密码返回 401
- 无 token 访问 /api/query 返回 401
- 普通用户访问 /api/admin/ingest 返回 403
- admin 访问 /api/admin/ingest 正常
- 默认 admin 初始化
