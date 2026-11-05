"""
任务级报告流式通道（进程内、非持久）— P2#18

generate_report 节点流式产出报告时，通过本通道把增量内容实时推送给订阅该
任务的 SSE 连接（type=report_delta 帧）。

边界：
- 投递给订阅者的队列本身是易失的（满则丢帧保活）；
- 但**每个任务的当前轮次增量会在进程内留一份副本**（_buffers），新订阅者一上线
  就收到一帧 type=report_snapshot 补齐历史增量。这样「流式生成中切到别的页面
  再回来」「刷新页面」不会丢开头与中段——此前只能等终态用 DB 全文覆盖；
- 半截内容仍不落库：worker 只在节点完成后把完整报告写入状态/DB，DB 依旧是终态事实源；
- 无订阅者时 push 只更新副本，worker 照常执行不受影响。
"""
import asyncio
import threading

_lock = threading.Lock()
_subs: dict[int, set] = {}  # task_id -> {(loop, queue), ...}
_runs: dict[int, int] = {}  # task_id -> 报告生成轮次（评审退回/驳回重写时递增）

#: 单轮正文/思考副本的上限（字符）。报告量级只有几 KB，留足冗余；超限后停止累积，
#: 快照退化为「前缀 + 后续实时增量」，与改造前的行为一致，不会无界吃内存。
_MAX_BUFFER_CHARS = 200_000

#: task_id -> {"run": 轮次, "report": 正文副本, "think": 思考副本}
_buffers: dict[int, dict] = {}

#: 同时保留增量副本的任务数上限。终态连接会主动 drop，这里只是兜底：
#: 任务在无人订阅时跑完（用户提前关了页面）就没人来 drop，靠上限淘汰最旧的。
_MAX_BUFFERED_TASKS = 64


def _prune_locked() -> None:
    while len(_buffers) > _MAX_BUFFERED_TASKS:
        _buffers.pop(next(iter(_buffers)), None)


def _append(task_id: int, field: str, run: int, text: str) -> None:
    """在锁内累积本轮增量；轮次不一致（重写已开始）时先重置副本"""
    buf = _buffers.get(task_id)
    if not buf or buf["run"] != run:
        _buffers[task_id] = buf = {"run": run, "report": "", "think": ""}
        _prune_locked()
    cur = buf[field]
    if len(cur) < _MAX_BUFFER_CHARS:
        buf[field] = cur + text


def begin_generation(task_id: int) -> int:
    """开启新一轮报告生成（重写时再次调用，前端据此清空缓冲区），返回轮次号"""
    with _lock:
        _runs[task_id] = _runs.get(task_id, 0) + 1
        # 新一轮从零开始累积：旧轮正文/思考副本作废
        _buffers[task_id] = {"run": _runs[task_id], "report": "", "think": ""}
        _prune_locked()
        return _runs[task_id]


def snapshot(task_id: int) -> dict | None:
    """当前轮次的增量副本（供 SSE 新连接补齐）；无副本或全空返回 None"""
    with _lock:
        return _snapshot_locked(task_id)


def _snapshot_locked(task_id: int) -> dict | None:
    buf = _buffers.get(task_id)
    if not buf or not (buf["report"] or buf["think"]):
        return None
    return {"type": "report_snapshot", "run": buf["run"],
            "report": buf["report"], "think": buf["think"]}


def drop(task_id: int) -> None:
    """任务终态后丢弃副本：全文已落库，没必要再占内存"""
    with _lock:
        _buffers.pop(task_id, None)


def subscribe(task_id: int) -> asyncio.Queue:
    """SSE 处理器（事件循环内）订阅某任务的增长流；返回供 await 的队列

    注册与快照取同一把锁：先入队快照、再登记订阅者，保证「快照之后、登记之前」
    这段窗口里 push 的增量不会既不在快照里、也不进队列（既不丢也不重复）。
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=2000)
    loop = asyncio.get_running_loop()
    with _lock:
        snap = _snapshot_locked(task_id)
        if snap:
            q.put_nowait(snap)
        _subs.setdefault(task_id, set()).add((loop, q))
    return q


def unsubscribe(task_id: int, q: asyncio.Queue) -> None:
    with _lock:
        subscribers = _subs.get(task_id)
        if subscribers:
            for pair in list(subscribers):
                if pair[1] is q:
                    subscribers.discard(pair)
            if not subscribers:
                _subs.pop(task_id, None)


def _safe_put(q: asyncio.Queue, item: dict) -> None:
    try:
        q.put_nowait(item)
    except asyncio.QueueFull:
        pass  # 订阅端消费过慢时丢帧保活；终态完整内容以 DB 为准


def push_delta(task_id: int, run: int, text: str) -> None:
    """worker 线程调用：向该任务全部 SSE 订阅者投递增量（跨线程 loop 调度）"""
    with _lock:
        if text:
            _append(task_id, "report", run, text)
        subscribers = list(_subs.get(task_id, ()))
    for loop, q in subscribers:
        try:
            loop.call_soon_threadsafe(_safe_put, q, {"type": "report_delta", "run": run, "text": text})
        except RuntimeError:
            pass  # 事件循环已关闭（连接方断开），忽略


def push_think(task_id: int, run: int, text: str) -> None:
    """worker 线程调用：投递思考过程增量（type=report_think 帧，前端 DeepSeek 式「深度思考中」面板）"""
    with _lock:
        if text:
            _append(task_id, "think", run, text)
        subscribers = list(_subs.get(task_id, ()))
    for loop, q in subscribers:
        try:
            loop.call_soon_threadsafe(_safe_put, q, {"type": "report_think", "run": run, "text": text})
        except RuntimeError:
            pass  # 事件循环已关闭（连接方断开），忽略


def push_think_reset(task_id: int, run: int, keep_text: str) -> None:
    """复读截断通知（type=think_reset 帧）：前端把该轮实时思考替换为截断版
    （丢弃重复尾巴），随后的下一轮 report_think 以 run+1 到达即开新轮展示"""
    with _lock:
        buf = _buffers.get(task_id)
        if buf and buf["run"] == run:
            buf["think"] = keep_text  # 副本同步截断，重连快照不能再带重复尾巴
        subscribers = list(_subs.get(task_id, ()))
    for loop, q in subscribers:
        try:
            loop.call_soon_threadsafe(
                _safe_put, q, {"type": "think_reset", "run": run, "text": keep_text})
        except RuntimeError:
            pass  # 事件循环已关闭（连接方断开），忽略
