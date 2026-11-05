"""
大屏数据接口 — 历史火点 / 预测火险 / 资源图层
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.fire_repository import FireRepository
from app.schemas.dashboard import (
    HistoryFireQuery,
    PredictRiskQuery,
    DashboardSummary,
)

router = APIRouter()


def _count_cities(db: Session) -> int:
    """覆盖州市数（只读、轻量计数）：优先 region_boundaries 的 city 级边界数，
    其次 predicted_fire_risks 的 DISTINCT city；均不可用/异常时降级为 0。
    注意 historical_fire_points.city 全为空，不能作为口径。"""
    try:
        n = db.execute(text(
            "SELECT COUNT(*) FROM region_boundaries WHERE region_level = 'city'"
        )).scalar()
        if n:
            return int(n)
        n = db.execute(text(
            "SELECT COUNT(DISTINCT city) FROM predicted_fire_risks"
        )).scalar()
        return int(n or 0)
    except Exception:
        return 0


def _count_agents() -> int:
    """协作智能体数：复用 /agent/status 的 AGENT_REGISTRY 注册表口径（当前 6）"""
    try:
        from app.api.v1.routes.agent import AGENT_REGISTRY
        return len(AGENT_REGISTRY)
    except Exception:
        return 0


@router.get("/history-fires")
async def get_history_fires(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    city: str | None = Query(None, description="州市名称"),
    confidence: str | None = Query(None, description="置信度"),
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """查询历史火点数据"""
    repo = FireRepository(db)
    query = HistoryFireQuery(
        start_date=start_date,
        end_date=end_date,
        city=city,
        confidence=confidence,
        page=page,
        page_size=page_size,
    )
    result = repo.query_history_fires(query)
    return {
        "code": 200,
        "message": "success",
        "data": result,
    }


@router.get("/predict-risks")
async def get_predict_risks(
    year: int | None = Query(None, ge=2025, le=2026),
    month: int | None = Query(None, ge=1, le=12),
    day: int | None = Query(None, ge=1, le=31),
    view_mode: str = Query("daily", pattern="^(daily|monthly)$"),
    city: str | None = Query(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """查询预测火险数据"""
    repo = FireRepository(db)
    query = PredictRiskQuery(
        year=year,
        month=month,
        day=day,
        view_mode=view_mode,
        city=city,
    )
    result = repo.query_predict_risks(query)
    return {
        "code": 200,
        "message": "success",
        "data": result,
    }


@router.get("/summary")
async def get_dashboard_summary(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """获取大屏摘要统计

    在既有统计之上附带两个登录页/门户用真实取数字段（查询异常降级为 0，不 500）：
    - city_count：覆盖州市数（region_boundaries city 级边界数优先，其次预测火险 DISTINCT city）；
    - agent_count：协作智能体数（/agent/status 注册表口径，当前 6）。

    # AUTH: PUBLIC —— 本端点刻意保持匿名可访问，且是唯一一个：
    # 门户首页 views/welcome/index.vue 与登录页要在「用户还没登录」时展示真实统计。
    # 只返回聚合计数，不含任何逐条火点坐标或用户数据；逐条数据在同文件的
    # /history-fires、/predict-risks 上，那两个已要求登录。
    # scripts/check_auth_coverage.py 以此标记为白名单依据，别在没读这段注释前放开别的端点。
    """
    repo = FireRepository(db)
    summary = repo.get_summary(start_date, end_date)
    summary["city_count"] = _count_cities(db)
    summary["agent_count"] = _count_agents()
    return {
        "code": 200,
        "message": "success",
        "data": summary,
    }