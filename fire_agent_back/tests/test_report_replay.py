"""
报告流式通道的增量副本与重连补齐（report_snapshot）

覆盖的用户可见行为：流式生成中切到别的页面再回来 / 刷新页面，已上屏的正文与
思考不能丢——新订阅的第一帧必须是本轮已产出增量的完整副本。
"""
import asyncio

import pytest

from app.core import report_channels as rc


@pytest.fixture(autouse=True)
def _isolate_channels():
    """每个用例前后清空模块级状态，避免用例间串味"""
    rc._subs.clear()
    rc._runs.clear()
    rc._buffers.clear()
    yield
    rc._subs.clear()
    rc._runs.clear()
    rc._buffers.clear()


def _drain(q):
    """取出队列里当前全部帧（不等待）"""
    frames = []
    while True:
        try:
            frames.append(q.get_nowait())
        except asyncio.QueueEmpty:
            return frames


def test_push_accumulates_copy_even_without_subscribers():
    run = rc.begin_generation(1)
    rc.push_delta(1, run, "第一章 ")
    rc.push_delta(1, run, "内容")
    rc.push_think(1, run, "先汇总火点")
    snap = rc.snapshot(1)
    assert snap["report"] == "第一章 内容"
    assert snap["think"] == "先汇总火点"
    assert snap["run"] == run


def test_subscribe_seeds_snapshot_as_first_frame():
    async def scenario():
        run = rc.begin_generation(2)
        rc.push_delta(2, run, "前半段")
        q = rc.subscribe(2)          # 新连接上线
        rc.push_delta(2, run, "后半段")  # 注册之后产生的增量必须进队列，不能只进副本
        # push 走 loop.call_soon_threadsafe，同循环内也要让出一轮才真正入队
        await asyncio.sleep(0)
        return run, _drain(q)

    run, frames = asyncio.run(scenario())
    assert frames[0]["type"] == "report_snapshot"
    assert frames[0]["report"] == "前半段"
    # 快照之后的实时增量照常投递：既不丢帧也不重复
    assert [f["type"] for f in frames[1:]] == ["report_delta"]
    assert frames[1]["text"] == "后半段"


def test_begin_generation_resets_copy_for_rewrite_round():
    r1 = rc.begin_generation(3)
    rc.push_delta(3, r1, "第一稿全文")
    r2 = rc.begin_generation(3)
    assert r2 == r1 + 1
    snap = rc.snapshot(3)
    # 新一轮尚未产出：不应把上一稿当作快照发给重连的客户端
    assert snap is None or snap["run"] == r2
    rc.push_delta(3, r2, "重写")
    assert rc.snapshot(3)["report"] == "重写"


def test_think_reset_truncates_copy():
    run = rc.begin_generation(4)
    rc.push_think(4, run, "正确的推理……然后开始复读复读复读")
    rc.push_think_reset(4, run, "正确的推理……")
    assert rc.snapshot(4)["think"] == "正确的推理……"


def test_drop_clears_copy_after_terminal():
    run = rc.begin_generation(5)
    rc.push_delta(5, run, "已成稿")
    rc.drop(5)
    assert rc.snapshot(5) is None


def test_buffer_count_is_capped():
    """任务在无人订阅时跑完就没人 drop，靠上限淘汰最旧的，避免无界增长"""
    for tid in range(rc._MAX_BUFFERED_TASKS + 20):
        run = rc.begin_generation(tid)
        rc.push_delta(tid, run, "x")
    assert len(rc._buffers) <= rc._MAX_BUFFERED_TASKS
    assert rc.snapshot(0) is None  # 最旧的已被淘汰


def test_buffer_char_cap_stops_growing():
    run = rc.begin_generation(6)
    chunk = "y" * 5000
    for _ in range(rc._MAX_BUFFER_CHARS // 5000 + 20):
        rc.push_delta(6, run, chunk)
    assert len(rc.snapshot(6)["report"]) <= rc._MAX_BUFFER_CHARS + 5000
