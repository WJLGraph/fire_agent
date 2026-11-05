"""日志脱敏回归（P1-2）。

运行：python -m pytest tests/test_log_redaction.py -q

覆盖 redact() 对各形态密钥/凭证/PII 的打码，以及 log_system_event 的写入口径
（系统日志会被 /admin/logs 整条回显给前端，异常串里的 api_key 必须在入缓冲前洗掉）。
"""
from app.api.v1.routes import admin as admin_routes
from app.core.redact import redact


def test_redacts_openai_style_key():
    out = redact("failed: sk-abcdefghijklmnop1234")
    assert "sk-abcdefghijklmnop1234" not in out
    assert "sk-****" in out


def test_redacts_query_param_keys():
    # fixture 必须是合成值：真实的两把地图 Key 已经在 git 历史里，不该再新增一次提交
    fake_key = "0123456789abcdef0123456789abcdef"
    msg = (f"APIError 401: https://api.example.com/v1/chat?api_key={fake_key}"
           "&model=qwen")
    out = redact(msg)
    assert fake_key not in out
    assert "api_key=0123****" in out
    # URL 其余部分保留：排障要看是哪个主机、哪个模型
    assert "api.example.com" in out and "model=qwen" in out


def test_redacts_bare_hex_key_and_jwt_and_bearer():
    fake_tianditu = "deadbeefcafe1234567890abcdef0011"
    assert fake_tianditu not in redact(f"tianditu key {fake_tianditu}")
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3IiwidHYiOjB9.abcDEF1234567890xyz"
    assert jwt_like not in redact(f"Authorization rejected: {jwt_like}")
    assert "Bearer ****" in redact("header was Bearer abcdefghijklmnopqrstuvwxyz012345")


def test_redacts_database_url_password_but_keeps_host():
    out = redact("connect failed postgresql://fire_user:Sup3rSecret@10.0.0.5:5432/fire_agent")
    assert "Sup3rSecret" not in out
    assert "fire_user:****@10.0.0.5" in out


def test_redacts_phone_and_email():
    out = redact("用户 13887123456 邮箱 zhang.wei@example.com 登录失败")
    assert "13887123456" not in out
    assert "zhang.wei@example.com" not in out
    assert "1388****3456" in out
    assert "z***@example.com" in out


def test_plain_business_text_is_untouched():
    """误打码会啃掉运维要看的正文：普通中文/数字任务日志必须原样通过。"""
    msg = "[wjl] 任务#1024 完成，报告长度: 8732 字符，用时 45.2s（2026-11-04 09:12:33）"
    assert redact(msg) == msg


def test_redact_is_idempotent():
    once = redact("api_key=abcdefghijklmnop1234")
    assert redact(once) == once


def test_log_system_event_scrubs_on_write():
    admin_routes._SYSTEM_LOGS.clear()
    admin_routes.log_system_event("llm", "AMD 调用失败 key=sk-abcdefghijklmnop1234")
    entry = admin_routes._SYSTEM_LOGS[0]
    assert "sk-abcdefghijklmnop1234" not in entry["message"]
    assert entry["source"] == "llm" and entry["level"] == "INFO"
    admin_routes._SYSTEM_LOGS.clear()
