"""
认证安全工具 — 密码哈希（bcrypt）+ JWT 令牌
"""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User


def client_ip(request: Request) -> str:
    """取真实来源 IP（登录节流用）

    后端在生产里始终躲在宝塔 Nginx 之后，直接取 request.client.host 只会得到
    127.0.0.1，全部用户挤进同一个节流桶 —— 一个失败就会把整站登录锁死。
    但 X-Forwarded-For 是客户端可伪造的头，无条件信任等于让攻击者每次换个值就
    绕过节流。折中：只有当直连方是回环（说明确实是本机反代在转发）时才采纳代理头。
    """
    peer = (request.client.host if request.client else "") or ""
    if peer in ("127.0.0.1", "::1", "localhost"):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return peer or "unknown"


# ===== 密码哈希（bcrypt） =====
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ===== JWT（密钥/算法/有效期一律运行时读取 settings） =====
# 不要在模块导入时把 settings.JWT_SECRET 绑成模块级常量：那样 .env 改动或
# POST /admin/config 热更新后，已加载的本模块仍用旧密钥签发，表现为
# 「配置页显示新值、签发的 token 却是旧密钥」——静默失效且极难定位。


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    # iat 供滑动续期判断「该 token 已存活多久」；exp 是唯一的过期判据
    to_encode.update({"iat": now, "exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """校验签名与 exp 并返回 payload；无效返回 None，由调用方决定 401 文案"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# OAuth2 bearer 认证方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def resolve_user(credential: Optional[str], db: Session) -> User:
    """唯一的「凭证 → 用户」入口。

    Authorization 头与 SSE query 参数两条通道都必须走这里，否则新增的校验规则
    只覆盖了其中一条，另一条就成了绕过点。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的登录凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credential:
        raise credentials_exception
    payload = decode_token(credential)
    if not payload:
        raise credentials_exception
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="该账号已被禁用",
        )
    # 改密 / 登出后吊销全部旧 token：token 内 tv 落后于库中 token_version 即失效。
    # 未带 tv 的历史 token 记为 0，与列默认值 0 对齐，不会误伤上线前的在线会话。
    if int(payload.get("tv") or 0) != int(user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _touch_last_seen(user, db)
    return user


def _touch_last_seen(user: User, db: Session) -> None:
    """记录最近活跃时间（15h 空闲规则的观测口径）。

    节流到 5 分钟一次：本函数在每个鉴权请求上都会被调用，逐次写库会把读接口
    变成写接口。时间戳只用于观测「谁闲置多久」，过期判定完全由 JWT 的 exp 负责，
    因此这里的精度不敏感，5 分钟的误差可接受。
    """
    now = datetime.utcnow()
    last = user.last_seen_at
    if last is not None and (now - last).total_seconds() < 300:
        return
    user.last_seen_at = now
    db.commit()


def issue_token(user: User) -> str:
    """为登录成功的用户签发 token（唯一签发入口，保证 tv 声明必然写入）"""
    return create_access_token({
        "sub": str(user.id),
        "tv": int(user.token_version or 0),
    })


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析 token 并返回当前用户；失败则抛 401"""
    return resolve_user(token, db)


def get_current_admin(current: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员，否则 403"""
    if current.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current