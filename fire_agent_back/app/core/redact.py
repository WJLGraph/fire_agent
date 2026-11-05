"""日志/错误信息脱敏 — 落库与回显前的最后一道

为什么需要：本项目的异常字符串会一路流到三处 —— uvicorn 控制台、Nginx error log
（经反向代理）、以及「系统管理 · 运行日志」接口的前端展示。而 LLM / 地图 / OCR 的
报错常常把**请求 URL 原样回显**（`APIError: 401 ... https://host/v1?api_key=sk-xxxx`），
数据库连接失败则常带完整 DSN。也就是说，一句没人留意的报错日志就是一把活的密钥。

规则只做「形状识别」，不识别语义：宁可把一条正常文本误打码，也不能放过一次密钥泄漏。
误打码的代价是运维少看几个字符，泄漏的代价是重开一轮密钥。
"""
from __future__ import annotations

import re

#: 打码后的占位（保留前 4 位便于辨认「是哪把 key」，与 admin._mask 口径一致）
_KEEP_PREFIX = 4

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # OpenAI / 百炼 / LongCat 风格：sk-xxx、sk-sp-xxx（点号连字符均可能）
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{10,}"), "sk-****"),
    # 形参式密钥：api_key=xxx / apiKey=xxx / key=xxx / secret=xxx / token=xxx
    # 值不能吃到 \S 末尾——URL query 里 & 后面还有别的参数，贪婪匹配会顺带吞掉排障要看的参数
    (re.compile(r"(?i)\b(api[_-]?key|apikey|access[_-]?key|secret|token|pwd|password)\b(\s*[=:]\s*)([^\s&\"',;]{4,})"),
     lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)[:_KEEP_PREFIX]}****"),
    # JWT：三段 base64url，点分
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "<jwt>****"),
    # Bearer 头原文
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]{16,}=*"), "Bearer ****"),
    # 连接串：scheme://user:pass@host —— 口令段必打码，用户名保留（排障要看是谁）
    (re.compile(r"(\b\w+://)([^/\s:@]+):([^@\s]{2,})@"),
     lambda m: f"{m.group(1)}{m.group(2)}:****@"),
    # 32 位十六进制串（天地图/高德 key 的常见形态）
    (re.compile(r"\b[0-9a-f]{28,40}\b"), lambda m: m.group(0)[:_KEEP_PREFIX] + "****"),
    # 手机号（11 位，1 开头）与邮箱：内部日志没必要带个人联系方式
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
     lambda m: m.group(0)[:4] + "****" + m.group(0)[-4:]),
    # 邮箱：内部日志没必要带个人联系方式，只留首字符与域名
    (re.compile(r"\b([A-Za-z0-9._%+\-])([A-Za-z0-9._%+\-]*)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"),
     lambda m: f"{m.group(1)}***@{m.group(3)}"),
]

#: 已打码标记：重复调用直接短路，避免二次处理把 `sk-****` 再套一层
_MASKED_MARK = "****"


def redact(text: object) -> str:
    """把可能含密钥/PII 的字符串洗成可安全落日志的形式。

    幂等：已经全是打码标记的串不会被反复加工。
    """
    if text is None:
        return ""
    s = text if isinstance(text, str) else str(text)
    if not s:
        return s
    for pattern, repl in _PATTERNS:
        s = pattern.sub(repl, s)
    return s
