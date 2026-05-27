"""密码哈希 + JWT token 生成/验证"""
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from ..config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    """bcrypt 哈希密码"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否匹配"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(data: dict) -> str:
    """生成 JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解码 JWT token，失败返回 None"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
