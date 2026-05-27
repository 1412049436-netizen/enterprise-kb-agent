"""认证 API — POST /api/auth/login"""
from fastapi import APIRouter, HTTPException, status
from ..auth.models import LoginRequest, Token
from ..auth.database import get_connection
from ..auth.security import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=Token)
def login(req: LoginRequest):
    """用户登录，返回 JWT access token"""
    conn = get_connection()
    row = conn.execute(
        "SELECT username, password_hash, role FROM users WHERE username = ?",
        (req.username,),
    ).fetchone()
    conn.close()

    if row is None or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token(data={"sub": row["username"], "role": row["role"]})
    return Token(access_token=token)
