"""滑动会话 / 鉴权收口回归（不依赖数据库）。

运行（仓库根目录）：python -m pytest tests/test_sliding_session.py -q

覆盖 P0-3「连续 15h 无活动才登出，15h 内有活动则重新计时」与服务端配套口径：
- token 有效期恰为 ACCESS_TOKEN_EXPIRE_MINUTES（15h），且带 iat/exp/tv 声明；
- SlidingSessionMiddleware 对合法 Bearer 请求在 X-Token-Refresh 下发续期票，
  匿名/坏票请求不下发；
- token_version 吊销：tv 与库中不一致即拒（resolve_user），历史无 tv 票按 0 兼容；
- 登录节流：同 (IP, 用户名) 连续失败 5 次锁 15 分钟；
- client_ip 只在直连方为回环时采纳 X-Forwarded-For，防伪造头绕过节流。
"""
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import ratelimit, session as session_mod
from app.core.config import settings
from app.core.security import client_ip, create_access_token, decode_token, resolve_user
from app.core.session import REFRESH_HEADER, SlidingSessionMiddleware, validate_security_config

EXPIRE_SECONDS = 15 * 3600


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    """把 JWT 密钥钉成固定值：否则各用例之间会互相污染签名。"""
    monkeypatch.setattr(settings, "JWT_SECRET", "test-only-secret-0123456789abcdef")
    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15 * 60)


async def _echo_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"code":200}'})


async def _call(middleware, headers):
    captured = {}

    async def send(message):
        if message["type"] == "http.response.start":
            # MutableHeaders 会把头名小写化；HTTP 头大小写不敏感，按小写比对
            captured[REFRESH_HEADER.lower()] = None
            for k, v in message.get("headers", []):
                captured[k.decode().lower()] = v.decode()

    scope = {
        "type": "http", "method": "GET", "path": "/api/v1/x", "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 1234), "server": ("test", 80), "scheme": "http",
    }
    await middleware(scope, None, send)
    return captured


def test_token_ttl_is_15h_and_carries_tv():
    token = create_access_token({"sub": "7", "tv": 2})
    payload = decode_token(token)
    assert payload["sub"] == "7" and payload["tv"] == 2
    assert int(payload["exp"] - payload["iat"]) == EXPIRE_SECONDS


@pytest.mark.asyncio
async def test_middleware_issues_refresh_ticket_for_valid_bearer():
    token = create_access_token({"sub": "7", "tv": 0})
    res = await _call(SlidingSessionMiddleware(_echo_app),
                      {"Authorization": f"Bearer {token}"})
    renewed = res.get(REFRESH_HEADER.lower())
    # 同一秒内续期票与原票可能逐字节相同（iat 只有秒级精度），所以只断言「能解出且口径一致」
    assert renewed
    payload = decode_token(renewed)
    # 续期票必须沿用同一 sub/tv：换人（sub）或绕过吊销（tv）都等于提权
    assert payload["sub"] == "7" and payload["tv"] == 0
    assert int(payload["exp"] - payload["iat"]) == EXPIRE_SECONDS


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [
    {},                                        # 匿名请求不该拿到票
    {"Authorization": "Bearer not-a-jwt"},     # 坏签名
    {"Authorization": "Token abc"},            # 非 Bearer 方案
])
async def test_middleware_skips_anonymous_or_bad_credential(headers):
    res = await _call(SlidingSessionMiddleware(_echo_app), headers)
    assert res.get(REFRESH_HEADER.lower()) is None


class _FakeUserQuery:
    """只够喂 resolve_user 的最小假 DB：filter(...).first() 返回给定用户。"""

    def __init__(self, user):
        self._user = user

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._user

    def commit(self):
        pass


def _user(token_version=0, is_active=True):
    return SimpleNamespace(id=7, token_version=token_version, is_active=is_active,
                           last_seen_at=None, role="user")


def test_revoked_token_version_is_rejected():
    token = create_access_token({"sub": "7", "tv": 0})
    db = _FakeUserQuery(_user(token_version=1))
    with pytest.raises(HTTPException) as exc:
        resolve_user(token, db)
    assert exc.value.status_code == 401


def test_legacy_token_without_tv_still_works():
    """上线前的老票没有 tv 声明，按 0 处理，不能让全站在线用户被踢。"""
    from jose import jwt
    legacy = jwt.encode({"sub": "7", "exp": _exp()}, settings.JWT_SECRET,
                        algorithm=settings.JWT_ALGORITHM)
    user = _user(token_version=0)
    assert resolve_user(legacy, _FakeUserQuery(user)) is user


def test_disabled_user_is_forbidden():
    token = create_access_token({"sub": "7", "tv": 0})
    with pytest.raises(HTTPException) as exc:
        resolve_user(token, _FakeUserQuery(_user(is_active=False)))
    assert exc.value.status_code == 403


def _exp():
    from datetime import datetime, timedelta
    return datetime.utcnow() + timedelta(minutes=15 * 60)


def test_login_throttle_locks_after_five_failures():
    ratelimit.reset()
    for _ in range(5):
        ratelimit.record_failure("alice", "1.2.3.4")
    allowed, retry_after = ratelimit.check("alice", "1.2.3.4")
    assert allowed is False
    assert 0 < retry_after <= ratelimit.LOCK_SECONDS
    # 撞库维度：同 IP 换个账号仍应放行，直到超过 IP 配额才整体锁
    assert ratelimit.check("bob", "1.2.3.4")[0] is True


def test_throttle_window_allows_after_success():
    ratelimit.reset()
    for _ in range(4):
        ratelimit.record_failure("carol", "5.6.7.8")
    assert ratelimit.check("carol", "5.6.7.8")[0] is True
    ratelimit.record_success("carol", "5.6.7.8")
    for _ in range(4):
        ratelimit.record_failure("carol", "5.6.7.8")
    # 成功登录清零后，同样的 4 次失败仍不该触发锁定
    assert ratelimit.check("carol", "5.6.7.8")[0] is True


@pytest.mark.parametrize("peer,forwarded,expected", [
    ("127.0.0.1", "9.9.9.9, 10.0.0.1", "9.9.9.9"),  # 本机反代：采纳 XFF 首个
    ("127.0.0.1", None, "127.0.0.1"),
    ("8.8.8.8", "9.9.9.9", "8.8.8.8"),              # 直连公网：伪造 XFF 无效
])
def test_client_ip_trusts_forwarded_headers_only_from_loopback(peer, forwarded, expected):
    headers = {}
    if forwarded:
        headers["x-forwarded-for"] = forwarded
    request = SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)
    assert client_ip(request) == expected


def test_production_refuses_weak_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "JWT_SECRET", "short")
    with pytest.raises(RuntimeError):
        validate_security_config()


def test_development_falls_back_to_dev_only_secret(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "JWT_SECRET", "")
    validate_security_config()
    assert settings.JWT_SECRET == session_mod._DEV_ONLY_SECRET


def test_production_refuses_public_placeholder_secret(monkeypatch):
    """占位值长度达标（45 字节），必须靠公开值黑名单而不是长度拦住。"""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(
        settings, "JWT_SECRET", "fire-agent-platform-secret-key-change-in-prod")
    with pytest.raises(RuntimeError):
        validate_security_config()


def test_development_keeps_placeholder_secret(monkeypatch):
    """dev 用占位值只告警、不换 key——换 key 会让本地已签发 token 全部失效。"""
    placeholder = "fire-agent-platform-secret-key-change-in-prod"
    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "JWT_SECRET", placeholder)
    validate_security_config()
    assert settings.JWT_SECRET == placeholder
