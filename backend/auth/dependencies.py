"""FastAPI 认证依赖注入"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .models import User
from .database import get_connection
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
) -> User:
    """从 Bearer token 中解析当前用户，未认证返回 401"""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 格式错误",
        )
    conn = get_connection()
    row = conn.execute(
        "SELECT username, role FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return User(username=row["username"], role=row["role"])


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员角色，否则返回 403"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
