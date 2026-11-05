"""
Agent 接口 — 任务创建（后台异步执行）& SSE 实时进度 & 任务历史 & HITL 审批恢复

P0/P1 升级说明：
- POST /tasks 立即返回 task_id，任务在后台线程执行（图执行为同步 LangGraph，
  通过 asyncio.to_thread 放入线程池，不阻塞事件循环）；
- 执行过程中每完成一个节点即增量落库 agent_task_steps，前端通过
  GET /tasks/{id}/stream（SSE）获取真实节点级进度，取代旧版整段同步等待；
- P1 图拓扑为并行 fan-out/join + 评审循环，worker 按 delta 语义合并状态
  （steps 键 extend、其余键覆盖），与 AgentState 的 reducer 语义一致；
- P1 HITL 审批：图执行到 approval_gate 时 interrupt 暂停，任务状态置为
  awaiting_approval（不落报告中心）；POST /tasks/{id}/resume 注入人工决策后
  以同 thread_id 恢复执行，approve/edit 完成后报告正常落报告中心。

任务状态机：running → awaiting_approval → running → completed / failed。

用户隔离：任务/报告归属当前用户；普通用户仅能查看自己的任务历史。
"""
import asyncio
import json
import re
import threading
import time
from datetime import datetime, timedelta
from math import isfinite

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user, resolve_user
from app.core import report_channels  # P2#18：报告流式增量通道（SSE report_delta 帧）
from app.models.user import User
from app.agents.orchestrator_agent import OrchestratorAgent
from app.schemas.agent import AgentTaskRequest, TaskResumeRequest
from app.schemas.report import ReportGenerateRequest
from app.models.task import AgentTask, AgentTaskStep
from app.models.report import AnalysisReport
from app.repositories.report_repository import ReportRepository
from app.api.v1.routes.admin import log_system_event

router = APIRouter()

# 协作智能体注册表（唯一事实源）：/agent/status、dashboard summary 等均以此计数，
# 增删 Agent 时只改这里，登录页「协作智能体」等统计自动同步
AGENT_REGISTRY = [
    {"name": "Orchestrator", "label": "Orchestrator", "framework": "LangGraph",
     "step": "parse_task", "capability": "任务拆解与计划路由"},
    {"name": "DataAgent", "label": "DataAgent", "framework": "LangChain Tool",
     "step": "query_data", "capability": "火点/火险多源数据查询"},
    {"name": "GisAgent", "label": "GisAgent", "framework": "Shapely/GeoPandas",
     "step": "analyze_gis", "capability": "空间聚类与高风险区域识别"},
    {"name": "RagAgent", "label": "RagAgent", "framework": "LangChain RAG",
     "step": "retrieve_knowledge", "capability": "知识库向量检索与引用"},
    {"name": "ReportAgent", "label": "ReportAgent", "framework": "LangChain LLM",
     "step": "generate_report", "capability": "研判报告生成"},
    {"name": "Reviewer", "label": "Reviewer", "framework": "LLM Review",
     "step": "review_report", "capability": "报告质量评审与退回"},
]

# SSE 单连接最长推送时长（防任务卡死导致连接永不关闭）
_SSE_MAX_SECONDS = 1800
# 停滞看门狗：连接保持但超过该秒数未推送任何实质事件（无新步骤/无终态），
# 判定 worker 已死（如后端重启/模型服务挂起），主动推 error 关闭，避免前端永久"执行中"
_SSE_STALL_SECONDS = 600


def _approval_gate_pending(db: Session, task_id: int) -> bool | None:
    """探测 approval_gate 是否真实挂起：True=挂起 / False=确认未挂起 / None=无法判定。
    db_session=None：用轻量兜底节点建图（拓扑一致），探测只需要图结构 + checkpointer，
    避免 RagService/GisAgent 等真实节点构造带来的 LLM/embedding 客户端初始化开销。"""
    try:
        agent = OrchestratorAgent(db_session=None, thread_id=f"task-{task_id}", task_id=task_id)
        return agent.has_pending_interrupt("approval_gate")
    except Exception:
        return None


def _resume_gate_guard(t: AgentTask, db: Session) -> None:
    """resume 前置校验：闸口未触发 / 已被处理 / 已结束 / checkpoint 不可恢复时抛 409。

    "第一次审批不生效"的根因链（按序硬校验，全部可区分错误码）：
    1) 任务已结束 → task_finished；
    2) 不在待审批态 → approval_not_ready；
    3) 审批行缺失/已处理/非挂起 → approval_not_ready / already_resumed / approval_busy；
    4) checkpoint 后端为 MemorySaver 降级 → checkpoint_unavailable：中断状态存在
       进程内旧连接的 MemorySaver 里，resume 的新 agent 拿到的是**空的** MemorySaver，
       stream(Command(resume=...)) 必然从 START 重跑全图并再次 interrupt（症状与用户
       三次反馈完全吻合：第一次假成功/未生效、刷新仍待审批）；
    5) probe 确认闸口无挂起 → approval_not_ready；probe 异常（None）不拦截——
       误拦真实审批比放行一次可观测的失败更糟（worker 失败会把任务置 failed 可见）。
    """
    if t.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail={
            "code": "task_finished", "message": f"任务已结束（{t.status}），无需审批"})
    if t.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail={
            "code": "approval_not_ready",
            "message": "审批闸口尚未就绪，请等待「人工审核」节点进入待审核状态后再提交"})
    row = (
        db.query(AgentTaskStep)
        .filter(AgentTaskStep.task_id == t.id, AgentTaskStep.step_name == "approval")
        .first()
    )
    if row is None:
        raise HTTPException(status_code=409, detail={
            "code": "approval_not_ready",
            "message": "审批闸口尚未触发（草稿尚未生成），请稍候再提交"})
    if (row.status or "") == "completed":
        raise HTTPException(status_code=409, detail={
            "code": "already_resumed",
            "message": "该审批已提交并处理完成，请勿重复操作"})
    if (row.status or "") != "awaiting":
        raise HTTPException(status_code=409, detail={
            "code": "approval_busy", "message": "审批正在处理中，请稍候查看结果"})
    # checkpoint 后端硬校验：MemorySaver 降级时 resume 根本无法续跑，必须明确拒绝
    from app.core.checkpointer import checkpointer_backend
    if checkpointer_backend().get("backend") != "postgres":
        raise HTTPException(status_code=409, detail={
            "code": "checkpoint_unavailable",
            "message": "审批持久化状态不可用（checkpoint 已降级为进程内存储），无法恢复审批；"
                       "请检查 PostgreSQL / langgraph-checkpoint-postgres 配置后重试"})
    pending = _approval_gate_pending(db, t.id)
    if pending is False:
        raise HTTPException(status_code=409, detail={
            "code": "approval_not_ready",
            "message": "审批闸口中断不存在（可能已被处理或状态丢失），请刷新任务状态"})
    # pending is True / None（探测异常）→ 放行：由 worker 真实执行，失败会将任务置 failed 可见


def _fmt(dt) -> str | None:
    """datetime → 可读字符串"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _progress_total(t: AgentTask, has_approval: bool | None) -> int:
    """进度分母（步骤总数口径）：
    - 已有审批步骤行（awaiting/completed 的 approval 行）→ 7（含人工审核）；
    - 已结束且无审批行的旧任务（HITL 上线前/未开启审批）→ 保持 6，不回溯显示 0/7；
    - 进行中/待审批的新任务（审批行尚未产生）按当前 HITL 配置给 7。
    """
    if has_approval:
        return 7
    if t.status in ("completed", "failed", "cancelled"):
        return 6
    from app.core.config import settings
    return 7 if settings.AGENT_REQUIRE_APPROVAL else 6


def _sum_step_tokens(steps: list) -> int:
    """各步骤 output.tokens.total_tokens 求和（报告级 usage 不在此并入，避免重复计数）"""
    total = 0
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        out = s.get("output") if isinstance(s.get("output"), dict) else (s if isinstance(s, dict) else {})
        tok = (out or {}).get("tokens") or {}
        v = tok.get("total_tokens") if isinstance(tok, dict) else None
        if isinstance(v, (int, float)) and isfinite(v):
            total += int(v)
    return total


def _tokens_total_of(usage) -> int | None:
    """从 usage 结构提取 total_tokens（兼容 dict / int / 其他）"""
    if isinstance(usage, dict):
        v = usage.get("total_tokens")
        return int(v) if isinstance(v, (int, float)) and isfinite(v) else None
    if isinstance(usage, (int, float)) and isfinite(usage):
        return int(usage)
    return None


def _task_to_dict(t: AgentTask, llm_provider: str | None = None,
                  llm_model: str | None = None, steps_done: int | None = None,
                  has_approval: bool | None = None, total_tokens: int | None = None) -> dict:
    """任务记录转可序列化字典（含起止时间与耗时，供前端展示"生成时间"）

    llm_provider / llm_model：关联报告的生成模型标识与详细模型名（列表页由
    list_tasks 批量查询注入，避免 N+1；无报告/模板生成时为 None，
    前端据此显示"模板生成"）。
    steps_done：已完成步骤数（列表页聚合注入），用于前端任务卡进度条；
    未传（详情页）时不输出 progress 字段。
    """
    duration = None
    if t.started_at and t.finished_at:
        duration = round((t.finished_at - t.started_at).total_seconds(), 1)
    out = {
        "id": t.id,
        "query": t.user_query,
        "task_name": t.task_name,
        "task_type": t.task_type,
        "status": t.status,
        "current_step": t.current_step,
        "current_agent": _RUNNING_AGENTS.get(t.current_step or "", ""),
        "final_summary": t.final_summary,
        "report_id": t.report_id,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "created_at": _fmt(t.created_at),
        "started_at": _fmt(t.started_at),
        "finished_at": _fmt(t.finished_at),
        "duration": duration,
    }
    # 统一「已用时」口径（秒）：started_at→finished_at；进行中/待审批按当前时间算，
    # started_at 缺失的老任务回落 created_at；新增字段不破坏老前端（纯增量字段）
    start_dt = t.started_at or t.created_at
    if start_dt:
        end_dt = t.finished_at or datetime.now()
        out["elapsed_seconds"] = max(0.0, round((end_dt - start_dt).total_seconds(), 1))
    else:
        out["elapsed_seconds"] = None
    # 统一「Token」口径：调用方聚合注入（详情页=步骤求和，报告级 usage 兜底；列表页批量注入）
    out["total_tokens"] = total_tokens if isinstance(total_tokens, int) and total_tokens > 0 else None
    if steps_done is not None:
        total = _progress_total(t, has_approval)
        done = min(int(steps_done), total)
        out["progress"] = {"done": done, "total": total, "percent": round(done / total * 100)}
    return out


def _step_to_dict(s: AgentTaskStep) -> dict:
    """步骤记录转可序列化字典（与旧版 GET /tasks/{id} 的 steps 契约保持一致）"""
    out = s.output_payload if isinstance(s.output_payload, dict) else {}
    duration = None
    if s.started_at and s.finished_at:
        duration = round((s.finished_at - s.started_at).total_seconds(), 1)
    return {
        "agent": s.agent_name or "",
        "step": s.step_name or "",
        "input": (s.input_payload or {}).get("input", "") if isinstance(s.input_payload, dict) else "",
        "output": out,
        "status": s.status or "completed",
        "summary": out.get("summary", "") or out.get("error", ""),
        "duration": duration,
    }


def _extract_audit(steps: list) -> dict:
    """从步骤输出提取 LLM 审计元数据（取最后一个带 llm_provider 的步骤 = generate_report）

    节点 output 中嵌入了 llm_provider / llm_degraded / tokens（无需额外 DB 迁移）。
    模板兜底或 LLM 不可用时无该字段 → 返回空 dict（前端据此显示"模板生成"）。
    """
    audit: dict = {}
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        out = s.get("output")
        if isinstance(out, dict) and out.get("llm_provider"):
            audit = {
                "llm_provider": out.get("llm_provider") or "",
                "llm_model": out.get("llm_model") or "",
                "llm_degraded": bool(out.get("llm_degraded")),
                "llm_tokens": out.get("tokens") or {},
            }
    return audit


def _task_detail(db: Session, t: AgentTask) -> dict:
    """任务详情装配（GET /tasks/{id} 与 SSE report 事件共用，保证契约一致）"""
    step_rows = (
        db.query(AgentTaskStep)
        .filter(AgentTaskStep.task_id == t.id)
        .order_by(AgentTaskStep.step_order.asc(), AgentTaskStep.id.asc())
        .all()
    )
    steps_out = [_step_to_dict(s) for s in step_rows]
    # 报告内容（有关联报告时；include_deleted：报告中心删除不影响 Agent 历史查看）
    report = ""
    llm_used = False
    meta = {"llm_provider": None, "llm_model": None, "llm_tokens": None, "llm_degraded": False}
    if t.report_id:
        rep = ReportRepository(db).get(t.report_id, user_id=t.user_id, is_admin=True,
                                       include_deleted=True)
        if rep:
            report = rep.get("content", "") or ""
            llm_used = "LLM" in (rep.get("tags") or [])
            meta = {
                "llm_provider": rep.get("llm_provider"),
                "llm_model": rep.get("llm_model"),
                "llm_tokens": rep.get("llm_tokens"),
                "llm_degraded": bool(rep.get("llm_degraded")),
            }
    if not meta.get("llm_provider"):
        # 报告未落库（审批中草稿）或历史数据缺失元数据 → 从执行步骤回退提取
        fallback = _extract_audit(steps_out)
        if fallback:
            meta = fallback
    # Token 汇总口径：步骤级 output.tokens.total_tokens 求和优先；
    # 步骤无用量时回落报告级 usage（llm_tokens），二者取其一避免重复计数
    step_tokens = _sum_step_tokens(steps_out)
    total_tokens = step_tokens or _tokens_total_of(meta.get("llm_tokens"))
    return {
        **_task_to_dict(t, total_tokens=total_tokens),
        "steps": steps_out,
        "report": report,
        "llm_used": llm_used,
        **meta,
    }


# ===================== 后台任务执行 =====================

# 持有后台任务强引用，防止 asyncio.create_task 结果被 GC 回收
_bg_tasks: set = set()

# 任务级 resume 并发防护：同一任务同时只允许一个恢复 worker。
# 重复提交时明确 409（task_busy），不假成功、不吞请求（避免两次 resume / 两条审批事件）。
_active_resume_runs: set[int] = set()
_resume_runs_lock = threading.Lock()

# ===== 进程内任务运行注册表 + 孤儿清扫（uvicorn --reload 重启自愈） =====
# --reload 重启会杀掉后台 worker 线程，但 DB 里任务仍是 running/pending（孤儿）：
# UI 永久"执行中"、审批/报告永不出现。本进程正在执行的任务都登记在
# _active_task_runs；重启后该集合为空，凡 running/pending 而不在集合中的任务
# 即孤儿，由清扫线程判 failed（可重试）。零迁移：不依赖 updated_at 心跳列。
_active_task_runs: set[int] = set()
_task_runs_lock = threading.Lock()
_orphan_sweeper_started = False
_ORPHAN_GRACE_SECONDS = 45.0    # 进程启动宽限：避免与正常启动竞态误杀
_ORPHAN_SCAN_INTERVAL = 30.0


def _register_task_run(task_id: int) -> None:
    with _task_runs_lock:
        _active_task_runs.add(task_id)


def _unregister_task_run(task_id: int) -> None:
    with _task_runs_lock:
        _active_task_runs.discard(task_id)


def _ensure_orphan_sweeper() -> None:
    """惰性启动孤儿清扫线程（首次派发 worker 时；每个进程只启动一次）"""
    global _orphan_sweeper_started
    with _task_runs_lock:
        if _orphan_sweeper_started:
            return
        _orphan_sweeper_started = True

    def _scan_loop() -> None:
        time.sleep(_ORPHAN_GRACE_SECONDS)
        while True:
            try:
                _sweep_orphan_tasks()
            except Exception:
                pass  # 清扫失败静默，下一周期重试
            time.sleep(_ORPHAN_SCAN_INTERVAL)

    threading.Thread(target=_scan_loop, name="agent-orphan-sweeper", daemon=True).start()


def _sweep_orphan_tasks() -> int:
    """running/pending 且进程内无对应 worker → 服务重启遗留孤儿，判 failed（可重试）"""
    with _task_runs_lock:
        alive = set(_active_task_runs)
    db = SessionLocal()
    try:
        rows = (
            db.query(AgentTask)
            .filter(AgentTask.status.in_(("running", "pending")))
            .all()
        )
        orphans = [t for t in rows if t.id not in alive]
        if not orphans:
            return 0
        now = datetime.now()
        for t in orphans:
            t.status = "failed"
            t.final_summary = "任务中断：服务重启导致执行中断，可从历史记录重试"
            t.finished_at = now
            (db.query(AgentTaskStep)
             .filter(AgentTaskStep.task_id == t.id, AgentTaskStep.status == "running")
             .update({"status": "skipped", "finished_at": now},
                     synchronize_session=False))
        db.commit()
        for t in orphans:
            log_system_event("agent",
                             f"任务#{t.id} 为服务重启遗留孤儿（进程内无运行 worker），已判 failed",
                             level="WARNING")
        return len(orphans)
    finally:
        db.close()


def _acquire_resume_run(task_id: int) -> bool:
    with _resume_runs_lock:
        if task_id in _active_resume_runs:
            return False
        _active_resume_runs.add(task_id)
        return True


def _release_resume_run(task_id: int) -> None:
    with _resume_runs_lock:
        _active_resume_runs.discard(task_id)


def _upsert_step_row(db: Session, task_id: int, step_order: int, st: dict) -> None:
    """按 (task_id, step_name) 增量落库/更新步骤（节点完成即写入，支撑实时进度）

    注意：SessionLocal 配置为 autoflush=False，新建行必须显式 flush 才能被同一会话
    的后续查询看到；否则预写的 running 行会被"再插一行"而非被终态覆盖（重复步骤 bug）。
    """
    step_name = st.get("step", "")
    if not step_name:
        return
    row = (
        db.query(AgentTaskStep)
        .filter(AgentTaskStep.task_id == task_id, AgentTaskStep.step_name == step_name)
        .first()
    )
    if row is None:
        row = AgentTaskStep(task_id=task_id)
        row.started_at = datetime.now()
        db.add(row)
    row.step_order = step_order
    row.agent_name = st.get("agent", "")
    row.step_name = step_name
    row.input_payload = {"input": st.get("input", "")}
    # summary 并入 output_payload 持久化（AgentTaskStep 无独立 summary 列）：
    # 节点 step dict 的 summary 是与 output 平级的键，此前只存 output 导致
    # 详情接口 _step_to_dict 永远读不到摘要、前端流水线只剩 chips（用户反馈修复）
    out_payload = {**st.get("output", {}), "summary": st.get("summary", "")}
    # 预写 running 行会覆盖原 output；generate_report 在评审退回/驳回重写时会再次
    # 预写 running，必须保留前几轮思考（旧字段 thinking + 分轮 thinking_rounds），
    # 否则"按任务累积全部思考轮次"会在每次重写时被清空（需求 3）。
    if st.get("status") == "running":
        prev = row.output_payload if isinstance(row.output_payload, dict) else {}
        for key in ("thinking", "thinking_rounds"):
            if key in prev and key not in out_payload:
                out_payload[key] = prev[key]
    row.output_payload = out_payload
    row.status = st.get("status", "completed")
    if row.status != "running":
        row.finished_at = datetime.now()
    db.flush()  # 让本会话后续查询可见（autoflush=False）


# ===================== 任务取消（进程内信号） =====================
# LangGraph 图执行为同步生成器，无法从外部直接中断；取消端点置 DB 状态为 cancelled
# 并打取消标记，worker 在节点边界检查标记后停止推进，避免继续调用 LLM/写报告。
_cancel_flags: dict[int, bool] = {}
_cancel_lock = threading.Lock()


def _request_cancel(task_id: int) -> None:
    with _cancel_lock:
        _cancel_flags[task_id] = True


def _is_cancel_requested(task_id: int) -> bool:
    with _cancel_lock:
        return _cancel_flags.get(task_id, False)


def _clear_cancel(task_id: int) -> None:
    with _cancel_lock:
        _cancel_flags.pop(task_id, None)


# P2#17：节点"开始执行"时预写的 running 步骤行（按图拓扑与计划静态预判；
# 节点完成后 _upsert_step_row 原行覆盖为终态，SSE 对 running 行做终态回推）
_RUNNING_AGENTS = {
    "parse_task": "Orchestrator",
    "query_data": "DataAgent",
    "analyze_gis": "GisAgent",
    "retrieve_knowledge": "RagAgent",
    "generate_report": "ReportAgent",
    "review_report": "Reviewer",
}


def _plan_types(merged: dict) -> set:
    return {p.get("task_type") for p in ((merged.get("parsed_intent") or {}).get("plan") or [])}


def _mark_running(db: Session, task_id: int, order: int, nodes: list[str], query: str) -> None:
    for n in nodes:
        _upsert_step_row(db, task_id, order,
                         {"step": n, "agent": _RUNNING_AGENTS.get(n, ""), "input": query,
                          "output": {}, "status": "running", "summary": "节点执行中"})
    db.commit()  # 立即可见：不 commit 时预写行对 SSE/详情会话不可见，前端表现为 0/6 空转


def _classify_report_type(query: str) -> str:
    """按用户查询语义归类报告类型（daily/weekly/monthly/special），供报告中心筛选"""
    q = query or ""
    if re.search(r"今天|今日|当天|当前|实时|日报|逐日|24小时", q):
        return "daily"
    if re.search(r"本周|上周|一周|近7天|七天|周报", q):
        return "weekly"
    if re.search(r"本月|上月|月报|近30天|三十天|一个月|整月|\d{1,2}月", q):
        return "monthly"
    return "special"


def _save_task_report(db: Session, task: AgentTask, query: str, report_data: str,
                      llm_used: bool, audit: dict | None = None) -> None:
    """将报告落库到报告中心（与旧版 POST /tasks 逻辑一致，标题含年月后缀）

    audit：_extract_audit() 产出的 LLM 元数据（provider/tokens/degraded），
    一并写入报告行，供报告中心展示「模型来源 / 是否降级 / token 用量」。
    """
    title = query[:50] or "Agent 分析报告"
    days_str = ""
    try:
        match = re.search(r"(\d{4})[年\-]?(\d{1,2})", query)
        if match:
            days_str = f"_{match.group(1)}-{match.group(2)}"
    except Exception:
        pass
    repo = ReportRepository(db)
    body = report_data if isinstance(report_data, str) else str(report_data)
    audit = audit or {}
    # 每次任务执行成功都新建一条报告记录（不做同标题/同任务覆盖合并）：
    # 用户要求新生成的报告在报告中心是独立新条目，重复问题重跑也各成一条，
    # 不需要的旧报告由用户在报告中心自行删除
    report = repo.create(
        ReportGenerateRequest(
            title=f"{title}{days_str}",
            report_type=_classify_report_type(query),
            summary=f"任务：{query[:80]}",
            content=body,
            tags=["Agent生成", "LLM" if llm_used else "模板"],
            llm_provider=audit.get("llm_provider"),
            llm_model=audit.get("llm_model"),
            llm_tokens=audit.get("llm_tokens"),
            llm_degraded=bool(audit.get("llm_degraded")),
        ),
        user_id=task.user_id,
    )
    if report:
        task.report_id = report.id


def _merge_update(merged: dict, update: dict) -> None:
    """按 delta 语义合并节点状态增量到累积结果

    steps 键 extend（AgentState 中 steps 为 operator.add reducer，节点只返回增量），
    其余键直接覆盖（单写者键：data_results/gis_results/report/status/revisions/...）。
    """
    for k, v in (update or {}).items():
        if k == "steps":
            merged.setdefault("steps", []).extend(v or [])
        else:
            merged[k] = v


def _step_done(merged: dict, name: str) -> bool:
    """该节点是否已产出终态步骤行（completed/failed/skipped）"""
    return any((s or {}).get("step") == name
               and (s or {}).get("status") in ("completed", "failed", "skipped")
               for s in (merged.get("steps") or []))


def _predict_next_nodes(merged: dict, node_name: str) -> list[str]:
    """P2#17：节点完成后按图拓扑静态预判下一批节点（预写 running 行，前端转圈三态）

    与 build_workflow_graph 的拓扑保持一致；fan-out 的两条分支谁先完成都预判
    join 之后的 generate_report；join 节点本身无步骤行，但同样触发预判
    （否则 generate_report 运行期间没有任何 running 行，前端会按线性步骤
    误显示成"检索知识运行中"的空转状态）。
    """
    if node_name == "parse_task":
        types = _plan_types(merged)
        out = []
        if "query_data" in types or not types:
            out.append("query_data")
        if "retrieve_knowledge" in types:
            out.append("retrieve_knowledge")
        return out or ["query_data"]
    if node_name == "query_data":
        return ["analyze_gis"]
    if node_name in ("analyze_gis", "retrieve_knowledge", "join"):
        types = _plan_types(merged)
        if "generate_report" not in types:
            return []
        # fan-out 的另一条分支仍在执行时，generate_report 还不能开始；
        # 该分支的 running 行继续展示，避免提前预写造成"跳步"观感
        peer = "retrieve_knowledge" if node_name == "analyze_gis" else (
            "query_data" if node_name == "retrieve_knowledge" else None)
        if peer and peer in types and not _step_done(merged, peer):
            return []
        return ["generate_report"]
    if node_name == "generate_report":
        return ["review_report"]
    if node_name == "review_report":
        review = merged.get("review_result") or {}
        if not review.get("passed") and merged.get("revisions", 0) < 2 and not review.get("forced"):
            return ["generate_report"]
        return []
    if node_name in ("approval", "approval_gate"):
        return ["generate_report"] if merged.get("decision") == "reject" else []
    return []


def _consume_agent_stream(step_iter, db: Session, task: AgentTask, username: str,
                          merged: dict | None = None) -> tuple[dict, bool]:
    """消费 agent 节点流（iter_steps / iter_resume 共用）：增量合并状态 + 落库步骤行

    merged：累积状态种子。新建执行传 None（从空开始）；HITL 恢复必须传入
    checkpointer 中的中断前状态——否则 stream(Command(resume=...)) 只产出中断之后的
    增量，report/steps 会丢失，导致审批通过后报告不落库（report_id 恒为 None）。

    返回 (merged, interrupted)；interrupted=True 表示命中 HITL 审批闸口：
    已写 approval 步骤行（含 draft_report 全文供前端审批卡展示）、任务状态置为
    awaiting_approval，等待 POST /tasks/{id}/resume 恢复。
    """
    task_id = task.id
    if merged is None:
        merged = {}
    # 步骤排序号接续已有最大号（新建执行预写的 running 行 / HITL 恢复时的历史行都算），
    # 保证后续步骤始终排在末尾，审批行不会因重新从 0 计而插到最前
    order = 0
    last = (db.query(AgentTaskStep.step_order)
            .filter(AgentTaskStep.task_id == task_id)
            .order_by(AgentTaskStep.step_order.desc()).first())
    if last is not None:
        order = (last[0] or 0) + 1
    interrupted = False
    for node_name, update in step_iter:
        # 取消请求：节点边界立即停止推进（不覆盖已由 cancel 端点写入的 cancelled 终态）
        if _is_cancel_requested(task_id):
            break
        if node_name == "__interrupt__":
            # LangGraph interrupt 事件：update 为 (Interrupt(...),) 元组
            payload = {}
            if isinstance(update, tuple) and update:
                payload = getattr(update[0], "value", None) or {}
            st = {"step": "approval", "agent": "HITL", "input": task.user_query,
                  "output": {"draft_report": payload.get("report", ""),
                             "review": payload.get("review", {}),
                             "revisions": payload.get("revisions", 0)},
                  "status": "awaiting", "summary": "报告已生成，等待人工审批"}
            _upsert_step_row(db, task_id, order, st)
            task.status = "awaiting_approval"
            task.current_step = "approval"
            db.commit()
            log_system_event("agent", f"[{username}] 任务#{task_id} 报告待审批（HITL 暂停）")
            interrupted = True
            break

        _merge_update(merged, update)
        steps = (update.get("steps") or [])
        if steps:
            # join 节点等无步骤的空更新不落库；审批闸口恢复后的 update 也不含 steps
            _upsert_step_row(db, task_id, order, steps[-1])
            order += 1
            task.current_step = node_name
            db.commit()
            log_system_event("agent", f"[{username}] 任务#{task_id} 节点 {node_name} 完成")
        # P2#17：预判下一批节点，预写 running 行（节点完成时原行覆盖为终态）。
        # 放在 if steps 之外：join 等无步骤的空更新节点也要触发，否则后续
        # generate_report 执行期间没有 running 行，前端会误当成"检索知识卡住"
        next_nodes = _predict_next_nodes(merged, node_name)
        if next_nodes:
            _mark_running(db, task_id, order, next_nodes, task.user_query)
            order += len(next_nodes)
    return merged, interrupted


def _finish_task(db: Session, task: AgentTask, merged: dict, user_query: str, username: str) -> None:
    """任务终态处理：更新状态 + 报告落报告中心（新建执行与 resume 恢复共用）"""
    task_id = task.id
    if task.status == "cancelled" or _is_cancel_requested(task_id):
        # 用户已取消：保持 cancelled 终态，不落报告、不覆盖状态。
        # generate_report 步骤行的思考内容由 worker 在流式循环中先行落库（需求 B），
        # 此处不再写任何行，避免覆盖取消端点已提交的终态。
        db.commit()
        return
    result_steps = merged.get("steps", [])
    report_data = merged.get("report", "")
    # 步骤 output 中带 llm_provider 审计信息 → 判定 LLM 是否真实参与 + 取 Provider/token
    audit = _extract_audit(result_steps)
    llm_used = bool(audit.get("llm_provider"))
    status = merged.get("status", "completed")
    if status not in ("completed", "failed"):
        # 纯查询/检索计划（计划不含 generate_report）图正常走完但未写 completed，视为完成
        status = "completed"
    task.status = status
    task.current_step = str(len(result_steps))
    task.final_summary = result_steps[-1].get("summary", "") if result_steps else ""
    task.finished_at = datetime.now()
    if report_data:
        _save_task_report(db, task, user_query, report_data, llm_used, audit)
    db.commit()
    log_system_event("agent", f"[{username}] 任务#{task_id} 完成，报告长度: {len(str(report_data))} 字符")
    # P2#15：任务完成后沉淀用户分析偏好（失败静默，不阻断终态）
    try:
        from app.core.memory_store import record_task_interests
        record_task_interests(task.user_id, user_query)
    except Exception:
        pass


def _run_agent_task(task_id: int, user_query: str, user_id: int, is_admin: bool, username: str) -> None:
    """后台 worker：逐步执行 LangGraph 工作流，节点完成即落库（在线程池中运行）"""
    db = SessionLocal()
    _register_task_run(task_id)  # 进程内登记：孤儿清扫据此区分"本进程在跑"与"重启遗留"
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task is None:
            return
        try:
            # P2#17：parse_task 为首事件前唯一静默节点，起始即写 running 行（转圈三态）
            _mark_running(db, task_id, 0, ["parse_task"], user_query)
            agent = OrchestratorAgent(db_session=db, user_id=user_id, is_admin=is_admin,
                                      thread_id=f"task-{task_id}", task_id=task_id,
                                      cancel_checker=lambda: _is_cancel_requested(task_id))
            merged, interrupted = _consume_agent_stream(agent.iter_steps(user_query), db, task, username)
            if not interrupted:
                _finish_task(db, task, merged, user_query, username)
        except Exception as e:
            if not _is_cancel_requested(task_id) and task.status != "cancelled":
                task.status = "failed"
                task.final_summary = f"任务执行异常: {str(e)[:200]}"
                task.finished_at = datetime.now()
            db.commit()
            log_system_event("agent", f"任务#{task_id} 失败: {str(e)[:120]}", level="ERROR")
    finally:
        _unregister_task_run(task_id)
        _clear_cancel(task_id)
        db.close()


def _run_resume_agent_task(task_id: int, resume_value: dict, user_id: int, is_admin: bool,
                           username: str) -> None:
    """HITL 恢复 worker：以同 thread_id 重建 OrchestratorAgent，从中断点续跑（新线程新连接）"""
    db = SessionLocal()
    _register_task_run(task_id)
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task is None:
            return
        try:
            agent = OrchestratorAgent(db_session=db, user_id=user_id, is_admin=is_admin,
                                      thread_id=f"task-{task_id}", task_id=task_id,
                                      cancel_checker=lambda: _is_cancel_requested(task_id))
            # 关键：以 checkpointer 中中断前的累积状态为种子，否则续跑只拿到增量，
            # report/steps 丢失 → 审批通过后报告不落库（report_id 恒为 None）
            merged, interrupted = _consume_agent_stream(
                agent.iter_resume(resume_value), db, task, username,
                merged=agent.snapshot_state())
            if not interrupted:
                _finish_task(db, task, merged, task.user_query, username)
            elif merged.get("decision") != "reject":
                # resume 后再次进入审批闸口：reject 重写属正常；approve/edit 走到这里说明
                # 恢复没有按预期消费决策（典型：checkpoint 丢失导致从 START 重跑全图），
                # 任务会重新回到待审批——显式告警便于定位"第一次审批不生效"
                log_system_event(
                    "agent",
                    f"任务#{task_id} resume 后再次中断（action={resume_value.get('action')}），"
                    "疑似 checkpoint 丢失导致流程重跑，任务已回到待审批",
                    level="ERROR")
            # interrupted=True 且 reject：驳回重写后再次进入审批闸口，等待下一次 resume
        except Exception as e:
            if not _is_cancel_requested(task_id) and task.status != "cancelled":
                task.status = "failed"
                task.final_summary = f"任务恢复执行异常: {str(e)[:200]}"
                task.finished_at = datetime.now()
            db.commit()
            log_system_event("agent", f"任务#{task_id} 恢复失败: {str(e)[:120]}", level="ERROR")
    finally:
        _unregister_task_run(task_id)
        _release_resume_run(task_id)
        _clear_cancel(task_id)
        db.close()


def _spawn_task(task_id: int, user_query: str, user_id: int, is_admin: bool, username: str) -> None:
    """把同步 worker 放入线程池执行（图执行为同步 LangGraph，不能阻塞事件循环）"""
    _ensure_orphan_sweeper()  # 惰性启动孤儿清扫（每进程一次）
    coro = asyncio.to_thread(_run_agent_task, task_id, user_query, user_id, is_admin, username)
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


def _spawn_resume_task(task_id: int, resume_value: dict, user_id: int, is_admin: bool, username: str) -> None:
    """把 HITL 恢复 worker 放入线程池执行"""
    _ensure_orphan_sweeper()
    coro = asyncio.to_thread(_run_resume_agent_task, task_id, resume_value, user_id, is_admin, username)
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


# ===================== 接口 =====================

@router.get("/tasks")
async def list_tasks(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """获取当前用户的任务历史（管理员可查全部）；附带各任务报告的生成模型"""
    q = db.query(AgentTask)
    if current.role != "admin":
        q = q.filter(AgentTask.user_id == current.id)
    tasks = q.order_by(AgentTask.created_at.desc()).limit(50).all()
    # 批量取关联报告的 llm_provider / llm_model / llm_tokens（一次 IN 查询，避免逐条 N+1）
    report_ids = [t.report_id for t in tasks if t.report_id]
    provider_map: dict[int, tuple] = {}
    report_tokens_map: dict[int, int] = {}
    if report_ids:
        rows = (
            db.query(AnalysisReport.id, AnalysisReport.llm_provider,
                     AnalysisReport.llm_model, AnalysisReport.llm_tokens)
            .filter(AnalysisReport.id.in_(report_ids))
            .all()
        )
        provider_map = {r.id: (r.llm_provider, r.llm_model) for r in rows}
        report_tokens_map = {r.id: v for r in rows
                             if (v := _tokens_total_of(r.llm_tokens)) is not None}
    # 批量统计各任务已完成步骤数（任务卡进度条；running 预写行不计入）
    task_ids = [t.id for t in tasks]
    done_map: dict[int, int] = {}
    if task_ids:
        from sqlalchemy import func
        rows = (
            db.query(AgentTaskStep.task_id, func.count(AgentTaskStep.id))
            .filter(AgentTaskStep.task_id.in_(task_ids),
                    AgentTaskStep.status.in_(("completed", "failed", "skipped")))
            .group_by(AgentTaskStep.task_id)
            .all()
        )
        done_map = {tid: cnt for tid, cnt in rows}
    # 批量标记各任务是否已有审批步骤行（进度分母 7/6 口径；待审批的 approval
    # 行 status=awaiting 不计入 done，定稿后被覆盖为 completed 计入）
    approval_set: set[int] = set()
    if task_ids:
        rows = (
            db.query(AgentTaskStep.task_id)
            .filter(AgentTaskStep.task_id.in_(task_ids),
                    AgentTaskStep.step_name == "approval")
            .distinct()
            .all()
        )
        approval_set = {r[0] for r in rows}
    # 批量聚合各任务步骤级 token 用量（output.tokens.total_tokens 求和；JSON 在 Python 侧聚合，
    # 不做破坏性迁移；步骤级为空时回落报告级 usage，避免重复计数）
    step_tokens_map: dict[int, int] = {}
    if task_ids:
        rows = (
            db.query(AgentTaskStep.task_id, AgentTaskStep.output_payload)
            .filter(AgentTaskStep.task_id.in_(task_ids))
            .all()
        )
        for tid, payload in rows:
            v = _tokens_total_of((payload or {}).get("tokens"))
            if v is not None:
                step_tokens_map[tid] = step_tokens_map.get(tid, 0) + v
    return {
        "code": 200,
        "message": "success",
        "data": [
            _task_to_dict(t, *(provider_map.get(t.report_id) or (None, None)),
                          steps_done=done_map.get(t.id, 0),
                          has_approval=t.id in approval_set,
                          total_tokens=step_tokens_map.get(t.id)
                          or report_tokens_map.get(t.report_id))
            for t in tasks
        ],
    }


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """任务详情：含执行步骤（Agent 执行过程）与报告内容（用户数据隔离）"""
    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current.role != "admin" and t.user_id != current.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return {"code": 200, "message": "success", "data": _task_detail(db, t)}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """删除任务历史（仅本人或管理员）"""
    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not t or (current.role != "admin" and t.user_id != current.id):
        raise HTTPException(status_code=404, detail="任务不存在或无权限删除")
    if t.status in ("running", "pending", "awaiting_approval"):
        raise HTTPException(status_code=400, detail="任务执行中，请先取消再删除")
    db.query(AgentTaskStep).filter(AgentTaskStep.task_id == task_id).delete()
    db.delete(t)
    db.commit()
    return {"code": 200, "message": "success", "data": {"id": task_id}}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """取消任务（running / awaiting_approval / pending）

    实现：置 DB 终态 cancelled 并打进程内取消标记；worker 在下一个节点边界停止推进，
    不再落报告。卡在单次 LLM 调用中的任务最迟在调用总时限（120s）返回后退出。
    """
    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current.role != "admin" and t.user_id != current.id:
        raise HTTPException(status_code=403, detail="无权操作该任务")
    if t.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="任务已结束，无需取消")
    _request_cancel(task_id)
    # 运行中的步骤行置为 skipped，避免前端详情一直显示转圈。
    # 只改 status/finished_at，不动 output_payload——generate_report 行的思考内容
    # 由 worker 运行中持续写入（需求 B），取消后必须保留供详情回看。
    rows = (db.query(AgentTaskStep)
            .filter(AgentTaskStep.task_id == task_id, AgentTaskStep.status == "running")
            .all())
    for r in rows:
        r.status = "skipped"
        r.finished_at = datetime.now()
    db.commit()  # 先落库步骤终态（含 worker 已写入的思考内容），再改任务状态
    t.status = "cancelled"
    t.finished_at = datetime.now()
    t.final_summary = t.final_summary or "用户取消任务"
    db.commit()
    log_system_event("agent", f"[{current.username}] 任务#{task_id} 已取消")
    return {"code": 200, "message": "任务已取消", "data": {"id": task_id, "status": "cancelled"}}


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """重试任务：以相同查询新建一个任务（原任务历史保留，失败/取消/已完成均可重跑）"""
    src = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current.role != "admin" and src.user_id != current.id:
        raise HTTPException(status_code=403, detail="无权操作该任务")
    if src.status in ("running", "pending", "awaiting_approval"):
        raise HTTPException(status_code=400, detail="任务执行中，请先取消再重试")
    task = AgentTask(
        user_id=current.id,
        task_name=src.user_query[:100],
        task_type="analysis",
        user_query=src.user_query,
        status="running",
        current_step="0",
        started_at=datetime.now(),
        created_at=datetime.now(),
    )
    db.add(task)
    db.commit()
    _spawn_task(task.id, task.user_query, current.id, current.role == "admin", current.username)
    log_system_event("agent", f"[{current.username}] 任务#{task_id} 重试 → 新任务#{task.id}")
    return {"code": 200, "message": "已重新发起任务",
            "data": {"task_id": task.id, "source_task_id": task_id, "status": "running"}}


@router.post("/tasks")
async def create_task(
    req: AgentTaskRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """创建 Agent 任务（立即返回 task_id，后台异步执行；进度通过 SSE 端点订阅）

    执行完成后报告自动落入报告中心（upsert 去重），任务/步骤全程落库。
    """
    query = req.query.strip()
    log_system_event("agent", f"[{current.username}] 接收到任务: {query[:60]}")

    task = AgentTask(
        user_id=current.id,
        task_name=query[:100],
        task_type="analysis",
        user_query=query,
        status="running",
        current_step="0",
        started_at=datetime.now(),
        created_at=datetime.now(),
    )
    db.add(task)
    db.commit()

    _spawn_task(task.id, query, current.id, current.role == "admin", current.username)

    return {
        "code": 200,
        "message": "任务已受理，后台执行中",
        "data": {"task_id": task.id, "status": "running"},
    }


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: int,
    req: TaskResumeRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """HITL 审批决策：从中断点恢复任务（仅任务所有者或管理员）

    action=approve  → 报告按原稿定稿并落报告中心
    action=edit     → 以提交的 content 作为最终报告落报告中心
    action=reject   → 携带驳回意见回 generate_report 重写，重写完成后再次进入审批
    """
    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current.role != "admin" and t.user_id != current.id:
        raise HTTPException(status_code=403, detail="无权操作该任务")
    # 闸口校验前置：未触发/已处理/已结束一律 409 + 语义化 code，前端据 detail.code 提示，
    # 避免"闸口未就绪却按成功处理"（用户反馈：第一次点击假成功、审批事件又把界面弹回待审批）
    _resume_gate_guard(t, db)
    if req.action == "edit" and not (req.content or "").strip():
        raise HTTPException(status_code=400, detail="编辑通过需提供修改后的报告内容")
    if req.action == "reject" and not (req.comment or "").strip():
        raise HTTPException(status_code=400, detail="驳回需填写驳回意见")
    # 同任务并发防护：已有恢复 worker 在跑时明确拒绝（不假成功、不吞请求、不产生第二次恢复）
    if not _acquire_resume_run(task_id):
        raise HTTPException(status_code=409, detail={
            "code": "task_busy",
            "message": "该任务的审批恢复正在执行中，请稍候刷新查看结果"})

    resume_value = {"action": req.action, "content": req.content or "", "comment": req.comment or ""}
    t.status = "running"
    t.current_step = "approval"
    db.commit()
    log_system_event("agent", f"[{current.username}] 任务#{task_id} 审批决策: {req.action}")

    # 以任务所有者身份恢复执行（RAG 检索等保持 owner 数据隔离）
    _spawn_resume_task(task_id, resume_value, t.user_id, current.role == "admin", current.username)
    return {"code": 200, "message": "审批已提交，任务继续执行",
            "data": {"task_id": task_id, "status": "running"}}


def get_stream_user(
    request: Request,
    token: str | None = Query(default=None, description="JWT 兜底通道，仅旧前端 bundle 使用"),
    db: Session = Depends(get_db),
) -> User:
    """SSE 鉴权依赖：优先 Authorization 头，回退到 ?token=

    刻意做成 Depends 而不是在端点函数体里手调：后者会让鉴权藏在 body 里，
    scripts/check_auth_coverage.py 解析依赖树时看不见，将来谁删掉那一行都没迹象。

    两条通道都必须交给 resolve_user 同一个入口——否则新增的校验规则
    （如 token_version 吊销）只覆盖了 Header 那条，query 那条就成了绕过点。

    `?token=` 之所以还留着：旧前端 bundle 在被浏览器/CDN 缓存命中期间仍在用它，
    直接删会让线上老页面立刻断流。前端全量迁移到 fetch 后可移除本分支。
    """
    auth = request.headers.get("authorization") or ""
    credential = auth[7:].strip() if auth[:7].lower() == "bearer " else (token or "")
    return resolve_user(credential, db)


def _sse(payload: dict) -> str:
    """格式化 SSE 数据帧"""
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    task_id: int,
    current: User = Depends(get_stream_user),
    db: Session = Depends(get_db),
):
    """SSE 实时推送任务执行进度

    事件流：
      - type=step    每个节点完成时推送（增量落库的步骤行）
      - type=approval HITL 审批事件（任务挂起等待人工决策，携带含 draft_report 的任务详情）后关闭
      - type=report  终态事件（completed/failed），携带完整任务详情（含报告）后关闭
    连接建立时先回放已落库的历史步骤（支持刷新/断线重连不丢进度），并由通道补一帧
    type=report_snapshot（本轮已产出的正文/思考增量副本），使「流式中切页再回来」
    不丢已上屏内容；终态完整内容仍以 DB 为准。
    """
    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current.role != "admin" and t.user_id != current.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")

    async def event_gen():
        last_step_id = 0
        started = time.monotonic()
        last_frame = time.monotonic()  # 最近一次实质事件（非 ping）推送时间
        running_rows: dict[int, int] = {}  # 已推送为 running 的步骤行 id（终态后需回推）
        terminal = False  # 本连接是否因终态收尾（决定要不要丢弃增量副本）
        # P2#18：订阅报告流式增量通道（队列易失，但通道会在新连接上线时补一帧
        # report_snapshot，把本轮已产出的增量一次性补齐——见 app/core/report_channels.py）
        q = report_channels.subscribe(task_id)
        try:
            while True:
                db.expire_all()  # 清空身份映射，保证轮询读到后台 worker 的最新提交
                for s in (
                    db.query(AgentTaskStep)
                    .filter(AgentTaskStep.task_id == task_id, AgentTaskStep.id > last_step_id)
                    .order_by(AgentTaskStep.id.asc())
                    .all()
                ):
                    last_step_id = s.id
                    yield _sse({"type": "step", "step": _step_to_dict(s)})
                    last_frame = time.monotonic()
                    if (s.status or "") == "running":
                        running_rows[s.id] = 1
                if running_rows:
                    # P2#17：running 行被 worker 覆盖为终态后，主动回推一次
                    rows = db.query(AgentTaskStep).filter(AgentTaskStep.id.in_(list(running_rows))).all()
                    for r in rows:
                        if (r.status or "") != "running":
                            running_rows.pop(r.id, None)
                            yield _sse({"type": "step", "step": _step_to_dict(r)})
                            last_frame = time.monotonic()

                t2 = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                status = t2.status if t2 else "failed"
                if status == "awaiting_approval":
                    # HITL：推送审批事件（含 draft_report 的步骤详情）后关闭，
                    # 前端展示审批卡，resume 提交后重新订阅本端点继续收进度
                    detail = _task_detail(db, t2)
                    yield _sse({"type": "approval", "data": detail})
                    break
                if status in ("completed", "failed", "cancelled"):
                    detail = _task_detail(db, t2) if t2 else None
                    yield _sse({"type": "report", "data": detail})
                    terminal = True  # 全文已落库，增量副本可以丢了
                    break
                if time.monotonic() - started > _SSE_MAX_SECONDS:
                    yield _sse({"type": "error", "message": "进度推送超时，请稍后刷新任务历史"})
                    break
                if time.monotonic() - last_frame > _SSE_STALL_SECONDS:
                    # 看门狗：worker 长时间无任何新步骤（如被重启杀掉 / 模型服务挂起）→ 主动收尾
                    yield _sse({"type": "error", "message": "任务长时间无进展（执行可能已中断），请刷新历史或重新发起任务"})
                    break
                yield ": ping\n\n"
                # 等待实时增量（0.6s 超时回到 DB 轮询；与节点进度共用同一条连接）
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=0.6)
                    yield _sse(ev)
                    while True:
                        try:
                            ev = q.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        yield _sse(ev)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise  # 客户端断开，正常结束
        finally:
            report_channels.unsubscribe(task_id, q)
            if terminal:
                # 只在真正终态时丢弃副本；客户端断开（切页/刷新）必须留着供重连补齐
                report_channels.drop(task_id)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/capabilities")
async def get_agent_capabilities(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """「系统能力」面板数据源 — 返回 P0/P1/P2 能力的**真实运行时状态**（非硬编码文案）

    仅需登录态即可查看；所有字段均可从配置/模块状态实时推导，便于前端可视化展示
    重试熔断、检查点、编排拓扑、双数据源、RAG、偏好记忆、MCP、观测与评估回归。
    """
    import sqlalchemy as sa
    from pathlib import Path

    from app.core.config import settings
    from app.core.llm import llm_available
    from app.core.checkpointer import checkpointer_backend
    from app.core.llm_invoker import breaker_status, _provider_chain, _RETRY_DELAYS

    # 知识库文档数（表不存在/查询失败不阻断面板）
    kb_total = None
    try:
        kb_total = db.execute(sa.text('SELECT COUNT(*) FROM kb_documents')).scalar()
    except Exception:
        kb_total = None

    # 评估回归金标用例数
    golden_cases = None
    try:
        import json as _json
        p = Path(__file__).resolve().parents[3] / "scripts" / "golden_set.json"
        if p.exists():
            data = _json.loads(p.read_text(encoding="utf-8"))
            golden_cases = len(data) if isinstance(data, list) else len(data.get("cases", []))
    except Exception:
        golden_cases = None

    active = settings.ACTIVE_LLM_PROVIDER
    model_map = {"aliyun": settings.LLM_MODEL, "amd": settings.AMD_MODEL, "ollama": settings.OLLAMA_MODEL}

    return {
        "code": 200,
        "message": "success",
        "data": {
            "llm": {
                "active_provider": active,
                "active_model": model_map.get(active, ""),
                "available": llm_available(),
                "stream_enabled": settings.LLM_STREAM_ENABLED,
                "provider_chain": _provider_chain(),
                "retry": {"delays": list(_RETRY_DELAYS), "max_attempts": len(_RETRY_DELAYS) + 1},
                "breakers": breaker_status(),
            },
            "checkpointer": checkpointer_backend(),
            "orchestration": {
                "framework": "LangGraph StateGraph",
                "topology": ["parse_task", "query_data ∥ retrieve_knowledge", "analyze_gis",
                             "join", "generate_report", "review_report", "approval_gate"],
                "plan_driven_routing": True,
                "parallel_fanout": True,
                "reflection_retry": {"max_rounds": 2, "trigger": "数据查询为空时 LLM 放宽参数重查"},
                "review_loop": {"max_revisions": 2, "hard_guardrail_min_chars": 800},
                "hitl": {"required": settings.AGENT_REQUIRE_APPROVAL,
                         "actions": ["approve", "edit", "reject"]},
                "node_progress_sse": True,
            },
            "data": {
                "dual_source": True,
                "sources": [
                    {"table": "historical_fire_points", "label": "历史火点",
                     "range": "2021-2025", "source_tag": "historical"},
                    {"table": "predicted_fire_risks", "label": "预测火险",
                     "range": "2025-2026", "source_tag": "predicted"},
                ],
                "gis": {"historical": "经纬度 0.1° 网格聚类识别聚集区",
                        "predicted": "火险等级 ≥ 3 级识别高风险州市"},
            },
            "rag": {
                "embedding_model": settings.EMBEDDING_MODEL,
                "retrieval": "中文分词关键词 + 向量余弦相似度 + bigram 兜底",
                "rerank": {"enabled": settings.RERANK_ENABLED, "model": settings.RERANK_MODEL,
                           "fallback": "失败降级 RRF 融合原序"},
                "top_k": settings.KB_TOP_K,
                "documents": kb_total,
                "citation": True,
                "stream": True,
            },
            "memory": {"preferences_enabled": settings.PREFERENCES_ENABLED,
                       "store": "PostgresStore(JSONB)",
                       "inject": "用户历史关注辖区/时段注入报告 prompt，任务完成后沉淀"},
            "mcp": {"enabled": settings.MCP_ENABLED,
                    "servers": ["weather_server（高德 geo→adcode→实时天气，只读）"],
                    "fallback": "未启用/依赖缺失/调用失败静默跳过"},
            "observability": {"langfuse_enabled": settings.LANGFUSE_ENABLED,
                              "fallback": "未启用时降级为纯日志，不影响主链路"},
            "evaluation": {"golden_cases": golden_cases,
                           "metrics": ["Tool Correctness", "路由正确性", "任务完成+轨迹", "轻量 Faithfulness"],
                           "modes": ["offline", "live"]},
            "degradation": {
                "llm": "指数重试(1s/2s/4s) → 熔断(3次/60s) → Provider 链切换 → 模板兜底",
                "checkpointer": "PostgresSaver → MemorySaver",
                "rerank": "Rerank → RRF 融合原序",
                "mcp": "静默跳过", "preferences": "静默跳过",
            },
        },
    }


@router.get("/status")
async def get_agent_status(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """获取 Agent 系统状态（六阶段流水线的真实运行时状态）

    返回 6 个 Agent（含 Reviewer），并根据当前用户最近一个活跃任务标注 busy，
    前端页头不再显示静态的"Agent 5 就绪"。
    """
    base_agents = AGENT_REGISTRY
    # 活跃任务分两层：running/pending 是"系统正在做的事"，awaiting_approval 是"等人处理"。
    # 待审批超过 STALE_AWAITING_HOURS 视为滞留（常见于测试遗留），不计入页头实时状态，
    # 否则会出现"一个进程都没有，却亮着 5 个待审批"的错觉；滞留只进任务抽屉单独展示。
    STALE_AWAITING_HOURS = 24
    active_statuses = ("pending", "running", "awaiting_approval")
    active_q = db.query(AgentTask).filter(AgentTask.status.in_(active_statuses))
    if current.role != "admin":
        active_q = active_q.filter(AgentTask.user_id == current.id)

    from sqlalchemy import and_, func, or_
    status_rows = (
        active_q.with_entities(AgentTask.status, func.count(AgentTask.id))
        .group_by(AgentTask.status)
        .all()
    )
    status_counts = {s: cnt for s, cnt in status_rows}
    running_tasks = status_counts.get("running", 0)
    pending_tasks = status_counts.get("pending", 0)
    awaiting_total = status_counts.get("awaiting_approval", 0)

    # started_at 为空的历史任务回落到 created_at 计算等待时长
    stale_cutoff = datetime.now() - timedelta(hours=STALE_AWAITING_HOURS)
    awaiting_started = func.coalesce(AgentTask.started_at, AgentTask.created_at)
    stale_awaiting_tasks = active_q.filter(
        AgentTask.status == "awaiting_approval",
        awaiting_started < stale_cutoff,
    ).count()
    awaiting_tasks = max(0, awaiting_total - stale_awaiting_tasks)
    active_tasks = running_tasks + pending_tasks + awaiting_tasks

    live_q = active_q.filter(or_(
        AgentTask.status.in_(("running", "pending")),
        and_(AgentTask.status == "awaiting_approval", awaiting_started >= stale_cutoff),
    ))

    # 运行中的 Agent 由所有 running 任务的 current_step 汇总，而非只看最近一条
    running_steps = {
        step for (step,) in live_q.filter(AgentTask.status == "running")
        .with_entities(AgentTask.current_step).all() if step
    }
    busy_agents = sorted({_RUNNING_AGENTS.get(s, "") for s in running_steps} - {""})

    active = live_q.order_by(AgentTask.created_at.desc()).first()
    for a in base_agents:
        if a["name"] in busy_agents:
            a["status"] = "busy"
        else:
            a["status"] = "ready"
    return {
        "code": 200,
        "message": "success",
        "data": {
            "status": "running" if running_tasks else "idle",
            "agents": base_agents,
            "active_tasks": active_tasks,
            "running_tasks": running_tasks,
            "pending_tasks": pending_tasks,
            "awaiting_tasks": awaiting_tasks,
            "stale_awaiting_tasks": stale_awaiting_tasks,
            "awaiting_stale_hours": STALE_AWAITING_HOURS,
            "busy_agents": busy_agents,
            # 当前实际生效的 LLM 通道（Agent 中心输入卡展示用）。
            # 放在 /agent/status 而不是让普通用户去轮询 /admin/status：
            # 模型名本身不敏感，但 /admin/status 里还有版本、库连通性与熔断器状态。
            "llm_provider": settings.ACTIVE_LLM_PROVIDER,
            "llm_model": {
                "amd": settings.AMD_MODEL,
                "ollama": settings.OLLAMA_MODEL,
                "longcat": settings.LONGCAT_MODEL,
            }.get(settings.ACTIVE_LLM_PROVIDER, settings.LLM_MODEL),
            "active_task": ({"id": active.id, "query": active.user_query,
                             "status": active.status, "current_step": active.current_step}
                            if active else None),
        },
    }
