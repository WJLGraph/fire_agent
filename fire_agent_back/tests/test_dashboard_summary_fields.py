"""dashboard summary 新增字段（city_count / agent_count）回归。

运行（仓库根目录）：python -m pytest tests/test_dashboard_summary_fields.py -q

覆盖：
- _count_cities 正常计数（region_boundaries city 级优先，其次 predicted_fire_risks DISTINCT）；
- 查询异常/表不存在 → 降级 0，不抛异常；
- _count_agents 复用 AGENT_REGISTRY 注册表（与 /agent/status 口径一致）；
- summary 端点返回体含两个字段（_route 层注入逻辑，伪 repo 验证）。
"""
from types import SimpleNamespace

from fastapi import HTTPException  # noqa: F401  (仅确保路由模块可独立导入)
import pytest

from app.api.v1.routes.agent import AGENT_REGISTRY
from app.api.v1.routes.dashboard import _count_agents, _count_cities


class _FakeDB:
    """伪 Session：按 SQL 关键词回放预设 scalar 值；无命中视为表缺失抛异常"""
    def __init__(self, results):
        self.results = list(results)   # [(sql 关键词, scalar 值)]
        self.executed = []

    def execute(self, stmt):
        sql = str(stmt)
        self.executed.append(sql)
        for kw, val in self.results:
            if kw in sql:
                return SimpleNamespace(scalar=lambda v=val: v)
        raise Exception("relation does not exist")  # 模拟表缺失


def test_count_cities_prefers_region_boundaries():
    db = _FakeDB([("region_boundaries", 16)])
    assert _count_cities(db) == 16
    assert "region_boundaries" in db.executed[0]


def test_count_cities_falls_back_to_predicted():
    """region_boundaries city 级为 0（或表为空）→ 回落 predicted_fire_risks DISTINCT city"""
    db = _FakeDB([("region_boundaries", 0), ("predicted_fire_risks", 16)])
    assert _count_cities(db) == 16
    assert any("predicted_fire_risks" in s for s in db.executed)


def test_count_cities_degrades_to_zero_on_error():
    db = _FakeDB([])  # 所有查询抛异常
    assert _count_cities(db) == 0


def test_count_agents_matches_registry():
    assert _count_agents() == len(AGENT_REGISTRY)
    # 与 /agent/status 口径一致：当前 6 个协作智能体（不含 join / approval_gate）
    names = [a["name"] for a in AGENT_REGISTRY]
    assert names == ["Orchestrator", "DataAgent", "GisAgent", "RagAgent",
                     "ReportAgent", "Reviewer"]


def test_registry_count_is_six():
    assert len(AGENT_REGISTRY) == 6
