"""评审三态判定回归：returned / degraded / passed。

运行（仓库根目录）：python -m pytest tests/test_review_tri_state.py -q

覆盖：
① 评审 LLM 抛异常 / 解析失败 → 不退回，passed=True（进审批闸口）、review_status=degraded；
② 评审成功且 0 问题 → 通过，无退回；
③ 评审返回具体问题 → 退回重写且最多 2 轮（达上限转人工 forced）；
④ issues 为空时 summary 不出现「：。」空拼接；0 问题通过文案为「未发现问题」；
   降级文案为「评审未完成，已转人工确认」。
另断言 route_after_review：degraded（passed=True）走 approval_gate 而非退回。
"""
from app.agents.orchestrator_agent import (
    _decide_review_outcome,
    route_after_review,
)


# ① 评审自身失败（异常/超时/解析失败）→ degraded，不退回
def test_review_exception_degrades_to_human():
    out = _decide_review_outcome(hard_issues=[], llm_ok=False, llm_passed=False,
                                 revisions=0, degraded_reason="评审 LLM 调用异常（TimeoutError）")
    assert out["passed"] is True              # 不阻断：直接转人工
    assert out["review_status"] == "degraded"
    assert out["forced"] is False
    assert out["issues"] == []
    assert "退回" not in out["summary"]
    assert "转人工确认" in out["summary"]
    assert "：" not in out["summary"].replace("（", "").replace("）", "") or "发现0项问题" not in out["summary"]


def test_review_parse_failure_degrades():
    out = _decide_review_outcome(hard_issues=[], llm_ok=False, llm_passed=False,
                                 revisions=1, degraded_reason="结构化评审输出解析失败")
    assert out["review_status"] == "degraded"
    assert "解析失败" in out["summary"]


def test_llm_rejects_without_issues_degrades():
    """LLM 判不通过但给不出具体问题（issues 全是占位词被过滤）→ 降级，不退回"""
    out = _decide_review_outcome(hard_issues=[], llm_ok=True, llm_passed=False,
                                 revisions=0, llm_issues=["问题1", "问题2", ""])
    assert out["issues"] == []                # 占位词全部过滤
    assert out["review_status"] == "degraded"
    assert "发现0项问题" not in out["summary"]


# ② 评审成功且 0 问题 → 通过
def test_review_pass_zero_issues():
    out = _decide_review_outcome(hard_issues=[], llm_ok=True, llm_passed=True,
                                 revisions=0, llm_issues=[], suggestion="结构完整")
    assert out["passed"] is True
    assert out["review_status"] == "passed"
    assert "未发现问题" in out["summary"]
    assert "退回" not in out["summary"]


# ③ 评审返回具体问题 → 退回，且最多 2 轮
def test_review_with_issues_returns_for_rewrite():
    issues = ["缺少执行摘要章节", "巡防建议不可执行"]
    out = _decide_review_outcome(hard_issues=[], llm_ok=True, llm_passed=False,
                                 revisions=0, llm_issues=issues)
    assert out["passed"] is False
    assert out["review_status"] == "returned"
    assert out["forced"] is False
    assert out["issues"] == issues
    assert "发现2项问题" in out["summary"] and "退回" in out["summary"]
    # 文案带具体问题，无空拼接
    assert "发现0项问题" not in out["summary"]
    assert "：" + "。" not in out["summary"]


def test_rewrite_rounds_capped_at_two():
    """revisions=0/1 → returned（继续重写）；revisions=2 → 停止重写转人工 forced"""
    for rev in (0, 1):
        out = _decide_review_outcome(hard_issues=[], llm_ok=True, llm_passed=False,
                                     revisions=rev, llm_issues=["数据未引用"])
        assert out["review_status"] == "returned" and out["forced"] is False
    out = _decide_review_outcome(hard_issues=[], llm_ok=True, llm_passed=False,
                                 revisions=2, llm_issues=["数据未引用"])
    assert out["passed"] is False
    assert out["review_status"] == "degraded"
    assert out["forced"] is True
    assert "转人工审核确认" in out["summary"]


def test_hard_guardrail_issues_return_even_if_llm_passes():
    """硬护栏问题一票否决：LLM 说通过也退回"""
    out = _decide_review_outcome(hard_issues=["报告正文仅 300 字符"], llm_ok=True,
                                 llm_passed=True, revisions=0)
    assert out["passed"] is False and out["review_status"] == "returned"


# ④ 路由：degraded（passed=True）→ 审批闸口，不再退回
def test_route_after_review_degraded_goes_approval():
    st = {"review_result": {"passed": True, "review_status": "degraded"}, "revisions": 0}
    assert route_after_review(st) == "approval_gate"
    st2 = {"review_result": {"passed": True, "review_status": "passed"}, "revisions": 0}
    assert route_after_review(st2) == "approval_gate"
    st3 = {"review_result": {"passed": False, "review_status": "returned"}, "revisions": 0}
    assert route_after_review(st3) == "generate_report"
    st4 = {"review_result": {"passed": False, "review_status": "degraded", "forced": True},
           "revisions": 2}
    assert route_after_review(st4) == "approval_gate"


# 文案空拼接专项：任何组合下 summary 都不出现「发现0项问题：。」
def test_no_empty_issue_summary():
    combos = [
        dict(hard_issues=[], llm_ok=False, llm_passed=False, revisions=0,
             degraded_reason="x"),
        dict(hard_issues=[], llm_ok=True, llm_passed=False, revisions=0, llm_issues=[]),
        dict(hard_issues=[], llm_ok=True, llm_passed=True, revisions=2),
    ]
    for c in combos:
        out = _decide_review_outcome(**c)
        assert "发现0项问题" not in out["summary"]
        assert "：。" not in out["summary"]
