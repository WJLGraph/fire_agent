"""
统一 LLM 调用层 — 重试 / 熔断 / 多 Provider 降级 / token 记账 / 结构化输出

所有 Agent / Service 的 LLM 调用统一走本模块（取代直接 llm.invoke），
保证生产可用性：
1. 重试：限流 / 超时 / 连接类异常指数退避重试（单 Provider 最多 3 次，1s/2s/4s）
2. 熔断：单 Provider 连续失败 ≥3 次则熔断 60s，期间直接跳过
3. 降级链：当前激活 Provider → 其余可用 Provider → 返回 None（调用方走规则兜底）
4. 审计：每次调用返回 token 用量与实际使用的 Provider，供 agent steps 落库展示
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Callable, Optional, Type, TypeVar

from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

# 降级链顺序：激活 Provider 优先，其余按固定顺序补充
_ALL_PROVIDERS = ("aliyun", "amd", "ollama", "longcat")


def _provider_chain() -> list[str]:
    active = settings.ACTIVE_LLM_PROVIDER or "aliyun"
    return [active] + [p for p in _ALL_PROVIDERS if p != active]


def _build_llm(provider: str, **kwargs):
    """构造指定 Provider 的 LLM 实例（复用 core/llm.py 的构建函数；未配置返回 None）"""
    from app.core import llm as _llm_mod
    if provider == "amd":
        return _llm_mod._get_amd_llm(**kwargs)
    if provider == "ollama":
        return _llm_mod._get_ollama_llm(**kwargs)
    if provider == "longcat":
        return _llm_mod._get_longcat_llm(**kwargs)
    return _llm_mod._get_aliyun_llm(**kwargs)


def _resolve_model(provider: str, kwargs: dict) -> str:
    """解析本次调用实际使用的模型名（显式指定优先，否则取该 Provider 的默认配置）"""
    if kwargs.get("model"):
        return str(kwargs["model"])
    if provider == "amd":
        return settings.AMD_MODEL or "DeepSeek-V4-Flash"
    if provider == "ollama":
        return settings.OLLAMA_MODEL or ""
    if provider == "longcat":
        return settings.LONGCAT_MODEL or ""
    return settings.LLM_MODEL or ""


# ===================== 简单熔断器（内存态，进程内共享） =====================

class _Breaker:
    """连续失败计数熔断：失败达阈值进入 open 状态，冷却期后放行一次探测"""

    def __init__(self, threshold: int = 3, cooldown: float = 60.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.consecutive_failures = 0
        self.opened_at: float = 0.0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.consecutive_failures < self.threshold:
                return True
            return (time.monotonic() - self.opened_at) >= self.cooldown

    def record_success(self) -> None:
        with self._lock:
            self.consecutive_failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.threshold:
                self.opened_at = time.monotonic()


_BREAKERS: dict[str, _Breaker] = {}
_BREAKERS_LOCK = threading.Lock()


def breaker_status() -> dict:
    """熔断器快照（供「系统能力」面板展示；线程安全只读拷贝）"""
    with _BREAKERS_LOCK:
        snap = {}
        for provider, b in _BREAKERS.items():
            opened = b.consecutive_failures >= b.threshold
            remaining = 0.0
            if opened:
                remaining = max(0.0, b.cooldown - (time.monotonic() - b.opened_at))
            snap[provider] = {
                "open": opened,
                "consecutive_failures": b.consecutive_failures,
                "threshold": b.threshold,
                "cooldown": b.cooldown,
                "remaining": round(remaining, 1),
            }
        return snap


def _breaker(provider: str) -> _Breaker:
    with _BREAKERS_LOCK:
        if provider not in _BREAKERS:
            _BREAKERS[provider] = _Breaker()
        return _BREAKERS[provider]


# ===================== 调用结果 =====================

@dataclass
class LLMResult:
    """LLM 调用结果（text 为响应文本；tokens/provider/model 供审计）"""
    text: str
    provider: str = ""
    tokens: dict = field(default_factory=dict)
    degraded: bool = False  # 是否发生了跨 Provider 降级
    model: str = ""         # 实际使用的模型名（详细展示用，如 qwen-max）


def _extract_tokens(resp) -> dict:
    """从 LangChain AIMessage 提取 token 用量（兼容不同 provider 返回）"""
    try:
        meta = getattr(resp, "response_metadata", None) or {}
        usage = meta.get("token_usage") or {}
        if not usage:
            usage = getattr(resp, "usage_metadata", None) or {}
        out = {}
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = usage.get(k)
            if isinstance(v, (int, float)):
                out[k] = int(v)
        return out
    except Exception:
        return {}


def _extract_text(resp) -> str:
    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    # 多模态/分块内容兜底
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(resp)


def _extract_reasoning(chunk) -> str:
    """提取流式 chunk 中的思考增量（ reasoning / reasoning_content 字段）。

    实测 AMD GPU Cloud（及多数 vLLM 系 OpenAI 兼容端点）思考型模型把思考过程放在
    delta.reasoning（非 content、非 <think> 标签），LangChain 收进 additional_kwargs；
    不提取则整个思考阶段 content 为空 → 前端长时间"等待输出"且无思考展示。
    """
    kw = getattr(chunk, "additional_kwargs", None) or {}
    r = kw.get("reasoning") or kw.get("reasoning_content") or ""
    return str(r) if r else ""


def _retryable(exc: Exception) -> bool:
    """判定异常是否可重试（限流/超时/连接类）；鉴权、参数错误不重试直接换 Provider"""
    import openai
    return isinstance(exc, (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.InternalServerError,
    ))


def _is_timeout(exc: Exception) -> bool:
    """超时类异常：服务端挂起/无响应（实测 AMD 免费端点会偶发挂死连接）。
    原地等待 1s/2s/4s 重试无意义，应立即熔断本 Provider 并切换下一个。"""
    import openai
    return isinstance(exc, openai.APITimeoutError)


# 总时限（读超时只约束"字节间隔"，防不住本地小模型逐 token 慢速生成的合法流）：
# 非流式调用超过该时限仍未完成 → 视同超时，切换下一个 Provider。
# 实测参考：CPU 跑 4B 模型约 1 token/s，2000 token 要 30 分钟，必须有时限兜底。
_INVOKE_DEADLINE = 120.0
# 流式总时限：读超时只约束"字节间隔"，本地小模型逐 token 慢速输出可合法地拖很久
# （实测 2B 模型 ~3 token/s，4000 token 要 20+ 分钟）。超时中止流，让调用方
# 走非流式或模板兜底，避免任务永远停在"生成报告"。
# 实测 AMD 免费端点冷启动排队可达 ~100s 才出首个 chunk，150s 会误杀合法长流 → 放宽到 240s。
_STREAM_DEADLINE = 240.0
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-call")


def _call_with_deadline(fn):
    """带总时限的阻塞调用；超时抛 TimeoutError（底层线程随生成结束自行回收）"""
    fut = _EXECUTOR.submit(fn)
    try:
        return fut.result(timeout=_INVOKE_DEADLINE)
    except FuturesTimeoutError:
        raise TimeoutError(f"LLM 调用超过 {_INVOKE_DEADLINE:.0f}s 总时限") from None


_RETRY_DELAYS = (1.0, 2.0, 4.0)


# ===================== 对外接口 =====================

def invoke_llm(
    prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
    enable_thinking: bool | None = None,
) -> LLMResult | None:
    """
    统一 LLM 文本调用入口。

    成功返回 LLMResult；所有 Provider 均失败返回 None（调用方自行走规则兜底）。
    enable_thinking=False：关闭思考型模型的 reasoning（防长思考吃满 max_tokens 导致正文为空）。
    """
    active = settings.ACTIVE_LLM_PROVIDER or "aliyun"
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if model is not None:
        kwargs["model"] = model
    if enable_thinking is not None:
        kwargs["enable_thinking"] = enable_thinking

    for provider in _provider_chain():
        breaker = _breaker(provider)
        if not breaker.allow():
            continue
        llm = _build_llm(provider, **kwargs)
        if llm is None:  # 该 Provider 未配置，跳过
            continue
        last_exc: Exception | None = None
        for attempt, delay in enumerate((None,) + _RETRY_DELAYS):
            if delay:
                time.sleep(delay)
            try:
                resp = _call_with_deadline(lambda: llm.invoke(prompt))
                breaker.record_success()
                return LLMResult(
                    text=_extract_text(resp),
                    provider=provider,
                    tokens=_extract_tokens(resp),
                    degraded=(provider != active),
                    model=_resolve_model(provider, kwargs),
                )
            except Exception as e:
                last_exc = e
                if not _retryable(e) or _is_timeout(e):
                    break  # 不可重试或超时（服务端挂起）→ 直接换下一个 Provider
        breaker.record_failure()
    return None


def invoke_structured(
    prompt: str,
    schema: Type[T],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    fallback: Optional[Callable[[str], Optional[T]]] = None,
) -> tuple[Optional[T], Optional[LLMResult]]:
    """
    统一 LLM 结构化输出入口。

    优先 with_structured_output（function calling）；Provider 不支持或调用失败时，
    降级为文本调用 + fallback(text) 解析。两级都失败返回 (None, None)。

    Args:
        fallback: 文本解析兜底函数（输入原始文本，返回 schema 实例或 None）
    Returns:
        (结构化对象, 调用元信息)；对象可能来自结构化输出或 fallback 解析
    """
    active = settings.ACTIVE_LLM_PROVIDER or "aliyun"
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    # 结构化输出走 function calling：思考型模型（qwen3.x 等）必须关闭思考，
    # 否则 reasoning 先吃满 max_tokens，正文为空触发 LengthFinishReasonError
    kwargs["enable_thinking"] = False
    # 显式传入的 max_tokens 优先（如 parse_task 传 300 控制首事件静默窗口）；
    # 未传时给 2000 兜底（防思考型模型 reasoning 吃满导致正文截断）
    if not kwargs.get("max_tokens"):
        kwargs["max_tokens"] = 2000

    # —— 第一级：结构化输出 ——
    for provider in _provider_chain():
        breaker = _breaker(provider)
        if not breaker.allow():
            continue
        llm = _build_llm(provider, **kwargs)
        if llm is None:
            continue
        try:
            structured = llm.with_structured_output(schema)
        except Exception:
            break  # 当前栈不支持结构化 → 直接走文本降级
        for delay in (None,) + _RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            try:
                obj = _call_with_deadline(lambda: structured.invoke(prompt))
                breaker.record_success()
                if obj is not None:
                    return obj, LLMResult(
                        text="",
                        provider=provider,
                        degraded=(provider != active),
                        model=_resolve_model(provider, kwargs),
                    )
                break  # 空响应 → 换下一个 Provider
            except Exception as e:
                if not _retryable(e) or _is_timeout(e):
                    break  # 不可重试或超时（服务端挂起）→ 直接换下一个 Provider
        breaker.record_failure()

    # —— 第二级：文本调用 + fallback 解析 ——
    if fallback is not None:
        res = invoke_llm(prompt, temperature=temperature, max_tokens=max_tokens)
        if res is not None:
            try:
                obj = fallback(res.text)
                if obj is not None:
                    return obj, res
            except Exception:
                pass
    return None, None


def _stream_amd_raw(prompt: str, kwargs: dict):
    """AMD 端点专用流式（原生 OpenAI SDK，绕过 LangChain 解析）。

    实测 langchain-openai 0.3.0 构造 AIMessageChunk 时会丢弃非标的 delta.reasoning
    字段（additional_kwargs 为空），思考增量在 LangChain 层即丢失。本生成器直接读
    原生 SDK 的 delta.reasoning / delta.content，产出与 stream_llm 相同契约的事件：
      {"type": "think", "text": str} / {"type": "delta", "text": str}
    """
    from openai import OpenAI
    model = kwargs.get("model") or settings.AMD_MODEL or "DeepSeek-V4-Flash"
    if "qwen3.8-flash" in model.lower():
        from app.core.llm import is_qwen3_8_available
        if not is_qwen3_8_available():
            return  # 不在可用窗口：不产出任何事件，外层按该 Provider 无产出换下一通道
    client = OpenAI(
        api_key=settings.AMD_API_KEY,
        base_url=settings.AMD_API_BASE or "https://developer.amd.com.cn/radeon/v1",
        timeout=45,
        max_retries=1,
    )
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    if kwargs.get("temperature") is not None:
        body["temperature"] = kwargs["temperature"]
    if kwargs.get("max_tokens") is not None:
        body["max_tokens"] = kwargs["max_tokens"]
    extra: dict = {}
    if kwargs.get("enable_thinking") is False:
        extra["chat_template_kwargs"] = {"enable_thinking": False}  # 实测唯一生效的关思形式
    if kwargs.get("reasoning_effort"):
        extra["reasoning_effort"] = str(kwargs["reasoning_effort"])  # 限思（low → 报告级 ~40s）
    if extra:
        body["extra_body"] = extra
    stream = client.chat.completions.create(**body)
    for ev in stream:
        choices = getattr(ev, "choices", None)
        if not choices:
            continue
        d = choices[0].delta
        ex = getattr(d, "model_extra", None) or {}
        r = ex.get("reasoning") or ex.get("reasoning_content") or ""
        if r:
            yield {"type": "think", "text": str(r)}
        if d.content:
            yield {"type": "delta", "text": str(d.content)}


def _closing(iterable):
    """包装流式迭代器：消费方提前 break/return 时主动 close 底层流（释放 HTTP 连接）。

    复读循环中断 / 思考超限 / 取消等场景会中途退出消费循环，不包装的话
    底层生成器要等 GC 才回收，OpenAI 兼容端点的连接会悬挂到 socket 超时。
    """
    it = iter(iterable)
    try:
        for item in it:
            yield item
    finally:
        close = getattr(it, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                pass


def stream_llm(
    prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
    enable_thinking: bool | None = None,
    reasoning_effort: str | None = None,
):
    """统一 LLM 流式文本生成入口（P2#18，与 invoke_llm 同级的流式通道）。

    逐 chunk 产出事件字典：
      {"type": "think", "text": str}                                        思考增量（reasoning 字段，0~n 条）
      {"type": "delta", "text": str}                                        增量内容（0~n 条）
      {"type": "meta",  "provider": str, "degraded": bool, "tokens": dict}  成功终态
      {"type": "error", "message": str}                                     失败终态（所有通道不可用）

    复用 invoke_llm 的 Provider 降级链 + 熔断器 + 重试；差别在于：仅在尚未产出
    任何内容前才允许重试/换 Provider（半截内容无法跨通道续写），已产出的 delta
    是否丢弃重试由调用方决定。
    enable_thinking=False：关闭思考型模型的 reasoning（同 invoke_llm，防长思考
    吃满 max_tokens 导致正文为空）。
    """
    active = settings.ACTIVE_LLM_PROVIDER or "aliyun"
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if model is not None:
        kwargs["model"] = model
    if enable_thinking is not None:
        kwargs["enable_thinking"] = enable_thinking
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort

    for provider in _provider_chain():
        breaker = _breaker(provider)
        if not breaker.allow():
            continue
        llm = _build_llm(provider, **kwargs)
        if llm is None:
            continue
        produced = False
        last_exc: Exception | None = None
        for delay in (None,) + _RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            started = time.monotonic()
            try:
                meta = {"type": "meta", "provider": provider,
                        "degraded": provider != active, "tokens": {},
                        "model": _resolve_model(provider, kwargs)}
                timed_out = False
                # AMD 走原生 SDK 通道（LangChain 0.3.0 丢弃 delta.reasoning，思考增量会丢）；
                # 原生通道直接产出 {"type": "think"/"delta"} 事件字典，其余 Provider 走 LangChain chunk
                # _closing 包装：消费方提前退出（循环中断/超时/取消）时主动关闭底层流
                if provider == "amd":
                    chunk_iter = _closing(_stream_amd_raw(prompt, kwargs))
                else:
                    chunk_iter = _closing(llm.stream(prompt))
                for chunk in chunk_iter:
                    if time.monotonic() - started > _STREAM_DEADLINE:
                        timed_out = True
                        break
                    if isinstance(chunk, dict):  # 原生 SDK 事件（AMD 通道）
                        if chunk.get("type") == "think":
                            produced = True  # 思考增量也是产出：不可跨通道续写
                            yield {"type": "think", "text": chunk.get("text", "")}
                        else:
                            text = chunk.get("text", "")
                            if text:
                                produced = True
                                yield {"type": "delta", "text": text}
                    else:  # LangChain AIMessageChunk（其余 Provider）
                        think = _extract_reasoning(chunk)
                        if think:
                            produced = True  # 思考增量也是产出：不可跨通道续写
                            yield {"type": "think", "text": think}
                        text = _extract_text(chunk)
                        if text:
                            produced = True
                            yield {"type": "delta", "text": text}
                    usage = _extract_tokens(chunk)
                    if usage:
                        meta["tokens"] = usage
                if timed_out:
                    breaker.record_failure()
                    yield {"type": "error",
                           "message": f"流式生成超过 {_STREAM_DEADLINE:.0f}s 总时限，已中止"}
                    return
                breaker.record_success()
                yield meta
                return
            except Exception as e:
                last_exc = e
                if produced or not _retryable(e) or _is_timeout(e):
                    break  # 已产出内容（无法跨通道续写）/ 不可重试 / 超时（服务端挂起）→ 换下一个 Provider
        breaker.record_failure()
    yield {"type": "error", "message": str(last_exc or "所有 LLM 通道均不可用")[:200]}
