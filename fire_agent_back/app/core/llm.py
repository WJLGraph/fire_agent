"""
LangChain LLM & Embedding 客户端 — 多提供商支持

支持的提供商:
  - aliyun:  阿里百炼 / 任意 OpenAI 兼容 API
  - amd:     AMD GPU Cloud（OpenAI 兼容格式）
  - ollama:  本地 Ollama（OpenAI 兼容格式，无需 API Key）
  - longcat: LongCat API（OpenAI 兼容格式，仅 LLM）
"""
from datetime import datetime
import base64

import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import settings


# ===================== 提供商路由 =====================

def get_llm(**kwargs) -> ChatOpenAI | None:
    """
    获取 LLM 实例（根据活跃提供商自动路由）

    Args:
        **kwargs: 可传入 model, temperature, max_tokens 覆盖默认值
    """
    provider = settings.ACTIVE_LLM_PROVIDER
    if provider == "amd":
        return _get_amd_llm(**kwargs)
    if provider == "ollama":
        return _get_ollama_llm(**kwargs)
    if provider == "longcat":
        return _get_longcat_llm(**kwargs)
    return _get_aliyun_llm(**kwargs)


def get_embedding() -> OpenAIEmbeddings | None:
    """获取 Embedding 实例（固定走阿里百炼 — AMD GPU Cloud 不提供 Embedding 模型）"""
    if not settings.LLM_API_KEY:
        return None
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE or None,
        timeout=45,
        max_retries=1,
        # DashScope 兼容端点只接受字符串输入；LangChain 默认会先 tiktoken 切词
        # 再以 token 数组提交，会被百炼以 InvalidParameter 拒绝
        check_embedding_ctx_length=False,
    )


# ===================== 视觉 / 语音（恒定阿里百炼） =====================

def _bailian_base() -> str:
    """阿里百炼 OpenAI 兼容端点"""
    return (settings.LLM_API_BASE or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")


def get_vision_llm(**kwargs) -> ChatOpenAI | None:
    """视觉理解模型实例（按 VISION_PROVIDER 路由：aliyun 百炼 / amd GPU Cloud）"""
    if settings.VISION_PROVIDER == "amd":
        if not settings.AMD_API_KEY or not settings.VISION_MODEL:
            return None
        return ChatOpenAI(
            model=kwargs.get("model", settings.VISION_MODEL),
            api_key=settings.AMD_API_KEY,
            base_url=settings.AMD_API_BASE or "https://developer.amd.com.cn/radeon/v1",
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 2048),
            timeout=45,
            max_retries=1,
        )
    # 默认阿里百炼
    if not settings.LLM_API_KEY:
        return None
    return ChatOpenAI(
        model=kwargs.get("model", settings.VISION_MODEL),
        api_key=settings.LLM_API_KEY,
        base_url=_bailian_base(),
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens", 2048),
        timeout=45,
        max_retries=1,
    )


def vision_available() -> bool:
    """视觉模型是否可用"""
    if settings.VISION_PROVIDER == "amd":
        return bool(settings.AMD_API_KEY and settings.VISION_MODEL)
    return bool(settings.LLM_API_KEY and settings.VISION_MODEL)


def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    """
    语音识别（ASR）：音频字节 → 文本

    走百炼 OpenAI 兼容 /chat/completions 端点 + input_audio（data URI）格式，
    模型: ASR_MODEL（qwen3-asr-flash / paraformer-v2）。音频需为 wav/mp3 格式。
    返回识别文本；失败抛出异常。
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_KEY，语音识别不可用")
    # 推断音频 mime（前端已转为 wav）
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    mime = {"wav": "wav", "mp3": "mp3", "opus": "opus", "aac": "aac", "amr": "amr"}.get(ext, "wav")
    b64 = base64.b64encode(file_bytes).decode()
    resp = httpx.post(
        f"{_bailian_base()}/chat/completions",
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        json={
            "model": settings.ASR_MODEL,
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "input_audio",
                    "input_audio": {"data": f"data:audio/{mime};base64,{b64}", "format": mime},
                }],
            }],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def synthesize_speech(text: str) -> bytes:
    """
    语音合成（TTS）：文本 → 音频字节（wav）

    按 TTS_PROVIDER 路由：
    - amd:  AMD GPU Cloud OmniVoice（POST {AMD_API_BASE}/audio/speech {model, input}，
            直接返回 wav 二进制；官方标注非商用），模型取 TTS_MODEL（如 OmniVoice）。
    - aliyun: 主路百炼原生 /api/v1/services/aigc/multimodal-generation/generation，
          模型 TTS_MODEL（qwen3-tts-flash），失败且配置了 AMD Key 时自动兜底 OmniVoice。
    返回音频二进制；两路均失败抛出异常。
    """
    text = text[:500]
    if settings.TTS_PROVIDER == "amd":
        return _amd_tts(text)
    # ---- aliyun 主路: 百炼 ----
    if settings.LLM_API_KEY:
        native_base = "https://dashscope.aliyuncs.com/api/v1"
        try:
            resp = httpx.post(
                f"{native_base}/services/aigc/multimodal-generation/generation",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json={"model": settings.TTS_MODEL, "input": {"text": text, "voice": "Cherry"}},
                timeout=120,
            )
            if resp.status_code != 200:
                # 解析百炼错误体（Arrearage 欠费 / InvalidApiKey 等），透出真实原因而非裸 400
                try:
                    err = resp.json()
                    raise RuntimeError(
                        f"百炼 TTS 错误 {err.get('code', resp.status_code)}: {err.get('message', '')[:160]}"
                    )
                except ValueError:
                    resp.raise_for_status()
            audio = resp.json().get("output", {}).get("audio", {})
            url = audio.get("url")
            if not url:
                raise RuntimeError("语音合成未返回音频 URL")
            audio_resp = httpx.get(url, timeout=60)
            audio_resp.raise_for_status()
            return audio_resp.content
        except Exception as primary_err:
            # 主路失败 → 落到 AMD 兜底；AMD 也未配置时原样抛出
            if not settings.AMD_API_KEY:
                raise
            primary_msg = str(primary_err)[:160]
        else:
            primary_msg = ""
    else:
        if not settings.AMD_API_KEY:
            raise RuntimeError("未配置 LLM_API_KEY，语音合成不可用")
        primary_msg = "未配置 LLM_API_KEY"

    # ---- aliyun 兜底: AMD GPU Cloud OmniVoice ----
    try:
        return _amd_tts(text)
    except Exception as amd_err:
        raise RuntimeError(f"语音合成失败（百炼: {primary_msg}；AMD 兜底: {amd_err})") from amd_err


def _amd_tts(text: str) -> bytes:
    """AMD GPU Cloud OmniVoice TTS：POST {AMD_API_BASE}/audio/speech {model, input} → wav 二进制"""
    if not settings.AMD_API_KEY:
        raise RuntimeError("未配置 AMD_API_KEY，AMD 语音合成不可用")
    resp = httpx.post(
        f"{settings.AMD_API_BASE.rstrip('/')}/audio/speech",
        headers={"Authorization": f"Bearer {settings.AMD_API_KEY}"},
        json={"model": settings.TTS_MODEL or "OmniVoice", "input": text},
        timeout=120,
    )
    if resp.status_code != 200:
        try:
            err = resp.json()
            msg = err.get("error", {}).get("message", "") if isinstance(err.get("error"), dict) else str(err)[:160]
        except ValueError:
            msg = resp.text[:160]
        raise RuntimeError(f"AMD OmniVoice 错误 {resp.status_code}: {msg}")
    return resp.content


def amd_ocr_pdf(file_path, max_pages: int = 60) -> str:
    """
    AMD MinerU 文档识别：PDF 逐页渲染为 PNG → POST {AMD_API_BASE}/ocr → markdown 文本

    请求体: {"model": OCR_MODEL, "document": {"type": "image_url", "image_url": "data:image/png;base64,..."}}
    响应: {"pages": [{"index": 0, "markdown": "..."}]}
    适用于 GB/T 标准 PDF（文字层乱码）与扫描件，识别质量优于本地 RapidOCR。
    未配置 AMD Key 或全部失败时抛出异常（调用方自行降级本地 OCR）。
    """
    import base64

    import pymupdf  # PyMuPDF

    if not settings.AMD_API_KEY:
        raise RuntimeError("未配置 AMD_API_KEY，AMD 文档识别不可用")
    base = settings.AMD_API_BASE.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.AMD_API_KEY}"}
    doc = pymupdf.open(str(file_path))
    pages_text = []
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                pages_text.append(f"[提示：文档超过 {max_pages} 页，仅识别前 {max_pages} 页]")
                break
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))  # 2x 渲染保证中文小字号可识别
            b64 = base64.b64encode(pix.tobytes("png")).decode()
            resp = httpx.post(
                f"{base}/ocr",
                headers=headers,
                json={
                    "model": settings.OCR_MODEL or "MinerU2.5-Pro",
                    "document": {"type": "image_url", "image_url": f"data:image/png;base64,{b64}"},
                },
                timeout=180,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"AMD OCR 第 {i + 1} 页错误 {resp.status_code}: {resp.text[:120]}")
            md_pages = resp.json().get("pages", [])
            pages_text.append("\n".join(p.get("markdown", "") for p in md_pages))
    finally:
        doc.close()
    return "\n".join(pages_text)


def llm_available() -> bool:
    """检查当前活跃的 LLM 提供商是否可用"""
    provider = settings.ACTIVE_LLM_PROVIDER
    if provider == "amd":
        return bool(settings.AMD_API_KEY)
    if provider == "ollama":
        return bool(settings.OLLAMA_API_BASE)  # 本地 Ollama 无需 API Key
    if provider == "longcat":
        return bool(settings.LONGCAT_API_KEY)
    return bool(settings.LLM_API_KEY)


def list_provider_models(provider: str | None = None) -> list[str]:
    """
    获取指定提供商可用模型列表（调用 OpenAI 兼容 /models 端点）

    返回模型 id 列表；Key 未配置或请求失败时返回空列表。
    """
    provider = provider or settings.ACTIVE_LLM_PROVIDER
    if provider == "amd":
        base = settings.AMD_API_BASE or "https://developer.amd.com.cn/radeon/v1"
        key = settings.AMD_API_KEY
        if not key:
            return []
    elif provider == "ollama":
        base = settings.OLLAMA_API_BASE
        key = "ollama"  # Ollama 不校验 Key
        if not base:
            return []
    elif provider == "longcat":
        base = settings.LONGCAT_API_BASE or "https://api.longcat.chat/openai"
        key = settings.LONGCAT_API_KEY
        if not key:
            return []
    else:  # aliyun
        base = settings.LLM_API_BASE or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        key = settings.LLM_API_KEY
        if not key:
            return []
    try:
        resp = httpx.get(
            f"{base.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [m.get("id") for m in data if m.get("id")]
    except Exception:
        return []


# ===================== 阿里云 / 通用 OpenAI 兼容 =====================

def _get_aliyun_llm(**kwargs) -> ChatOpenAI | None:
    """阿里百炼 LLM 实例（enable_thinking=False 可关闭思考型模型的 reasoning——
    长思考会吃满 max_tokens 导致正文 content 为空，报告等长文输出必须关闭）"""
    if not settings.LLM_API_KEY:
        return None
    extra_body = None
    if kwargs.get("enable_thinking") is not None:
        extra_body = {"enable_thinking": bool(kwargs["enable_thinking"])}
    return ChatOpenAI(
        model=kwargs.get("model", settings.LLM_MODEL),
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE or None,
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens", 2048),
        extra_body=extra_body,
        timeout=45,
        max_retries=1,
    )


# ===================== AMD GPU Cloud =====================

def _get_amd_llm(**kwargs) -> ChatOpenAI | None:
    """AMD GPU Cloud LLM 实例（含 Qwen3.8-Flash-Next 时间窗口校验）

    enable_thinking=False 实测有效形式：extra_body={"chat_template_kwargs": {"enable_thinking": false}}
    （AMD 端点为 vLLM 系；直接传 enable_thinking 会被忽略，思考 token 会吃满 max_tokens
    导致正文为空/结构化输出失败）。enable_thinking=True 或缺省 → 保持端点默认（带思考）。
    """
    if not settings.AMD_API_KEY:
        return None
    # 模型选择：优先使用 kwargs 参数，否则使用配置的默认模型
    model = kwargs.get("model", settings.AMD_MODEL or "DeepSeek-V4-Flash")
    # Qwen3.8-Flash 系列免费模型需时间窗口校验（Qwen3.8-27B 等付费专属模型不受限）
    if "qwen3.8-flash" in model.lower():
        if not is_qwen3_8_available():
            return None  # 不在可用窗口内，返回 None 触发降级
    extra_body = None
    if kwargs.get("enable_thinking") is False:
        extra_body = {"chat_template_kwargs": {"enable_thinking": False}}
    # reasoning_effort：限制思考长度（实测 low → 报告级生成 ~40s；缺省思考可达 100s+ 且正文迟迟不出）
    effort = kwargs.get("reasoning_effort")
    if effort:
        extra_body = {**(extra_body or {}), "reasoning_effort": str(effort)}
    return ChatOpenAI(
        model=model,
        api_key=settings.AMD_API_KEY,
        base_url=settings.AMD_API_BASE or "https://developer.amd.com.cn/radeon/v1",
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens", 2048),
        extra_body=extra_body,
        timeout=45,
        max_retries=1,
    )


# ===================== 本地 Ollama =====================

def _get_ollama_llm(**kwargs) -> ChatOpenAI | None:
    """本地 Ollama LLM 实例（OpenAI 兼容接口，无需 API Key）"""
    if not settings.OLLAMA_API_BASE:
        return None
    return ChatOpenAI(
        model=kwargs.get("model", settings.OLLAMA_MODEL),
        api_key="ollama",  # Ollama 不校验 Key，但 SDK 要求非空
        base_url=settings.OLLAMA_API_BASE,
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens", 2048),
        timeout=45,
        max_retries=1,
    )


# ===================== LongCat =====================

def _get_longcat_llm(**kwargs) -> ChatOpenAI | None:
    """LongCat LLM 实例（OpenAI 兼容接口，仅对话模型；不透传百炼专有 extra_body）"""
    if not settings.LONGCAT_API_KEY:
        return None
    return ChatOpenAI(
        model=kwargs.get("model", settings.LONGCAT_MODEL),
        api_key=settings.LONGCAT_API_KEY,
        base_url=settings.LONGCAT_API_BASE or "https://api.longcat.chat/openai",
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens", 2048),
        timeout=45,
        max_retries=1,
    )


def is_qwen3_8_available() -> bool:
    """
    检查 Qwen3.8-Flash-Next 模型是否在可用时间窗口内
    
    配置 QWEN3_8_FLASH_START / QWEN3_8_FLASH_END 定义时间窗口。
    若两个字段均为空，则视为始终可用。
    格式: "YYYY-MM-DD HH:MM:SS"
    """
    start_str = settings.QWEN3_8_FLASH_START
    end_str = settings.QWEN3_8_FLASH_END
    if not start_str or not end_str:
        return True  # 未配置时间窗口，视为可用
    try:
        now = datetime.now()
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        return start <= now <= end
    except (ValueError, TypeError):
        return True  # 格式解析错误，保守视为可用