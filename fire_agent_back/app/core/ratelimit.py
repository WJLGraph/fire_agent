"""
登录节流 — 内存计数，零外部依赖

为什么不用 slowapi / Redis：本项目没有 Redis，进程内字典足够 ——
需要防的是「在线爆破口令」，而不是「重启后仍然记住攻击者」；重启即清零，
对单次攻击窗口（分钟级）而言保护效果相同，却省掉一个依赖和一套序列化。

只用于登录/注册这类低频端点；高频业务接口走 Nginx limit_req（见 docs/安全加固方案.md §5），
在应用层给每个请求加计数只会变成新的性能瓶颈。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

#: 窗口长度（秒）与阈值：同一 (IP, 用户名) 组合 5 分钟内失败 5 次即锁定 15 分钟
FAIL_WINDOW = 300
MAX_FAILS = 5
LOCK_SECONDS = 900

#: 匿名侧全局限流：同一 IP 每窗口最多尝试多少个不同账号（防「一个口令试千百个用户名」）
IP_ATTEMPTS_PER_WINDOW = 20

_lock = threading.Lock()


@dataclass
class _Bucket:
    hits: list[float] = field(default_factory=list)
    locked_until: float = 0.0


_BUCKETS: dict[str, _Bucket] = {}


def _trim(now: float) -> None:
    """清掉过期桶。

    调用方已持有 _lock。字典本身有界（键含 IP，攻击者也无法凭空造出无限多 IP 段），
    但仍要防止长期驻留，超过 1000 个键时做一次全量清扫。
    """
    if len(_BUCKETS) <= 1000:
        for key, b in list(_BUCKETS.items()):
            b.hits = [h for h in b.hits if now - h < FAIL_WINDOW]
            if not b.hits and b.locked_until < now:
                _BUCKETS.pop(key, None)
        return
    for key, b in list(_BUCKETS.items()):
        b.hits = [h for h in b.hits if now - h < FAIL_WINDOW]
        if not b.hits and b.locked_until < now:
            _BUCKETS.pop(key, None)


def check(username: str, client_ip: str) -> tuple[bool, int]:
    """是否允许本次尝试；返回 (allowed, retry_after_seconds)"""
    now = time.monotonic()
    with _lock:
        _trim(now)
        for key in (f"u:{client_ip}|{username}", f"i:{client_ip}"):
            bucket = _BUCKETS.get(key)
            if bucket and bucket.locked_until > now:
                return False, int(bucket.locked_until - now)
        # 同一 IP 尝试过多不同账号 → 视为撞库，直接锁 IP
        ip_bucket = _BUCKETS.setdefault(f"i:{client_ip}", _Bucket())
        if len(ip_bucket.hits) >= IP_ATTEMPTS_PER_WINDOW:
            ip_bucket.locked_until = now + LOCK_SECONDS
            return False, LOCK_SECONDS
    return True, 0


def record_failure(username: str, client_ip: str) -> None:
    """记一次失败；达到阈值则锁定"""
    now = time.monotonic()
    with _lock:
        for key in (f"u:{client_ip}|{username}", f"i:{client_ip}"):
            bucket = _BUCKETS.setdefault(key, _Bucket())
            bucket.hits.append(now)
        user_bucket = _BUCKETS[f"u:{client_ip}|{username}"]
        if len(user_bucket.hits) >= MAX_FAILS:
            user_bucket.locked_until = now + LOCK_SECONDS


def record_success(username: str, client_ip: str) -> None:
    """登录成功后清零，避免正常用户被历史失败误锁"""
    with _lock:
        _BUCKETS.pop(f"u:{client_ip}|{username}", None)
        _BUCKETS.pop(f"i:{client_ip}", None)


def reset() -> None:
    """测试用：清空全部计数"""
    with _lock:
        _BUCKETS.clear()
