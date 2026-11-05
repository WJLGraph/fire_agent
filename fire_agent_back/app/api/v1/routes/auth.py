"""
认证接口 — 注册 / 登录 / 当前用户 / 登出
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    client_ip,
    hash_password,
    issue_token,
    verify_password,
    get_current_user,
)
from app.core.ratelimit import check as throttle_check, record_failure, record_success
from app.models.user import User
from app.schemas.user import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenData,
    UpdateMeRequest,
    UserOut,
)

router = APIRouter()


def _enforce_password_strength(password: str) -> None:
    """口令强度：≥8 位且同时含字母与数字。

    只在服务端判（前端校验能绕过）。不设花哨规则——历史上「必须含符号」的结果
    是用户把口令写成 `Abc12345!` 贴在水晶板上，长度与字符类别才是有效变量。
    """
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="密码需同时包含字母和数字")


def _assert_can_login(user: User) -> None:
    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该账号已被禁用")


@router.post("/register")
async def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """用户注册（同 IP 有失败次数限制，防脚本批量灌号）"""
    allowed, retry_after = throttle_check("register", client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"注册过于频繁，请 {retry_after} 秒后重试",
        )
    username = req.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if req.email and db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被使用")
    _enforce_password_strength(req.password)

    user = User(
        username=username,
        email=req.email.strip() or None,
        password_hash=hash_password(req.password),
        role="user",
        created_at=datetime.now(),
        token_version=0,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)  # 回填自增 id
    record_success("register", client_ip(request))

    token = issue_token(user)
    return {"code": 200, "message": "注册成功", "data": TokenData(
        access_token=token,
        user=UserOut.model_validate(user),
    )}


@router.post("/login")
async def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """用户登录（同时支持 OAuth2 表单或 JSON）

    节流按 (IP, 用户名) 双维度计：单账号连续失败 5 次锁 15 分钟，
    同一 IP 尝试过多不同账号（撞库）直接锁 IP。
    """
    ip = client_ip(request)
    username = req.username.strip()
    allowed, retry_after = throttle_check(username, ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"失败次数过多，请 {retry_after} 秒后重试",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(req.password, user.password_hash):
        # 用户名不存在与口令错误返回同一句话：别让登录接口变成用户名枚举器
        record_failure(username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    _assert_can_login(user)
    record_success(username, ip)
    user.last_seen_at = datetime.utcnow()
    db.commit()

    token = issue_token(user)
    return {"code": 200, "message": "登录成功", "data": TokenData(
        access_token=token,
        user=UserOut.model_validate(user),
    )}


@router.post("/logout")
async def logout(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """登出：token_version +1，此前签发的全部 token 立即失效。

    没有这一步的话「登出」只是前端删掉 localStorage，token 在 15h 内依然可用——
    公用电脑上这是实打实的会话劫持面。
    """
    current.token_version = int(current.token_version or 0) + 1
    db.commit()
    return {"code": 200, "message": "已退出登录", "data": {"ok": True}}


@router.get("/me")
async def me(current: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {"code": 200, "message": "success", "data": UserOut.model_validate(current)}


@router.put("/me")
async def update_me(req: UpdateMeRequest, current: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """修改个人资料（邮箱）"""
    if req.email is not None:
        email = req.email.strip() or None
        if email and db.query(User).filter(User.email == email, User.id != current.id).first():
            raise HTTPException(status_code=400, detail="邮箱已被其他账号使用")
        current.email = email
        db.commit()
        db.refresh(current)
    return {"code": 200, "message": "资料已更新", "data": UserOut.model_validate(current)}


@router.put("/me/password")
async def change_password(req: ChangePasswordRequest, current: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """修改密码（需验证旧密码；修改后需重新登录）"""
    if not verify_password(req.old_password, current.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    _enforce_password_strength(req.new_password)
    current.password_hash = hash_password(req.new_password)
    # 改口令必须吊销旧会话，否则「修改密码」拦不住拿到旧 token 的人继续用。
    # 上面的 docstring 早就这么写了，但此前没有任何代码兑现它。
    current.token_version = int(current.token_version or 0) + 1
    db.commit()
    return {"code": 200, "message": "密码已修改，请使用新密码重新登录", "data": {"ok": True}}