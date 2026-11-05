"""
编排 Agent — 使用 LangGraph StateGraph 做任务编排（P1 升级版）

P1 新增能力：
- #5 plan 驱动路由：parse_task 结构化产出执行计划，后续节点按计划执行/跳过（跳过=no-op 节点，保留 join 屏障正确性）
- #6 并行 fan-out/join：query_data 与 retrieve_knowledge 并行执行，join 节点汇聚
- #7 反思重试：query_data 结果为空时由 LLM 反思放宽参数重查（最多 2 轮）
- #8 评审循环：review_report 低温度 LLM 评审 + 硬护栏，不通过带意见回 generate_report 重写（最多 2 轮）
- #11 HITL 审批：approval_gate 使用 langgraph interrupt 暂停，resume 端点注入人工决策

并发防冲突约定（重要）：
- steps / knowledge_results 使用 operator.add reducer，所有节点只返回 delta（新增的部分），禁止返回全量列表；
- status 键仅由 parse_task（"parsed"）与 generate_report / approval_gate（"completed"）写入，
  并行波次节点不得写 status，条件路由一律读取 parsed_intent.plan，不读 status。
"""
import json
import operator
import re
import time
from typing import TYPE_CHECKING, Annotated, Any, TypedDict, Literal, Callable

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.checkpointer import create_checkpointer
from app.core.llm import llm_available
from app.core.llm_invoker import invoke_llm, invoke_structured, stream_llm, LLMResult

# ==================== AgentGauntlet 评测挂接（已全部停用） ====================
# 原攻击轮输出护栏（W2 canary）与故障注入挂接（W1 chaos）代码已按需求注释下线，
# 正常服务不再打印 [gauntlet-chaos] 日志、不再包装任何工具。如需恢复评测能力，
# 从版本历史中找回 _chaos_wrap / _guard_canary_output 相关代码。

# 仅用于类型检查解析，避免运行时强制导入 langgraph（保持懒加载、加快启动）
if TYPE_CHECKING:
    from langgraph.graph import CompiledStateGraph


# ===== 任务计划结构化输出 Schema（parse_task 使用，驱动 P1 条件路由） =====
class SubTaskPlan(BaseModel):
    """单个子任务"""
    task_type: Literal["query_data", "analyze_gis", "retrieve_knowledge", "generate_report"] = Field(
        description="子任务类型")
    description: str = Field(default="", description="子任务具体描述")
    reason: str = Field(default="", description="为什么需要/不需要该子任务")
    required: bool = Field(default=True, description="该子任务是否必须执行")


class TaskPlan(BaseModel):
    """Orchestrator 拆解出的执行计划"""
    plan: list[SubTaskPlan] = Field(default_factory=list, description="子任务列表")


# ===== 反思重试 Schema（query_data 为空时 LLM 调整查询参数） =====
class QueryRetryPlan(BaseModel):
    """查询为空时的参数调整建议（None 字段 = 放宽为不限）"""
    reason: str = Field(default="", description="查询为空的可能原因")
    adjusted_year: int | None = Field(default=None, description="调整后的年份；null 表示不限年份")
    adjusted_month: int | None = Field(default=None, description="调整后的月份(1-12)；null 表示不限月份")
    adjusted_city: str | None = Field(default=None, description="调整后的州市名；null 表示不限州市")
    adjusted_view_mode: Literal["daily", "monthly"] | None = Field(
        default=None, description="调整后的视图模式；null 表示不限")


# ===== 报告评审 Schema（review_report 使用） =====
class ReviewVerdict(BaseModel):
    """报告评审结论"""
    passed: bool = Field(description="报告是否通过评审")
    issues: list[str] = Field(default_factory=list, description="发现的问题列表")
    suggestion: str = Field(default="", description="针对性修改建议")


def _parse_plan_text(text: str) -> TaskPlan | None:
    """结构化输出失败时的文本解析兜底（兼容旧版 ```json 清洗逻辑）"""
    try:
        text = text.strip().removeprefix("```json").removesuffix("```").strip()
        data = json.loads(text)
        if not isinstance(data, list):
            data = data.get("plan") if isinstance(data, dict) else None
        if not isinstance(data, list):
            return None
        allowed = {"query_data", "analyze_gis", "retrieve_knowledge", "generate_report"}
        plan = [SubTaskPlan(task_type=d.get("task_type"), description=d.get("description", ""),
                            reason=d.get("reason", ""), required=bool(d.get("required", True)))
                for d in data if isinstance(d, dict) and d.get("task_type") in allowed]
        return TaskPlan(plan=plan)
    except Exception:
        return None


# ===== LangGraph 状态定义（并发安全：steps / knowledge_results 用 add reducer，节点只返回 delta） =====
class AgentState(TypedDict):
    """Agent 工作流状态"""
    user_query: str
    parsed_intent: dict
    data_results: dict
    gis_results: dict
    knowledge_results: Annotated[list, operator.add]
    report: str
    status: str
    steps: Annotated[list[dict], operator.add]
    error: str | None
    # P1：评审循环 + HITL 审批
    revisions: int            # 报告重写轮次（评审驳回计数）
    review_result: dict       # 最新评审结论 {passed, issues, suggestion, forced?}
    decision: str             # 审批决策 approve / edit / reject
    rejection_feedback: str   # 用户驳回意见（reject 时注入报告重写 prompt）


# ===== 流式复读循环 / 思考超限防护（需求 A）=====
# 阈值说明：思考段是可丢弃内容，判定从严（同句 4 次）；正文为交付物，判定放宽
# （同句 6 次）。两类文本都先做 Markdown 归一化（剥离列表序号/强调符号），
# 且结构行、标题行、短标签不参与句子计数，避免思考里的 Markdown 排版被误判复读。
_THINK_MAX_CHARS = 6000        # 思考累计字符上限（实测报告级思考 ~770 字，6000 已远超正常范围）
_THINK_MAX_SECONDS = 150.0     # 思考阶段时长上限（reasoning_effort=low 正常 ~40s）
_THINK_STORE_MAX_CHARS = 12000  # 步骤行 output.thinking 落库上限（保留尾部）
_PARTIAL_ADOPT_CHARS = 600     # 中断时正文达到该长度才采纳部分稿（与流式 error 路径一致）
_THINK_PERSIST_STEP_CHARS = 400  # 思考内容每累积该字符数落库一次（需求 B：运行中及时写步骤行）

# Markdown 归一化（只用于复读计数，不改变展示/落库原文）
_MD_PREFIX_RE = re.compile(r"^\s*(?:[-*+•]\s+|\d{1,3}[.)、．]\s*|>\s*|#{1,6}\s+)+")
_MD_INLINE_RE = re.compile(r"[*_`~]+")
_STRUCT_ONLY_RE = re.compile(r"^[=\-|`#>*~+_ \t0-9.、。！？；，,：:()（）\[\]【】]+$")
_SEMANTIC_RE = re.compile(r"[\u4e00-\u9fffA-Za-z]")
_STRUCT_CHARS = set("-=|`#>*~+_ \t\r\n0123456789.、。！？；，,：:()（）[]【】")


def _normalize_markdown_line(sent: str) -> str:
    """剥离 Markdown 列表序号/引用/标题前缀与强调符号，供复读计数比较"""
    s = _MD_PREFIX_RE.sub("", (sent or "").strip())
    s = _MD_INLINE_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_structural_or_title(raw: str, norm: str) -> bool:
    """结构行 / 章节标题 / 短标签行：不参与句子级复读计数"""
    s = (raw or "").strip()
    if not s:
        return True
    if s.startswith("#"):  # Markdown 标题
        return True
    if _STRUCT_ONLY_RE.match(norm or s):  # 表格分隔线/代码围栏/水平线/纯序号
        return True
    # 整行加粗的章节名（**二、数据来源与分析方法**）
    if re.fullmatch(r"\*\*[^*]+\*\*", s) and len(norm) <= 32:
        return True
    # 冒号结尾的短标题/标签（* **二、数据来源与分析方法**:）
    if norm.endswith(":") or norm.endswith("："):
        return True
    return False


# ===== 复读比较归一化 / 近似度（微变体重复检测）=====
# 强归一化：去 Markdown 前缀/强调符之外，再去掉全部标点、引号、空白——
# "等等，提示词说“X”。" 与 "等等，提示词说“Y”。" 的骨架即可对齐，引号内容微变体
# 靠字符 bigram Jaccard 判近似（截图 4.0k 字复读即此类，逐字计数完全失效）。
_DUP_STRIP_RE = re.compile(
    r"[\s，。！？；：、,.!?;:·\"'“”‘’「」『』（）()【】\[\]{}<>《》—\-–…•|\\/_~`^]+")


def _normalize_for_dup(sent: str) -> str:
    """复读比较用强归一化（只用于检测，不改变展示/落库原文）"""
    return _DUP_STRIP_RE.sub("", _normalize_markdown_line(sent))


def _bigram_jaccard(a: str, b: str) -> float:
    """字符 bigram Jaccard 相似度（0~1）；短串按单字集合退化"""
    A = {a[i:i + 2] for i in range(len(a) - 1)} or ({a} if a else set())
    B = {b[i:i + 2] for i in range(len(b) - 1)} or ({b} if b else set())
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _fragment_long_sentence(raw: str) -> list:
    """超长句按 逗号/顿号 切成 ≥12 字片段（比较粒度）；不超长则整句返回"""
    s = (raw or "").strip()
    if len(_normalize_for_dup(s)) <= 60:
        return [s]
    frags, buf = [], ""
    for part in re.split(r"[，、,]", s):
        cand = f"{buf}，{part}" if buf else part
        if len(_normalize_for_dup(cand)) >= 12:
            frags.append(cand)
            buf = ""
        else:
            buf = cand
    if buf.strip():
        frags.append(buf)
    return frags or [s]


class _StreamLoopGuard:
    """流式复读循环检测器 v2（逐字 + 近似微变体簇 + 后缀块 + 多窗口确认）

    - 句子级：按 。！？；\\n 切句，超长句再按 ，、 切成 12~60 字片段，强归一化后：
      a) 逐字计数：同一句重复 ≥repeat_threshold 次；
      b) 近似簇：与最近 near_window(12) 句内 ≥near_threshold(0.72) 相似
         （且长度 ≥min_sent_chars）的句子，簇内出现 ≥near_cluster(3) 次
         ——微变体复读（换引号内容/换说法）由此捕获；
      c) 连续相似：与前一句相似度 ≥0.85（背靠背微变体）；
    - 结构行/标题行/短标签行不参与（见 _is_structural_or_title）；不同州市等
      "结构相同、内容不同"的数据行相似度低于 0.72 且不成簇，不误判；
    - 后缀级：≥10 字块在尾部无间隔重复 ≥3 次（含语义字符）、4~24 字块重复 ≥4 次、
      单一语义字符连刷 ≥16 次；
    - 多窗口确认：疑似复读需连续 confirm_windows 个 feed 窗口命中才中断；
    - cut_offset：命中时给出重复起始偏移（句子边界），调用方据此把思考
      截断到重复开始前，丢弃重复尾巴。
    feed() 返回 True 即应中断本轮思考（调用方发起下一轮或降级收尾）。
    """

    _BOUNDARY = "。！？；;\n"
    _SENT_RE = re.compile(r"[^。！？；;\n]+")

    def __init__(self, repeat_threshold: int = 4, min_sent_chars: int = 12,
                 min_total: int = 48, confirm_windows: int = 2,
                 near_threshold: float = 0.72, near_window: int = 12,
                 near_cluster: int = 3, consecutive_threshold: float = 0.85):
        self._pending = ""    # 未跨过句读边界的尾巴（跨 chunk 成句后再计数）
        self._counts: dict[str, int] = {}
        self._spans: list[tuple[int, str]] = []  # 最近完成句 (起始偏移, 强归一化)
        self._recent = ""     # 原始文本尾窗（后缀重复检测用，不切成句）
        self.total = 0
        self.repeat_threshold = repeat_threshold
        self.min_sent_chars = min_sent_chars
        self.min_total = min_total
        self.confirm_windows = max(1, int(confirm_windows))
        self.near_threshold = near_threshold
        self.near_window = near_window
        self.near_cluster = near_cluster
        self.consecutive_threshold = consecutive_threshold
        self._suspect_streak = 0
        self.cut_offset = None  # 命中时的重复起始偏移（句子边界）

    def feed(self, text: str) -> bool:
        """喂入增量；返回 True 表示判定为复读循环，应中断本轮思考"""
        if not text:
            return False
        self.total += len(text)
        self._recent = (self._recent + text)[-256:]
        suspect = False
        checked = False
        if self._suffix_repeat(self._recent):
            suspect = checked = True
        self._pending += text
        last = -1
        for ch in self._BOUNDARY:
            idx = self._pending.rfind(ch)
            if idx > last:
                last = idx
        if last >= 0:
            complete = self._pending[:last + 1]
            off = self.total - len(self._pending)  # complete 段在全文中的起点
            self._pending = self._pending[last + 1:]
            checked = True
            hit = False
            for m in self._SENT_RE.finditer(complete):
                if self._check_sentence(m.group(), off + m.start()):
                    hit = True
            if hit:
                suspect = True
        # 没有新完成句/后缀命中时不重置确认计数：复读可能跨 chunk 持续
        if not checked:
            return False
        if suspect:
            self._suspect_streak += 1
        else:
            self._suspect_streak = 0
        # min_total 只门控判定结论，不阻断计数累积（开头短句也要进统计，防漏判）
        return self._suspect_streak >= self.confirm_windows and self.total >= self.min_total

    def _check_sentence(self, raw: str, offset: int) -> bool:
        raw = (raw or "").strip()
        if not raw:
            return False
        if _is_structural_or_title(raw, _normalize_markdown_line(raw)):
            return False
        hit = False
        for frag in _fragment_long_sentence(raw):
            if self._check_fragment(frag, offset):
                hit = True
        return hit

    def _check_fragment(self, raw: str, offset: int) -> bool:
        norm = _normalize_for_dup(raw)
        if not norm or len(norm) < self.min_sent_chars:
            return False
        if not _SEMANTIC_RE.search(norm):  # 纯数字/符号/表格片不计数
            return False
        # a) 逐字重复计数
        n = self._counts.get(norm, 0) + 1
        self._counts[norm] = n
        # b/c) 近似簇 + 连续相似（先取窗口，再入列）
        window = self._spans[-self.near_window:]
        near = [(o, s) for (o, s) in window
                if s == norm or _bigram_jaccard(norm, s) >= self.near_threshold]
        prev_off, prev_norm = (window[-1] if window else (offset, ""))
        sim_prev = _bigram_jaccard(norm, prev_norm) if prev_norm else 0.0
        self._spans.append((offset, norm))
        if len(self._spans) > self.near_window:
            self._spans.pop(0)
        if n >= self.repeat_threshold:  # a) 逐字：截到第二次出现（首次是原创内容）
            occurs = [o for (o, s) in self._spans if s == norm]
            self.cut_offset = occurs[1] if len(occurs) >= 2 else (occurs[0] if occurs else offset)
            return True
        if len(near) >= self.near_cluster - 1:  # b) 此前簇员 ≥2 + 当前 = 簇内 ≥3 次
            near_sorted = sorted(near)  # 按偏移排序：第二次出现 = 重复开始处
            self.cut_offset = near_sorted[1][0] if len(near_sorted) >= 2 else near_sorted[0][0]
            return True
        if sim_prev >= self.consecutive_threshold:  # c) 背靠背高度相似
            self.cut_offset = prev_off
            return True
        return False

    @classmethod
    def _suffix_repeat(cls, recent: str) -> bool:
        n = len(recent)
        if n < 16:
            return False
        tail = recent[-16:]
        if len(set(tail)) == 1:  # 单字符连续刷屏（≥16 个相同语义字符）
            ch = tail[0]
            if ch not in _STRUCT_CHARS and _SEMANTIC_RE.match(ch):
                return True
        for p in range(4, 25):           # 短语块（≥4 字）无间隔连续重复 ≥4 次
            if n < p * 4:
                break
            block = recent[-p:]
            if len(_SEMANTIC_RE.findall(block)) < 3:
                continue  # 结构符号/数字为主的块（表格行、分隔线）不触发
            if recent[n - p * 4:] == block * 4:
                return True
        for p in range(10, 14):          # ≥10 字块（含语义字符）在尾部重复 ≥3 次
            if n < p * 3:
                break
            block = recent[-p:]
            if len(_SEMANTIC_RE.findall(block)) < 4:
                continue
            if recent[n - p * 3:] == block * 3:
                return True
        return False


def _load_step_payload(db_session, task_id: int) -> dict:
    """读取 generate_report 步骤行 output（查询不按 status 过滤：取消后行可能已置 skipped）"""
    if db_session is None or task_id is None:
        return {}
    try:
        from app.models.task import AgentTaskStep
        row = (
            db_session.query(AgentTaskStep)
            .filter(AgentTaskStep.task_id == task_id,
                    AgentTaskStep.step_name == "generate_report")
            .first()
        )
        return dict(row.output_payload or {}) if row is not None else {}
    except Exception:
        return {}


def _normalize_thinking_rounds(payload: dict) -> list[dict]:
    """兼容旧字段的轮次归一化：thinking_rounds 优先，旧 thinking 视为第 1 轮"""
    rounds = payload.get("thinking_rounds")
    out: list[dict] = []
    if isinstance(rounds, list):
        for i, r in enumerate(rounds):
            if isinstance(r, str) and r.strip():
                out.append({"round": i + 1, "text": r})
            elif isinstance(r, dict) and str(r.get("text") or "").strip():
                try:
                    no = int(r.get("round") or i + 1)
                except Exception:
                    no = i + 1
                item = {"round": no, "text": str(r.get("text"))}
                if r.get("note"):
                    item["note"] = str(r.get("note"))
                out.append(item)
    if not out:
        old = payload.get("thinking")
        if isinstance(old, str) and old.strip():
            out = [{"round": 1, "text": old}]
    out.sort(key=lambda x: x["round"])
    return out


def _join_thinking_rounds(rounds: list[dict]) -> str:
    """轮次原文拼接（不含「第 N 轮」标签；标签由前端展示层补，避免反复改动落库格式）"""
    return "\n\n".join(str(r.get("text") or "").strip()
                       for r in rounds if str(r.get("text") or "").strip())


def _upsert_thinking_round(rounds: list[dict], run, text: str, note: str = "") -> list[dict]:
    """按轮次号写入/更新思考文本（同轮覆盖为最新全量，重写轮追加为新条目）"""
    text = str(text or "")
    if not text.strip():
        return rounds
    try:
        round_no = int(run) if run else (rounds[-1]["round"] if rounds else 1)
    except Exception:
        round_no = rounds[-1]["round"] if rounds else 1
    for item in rounds:
        if item.get("round") == round_no:
            item["text"] = text
            if note:
                item["note"] = str(note)
            break
    else:
        item = {"round": round_no, "text": text}
        if note:
            item["note"] = str(note)
        rounds.append(item)
    rounds.sort(key=lambda x: x["round"])
    return rounds


def _persist_step_thinking(db_session, task_id: int, thinking: str,
                           run=None, note: str = "") -> None:
    """把当前轮思考写入 generate_report 步骤行（需求 B：运行中及时落库）

    节点尚未结束时也要能看到已产生的思考（取消/断线/刷新后回看）。
    output.thinking 保留为全部轮次拼接（向后兼容旧读法），新增
    output.thinking_rounds = [{round, text, note?}] 供前端按轮次合并展示。
    任何失败静默回滚，不阻断生成主流程（思考是附属产物，不值得为之冒险）。
    """
    if db_session is None or task_id is None:
        return
    try:
        from app.models.task import AgentTaskStep
        row = (
            db_session.query(AgentTaskStep)
            .filter(AgentTaskStep.task_id == task_id,
                    AgentTaskStep.step_name == "generate_report")
            .first()
        )
        if row is None:
            return
        payload = dict(row.output_payload or {})
        rounds = _normalize_thinking_rounds(payload)
        rounds = _upsert_thinking_round(rounds, run, thinking, note)
        payload["thinking_rounds"] = rounds
        payload["thinking"] = _join_thinking_rounds(rounds)[-_THINK_STORE_MAX_CHARS:]
        row.output_payload = payload
        db_session.commit()
    except Exception:
        try:
            db_session.rollback()
        except Exception:
            pass


def _finalize_step_thinking(db_session, task_id: int, round_text: str,
                            run, note: str = "") -> tuple[str, list[dict]]:
    """节点收尾：把本轮完整思考并入历史轮次，返回 (全量 thinking, thinking_rounds)"""
    payload = _load_step_payload(db_session, task_id)
    rounds = _normalize_thinking_rounds(payload)
    if round_text or note:
        rounds = _upsert_thinking_round(rounds, run, round_text, note)
    return _join_thinking_rounds(rounds)[-_THINK_STORE_MAX_CHARS:], rounds


def _loopbreak_prompt(base_prompt: str, prev_tail: str) -> str:
    """第二轮思考提示词：注入第一轮截断摘要，禁止复述任务设定/推理，直接推进到正文"""
    tail = (prev_tail or "").strip()[-800:]
    return (base_prompt
            + "\n\n## 上一轮推理摘要（已因原地重复被系统截断，禁止复述）\n"
            + "你上一轮的推理陷入原地重复。以下是其结尾要点，仅供衔接参考：\n"
            + "<prev_reasoning>\n" + tail + "\n</prev_reasoning>\n"
            + "硬性要求：1) 禁止再次复述或换说法重复上述推理，也不要复述任务设定、"
            + "角色、数据构成等背景信息；2) 直接基于已确认的结论推进：立即开始撰写"
            + "报告正文（Markdown），不要再输出大段推理过程。")


def _stream_report(prompt: str, task_id: int, db_session=None, should_cancel=None,
                   max_think_rounds: int = 2):
    """P2#18：流式生成报告（增量经 report_channels 实时推送 SSE），含两轮思考重试。

    思考型模型（qwen3 / DeepSeek 系）的 <think> 段用 _ThinkFilter 流式拆分：
    思考增量经 report_think 帧推送（前端「深度思考中」面板），只有干净正文
    进入 report_delta / 终态报告（DB 不落思考内容）。

    防护与轮次（任一防护触发即中断当前流，任务不卡 running）：
    - 复读循环：思考段 / 正文段分别经 _StreamLoopGuard 检测（逐字 + 近似微变体）；
      思考命中 → 截断到重复前的句子边界、以 note=think_loop 落库该轮、推 think_reset
      帧（前端丢弃重复尾巴）→ **立即发起第二轮**（run+1，提示词注入截断摘要并禁止
      复述）；第二轮再命中 → 截断后直接进入正文（不得无限重试，最多 max_think_rounds 轮）；
    - 思考超限（think_limit）：与复读同样推进第二轮；
    - 用户取消：should_cancel() 为 True 时立即停止（不丢弃已累积思考，不重试）。
    思考内容每累积 _THINK_PERSIST_STEP_CHARS 字符经 _persist_step_thinking 落库。

    返回 (LLMResult | None, 各轮思考文本列表, 中断原因, 最终轮次 run)：
    - think_rounds[k] 为第 k+1 轮思考（命中轮已截断，前几轮已带 note 落库，
      最后一轮由调用方 _finalize_step_thinking 并入 thinking_rounds）；
    - LLMResult 非 None：流式产物（含中断时的部分稿，degraded=True）；
    - None：流式失败/中断且正文不足，调用方走非流式或模板兜底（已取消时调用方
      应跳过非流式重试直接走模板，见 generate_report 节点）。
    通道易失：无订阅者时 push 为 no-op，worker 不受影响；半截内容不落库，
    终态完整报告仍由节点返回值落库（DB 唯一事实源）。
    """
    from app.core import report_channels
    base_prompt = prompt
    run = report_channels.begin_generation(task_id)  # 重写轮次递增，前端据此清缓冲
    result = None
    stop_reason = ""
    first_loop_note = ""
    think_rounds: list[str] = []
    for round_no in range(1, max_think_rounds + 1):
        round_prompt = base_prompt if round_no == 1 else _loopbreak_prompt(
            base_prompt, think_rounds[-1] if think_rounds else "")
        # 第二轮预算放宽一倍（12k/180s）：给自然推理留足空间，只有真复读才截断
        budget = (6000, 150.0) if round_no == 1 else (12000, 180.0)
        result, round_text, reason, run = _stream_report_once(
            round_prompt, task_id, db_session, should_cancel, run,
            think_max_chars=budget[0], think_max_seconds=budget[1])
        think_rounds.append(round_text)
        if reason:
            stop_reason = reason
            first_loop_note = first_loop_note or reason
        if reason in ("think_loop", "think_limit") and round_no < max_think_rounds:
            # 命中复读/超限：本轮已截断落库（note）+ 推 think_reset；
            # run+1 发起第二轮（摘要注入提示词，禁止复述，直接推进）
            run = report_channels.begin_generation(task_id)
            continue
        break
    return result, think_rounds, (first_loop_note or stop_reason), run


def _truncate_to_sentence(text: str, min_keep: int = 60) -> str:
    """截断到最后一个完整句读边界（think_limit 等无 guard 偏移时的安全截断）；
    保留长度不足 min_keep 时不截，避免把推理截成半句"""
    if not text:
        return text
    for i in range(len(text) - 1, min_keep - 1, -1):
        if text[i] in "。！？；;\n":
            return text[:i + 1]
    return text


def _stream_report_once(prompt: str, task_id: int, db_session=None, should_cancel=None,
                        run: int = 0, think_max_chars: int = 6000,
                        think_max_seconds: float = 150.0):
    """单轮流式生成（由 _stream_report 按轮调用）。

    思考命中复读/超限时：截断到重复前/最后完整句子边界 → note 落库 → 推 think_reset
    帧（前端丢弃重复尾巴）。复读轮不采纳正文部分稿（正文交给下一轮或非流式兜底）；
    think_limit 轮按句界截断思考后仍采纳足量正文部分稿（自然推理不在句中断开）。
    返回 (LLMResult | None, 本轮思考文本(命中轮为截断版), 中断原因, 轮次 run)。
    """
    from app.core import report_channels
    from app.services.rag_service import _ThinkFilter
    think = _ThinkFilter()
    buf: list[str] = []
    think_buf: list[str] = []
    think_chars = 0
    think_started: float | None = None
    persisted_len = 0
    stop_reason = ""
    # 正文/思考分别设定阈值与最小句长；思考 Markdown 更密，最小句长放宽到 12
    think_guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    content_guard = _StreamLoopGuard(repeat_threshold=6, min_sent_chars=12, confirm_windows=2)
    result = None

    def _flush_thinking(force: bool = False, note: str = "") -> None:
        nonlocal persisted_len
        text = "".join(think_buf)
        if not force and len(text) - persisted_len < _THINK_PERSIST_STEP_CHARS:
            return
        _persist_step_thinking(db_session, task_id, text, run=run, note=note)
        persisted_len = len(text)

    def _finish_partial(reason: str) -> None:
        """中断收尾：思考先落库；正文足量则采纳部分稿（degraded），否则交兜底"""
        nonlocal result, stop_reason
        stop_reason = reason
        _flush_thinking(force=True, note=reason)
        text = "".join(buf)
        if len(text) >= _PARTIAL_ADOPT_CHARS:
            result = LLMResult(text=text, provider="", tokens={}, degraded=True, model="")

    def _finish_think_round(reason: str, adopt_body: bool) -> None:
        """思考轮次命中复读/超限：截断到句子边界（guard 偏移优先，think_limit 回落
        到最后句界）→ note 落库 → 推 think_reset。adopt_body=True（think_limit/
        第二轮兜底）时正文足量仍采纳部分稿；复读轮不采纳（正文由下一轮重生成）。"""
        nonlocal stop_reason, persisted_len, result
        stop_reason = reason
        full = "".join(think_buf)
        cut = think_guard.cut_offset
        if isinstance(cut, int) and 60 <= cut < len(full):
            truncated = full[:cut]
        elif reason == "think_limit":
            truncated = _truncate_to_sentence(full)  # 自然推理只在句界截断
        else:
            truncated = full
        _persist_step_thinking(db_session, task_id, truncated, run=run, note=reason)
        persisted_len = len(truncated)
        think_buf.clear()
        think_buf.append(truncated)  # 返回值/后续 flush 以截断版为准（不丢重复前内容）
        report_channels.push_think_reset(task_id, run, truncated)
        if adopt_body:
            text = "".join(buf)
            if len(text) >= _PARTIAL_ADOPT_CHARS:
                result = LLMResult(text=text, provider="", tokens={}, degraded=True, model="")

    try:
        # enable_thinking=True：开启思考型模型推理，思考增量实时推前端「深度思考中」面板；
        # reasoning_effort=low 限思（实测报告级 ~40s；缺省思考首字延迟可达 100s+）；
        # max_tokens 留足思考+正文预算，防思考吃满额度正文为空
        for chunk in stream_llm(prompt, temperature=0.4, max_tokens=4800,
                                enable_thinking=True, reasoning_effort="low"):
            ctype = chunk.get("type")
            if should_cancel is not None and should_cancel():
                _finish_partial("cancelled")
                break
            if ctype == "think":
                # 思考型模型 reasoning 字段增量（AMD/vLLM 端点）：直接推前端「深度思考中」面板
                t = chunk.get("text", "")
                if t:
                    if think_started is None:
                        think_started = time.monotonic()
                    think_buf.append(t)
                    think_chars += len(t)
                    report_channels.push_think(task_id, run, t)
                    _flush_thinking()
                    if think_guard.feed(t):
                        # 真复读：第一轮截断并立即发起第二轮；第二轮截断后采纳正文/兜底
                        _finish_think_round("think_loop", adopt_body=bool(buf))
                        break
                    if (not buf and (think_chars > think_max_chars
                                     or time.monotonic() - think_started > think_max_seconds)):
                        # 字数/时长上限：句界截断，正文足量则采纳（不无限重试）
                        _finish_think_round("think_limit", adopt_body=True)
                        break
            elif ctype == "delta":
                clean = think.feed(chunk.get("text", ""))
                think_delta = think.take_think_delta()
                if think_delta:
                    think_buf.append(think_delta)
                    think_chars += len(think_delta)
                    report_channels.push_think(task_id, run, think_delta)
                    _flush_thinking()
                    if think_guard.feed(think_delta):
                        _finish_think_round("think_loop")
                        break
                if clean:
                    buf.append(clean)
                    report_channels.push_delta(task_id, run, clean)
                    if content_guard.feed(clean):
                        _finish_partial("content_loop")
                        break
            elif ctype == "meta":
                # 全程 0 字符的"成功"（如思考型模型 token 全花在 reasoning、content 为空）
                # 视为失败：result 置 None，让调用方走非流式/模板兜底，避免落库空报告
                if buf:
                    result = LLMResult(text="".join(buf), provider=chunk.get("provider", ""),
                                       tokens=chunk.get("tokens") or {},
                                       degraded=bool(chunk.get("degraded")),
                                       model=chunk.get("model", ""))
                _flush_thinking(force=True)
                break
            elif ctype == "error":
                # 流式超时/中断：已有足量正文（≥600 字符）时直接采纳部分稿，
                # 避免非流式兜底再从头生成一遍（慢模型下又是 1-2 分钟）
                if len("".join(buf)) >= _PARTIAL_ADOPT_CHARS:
                    result = LLMResult(text="".join(buf), provider="", tokens={},
                                       degraded=True, model="")
                _flush_thinking(force=True)
                break
        if result is not None:
            tail = think.finish()  # 吐出扣留的疑似标签尾巴（不完整 <think> 中断场景）
            if tail:
                buf.append(tail)
                report_channels.push_delta(task_id, run, tail)
                result = LLMResult(text="".join(buf), provider=result.provider,
                                   tokens=result.tokens, degraded=result.degraded,
                                   model=result.model)
    except Exception:
        _flush_thinking(force=True)
        result = None
    return result, "".join(think_buf), stop_reason, run


# ===== 节点工厂（注入 db session 依赖） =====

def _make_nodes(db_session, user_id=None, is_admin=False, task_id=None, cancel_checker=None):
    """构造依赖 db 的节点函数（闭包），使 LangGraph 节点能访问数据库

    cancel_checker：可选的取消探测回调（路由层注入 _is_cancel_requested），
    生成报告流式循环内逐 chunk 检查，取消时立即中断并保留已有思考/正文。
    """
    from app.repositories.fire_repository import FireRepository
    from app.agents.gis_agent import GisAgent
    from app.services.rag_service import RagService

    fire_repo = FireRepository(db_session)
    gis_agent = GisAgent()
    # W1 chaos 挂接已下线（原 _chaos_wrap 包装代码已注释，见文件头部说明）
    rag_service = RagService(db_session)

    # ---------- 节点1：解析用户任务（结构化输出 plan，驱动条件路由） ----------
    def parse_task(state: AgentState) -> dict:
        query = state["user_query"]

        default_plan = [
            {"task_type": "query_data", "description": f"查询「{query}」相关的历史火点与预测火险双数据源",
             "reason": "数据分析类任务默认需要真实数据", "required": True},
            {"task_type": "retrieve_knowledge", "description": "检索知识库（防火规范/应急预案等文档）",
             "reason": "知识库参考固定检索", "required": True},
            {"task_type": "generate_report", "description": "基于数据生成分析报告",
             "reason": "默认输出分析报告", "required": True},
        ]
        if llm_available():
            prompt = f"""你是一个森林火险分析任务编排助手。系统对任何需求都会固定执行：
双数据源查询(query_data) → 空间分析(analyze_gis) → 知识库检索(retrieve_knowledge) → 生成分析报告(generate_report)，
四个步骤全部固定执行（知识库检索即使未命中也会如实说明）。你只需为各步骤生成贴合用户需求的描述。

用户需求：{query}

子任务类型：
- query_data: 查询历史火点(2021-2025)+预测火险(2025-2026)双数据源（固定执行，必须列出）
- analyze_gis: 空间分析（网格聚类+高风险识别，固定执行，必须列出）
- retrieve_knowledge: 检索知识库（防火规范/应急预案等文档，固定执行，必须列出）
- generate_report: 生成分析报告（固定执行，必须列出）

请输出 JSON 对象：{{"plan": [{{"task_type": "...", "description": "...", "required": true}}, ...]}}
仅输出 JSON，不要其他文字。"""
            try:
                # P2#17 轻量化：意图解析输出为小体积 JSON，限 max_tokens 缩短首事件前的静默窗口
                plan_obj, meta = invoke_structured(prompt, TaskPlan, temperature=0.1, max_tokens=300,
                                                   fallback=_parse_plan_text)
                if plan_obj is not None and plan_obj.plan:
                    plan = [s.model_dump() for s in plan_obj.plan]
                else:
                    plan = default_plan
                # 审计信息：实际使用的 Provider / 模型 / 降级 / token
                audit = {}
                if meta is not None:
                    audit = {"llm_provider": meta.provider, "llm_model": meta.model,
                             "llm_degraded": meta.degraded}
                    if meta.tokens:
                        audit["tokens"] = meta.tokens
            except Exception:
                plan = default_plan
                audit = {}
        else:
            # 无 LLM 时生成默认计划
            plan = default_plan
            audit = {}

        # 计划归一化（硬约束，防 LLM 漏规划导致任务跑完无报告）：
        # query_data / analyze_gis / retrieve_knowledge / generate_report 全部固定执行——
        # 知识库检索不再按计划跳过（用户要求：即使未命中也要如实说明检索结果），
        # LLM 计划仅用于补充各步骤的描述文案
        kb_desc = next((s.get("description", "") for s in plan
                        if s.get("task_type") == "retrieve_knowledge"), "")
        plan = [
            {"task_type": "query_data", "required": True,
             "description": f"查询「{query}」相关的历史火点(2021-2025)与预测火险(2025-2026)双数据源",
             "reason": "双数据源查询为固定步骤"},
            {"task_type": "analyze_gis", "required": True,
             "description": "对查询结果做空间分析（历史0.1°网格聚类+预测高风险识别）",
             "reason": "有数据即执行空间分析"},
            {"task_type": "retrieve_knowledge", "required": True,
             "description": kb_desc or "检索知识库（防火规范/应急预案等文档）",
             "reason": "知识库参考固定检索，未命中时如实说明"},
        ]
        plan.append({"task_type": "generate_report", "required": True,
                     "description": "汇总数据/空间分析/知识检索结果，生成分析报告",
                     "reason": "分析报告为系统固定产出"})

        # 摘要说清楚"计划了哪几步、每步干什么"（用户要求：有描述，而非只给步数）
        _step_labels = {"query_data": "数据查询", "analyze_gis": "空间分析",
                        "retrieve_knowledge": "知识检索", "generate_report": "生成报告"}
        plan_txt = " → ".join(_step_labels.get(s.get("task_type"), s.get("task_type") or "?") for s in plan)
        # 熔断器快照透出（重试/熔断可见化：parse_task 偶发慢时可在步骤行看到各 Provider
        # 的失败计数与冷却剩余，而不是"看起来卡死"）；无 LLM 时不带
        try:
            from app.core.llm_invoker import breaker_status
            breaker_snap = breaker_status()
        except Exception:
            breaker_snap = {}
        step = {"step": "parse_task", "agent": "Orchestrator", "input": query,
                "output": {"plan": plan, **audit,
                           **({"llm_breaker": breaker_snap} if breaker_snap else {})},
                "status": "completed",
                "summary": (f"已理解任务并规划 {len(plan)} 步：{plan_txt}。"
                            "先查历史火点(2021-2025)与预测火险双数据源，再做热点空间聚类定位高风险区域，"
                            "同时检索防火规范/预案作为依据，最后汇总生成正式分析报告")}
        return {"parsed_intent": {"plan": plan}, "steps": [step], "status": "parsed"}

    # ---------- 节点2：数据查询（双源 + 空结果反思重试，与 retrieve_knowledge 并行执行） ----------
    def _parse_query_params(query: str):
        """从查询文本提取年/月/城市/视图模式（初始参数）"""
        import re
        years = re.findall(r"(20\d{2})", query)
        month_m = re.search(r"(\d{1,2})月", query)
        month = int(month_m.group(1)) if month_m and 1 <= int(month_m.group(1)) <= 12 else None
        city = None
        from app.services.query_service import CITIES, SHORT_CITY_MAP
        for c in CITIES:
            if c in query:
                city = c
                break
        if not city:
            for short, full in SHORT_CITY_MAP.items():
                if short in query:
                    city = full
                    break
        year = int(years[0]) if len(years) == 1 else None
        view_mode = "daily" if any(k in query for k in ("逐日", "每日", "日报", "当天")) else "monthly"
        return year, month, city, view_mode

    def _run_dual_query(year, month, city, view_mode):
        """执行历史火点 + 预测火险双表查询（硬约束：只要查数必须双源）"""
        from app.schemas.dashboard import HistoryFireQuery, PredictRiskQuery
        from app.services.query_service import CITY_CENTERS

        # 1) 历史火点（historical_fire_points 表，覆盖 2021-2025）
        hq = HistoryFireQuery(
            start_date=f"{year}-01-01" if year else None,
            end_date=f"{year}-12-31" if year else None,
            city=city,
            page_size=5000,
        )
        hist = fire_repo.query_history_fires(hq)
        hist_items = []
        for it in hist.get("items", []):
            it = dict(it)
            it["source"] = "historical"
            hist_items.append(it)

        # 2) 预测火险（predicted_fire_risks 表，覆盖 2025-2026）
        pq = PredictRiskQuery(
            year=year if year and 2025 <= year <= 2026 else None,
            month=month if view_mode == "monthly" else None,
            view_mode=view_mode,
            city=city,
        )
        pred = fire_repo.query_predict_risks(pq)
        pred_items = []
        for it in pred.get("items", []):
            lng, lat = it.get("longitude"), it.get("latitude")
            if lng is None or lat is None:
                center = CITY_CENTERS.get(it.get("city"))
                if center:
                    lng, lat = center
            day = it.get("day")
            date_str = f"{it.get('year')}-{it.get('month'):02d}" + (f"-{day:02d}" if day else "")
            pred_items.append({
                "id": it.get("id"),
                "acq_date": date_str,
                "frp": it.get("pred_fire_risk") or it.get("pred_fire_count") or it.get("final_fire_index") or 0,
                "longitude": lng,
                "latitude": lat,
                "city": it.get("city"),
                "risk_score": it.get("risk_score"),
                "fire_level": it.get("fire_level"),
                "source": "predicted",
            })

        hist_total = hist.get("total", 0)
        pred_total = len(pred_items)
        data = {
            "status": "queried",
            "total": hist_total + pred_total,
            "hist_total": hist_total,
            "pred_total": pred_total,
            "items": hist_items + pred_items,
            "data_type": f"历史火点({hist_total})+预测火险({pred_total})",
        }
        return data, view_mode

    # W1 chaos 挂接已下线：双源查询不再包装（原 _chaos_wrap("query_fire_data", ...) 已注释）

    def _reflect_and_adjust(query, year, city, view_mode, tried):
        """LLM 反思：查询为空时建议放宽参数；返回 (year, city, view_mode) 或 None"""
        prompt = f"""森林火险数据查询结果为空，请分析原因并建议放宽后的查询参数。

用户需求：{query}
已尝试参数：{json.dumps(tried, ensure_ascii=False)}

数据范围说明：历史火点覆盖 2021-2025 年；预测火险覆盖 2025-2026 年。
请输出 JSON（null 表示该项不限/放宽）：
{{"reason": "无数据的可能原因", "adjusted_year": null, "adjusted_month": null,
  "adjusted_city": null, "adjusted_view_mode": "daily 或 monthly 或 null"}}
仅输出 JSON。"""
        try:
            adj, _meta = invoke_structured(prompt, QueryRetryPlan, temperature=0.2)
            if adj is None:
                return None
            new_year = adj.adjusted_year if adj.adjusted_year else None
            new_month = adj.adjusted_month if adj.adjusted_month else None
            new_city = adj.adjusted_city if adj.adjusted_city else None
            new_view = adj.adjusted_view_mode if adj.adjusted_view_mode else view_mode
            return new_year, new_month, new_city, new_view
        except Exception:
            return None

    def query_data(state: AgentState) -> dict:
        query = state["user_query"]
        year, month, city, view_mode = _parse_query_params(query)

        data = {"status": "no_data", "total": 0, "items": []}
        tried = []
        empty_reason = ""
        summary = ""
        for attempt in range(3):  # 初次查询 + 最多 2 轮反思重试
            try:
                data, view_mode = _run_dual_query(year, month, city, view_mode)
            except Exception as e:
                data = {"status": "error", "total": 0, "items": [], "error": str(e)}
                summary = f"DataAgent 查询失败: {str(e)[:50]}"
                break
            total = data.get("total", 0)
            tried.append({"year": year, "month": month, "city": city,
                          "view_mode": view_mode, "total": total})
            if total > 0:
                hist_total = data.get("hist_total", 0)
                pred_total = data.get("pred_total", 0)
                # 火点最集中的州市（数据画像，供流水线摘要与报告呼应）
                _city_counter = {}
                for _it in (data.get("items") or []):
                    _c = str(_it.get("city") or "").strip()
                    if _c:
                        _city_counter[_c] = _city_counter.get(_c, 0) + 1
                _top_city, _top_n = (max(_city_counter.items(), key=lambda kv: kv[1])
                                     if _city_counter else ("—", 0))
                summary = (f"DataAgent 查询到 {hist_total} 条历史火点（2021-2025 卫星存档）"
                           f" + {pred_total} 条{view_mode}预测火险（2025-2026 模型预测），共 {total} 条；"
                           f"其中{_top_city}数据量最大（{_top_n} 条），将作为空间分析与报告的重点区域")
                break
            if attempt >= 2 or not llm_available():
                empty_reason = ("条件范围内无数据（含放宽重试）" if attempt > 0 else "条件范围内无数据")
                summary = f"DataAgent 未查询到数据（尝试 {len(tried)} 组参数）：{empty_reason}"
                break
            adjusted = _reflect_and_adjust(query, year, city, view_mode, tried)
            if adjusted is None:
                empty_reason = "LLM 反思不可用，无法调整查询参数"
                summary = f"DataAgent 未查询到数据（尝试 {len(tried)} 组参数）"
                break
            year, month, city, view_mode = adjusted

        output = {"total": data.get("total", 0),
                  "first_city": (data.get("items") or [{}])[0].get("city") if data.get("items") else None}
        if data.get("error"):
            output["error"] = data["error"]  # 查询失败原因透传进轨迹
        # AgentGauntlet 工具夹带透传（_gauntlet_note）已随 chaos 下线一并注释
        if tried:
            output["attempts"] = tried
        if empty_reason:
            output["empty_reason"] = empty_reason
        step = {"step": "query_data", "agent": "DataAgent", "input": query,
                "output": output, "status": "completed", "summary": summary}
        return {"data_results": data, "steps": [step]}

    # ---------- 节点3：GIS 分析（历史火点网格聚类 + 预测数据高风险识别；计划未含或无数据时 no-op 跳过） ----------
    def analyze_gis(state: AgentState) -> dict:
        plan_types = {p.get("task_type") for p in (state.get("parsed_intent", {}).get("plan") or [])}
        data = state.get("data_results", {}) or {}

        if "analyze_gis" not in plan_types:
            step = {"step": "analyze_gis", "agent": "GisAgent",
                    "input": state["user_query"], "output": {"skipped": True, "reason": "计划未包含 GIS 分析"},
                    "status": "skipped", "summary": "计划未包含 GIS 分析，已跳过"}
            return {"gis_results": {"status": "skipped", "hotspots": [], "summary": "已跳过"}, "steps": [step]}
        if not data.get("items"):
            step = {"step": "analyze_gis", "agent": "GisAgent",
                    "input": state["user_query"], "output": {"skipped": True, "reason": "无数据可供空间分析"},
                    "status": "skipped", "summary": "无数据可供空间分析，已跳过"}
            return {"gis_results": {"status": "no_data", "hotspots": [], "summary": "无数据"}, "steps": [step]}

        gis = {"status": "no_data", "hotspots": [], "summary": "无数据"}
        try:
            items = data.get("items", []) or []
            hist_items = [i for i in items if i.get("source") != "predicted"]
            pred_items = [i for i in items if i.get("source") == "predicted"]
            hotspots = []
            hist_count = pred_count = 0
            if hist_items:
                h = asyncio_run(gis_agent.analyze_hotspots({"items": hist_items}))
                for x in h.get("hotspots", []):
                    x["kind"] = "历史聚类"
                hist_count = h.get("total_hotspots", 0)
                hotspots.extend(h.get("hotspots", []))
            if pred_items:
                p = asyncio_run(gis_agent.analyze_predicted({"items": pred_items}))
                for x in p.get("hotspots", []):
                    x["kind"] = "预测高风险"
                pred_count = p.get("total_hotspots", 0)
                hotspots.extend(p.get("hotspots", []))
            gis = {
                "status": "analyzed",
                "hotspots": hotspots[:40],
                "total_hotspots": hist_count + pred_count,
                "hist_hotspots": hist_count,
                "pred_hotspots": pred_count,
                "summary": f"识别到 {hist_count + pred_count} 个热点区域（历史聚类 {hist_count} 个 + 预测高风险 {pred_count} 个）",
            }
        except Exception as e:
            gis = {"status": "error", "hotspots": [], "summary": str(e)}

        _hs_all = gis.get("hotspots") or []
        _top_hs = next((h.get("city") for h in _hs_all if h.get("city")), "")
        _top_bit = (f"，最高优先级热点位于{_top_hs}（已标注坐标/火点数/FRP/风险评分）"
                    if _top_hs else "")
        step = {"step": "analyze_gis", "agent": "GisAgent",
                "input": f"对 {data.get('total', 0)} 条数据做空间分析（历史网格聚类+预测风险识别）",
                "output": {"hotspots": _hs_all[:5],
                           "total_hotspots": gis.get("total_hotspots", 0)},
                "status": "completed",
                "summary": (f"GisAgent 对查询数据完成空间聚类，识别到 {gis.get('total_hotspots', 0)} 个热点区域"
                            f"（历史火点聚类 {gis.get('hist_hotspots', 0)} 个 + 预测高风险区 {gis.get('pred_hotspots', 0)} 个）"
                            f"{_top_bit}，为巡防部署提供空间依据")}
        return {"gis_results": gis, "steps": [step]}

    # ---------- 节点4：知识库检索（真实调用 RagAgent/RagService，与 query_data 并行执行） ----------
    def retrieve_knowledge(state: AgentState) -> dict:
        from app.agents.rag_agent import RagAgent
        rag_agent = RagAgent(rag_service)
        try:
            retri = asyncio_run(rag_agent.retrieve(state["user_query"], 5, user_id=user_id, is_admin=is_admin))
            # retri 现为 dict（含 items/method 等元数据）
            items = retri.get("items", [])
            knowledge = [
                {"document": r.get("document_title", "未知"),
                 "content": r.get("content", "")[:200],
                 "score": r.get("score", 0)}
                for r in items
            ]
            method = retri.get("method", "none")
            if retri.get("reranked"):
                method += "+rerank"
            if items:
                _srcs = "《" + "》《".join(sorted({r.get("document_title", "未知") for r in items})[:3]) + "》"
                summary = (f"RagAgent 以向量召回+关键词双路检索并精排，命中 {len(items)} 段相关片段"
                           f"（主要来自{_srcs}等文档），将作为报告中规范引用与巡防建议的依据")
                note = ""
            else:
                # 未命中也要给出明确交代（用户要求：不跳过、不沉默）
                note = "未检索到任何与任务相关的知识库内容（已执行向量召回+关键词检索，可能知识库暂无该主题文档）"
                summary = ("RagAgent 已执行向量召回+关键词双路检索，未命中任何相关片段——"
                           "可能知识库暂无该主题文档，报告将如实注明无知识库引用")
            step = {"step": "retrieve_knowledge", "agent": "RagAgent",
                    "input": state["user_query"],
                    "output": {"matched": len(items), "method": method, **({"note": note} if note else {})},
                    "status": "completed",
                    "summary": summary}
            return {"knowledge_results": knowledge, "steps": [step]}
        except Exception as e:
            step = {"step": "retrieve_knowledge", "agent": "RagAgent", "input": state["user_query"],
                    "output": {"error": str(e)}, "status": "failed",
                    "summary": f"RagAgent 检索失败: {str(e)[:50]}"}
            return {"knowledge_results": [], "steps": [step]}

    # ---------- 节点5：join 屏障（并行波次汇聚点，本身为 no-op） ----------
    def join(state: AgentState) -> dict:
        return {}

    # ---------- 节点6：生成报告（注入真实数据 + 评审意见/驳回意见重写） ----------
    def generate_report(state: AgentState) -> dict:
        query = state["user_query"]
        data = state.get("data_results", {}) or {}
        gis = state.get("gis_results", {}) or {}
        knowledge = state.get("knowledge_results", []) or []
        revisions = state.get("revisions", 0)
        review_fb = state.get("review_result", {}) or {}
        rejection = state.get("rejection_feedback", "") or ""

        # 需求 C：历轮评审打回记录（steps 为 operator.add，历史轮 review_report 步骤全量可查；
        # 供前端节点卡展示「第几轮 + 每轮打回原因」，轮次上限仍为 2，见 route_after_review）
        review_history = []
        for s in state.get("steps", []):
            if s.get("step") == "review_report":
                o = s.get("output") or {}
                review_history.append({
                    "round": o.get("revisions", len(review_history)),
                    "passed": bool(o.get("passed")),
                    "issues": list(o.get("issues") or []),
                    "suggestion": str(o.get("suggestion") or ""),
                })

        # 汇总真实数据
        data_total = data.get("total", 0)
        hist_total = data.get("hist_total", 0)
        pred_total = data.get("pred_total", 0)
        items = data.get("items", []) or []
        top_cities = {}
        for it in items:
            c = it.get("city")
            if c:
                top_cities[c] = top_cities.get(c, 0) + 1
        top_cities_str = ", ".join(f"{c}({n})" for c, n in sorted(top_cities.items(), key=lambda x: -x[1])[:10]) or "无"

        hotspots = gis.get("hotspots", []) or []
        hotspot_str = "; ".join(
            (f"[{h.get('kind', '热点')}] " if h.get("kind") else "")
            + (f"{h.get('city')} " if h.get("city") else "")
            + f"[{h.get('lng', 0):.2f},{h.get('lat', 0):.2f}] 火点{h.get('count', 0)}个/平均FRP{h.get('avg_frp', 0)}"
            + (f"/风险评分{h.get('risk_score', 0)}" if h.get("risk_score") is not None else "")
            for h in hotspots[:12]
        ) or "无"

        kb_str = "\n".join(
            f"- （{k.get('document', '未知')}，相关度{k.get('score', 0)}）{k.get('content', '')[:150]}"
            for k in knowledge[:5]
        ) or "无"

        empty_reason = ""
        q_out = {}
        for s in reversed(state.get("steps", [])):
            if s.get("step") == "query_data":
                q_out = s.get("output", {}) or {}
                break
        if q_out.get("empty_reason"):
            empty_reason = q_out["empty_reason"]
        # AgentGauntlet 工具夹带附注（data_note）已随 chaos 下线一并注释

        # P2#14：重点区域实时天气（MCP 高德只读数据源；未启用/依赖缺失/调用失败静默跳过）
        weather_str = ""
        if settings.MCP_ENABLED and (hotspots or items):
            try:
                from app.core.mcp_client import get_weather_for_city
                _city = ((hotspots[0].get("city") if hotspots else None)
                         or (items[0].get("city") if items else None))
                if _city:
                    weather_str = get_weather_for_city(_city)
            except Exception:
                weather_str = ""

        # P2#15：用户分析偏好（PostgresStore 长期记忆；未启用/无记录时为空，失败静默）
        prefs_str = ""
        if settings.PREFERENCES_ENABLED and user_id is not None:
            try:
                from app.core.memory_store import prefs_context
                prefs_str = prefs_context(user_id)
            except Exception:
                prefs_str = ""

        # 评审意见 / 用户驳回意见（重写轮注入）
        revise_hint = ""
        if review_fb.get("issues") or review_fb.get("suggestion"):
            issues_str = "\n".join(f"  - {i}" for i in (review_fb.get("issues") or []))
            revise_hint += (f"\n## 评审意见（上一稿未通过评审，必须针对性修改）\n"
                            f"发现的问题：\n{issues_str or '  - 无'}\n"
                            f"修改建议：{review_fb.get('suggestion', '') or '无'}\n")
        if rejection:
            revise_hint += f"\n## 用户驳回意见（必须吸收进本稿）\n{rejection}\n"

        # 流式侧产物（各轮思考 / 中断原因 / 轮次）：无 LLM 时为空，供步骤行 output 携带
        think_rounds_texts: list[str] = []
        stream_note = ""
        stream_run = None

        if llm_available():
            prompt = f"""你是资深森林防火专家（ReportAgent），为森林防火指挥中心撰写正式分析报告。请根据以下多 Agent 协作产出的真实数据，撰写一份**详尽、专业、直击重点**的 Markdown 分析报告。

用户需求：{query}

## DataAgent 查询结果（真实数据库数据）
- 数据构成：历史火点 {hist_total} 条（覆盖2021-2025，NASA FIRMS 卫星观测）+ 预测火险 {pred_total} 条（覆盖2025-2026，模型预测）
- 记录总数：{data_total} 条
- 火点/风险分布（按州市统计）：{top_cities_str}
{('- 数据为空原因：' + empty_reason + chr(10)) if empty_reason else ''}
## GisAgent 空间分析结果
- 热点区域明细：{hotspot_str}
{('- 重点区域实时天气（MCP 高德数据源）：' + weather_str + chr(10)) if weather_str else ''}

## RagAgent 知识库检索（防火规范/预案参考）
{ kb_str }
{revise_hint}{(chr(10) + '## 用户分析偏好（历史查询习惯，巡防建议尽量贴合其辖区与关注时段）' + chr(10) + prefs_str + chr(10)) if prefs_str else ''}
## 报告模板（强制：所有报告必须一字不差地套用以下固定模板，章节标题、顺序、数量都不可改动）
# 云南森林火险分析报告
## 一、执行摘要
（用「1. 2. 3.」分条列出 3-5 条核心结论：哪里最危险（州市/热点名）、为什么（数据依据）、建议干什么）
## 二、数据来源与分析方法
（分条列举：历史火点数据源与时间范围、预测数据源与模型口径、空间分析方法、天气数据源；每条注明数据时间口径）
## 三、火情数据分析
（先用 Markdown 表格呈现「表 1：各州市火点/风险统计」（列：州市、历史火点数、预测风险数、风险等级），表格下方必须有「表 1 说明：」段落解读数据揭示的规律；再分条详述高发区域与时段规律，每条先给数字后阐释成因）
## 四、高风险区域识别
（逐个热点区域分条列举，每条格式「N. 所属州市[坐标]：火点数/平均FRP/风险评分——成因阐释」；区域定位必须使用数据中标注的所属州市名称，**严禁仅凭经纬度自行推断地名**；植被、地形类成因若无数据或知识库支撑，写明「待实地核查」，禁止臆断）
## 五、重点巡防建议
（分区域分条给出可执行措施——巡防时段（结合火险等级）、重点地段、卡口设置、瞭望监测、力量部署、物资准备、宣传管控；每条建议后用一句话说明依据）
## 六、结论与展望
## 附：参考依据
（编号列举所有引用来源，每条注明来源类型（知识库文档/历史火点统计/模型预测/高德实时天气）+ 名称或片段主题 + 相似度/时间口径；无检索结果时写明"本次未检索到匹配知识库文档"）

## 撰写要求（必须严格遵守）
1. **所有数字必须直接引用上面的真实数据**，禁止编造；数据为 0 的部分要说明原因（如该时段无历史记录、以预测数据为准）。
2. **模板刚性**：上面是唯一合法的报告结构——七个章节的标题文字与顺序完全固定，每章必须有内容（数据为空时写明原因），不得省略、合并、改名或新增章节。
3. **表达形式**：全文以分条列举为主，每条做到「结论 + 数据 + 阐释」三要素齐全；关键统计必须用 Markdown 表格呈现并配「表 N 说明」图注文字；禁止整段泛泛而谈。
4. 篇幅要求：**不少于 800 字**，重点区域分析要具体到州市名称和数据，巡防建议要能直接落地执行。
5. 语言风格：正式公文风格，直接陈述，不用客套话。
6. 报告头部的「报告生成时间」由系统自动注入，无需你撰写任何时间信息。

仅输出 Markdown 报告正文。"""
            # W2 攻击轮哨兵串注入（GAUNTLET_SYS_CANARY）已随 gauntlet 下线一并注释
            try:
                res = None
                if settings.LLM_STREAM_ENABLED and task_id is not None:
                    # P2#18 流式生成（增量经 report_channels 实时推送 SSE）；
                    # 内置复读循环检测 / 思考超限 / 取消中断，中断时保留已产生内容降级收尾；
                    # 失败/0 字符返回 None 走非流式兜底
                    res, think_rounds_texts, stream_note, stream_run = _stream_report(
                        prompt, task_id, db_session=db_session,
                        should_cancel=cancel_checker)
                    if res is not None and not (res.text or "").strip():
                        res = None  # 流式 0 字符（思考型模型 content 为空等）→ 必须兜底重试
                if res is None and not (cancel_checker and cancel_checker()):
                    # 已取消时不做非流式重试（任务即将终止，避免再耗 1-2 分钟 LLM 调用）
                    res = invoke_llm(
                        prompt, temperature=0.4, max_tokens=2400,
                        enable_thinking=False)
                if res is not None and (res.text or "").strip():
                    from app.services.rag_service import _strip_think
                    report = _strip_think(res.text) or res.text  # 兜底剥离可能混入的思考段，报告正文不含 <think>
                    audit = {"llm_provider": res.provider, "llm_model": res.model,
                             "llm_degraded": res.degraded}
                    if res.tokens:
                        audit["tokens"] = res.tokens
                else:
                    # 所有 Provider 均不可用 / 均返回空内容 / 已取消 → 模板兜底，保证报告正文永不为空
                    report = _template_report(query, data_total, hist_total, pred_total,
                                              top_cities_str, hotspot_str, kb_str)
                    audit = {}
            except Exception as e:
                report = _template_report(query, data_total, hist_total, pred_total,
                                          top_cities_str, hotspot_str, kb_str) + f"\n\n> LLM 调用异常：{e}"
                audit = {}
        else:
            report = _template_report(query, data_total, hist_total, pred_total,
                                      top_cities_str, hotspot_str, kb_str)
            audit = {}

        _kb_n = len(knowledge)
        summary = (f"ReportAgent 已生成 {len(report)} 字符报告，按模板涵盖执行摘要/数据来源与分析方法/"
                   f"火情数据分析/高风险区域识别/巡防建议/结论六个章节"
                   f"（引用历史火点 {hist_total} 条、预测火险 {pred_total} 条真实数据"
                   + (f"，参考知识库片段 {_kb_n} 段" if _kb_n else "")
                   + "）")
        if revisions > 0:
            # 需求 C：摘要带上最近一轮被打回的原因（完整历轮记录在 output.review_history）
            last_issues = (review_history[-1].get("issues") if review_history else []) or []
            reason_brief = "；".join(str(i)[:40] for i in last_issues[:2])
            summary += (f"（第 {revisions} 轮修订稿，已吸收评审意见"
                        + (f"：{reason_brief}" if reason_brief else "") + "）")
        # 思考按轮次保存：最后一轮由 finalize 并入历史轮次（前几轮命中时已在
        # 流式中以 note=think_loop/think_limit 截断落库），thinking 为全部轮次拼接
        think_final = think_rounds_texts[-1] if think_rounds_texts else ""
        think_joined, think_rounds = _finalize_step_thinking(
            db_session, task_id, think_final, stream_run, stream_note)
        _step_out = {"report_length": len(report), **audit,
                     "thinking": think_joined,
                     "thinking_rounds": think_rounds,
                     "review_history": review_history}
        if stream_note:
            _step_out["stream_note"] = stream_note  # 思考复读中断/思考超限/取消等（A/B 降级收尾标记）
        step = {"step": "generate_report", "agent": "ReportAgent", "input": query,
                "output": _step_out, "status": "completed",
                "summary": summary}
        # 系统注入报告生成时间（不依赖 LLM，避免时间幻觉）；统一追加系统署名（开发者信息 + 项目地址）
        from datetime import datetime
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = (f"> 报告生成时间：{generated_at} ｜ 数据构成：历史火点 {hist_total} 条 · 预测火险 {pred_total} 条\n\n"
                  + report + settings.REPORT_FOOTER)
        return {"report": report, "steps": [step], "status": "completed"}

    # ---------- 节点7：质量评审（LLM 评审 + 硬护栏；不通过仅标注问题，交人工审批定夺，不自动重写） ----------
    def review_report(state: AgentState) -> dict:
        report = state.get("report", "")
        revisions = state.get("revisions", 0)

        # 硬护栏（不依赖 LLM，一票否决）
        issues = []
        core = report.replace(settings.REPORT_FOOTER, "")
        if len(core.strip()) < 800:
            issues.append(f"报告正文仅 {len(core.strip())} 字符，要求不少于 800 字符")
        if "执行摘要" not in report:
            issues.append("缺少「执行摘要」章节")
        if "巡防" not in report:
            issues.append("缺少巡防建议相关内容")
        data = state.get("data_results", {}) or {}
        for label, key in (("历史火点", "hist_total"), ("预测火险", "pred_total")):
            v = data.get(key, 0)
            if v > 0 and str(v) not in report:
                issues.append(f"报告未引用{label}真实数据（{v} 条）")

        # LLM 评审（低温度）：成功与否不影响任务推进——失败走 degraded 转人工
        suggestion = ""
        llm_ok = False
        llm_passed = True
        llm_issues: list = []
        degraded_reason = ""
        if llm_available():
            prompt = f"""你是严格的分析报告质量评审员（Reviewer）。请评审以下森林火险分析报告。

评审标准：
1. 结构完整（执行摘要/数据分析/风险识别/巡防建议等章节）
2. 数据引用真实（数字与给定数据一致，无编造）
3. 巡防建议具体可执行（分区域、有时段、有措施）

报告内容：
{report[:4000]}

返回 JSON（严格格式）：{{"passed": true或false, "issues": ["具体问题描述", "..."], "suggestion": "针对性修改建议"}}
要求：
- issues 每一项都必须是具体问题：指出缺哪个章节、哪处数据未引用或与给定数据不符、哪条建议不可执行；
  禁止输出「问题1」「问题2」这类占位词；没有问题时 issues 为空数组 []
- suggestion 给出可落地的修改方向
仅输出 JSON。"""
            try:
                verdict, _meta = invoke_structured(prompt, ReviewVerdict, temperature=0.0)
                if verdict is not None:
                    llm_ok = True
                    llm_passed = bool(verdict.passed)
                    llm_issues = list(verdict.issues or [])
                    suggestion = verdict.suggestion or ""
                else:
                    degraded_reason = "结构化评审输出解析失败"
            except Exception as e:
                degraded_reason = f"评审 LLM 调用异常（{str(e)[:60] or type(e).__name__}）"
        else:
            degraded_reason = "LLM 不可用"

        # 三态判定（returned 退回重写 ≤2 轮 / degraded 评审失败转人工 / passed 通过）：
        # 评审自身失败（异常/解析失败/给不出具体问题）不是驳回——报告直接进人工审核，
        # 步骤不再置 failed、不空拼「发现0项问题：。」
        outcome = _decide_review_outcome(
            hard_issues=issues, llm_ok=llm_ok, llm_passed=llm_passed,
            revisions=revisions, llm_issues=llm_issues,
            suggestion=suggestion, degraded_reason=degraded_reason)
        passed = outcome["passed"]
        review_status = outcome["review_status"]

        review = {"passed": passed, "issues": outcome["issues"],
                  "suggestion": outcome["suggestion"],
                  "review_status": review_status}
        if outcome["forced"]:
            review["forced"] = True

        step = {"step": "review_report", "agent": "Reviewer", "input": f"评审报告（{len(report)} 字符）",
                "output": {"passed": passed, "review_status": review_status,
                           "issues": outcome["issues"][:5],
                           "suggestion": outcome["suggestion"][:100],
                           "revisions": revisions,
                           **({"degraded_reason": degraded_reason} if degraded_reason else {})},
                # 退回重写是业务预期结论，评审节点本身已完成：不再置 failed
                "status": "completed",
                "summary": outcome["summary"]}
        result = {"review_result": review, "steps": [step]}
        if review_status == "returned":
            result["revisions"] = revisions + 1
        return result

    # ---------- 节点8：HITL 审批闸口（interrupt 暂停，等待 resume 注入人工决策） ----------
    def approval_gate(state: AgentState) -> dict:
        from langgraph.types import interrupt
        draft = state.get("report", "")
        review = state.get("review_result", {}) or {}
        resume = interrupt({
            "report": draft,
            "review": review,
            "revisions": state.get("revisions", 0),
        })
        resume = resume or {}
        action = resume.get("action", "approve")

        if action == "edit":
            content = resume.get("content") or draft
            step = {"step": "approval", "agent": "HITL", "input": state["user_query"],
                    "output": {"action": "edit", "content_length": len(content)},
                    "status": "completed", "summary": "人工审批：编辑后通过"}
            return {"report": content, "decision": "edit", "status": "completed", "steps": [step]}
        if action == "reject":
            comment = resume.get("comment", "") or ""
            step = {"step": "approval", "agent": "HITL", "input": state["user_query"],
                    "output": {"action": "reject", "comment": comment[:200]},
                    "status": "completed", "summary": f"人工驳回：{comment[:50]}"}
            return {"decision": "reject", "rejection_feedback": comment, "revisions": 0, "steps": [step]}
        step = {"step": "approval", "agent": "HITL", "input": state["user_query"],
                "output": {"action": "approve"},
                "status": "completed", "summary": "人工审批：通过"}
        return {"decision": "approve", "status": "completed", "steps": [step]}

    return parse_task, query_data, analyze_gis, retrieve_knowledge, join, generate_report, review_report, approval_gate


def _template_report(query, data_total, hist_total, pred_total, top_cities, hotspot, kb) -> str:
    """无 LLM 时的模板报告（仍含真实数据，结构完整；输出规范 Markdown 表格而非原始串）"""
    import re as _re

    # 解析「保山市(24), 大理白族自治州(24), …」→ 有序排名
    cities: list[tuple[str, int]] = []
    for part in str(top_cities or "").split(","):
        part = part.strip()
        if part.endswith(")") and "(" in part:
            name, _, cnt = part.rpartition("(")
            if name.strip() and cnt.rstrip(")").isdigit():
                cities.append((name.strip(), int(cnt.rstrip(")"))))

    # 解析热点串 → 表格行：[历史聚类] 文山州 [104.70,24.30] 火点38个/平均FRP55.64/风险评分x
    hs_pat = _re.compile(
        r"(?:\[(历史聚类|预测高风险|热点)\]\s*)?([^\s\[]+)\s*\[([\d.]+),([\d.]+)\]\s*"
        r"火点(\d+)个/平均FRP([\d.]+)(?:/风险评分([\d.]+))?")
    hotspots = [m.groups() for m in (hs_pat.match(seg.strip().lstrip(";；"))
                                     for seg in str(hotspot or "").split(";")) if m]

    city_table = ""
    if cities:
        rows = "\n".join(f"| {i} | {n} | {c} |" for i, (n, c) in enumerate(cities, 1))
        city_table = (f"\n**表 1：各州市火点/风险记录统计**\n\n"
                      f"| 排名 | 州市 | 记录数 |\n| --- | --- | --- |\n{rows}\n")
    hs_table = ""
    if hotspots:
        rows = "\n".join(
            f"| {kind or '热点'} | {city} | {lng},{lat} | {cnt} | {frp} | {risk or '—'} |"
            for kind, city, lng, lat, cnt, frp, risk in hotspots)
        hs_table = (f"\n**表 2：热点区域明细（Top {len(hotspots)}）**\n\n"
                    f"| 类型 | 州市 | 中心坐标 | 火点数 | 平均FRP | 风险评分 |\n"
                    f"| --- | --- | --- | --- | --- | --- |\n{rows}\n")

    top3 = "、".join(n for n, _ in cities[:3]) if cities else "无（数据为空）"
    hs_lines = "\n".join(
        f"- **{city}**（{kind or '热点'}，中心 {lng},{lat}）：火点 {cnt} 个，平均FRP {frp}"
        + (f"，风险评分 {risk}" if risk else "")
        for kind, city, lng, lat, cnt, frp, risk in hotspots) or "- 无热点区域"

    return f"""# 云南森林火险分析报告

## 一、执行摘要
针对「{query}」，系统完成 DataAgent（双源数据查询）→ GisAgent（空间分析）→ RagAgent（知识检索）多 Agent 协作分析，共获取 **{data_total} 条**真实数据。数据量排名前三的州市为：**{top3}**。

## 二、数据来源与分析方法
- 历史火点数据：{hist_total} 条（NASA FIRMS 卫星观测，覆盖 2021-2025 年）
- 预测火险数据：{pred_total} 条（模型预测，覆盖 2025-2026 年）
- 分析方法：历史火点按 0.1° 网格聚类识别聚集区；预测数据按火险等级识别高风险区域

## 三、火情数据分析
- 记录总数：{data_total} 条（历史 {hist_total} + 预测 {pred_total}）
{city_table}
{hs_table}
## 四、高风险区域识别
{hs_lines}

## 五、重点巡防建议
1. 对上述热点区域所在的州市提高巡查频次，火险等级 4 级以上区域实行每日巡护；
2. 在高火险时段（10:00-18:00）加强瞭望监测与卡口检查；
3. 预置扑火队伍与物资至重点乡镇，检查风力灭火机、水泵等装备；
4. 结合知识库规范开展防火宣传与野外用火管控。

## 附：参考依据
{kb if kb != "无" else "- 本次未检索到匹配知识库文档"}

> 注：LLM 服务暂不可用，本报告由结构化模板基于真实查询与分析数据生成。"""


def asyncio_run(coro):
    """同步环境中执行协程"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # 已在事件循环内（FastAPI async 上下文）→ 用新循环跑
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            return ex.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ===== 条件路由函数（模块级纯函数：只读 parsed_intent.plan / review_result / decision，不读并行节点写入的键） =====

def route_after_parse(state: AgentState) -> list[str]:
    """parse_task 后的并行 fan-out：按计划并行触发 query_data 与 retrieve_knowledge"""
    plan = (state.get("parsed_intent", {}) or {}).get("plan") or []
    types = {p.get("task_type") for p in plan}
    targets = []
    if "query_data" in types:
        targets.append("query_data")
    if "retrieve_knowledge" in types:
        targets.append("retrieve_knowledge")
    if not targets:
        # 兜底：默认执行数据查询（双源查询硬约束）
        targets = ["query_data"]
    return targets


def route_after_join(state: AgentState) -> Literal["generate_report", "end"]:
    """join 后按计划决定是否生成报告"""
    plan = (state.get("parsed_intent", {}) or {}).get("plan") or []
    types = {p.get("task_type") for p in plan}
    if "generate_report" in types:
        return "generate_report"
    return "end"


def _decide_review_outcome(hard_issues: list, llm_ok: bool, llm_passed: bool,
                           revisions: int, llm_issues: list | None = None,
                           suggestion: str = "", degraded_reason: str = "") -> dict:
    """评审三态判定（纯函数，供 review_report 节点与单测使用）：

    - returned：有**可信问题项**（硬护栏问题，或 LLM 明确列出的非占位问题）
      → 退回重写，最多 2 轮（revisions≥2 时停止重写转人工）；
    - degraded：评审自身失败（异常/超时/解析失败/LLM 判不通过却给不出具体问题）
      → **不得退回**，直接转人工审核确认（用户仍可审批定稿，任务不失败）；
    - passed：评审成功且未发现问题。

    占位词过滤（"问题1"/"issue 2"）在此统一处理。返回
    dict(passed, review_status, forced, issues, suggestion, summary)。
    """
    issues = list(hard_issues or [])
    for i in (llm_issues or []):
        s = str(i or "").strip()
        tail = s[2:] if s.startswith("问题") else (s[5:] if s.lower().startswith("issue") else None)
        if s and tail is not None and tail.strip().isdigit():
            continue  # 模型照抄提示词示例的占位词，不算可信问题
        if s and s not in issues:
            issues.append(i)

    if issues:
        brief = "；".join(str(i)[:48] for i in issues[:3])
        more = f" 等{len(issues)}项" if len(issues) > 3 else ""
        if revisions < 2:
            return {"passed": False, "review_status": "returned", "forced": False,
                    "issues": issues, "suggestion": suggestion,
                    "summary": f"发现{len(issues)}项问题：{brief}{more}。退回 ReportAgent 重写"}
        # 达重写上限仍不通过：停止重写转人工（不再打回）
        return {"passed": False, "review_status": "degraded", "forced": True,
                "issues": issues, "suggestion": suggestion,
                "summary": f"自动评审未通过（{brief}…），已达重写上限，转人工审核确认"}

    if llm_ok:
        if llm_passed:
            return {"passed": True, "review_status": "passed", "forced": False,
                    "issues": [], "suggestion": suggestion,
                    "summary": "Reviewer 评审通过：未发现问题，报告结构完整，已提交人工审批"}
        # LLM 判"不通过"却拿不出具体问题 → 不可信，降级转人工（不浪费一轮重写）
        return {"passed": True, "review_status": "degraded", "forced": False,
                "issues": [], "suggestion": suggestion or "模型未给出具体问题项",
                "summary": "评审未完成，已转人工确认（模型未给出具体问题项）"}

    return {"passed": True, "review_status": "degraded", "forced": False,
            "issues": [], "suggestion": degraded_reason or "评审不可用",
            "summary": f"评审未完成，已转人工确认（{degraded_reason}）"}


def route_after_review(state: AgentState) -> Literal["generate_report", "approval_gate", "end"]:
    """评审后：不通过且未达重写上限 → 自动退回重写（重新流式生成）；
    通过 / 强制放行（达上限）→ 审批闸口 / 结束；人工驳回走 approval 后的路由"""
    review = state.get("review_result", {}) or {}
    if not review.get("passed") and state.get("revisions", 0) < 2 and not review.get("forced"):
        return "generate_report"
    if settings.AGENT_REQUIRE_APPROVAL:
        return "approval_gate"
    return "end"


def route_after_approval(state: AgentState) -> Literal["generate_report", "end"]:
    """审批后：reject → 按驳回意见重写；approve/edit → 结束"""
    if state.get("decision") == "reject":
        return "generate_report"
    return "end"


# ===== 构建 LangGraph 图 =====

def build_workflow_graph(nodes: list[Callable], checkpointer=None) -> "CompiledStateGraph":
    """构建 LangGraph StateGraph（P1 拓扑：fan-out/join + 评审循环 + 审批闸口）

    图拓扑：
      parse_task →(条件fan-out)→ [query_data?, retrieve_knowledge?]
      query_data → analyze_gis → join
      retrieve_knowledge → join
      join →(条件)→ generate_report | END
      generate_report → review_report →(条件)→ generate_report(重写) / approval_gate / END
      approval_gate →(条件)→ generate_report(驳回重写) / END
    """
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(AgentState)
    (parse_task, query_data, analyze_gis, retrieve_knowledge,
     join, generate_report, review_report, approval_gate) = nodes

    workflow.add_node("parse_task", parse_task)
    workflow.add_node("query_data", query_data)
    workflow.add_node("analyze_gis", analyze_gis)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge)
    workflow.add_node("join", join)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("review_report", review_report)
    workflow.add_node("approval_gate", approval_gate)

    workflow.set_entry_point("parse_task")

    # 并行 fan-out：路由函数返回 list 时 LangGraph 并行触发多个分支
    workflow.add_conditional_edges("parse_task", route_after_parse, {
        "query_data": "query_data",
        "retrieve_knowledge": "retrieve_knowledge",
    })
    workflow.add_edge("query_data", "analyze_gis")       # 计划未含时 analyze_gis 内部 no-op 跳过
    workflow.add_edge("analyze_gis", "join")
    workflow.add_edge("retrieve_knowledge", "join")
    workflow.add_conditional_edges("join", route_after_join, {
        "generate_report": "generate_report",
        "end": END,
    })
    workflow.add_edge("generate_report", "review_report")
    workflow.add_conditional_edges("review_report", route_after_review, {
        "generate_report": "generate_report",
        "approval_gate": "approval_gate",
        "end": END,
    })
    workflow.add_conditional_edges("approval_gate", route_after_approval, {
        "generate_report": "generate_report",
        "end": END,
    })

    return workflow.compile(checkpointer=checkpointer)


# ===== 编排器对外接口 =====

def _initial_state(user_query: str) -> AgentState:
    """构造任务初始状态（execute 与 stream 共用，保证两接口行为一致）"""
    return AgentState(
        user_query=user_query,
        parsed_intent={},
        data_results={},
        gis_results={},
        knowledge_results=[],
        report="",
        status="pending",
        steps=[],
        error=None,
        revisions=0,
        review_result={},
        decision="",
        rejection_feedback="",
    )


class OrchestratorAgent:
    """任务编排 Agent（依赖 db session 构造真实节点）

    checkpointer：每实例独享（PostgresSaver 单连接非线程安全，禁止跨实例共享）。
    thread_id 按任务固定（task-{id}），HITL 中断态由 checkpointer 持久化，
    resume 时用同 thread_id 重建实例并 stream(Command(resume=...)) 即可续跑。
    """

    def __init__(self, db_session=None, user_id=None, is_admin=False, thread_id: str | None = None,
                 task_id: int | None = None, cancel_checker=None):
        self.db = db_session
        self.user_id = user_id
        self.is_admin = is_admin
        self.thread_id = thread_id
        self.task_id = task_id
        self.checkpointer = create_checkpointer()
        nodes = (_make_nodes(db_session, user_id=user_id, is_admin=is_admin, task_id=task_id,
                             cancel_checker=cancel_checker)
                 if db_session is not None else _make_fallback_nodes())
        self.graph = build_workflow_graph(nodes, checkpointer=self.checkpointer)

    def snapshot_state(self) -> dict:
        """取当前 thread 在 checkpointer 中的累积状态（HITL 恢复时必须先调用）

        stream(Command(resume=...)) 只产出中断之后的增量，若从空字典开始累积，
        中断前已生成的 report/steps/data_results 全部丢失（报告将无法落库）。
        """
        try:
            snap = self.graph.get_state(self._config())
            return dict(snap.values or {})
        except Exception:
            return {}

    def has_pending_interrupt(self, node_name: str | None = None) -> bool | None:
        """当前 thread 是否存在挂起的 interrupt（可限定节点名，如 "approval_gate"）

        供 resume 端点幂等校验：闸口未挂起时（决策已注入/图已跑完/checkpoint 丢失）
        应拒绝放行——否则 stream(Command(resume=...)) 会把整个流程静默重跑一遍并
        再次中断，表现为"审批后任务又回到待审批、需要点两次"（用户反馈根因之一）。
        返回三态：True=确认挂起 / False=确认未挂起 / None=探测失败（无法判定，
        调用方不得把 None 当 False 拦截真实审批——False 语义混入异常曾导致误 409）。
        """
        try:
            snap = self.graph.get_state(self._config())
            for task in getattr(snap, "tasks", ()) or ():
                interrupts = getattr(task, "interrupts", None) or ()
                if not interrupts:
                    continue
                if node_name is None or getattr(task, "name", "") == node_name:
                    return True
            return False
        except Exception:
            return None

    def _config(self) -> dict:
        """LangGraph 运行配置（thread_id 用于 checkpoint 状态隔离）

        P2#12：启用 Langfuse 时附加观测 callbacks（未启用/未部署返回 None，无副作用）
        """
        cfg = {"configurable": {"thread_id": self.thread_id or "default"}}
        try:
            from app.core.observability import build_callback_config
            obs = build_callback_config(task_id=self.task_id, thread_id=self.thread_id)
            if obs:
                cfg.update(obs)
        except Exception:
            pass
        return cfg

    async def execute(self, user_query: str) -> dict[str, Any]:
        """执行完整分析流程（一次性返回最终结果，兼容旧调用方）"""
        result = self.graph.invoke(_initial_state(user_query), self._config())
        return {
            "report": result.get("report", ""),
            "steps": result.get("steps", []),
            "status": result.get("status", "failed"),
            "llm_used": llm_available(),
            "data": result.get("data_results", {}),
            "gis": result.get("gis_results", {}),
            "knowledge": result.get("knowledge_results", []),
        }

    def iter_steps(self, user_query: str):
        """逐步执行（生成器）：yield (节点名或"__interrupt__", 该节点返回的状态增量)

        供后台 worker 流式落库步骤 + SSE 推送进度；遇到 interrupt 时 yield
        ("__interrupt__", (Interrupt(...),))，由调用方决定暂停/恢复。
        """
        for event in self.graph.stream(_initial_state(user_query), self._config(),
                                       stream_mode="updates"):
            for node_name, update in (event or {}).items():
                yield node_name, update or {}

    def iter_resume(self, resume_value: dict):
        """从 HITL 中断点恢复执行：yield (节点名或"__interrupt__", 状态增量)

        resume_value 为人工决策：{"action": "approve"|"edit"|"reject", "content": str, "comment": str}
        """
        from langgraph.types import Command
        for event in self.graph.stream(Command(resume=resume_value), self._config(),
                                       stream_mode="updates"):
            for node_name, update in (event or {}).items():
                yield node_name, update or {}


def _make_fallback_nodes():
    """无 db 时的兜底节点（保持新图结构可用，返回占位数据；同样只返回 delta）"""
    def parse_task(state: AgentState) -> dict:
        plan = [
            {"task_type": "query_data", "description": "默认计划（数据库未连接）", "required": True},
            {"task_type": "generate_report", "description": "生成模板报告", "required": True},
        ]
        step = {"step": "parse_task", "agent": "Orchestrator", "input": state["user_query"],
                "output": {"plan": plan},
                "status": "completed", "summary": "任务拆解完成（数据库未连接）"}
        return {"parsed_intent": {"plan": plan}, "steps": [step], "status": "parsed"}

    def query_data(state: AgentState) -> dict:
        step = {"step": "query_data", "agent": "DataAgent", "input": state["user_query"],
                "output": {"error": "数据库未连接"}, "status": "failed",
                "summary": "DataAgent 无法查询（数据库未连接）"}
        return {"data_results": {"status": "no_db", "total": 0, "items": []}, "steps": [step]}

    def analyze_gis(state: AgentState) -> dict:
        step = {"step": "analyze_gis", "agent": "GisAgent", "input": state["user_query"],
                "output": {"skipped": True, "reason": "无数据"}, "status": "skipped",
                "summary": "GisAgent 无数据可分析，已跳过"}
        return {"gis_results": {"status": "no_data", "hotspots": [], "summary": "无数据"}, "steps": [step]}

    def retrieve_knowledge(state: AgentState) -> dict:
        step = {"step": "retrieve_knowledge", "agent": "RagAgent", "input": state["user_query"],
                "output": {"matched": 0}, "status": "completed", "summary": "RagAgent 无知识库可检索"}
        return {"knowledge_results": [], "steps": [step]}

    def join(state: AgentState) -> dict:
        return {}

    def generate_report(state: AgentState) -> dict:
        report = _template_report(state["user_query"], 0, 0, 0, "无", "无", "无") + settings.REPORT_FOOTER
        step = {"step": "generate_report", "agent": "ReportAgent", "input": state["user_query"],
                "output": {"report_length": len(report)}, "status": "completed",
                "summary": "ReportAgent 生成报告（无数据库）"}
        return {"report": report, "steps": [step], "status": "completed"}

    def review_report(state: AgentState) -> dict:
        review = {"passed": True, "issues": [], "suggestion": "无 LLM 环境，跳过评审"}
        step = {"step": "review_report", "agent": "Reviewer", "input": "模板报告",
                "output": {"passed": True}, "status": "completed",
                "summary": "Reviewer 评审通过（无 LLM，硬护栏跳过）"}
        return {"review_result": review, "steps": [step]}

    def approval_gate(state: AgentState) -> dict:
        # 无 db 场景（内部工具/测试）不做真实 HITL，自动通过
        step = {"step": "approval", "agent": "HITL", "input": state["user_query"],
                "output": {"action": "auto_approve"}, "status": "completed",
                "summary": "审批闸口：无数据库环境自动通过"}
        return {"decision": "approve", "status": "completed", "steps": [step]}

    return parse_task, query_data, analyze_gis, retrieve_knowledge, join, generate_report, review_report, approval_gate
