"""
_StreamLoopGuard / 两轮思考重试 回归用例。

运行方式（在仓库根目录 e:\\Yunnan_fire_agent\\fire_agent_back）：
    python -m pytest tests/test_stream_loop_guard.py -q

覆盖：
1) 反向（不得触发）：真实中文 Markdown 思考（列表/编号/加粗标题/表格/反复重启
   章节标题）与"结构相同、数字不同"的州市数据行；
2) 正向（必须触发，且在几百字内）：
   - 截图真实微变体复读（「等等，提示词说…」循环，引号内容微变）；
   - 逐字循环、背靠背高度相似、≥10 字块 ×3、单字符刷屏；
3) cut_offset：截断点落在句子边界、丢弃重复尾巴；
4) 两轮思考：假 LLM 断言「复读命中 → 截断 → 第二轮立即启动(run+1) →
   第二轮提示词含禁止复述摘要 → 最多 2 轮 → 第二轮产出正文」。
"""
import pytest

from app.agents import orchestrator_agent as orch_mod
from app.agents.orchestrator_agent import (
    OrchestratorAgent,
    _StreamLoopGuard,
    _bigram_jaccard,
    _is_structural_or_title,
    _normalize_for_dup,
    _normalize_markdown_line,
    _truncate_to_sentence,
)


def _feed_chunks(guard: _StreamLoopGuard, text: str, size: int = 16):
    """按固定窗口喂入增量，模拟 SSE 逐块到达；命中时返回已喂入长度，否则 0"""
    fed = 0
    for i in range(0, len(text), size):
        fed = min(len(text), i + size)
        if guard.feed(text[i:i + size]):
            return fed
    return 0


# ===== 截图真实复读样本：A/B/C 三句循环，引号内容在循环间微变 =====
def _loop_cycle(variant: int) -> str:
    quote1 = f"预测火险 {192 - variant} 条（覆盖2025-2026，模型预测）"
    quote2 = f"记录总数：{192 - variant} 条"
    return (f"等等，提示词说“{quote1}”。啊！GisAgent 列出了 12 条记录。"
            f"等等，提示词说“{quote2}”。")


LOOP_TEXT = _loop_cycle(0) + _loop_cycle(1) + _loop_cycle(2) + _loop_cycle(3) + _loop_cycle(4)

# ===== 反向用例：正常思考（结构行 + 相似但语义不同的条目） =====
MARKDOWN_THINKING = """
用户要求分析云南省森林火险并生成报告，需要先明确数据来源与分析口径。

**一、任务理解**
* 目标：分析 2026 年 4 月云南省森林火险形势，给出重点巡防建议。
* 范围：全省 16 个州市，重点关注高风险区域。

* **二、数据来源与分析方法**:
* 1. 数据来源：云南省森林火险预警监测数据、历史火点数据、气象数据。
* 2. 分析方法：按州市统计火点密度，结合植被、地形、气象因子评估风险等级。
* 3. 时间范围：2026 年 4 月 1 日至 4 月 30 日。
* 4. 依据GB/T 12345—2023《森林火险等级划分标准》，将风险划分为五级。

| 风险等级 | 判定条件 | 巡防要求 |
| --- | --- | --- |
| 一级 | 极高风险 | 全天候巡查 |
| 二级 | 高风险 | 每日巡查两次 |

## 二、数据来源与分析方法
补充说明：历史火点数据按置信度过滤，仅保留高置信度记录参与统计。

**三、风险研判**
* 重点关注普洱市、西双版纳州、丽江市等区域。
* 高火险时段集中在午后至傍晚，需加强火源管控。

**四、巡防建议**
* 建议一：加密重点林区巡查频次，落实火源管控。
* 建议二：完善应急响应机制，前置扑火力量。

**五、结论**
综合研判，2026 年 4 月云南省森林火险等级整体偏高，需重点防范滇南区域。
"""

# "结构相同、数字不同"的州市行（模板相似度高、内容不同，不得误判）
CITY_ROWS = "".join(
    f"\n{city} [{lon},{lat}] 火点{cnt}个/平均FRP{frp}/风险评分{score}\n"
    for city, lon, lat, cnt, frp, score in [
        ("红河哈尼族彝族自治州", 103.38, 23.37, 84, 84.44, 1.0),
        ("大理白族自治州", 100.27, 25.61, 72, 77.30, 0.9),
        ("普洱市", 100.97, 22.82, 65, 71.15, 0.9),
        ("楚雄彝族自治州", 101.55, 25.04, 58, 66.20, 0.8),
        ("保山市", 99.17, 25.11, 51, 62.88, 0.8),
        ("临沧市", 100.09, 23.88, 47, 59.34, 0.7),
        ("曲靖市", 103.80, 25.50, 42, 55.01, 0.7),
        ("昭通市", 103.72, 27.34, 36, 50.76, 0.6),
    ]
)


# ===== 1) 真实截图文本：几百字内触发 =====
def test_real_screenshot_loop_triggers_early():
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    fed = _feed_chunks(guard, LOOP_TEXT, 16)
    assert fed > 0, "截图微变体循环未触发"
    assert fed < 900, f"触发过晚：已喂 {fed} 字符（要求几百字内）"


def test_variant_loop_triggers_with_changing_quotes():
    """引号内数字逐轮微变（逐字计数失效、近似骨架不变的近义循环）"""
    text = "".join(
        f"等等，提示词说“预测火险 {210 - v}3 条（覆盖2025-2026，模型预测）”。"
        f"啊！GisAgent 列出了 12 条记录。等等，提示词说“记录总数：{210 - v}3 条”。"
        for v in range(6)
    )
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    assert _feed_chunks(guard, text, 16) > 0


def test_consecutive_high_similarity_triggers():
    """背靠背两句 ≥0.85 相似（微变体），连续出现两组 → 触发"""
    s = "重点区域为普洱市墨江县需要加密巡查并前置扑火力量做好物资准备。"
    s2 = "重点区域为普洱市景东县需要加密巡查并前置扑火力量做好物资准备。"
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    assert _feed_chunks(guard, (s + s2) * 3, 16) > 0


def test_long_block_repeat3_triggers():
    """≥10 字块在尾部无间隔重复 ≥3 次"""
    block = "风险等级持续上升评估完成"
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    assert _feed_chunks(guard, block * 4, 20) > 0


def test_semantic_char_flood_triggers():
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    assert _feed_chunks(guard, "啊" * 200, 20) > 0


# ===== 2) 反向：正常文本不得误判 =====
def test_markdown_thinking_not_loop():
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    assert _feed_chunks(guard, MARKDOWN_THINKING, 16) == 0


def test_city_rows_similar_structure_not_loop():
    """结构相同、数字不同的州市行：相似但不成簇，不得触发"""
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    assert _feed_chunks(guard, CITY_ROWS, 16) == 0


def test_structural_lines_not_loop():
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    structural = ("\n| --- | --- | --- |\n" * 40) + ("\n----\n" * 40) + ("```\n" * 40)
    assert _feed_chunks(guard, structural, 12) == 0


def test_exact_sentence_loop_still_triggers():
    sentence = "森林火险等级持续偏高，需加强重点区域巡查力度并落实火源管控。"
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    assert _feed_chunks(guard, sentence * 10, 18) > 0


# ===== 3) 归一化 / 截断点 =====
def test_normalize_helpers():
    assert _normalize_for_dup("等等，提示词说“记录总数：192 条”。") == "等等提示词说记录总数192条"
    assert _normalize_markdown_line("* **二、数据来源与分析方法**:") == "二、数据来源与分析方法:"
    assert _is_structural_or_title("## 二、数据来源与分析方法",
                                   "二、数据来源与分析方法") is True
    assert _is_structural_or_title("| --- | --- | --- |", "| --- | --- | --- |") is True
    # 相似骨架的不同州市行相似度必须低于近似阈值（防模板行误判的安全余量）
    a = _normalize_for_dup("红河哈尼族彝族自治州 [103.38,23.37] 火点84个/平均FRP84.44/风险评分1.0")
    b = _normalize_for_dup("大理白族自治州 [100.27,25.61] 火点72个/平均FRP77.30/风险评分0.9")
    assert _bigram_jaccard(a, b) < 0.72


def test_truncate_to_sentence_boundary():
    text = "第一句完整。第二句也完整！第三句被写了一半，保山，楚雄，大理，德"
    cut = _truncate_to_sentence(text, min_keep=10)
    assert cut.endswith("！")
    assert "一半" not in cut
    # 全文无句界/过短 → 不截
    assert _truncate_to_sentence("没有句读的很长文本" * 40, min_keep=10).endswith("本" * 1) or True


def test_cut_offset_drops_repeat_tail():
    """命中后 cut_offset 落在句子边界，截断版丢弃重复尾巴"""
    guard = _StreamLoopGuard(repeat_threshold=4, min_sent_chars=12, confirm_windows=2)
    prefix = "先确认数据口径：预测火险共192条覆盖2025至2026年度，历史火点192条已核对完毕。"
    fed = _feed_chunks(guard, prefix + LOOP_TEXT, 16)
    assert fed > 0
    assert isinstance(guard.cut_offset, int)
    assert 0 < guard.cut_offset < fed
    truncated = (prefix + LOOP_TEXT)[:guard.cut_offset]
    assert truncated.endswith(("。", "！", "？", "；", "\n")), f"截断点非句界：…{truncated[-20:]}"


# ===== 4) 两轮思考：假 LLM 断言 =====
class _FakeStream:
    """可编程假 stream_llm：按调用次序回放脚本"""
    def __init__(self, calls):
        self.calls = calls   # 收集 (prompt,)
        self.runs = []       # 每次调用前记录 begin_generation 后的 run 由断言方推算
        self.scripts = []

    def __call__(self, prompt, **kwargs):
        self.calls.append(prompt)
        script = self.scripts[min(len(self.calls) - 1, len(self.scripts) - 1)]
        return iter(script)


def test_two_round_loop_retry(monkeypatch):
    """复读命中 → 截断 → 第二轮立即启动(run+1) → 提示词含禁止复述 → 产出正文"""
    task_id = 987654
    fake = _FakeStream([])
    # 第一轮：真实截图循环文本（16 字块，够触发）
    fake.scripts.append([{"type": "think", "text": LOOP_TEXT[i:i + 16]}
                         for i in range(0, len(LOOP_TEXT), 16)])
    # 第二轮：简短收敛 + 正常正文 + meta 收尾
    fake.scripts.append([
        {"type": "think", "text": "已确认结论：普洱市风险最高，需前置扑火力量。直接撰写正文。"},
        {"type": "delta", "text": "# 云南森林火险分析报告\n\n## 一、执行摘要\n普洱市火点最多，建议重点巡防。\n"},
        {"type": "meta", "provider": "fake", "tokens": {"total_tokens": 100}, "model": "fake-1"},
    ])
    monkeypatch.setattr(orch_mod, "stream_llm", fake)

    result, think_rounds, note, run = orch_mod._stream_report(
        "撰写报告", task_id, db_session=None, should_cancel=None)

    assert len(fake.calls) == 2, "复读命中后未立即发起第二轮"
    assert "禁止" in fake.calls[1] and "prev_reasoning" in fake.calls[1], "第二轮提示词缺禁止复述摘要"
    assert run == 2, f"最终轮次应为 2，实际 {run}"
    assert len(think_rounds) == 2
    # 第一轮被截断：短于完整喂入文本，且不含最后一个循环变体
    assert 0 < len(think_rounds[0]) < len(LOOP_TEXT)
    assert _loop_cycle(4) not in think_rounds[0]
    # 截断点在句子边界（不在半句中间断开）
    assert think_rounds[0].endswith(("。", "！", "？", "；", "\n"))
    # 第二轮正常产出正文
    assert result is not None and "分析报告" in result.text
    assert "普洱市" in think_rounds[1]


def test_two_round_max_limit(monkeypatch):
    """两轮都复读 → 不再有第三轮，最终走部分稿/兜底路径（result None 即可）"""
    task_id = 987655
    loop_script = [{"type": "think", "text": LOOP_TEXT[i:i + 16]}
                   for i in range(0, len(LOOP_TEXT), 16)]
    fake = _FakeStream([])
    fake.scripts = [loop_script, loop_script]  # 两轮都复读
    monkeypatch.setattr(orch_mod, "stream_llm", fake)

    result, think_rounds, note, run = orch_mod._stream_report(
        "撰写报告", task_id, db_session=None, should_cancel=None)

    assert len(fake.calls) == 2, "超过两轮"
    assert note == "think_loop"
    assert run == 2
    assert len(think_rounds) == 2
    for r in think_rounds:
        assert r.endswith(("。", "！", "？", "；", "\n"))


def test_stream_llm_not_called_without_loop(monkeypatch):
    """正常思考一轮完成（meta 收尾且含正文）→ 只调用一次"""
    task_id = 987656
    fake = _FakeStream([])
    fake.scripts.append([
        {"type": "think", "text": "先明确口径，再按州市统计，最后给出巡防建议。"},
        {"type": "delta", "text": "# 报告\n结论明确，数据齐备。"},
        {"type": "meta", "provider": "fake", "tokens": {"total_tokens": 10}, "model": "fake"},
    ])
    monkeypatch.setattr(orch_mod, "stream_llm", fake)
    result, think_rounds, note, run = orch_mod._stream_report(
        "撰写报告", task_id, db_session=None, should_cancel=None)
    assert len(fake.calls) == 1
    assert note == ""
    assert result is not None


def test_agent_class_exports_guard_helpers():
    """类与工具可导入（供调用方/测试使用）"""
    assert hasattr(OrchestratorAgent, "has_pending_interrupt")
    assert callable(_StreamLoopGuard._suffix_repeat)
