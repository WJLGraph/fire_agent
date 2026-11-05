"""
滑动会话 — 「连续 15 小时无任何请求才需要重新登录」

规则：JWT 的 exp = 签发时刻 + ACCESS_TOKEN_EXPIRE_MINUTES（15h）。会话存续期间任意一次
带凭证的请求，都由本模块在响应头 X-Token-Refresh 下发一枚同 payload 的新 token（exp 再
往后推 15h），前端 api/http.js 静默替换 localStorage 里的旧值。于是：

  - 15h 内出现过任何请求 → 计时器从那次请求重新起算，用户不会被踢下线；
  - 连续 15h 一次请求都没有 → 手上最后一枚 token 的 exp 到期 → 401 → 回登录页。

实现为纯 ASGI 中间件而不是 BaseHTTPMiddleware：后者会为每个响应建立缓冲包装，
对本项目大量使用的 StreamingResponse / SSE 长连接是已知风险点；这里只在
http.response.start 消息上补一个头，不碰消息体，零缓冲开销。

顺带一条安全收益：前端不再需要把 JWT 拼进 SSE 的 query（token 从响应头拿），
日志里也就不会再出现活 token。
"""
from __future__ import annotations

from starlette.datastructures import Headers, MutableHeaders

from app.core.config import settings
from app.core.security import create_access_token, decode_token

#: 下发续期 token 的响应头名（前端 http.js 读取该头）
REFRESH_HEADER = "X-Token-Refresh"


class SlidingSessionMiddleware:
    """对携带有效 Bearer 的请求，在响应头下发续期 token。

    不校验用户是否存在 / 是否被吊销——那件事只有 resolve_user 一个入口负责，
    这里刻意只做无状态的签名校验，避免每个请求多一次库查询；
    即使给一枚已吊销的 token 签发续命版，tv 比对仍会把它挡在鉴权之外。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        auth = headers.get("authorization") or ""
        credential = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
        payload = decode_token(credential) if credential else None
        sub = (payload or {}).get("sub")
        if not sub:
            await self.app(scope, receive, send)
            return

        # 原 payload 只保留 sub / tv：其余业务声明不自动续传，避免签发口径失控
        new_token = create_access_token({"sub": sub, "tv": int(payload.get("tv") or 0)})

        async def send_with_refresh(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                MutableHeaders(scope=message)[REFRESH_HEADER] = new_token
            await send(message)

        await self.app(scope, receive, send_with_refresh)


#: 仅供开发环境兜底：生产环境（ENV=production）在自检阶段直接拒绝启动，
#: 因此这把公开常量不可能参与生产 token 的签发。
_DEV_ONLY_SECRET = "insecure-dev-only-jwt-secret"

#: 仓库里公开过的占位值。长度虽达标，但任何人都能拿它伪造 token，等同弱密钥。
_KNOWN_PLACEHOLDER_SECRETS = {
    _DEV_ONLY_SECRET,
    "fire-agent-platform-secret-key-change-in-prod",  # .env.example 模板值
}


def validate_security_config() -> None:
    """启动自检：生产环境禁止用弱/缺省的 JWT_SECRET 起服务。

    development 下回退到一把明确标注「仅开发」的密钥并告警——本项目历史部署
    大多没配过 JWT_SECRET，直接 raise 会让开发环境当场起不来；换成每次启动
    随机生成又会「重启即全员掉线」。折中：固定 dev 常量 + 生产硬拒绝。
    """
    secret = settings.JWT_SECRET
    problem = None
    # 占位值长度达标，因此单独判定：development 下只告警不替换（换 key 会让本地
    # 已签发的 token 全部失效，而 dev 用它并无实际风险），production 下硬拒绝。
    is_placeholder = secret in _KNOWN_PLACEHOLDER_SECRETS
    if not secret:
        problem = "JWT_SECRET 未配置"
    elif len(secret) < 32:
        problem = "JWT_SECRET 长度不足 32 字节"
    elif is_placeholder:
        problem = "JWT_SECRET 仍是仓库里公开过的模板占位值"
    if problem is None:
        return
    if settings.ENV == "production":
        raise RuntimeError(
            f"生产环境拒绝启动：{problem}。请执行 "
            "`python -c \"import secrets;print(secrets.token_urlsafe(64))\"` "
            "生成强随机值并写入 .env，同时把 ENV 保持为 production"
        )
    if is_placeholder:
        print(f"[SECURITY][WARN] {problem}，开发环境可继续，上线前必须更换为随机值")
        return
    settings.JWT_SECRET = _DEV_ONLY_SECRET
    print(f"[SECURITY][WARN] {problem}，已回退到仅开发可用的固定密钥，禁止用于生产")
