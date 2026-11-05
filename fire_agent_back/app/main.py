"""
FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.core.session import SlidingSessionMiddleware, validate_security_config
from app.api.v1.routes import dashboard as dashboard_router
from app.api.v1.routes import query as query_router
from app.api.v1.routes import rag as rag_router
from app.api.v1.routes import agent as agent_router
from app.api.v1.routes import report as report_router
from app.api.v1.routes import admin as admin_router
from app.api.v1.routes import auth as auth_router
from app.api.v1.routes import media as media_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 兼容旧库补列 + 种子管理员账号"""
    # 启动时创建所有表（开发阶段方便，生产环境用 Alembic）
    Base.metadata.create_all(bind=engine)

    # 兼容旧库：create_all 不会修改已存在的表，这里幂等地补充新增列（如 user_id）
    from app.core.database import SessionLocal
    import sqlalchemy as sa
    db = SessionLocal()
    try:
        for table, col, coltype in (
            ("kb_documents", "user_id", "INTEGER"),
            ("analysis_reports", "user_id", "INTEGER"),
            ("analysis_reports", "llm_provider", "VARCHAR(50)"),
            ("analysis_reports", "llm_model", "VARCHAR(120)"),
            ("analysis_reports", "llm_tokens", "JSON"),
            ("analysis_reports", "llm_degraded", "BOOLEAN DEFAULT FALSE"),
            ("agent_tasks", "user_id", "INTEGER"),
            ("query_history", "result", "JSON"),
            ("rag_history", "result", "JSON"),
            # 会话吊销与活跃观测（见 app.models.user / app.core.session）
            ("users", "token_version", "INTEGER DEFAULT 0 NOT NULL"),
            ("users", "is_active", "BOOLEAN DEFAULT TRUE"),
            ("users", "last_seen_at", "TIMESTAMP"),
        ):
            try:
                db.execute(sa.text(
                    f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{col}" {coltype}'
                ))
            except Exception as e:
                print(f"[INIT] 为 {table}.{col} 补列失败（可能表不存在）: {e}")
        # token_version 为 NOT NULL，历史行需回填 0（ADD COLUMN 带 DEFAULT 已覆盖，此处兜底）
        try:
            db.execute(sa.text("UPDATE users SET token_version = 0 WHERE token_version IS NULL"))
        except Exception:
            pass
        db.commit()
    finally:
        db.close()

    # 种子默认管理员。
    # 口令来源只有 ADMIN_INIT_PASSWORD；未配置时生产环境拒绝启动、开发环境回退到 123456。
    # 不再把口令 print 到 stdout——宝塔日志与容器日志会永久留下那行明文。
    from app.core.security import hash_password
    from app.models.user import User
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            if not settings.ADMIN_INIT_PASSWORD:
                if settings.ENV == "production":
                    raise RuntimeError(
                        "生产环境需在 .env 配置 ADMIN_INIT_PASSWORD 后再首次启动，"
                        "以避免弱口令管理员账号"
                    )
                seed_password = "123456"
                print("[INIT][WARN] 未配置 ADMIN_INIT_PASSWORD，开发环境使用默认口令创建 admin")
            else:
                seed_password = settings.ADMIN_INIT_PASSWORD
            db.add(User(
                username="admin",
                email=None,
                password_hash=hash_password(seed_password),
                role="admin",
            ))
            db.commit()
            print("[INIT] 已创建默认管理员账号 admin（口令取自 ADMIN_INIT_PASSWORD，未打印）")
    finally:
        db.close()

    # 启动自愈：worker 随进程消亡，running 任务不可能再推进 → 标记中断；
    # awaiting_approval 不动（HITL 中断态存于 PostgresSaver，重启后仍可审批恢复）
    from datetime import datetime
    from app.models.task import AgentTask, AgentTaskStep
    db = SessionLocal()
    try:
        stuck = db.query(AgentTask).filter(AgentTask.status == "running").all()
        for t in stuck:
            t.status = "failed"
            t.final_summary = "服务重启导致任务中断，请重新发起任务"
            t.finished_at = datetime.now()
        if stuck:
            db.commit()
            print(f"[INIT] 已将 {len(stuck)} 个中断的 running 任务标记为 failed")

        # 清理僵尸 running 步骤行：① 同 (task_id, step_name) 已被终态行取代的历史重复行
        # ② 归属于已中断任务、永远不会再推进的 running 行
        running_rows = db.query(AgentTaskStep).filter(AgentTaskStep.status == "running").all()
        terminal_keys = {(r.task_id, r.step_name) for r in db.query(AgentTaskStep).all()
                         if (r.status or "") != "running"}
        dead_ids = {t.id for t in stuck}
        removed = 0
        for r in running_rows:
            if (r.task_id, r.step_name) in terminal_keys or r.task_id in dead_ids:
                db.delete(r)
                removed += 1
        if removed:
            db.commit()
            print(f"[INIT] 已清理 {removed} 条僵尸 running 步骤行")
    finally:
        db.close()

    yield


_is_prod = settings.ENV == "production"

# 启动自检：生产环境缺 / 弱 JWT_SECRET 直接拒绝启动（见 app/core/session.py）
validate_security_config()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="焰哨多Agent与可视化平台 · 后端服务",
    lifespan=lifespan,
    # 生产不挂载文档路由：/openapi.json 等于把全部端点、参数模型和高危管理端点
    # 清单交给未登录的攻击者。反代层的 404 只是第二道兜底，应用层关掉才可靠。
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# 滑动会话续期（15h 空闲判定，见 app/core/session.py 模块文档）
app.add_middleware(SlidingSessionMiddleware)


class SecurityHeadersMiddleware:
    """统一安全响应头（纯 ASGI，不缓冲 SSE）。

    写在应用层而不是只写反代层：本机 curl 127.0.0.1:8000、compose 直连、
    以及任何没同步 Nginx 配置的入口都因此同享一套口径；反代头只是第二道。

    已知摘不掉的：`Server: uvicorn`。它由 uvicorn 在协议层追加（实测在应用回包里
    补同名空值只会变成两个 Server 头，反而更糟），所以这一条只能由反代处理：
    Nginx 侧 `server_tokens off;` + `proxy_hide_header Server;`（见 §5）。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                raw = list(message.get("headers") or [])
                # 去掉框架自报家门的头，再补安全头（同名大小写一并清理）
                drop = {b"server", b"x-powered-by"}
                raw = [(k, v) for k, v in raw if k.lower() not in drop]
                raw.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"geolocation=(), camera=(), microphone=()"),
                ])
                message = {**message, "headers": raw}
            await send(message)

        await self.app(scope, receive, send_with_headers)


app.add_middleware(SecurityHeadersMiddleware)

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    # 前端需要读到 X-Token-Refresh 才能完成静默续期；不 expose 的话跨域下读不到，
    # 用户会「每 15 小时被踢一次」而不是滑动续期
    expose_headers=["X-Token-Refresh"],
)


# ===== 注册路由 =====
app.include_router(dashboard_router.router, prefix="/api/v1/dashboard", tags=["大屏数据"])
app.include_router(query_router.router, prefix="/api/v1/query", tags=["智能查询"])
app.include_router(rag_router.router, prefix="/api/v1/rag", tags=["知识库 RAG"])
app.include_router(agent_router.router, prefix="/api/v1/agent", tags=["Agent 协作"])
app.include_router(report_router.router, prefix="/api/v1/reports", tags=["报告中心"])
app.include_router(admin_router.router, prefix="/api/v1/admin", tags=["系统管理"])
app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(media_router.router, prefix="/api/v1/vision", tags=["视觉与语音"])


@app.get("/")
async def root():
    """存活探针。不回显项目名与版本号——那等于给扫描器递指纹。"""
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}