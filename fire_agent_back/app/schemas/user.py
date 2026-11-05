"""
认证 Schema — 注册 / 登录
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: str = ""
    # 与 auth._enforce_password_strength 同口径（≥8 且含字母数字）。schema 这层是
    # 「明显不合法连业务都不用进」，路由那层才判字符类别；两处数字必须一致，否则
    # 422 与 400 谁先命中取决于写法，前端文案会对不上。
    password: str = Field(min_length=8, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateMeRequest(BaseModel):
    """个人资料更新（邮箱）"""
    email: Optional[str] = Field(default=None, max_length=120)


class ChangePasswordRequest(BaseModel):
    """修改密码（需验证旧密码）

    old_password 不设 min_length：历史账号里存在 6 位口令的用户，加了下限会把他们
    卡在「无法通过校验、也就永远改不了密码」上。新口令的强度由路由判（≥8 + 字母数字）。
    """
    old_password: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=8, max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    role: str
    created_at: Optional[datetime] = None


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut