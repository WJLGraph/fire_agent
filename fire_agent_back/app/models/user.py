"""
用户表
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    email = Column(String(120), unique=True, nullable=True, comment="邮箱")
    password_hash = Column(String(200), nullable=False, comment="密码哈希 (bcrypt)")
    role = Column(String(20), default="user", comment="角色 user/admin")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    # token 版本号：签发时写入 JWT 的 tv 声明，鉴权时与库中值比对。
    # 改密 / 登出 / 管理员禁用时 +1，该用户此前签发的全部 token 立即失效——
    # 用一列整数替代 Redis jti 黑名单，零外部依赖（本项目没有 Redis）。
    token_version = Column(Integer, default=0, nullable=False, comment="token 版本号（吊销用）")
    is_active = Column(Boolean, default=True, comment="是否启用；False 时禁止登录")
    last_seen_at = Column(DateTime, nullable=True, comment="最近一次鉴权通过时间（滑动会话的空闲判定）")
