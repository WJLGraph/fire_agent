"""上传校验 — 体积上限、扩展名白名单、magic bytes 一致性

为什么必须在这里拦：知识库上传历史上是「客户端说是什么就是什么」——
`await file.read()` 把整个请求体一次性读进内存，扩展名原样拼进落盘路径，
内容再按扩展名猜解析器。后果依次是：

  1. 一个几十 MB 以上的文件就能把 worker 内存打满（本项目单进程 uvicorn，宝塔机上
     和 Postgres 抢内存）；
  2. 伪装扩展名（`evil.pdf` 实为 zip/HTML）走进 `read_text(errors="ignore")` 兜底分支，
     把二进制当正文切块入库，污染检索还白烧 embedding 配额；
  3. `Path(filename).suffix` 直接进落盘路径，虽然后面用 uuid 重命名挡住了穿越，
     但白名单才是「只允许解析器真能处理的类型」这件事的显式契约。

magic bytes 只判「文件头像不像它声称的类型」，不做防病毒级检测——那需要外部服务。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

#: 知识库单个文档上限（MB）。够放一份全省年度防火令 PDF，也够挡住误传的录像文件。
KB_MAX_MB = 50

#: 知识库允许的类型 = _extract_text 真正处理得了的类型。
#: 兜底分支（read_text errors=ignore）不算「支持」：它会把任何二进制喂进向量库。
KB_ALLOWED_EXT = {".pdf", ".txt", ".md"}

#: 图片（视觉识别）：与 media.py 既有白名单一致
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def sniff_magic(ext: str, head: bytes) -> bool:
    """文件头是否与该扩展名相符"""
    if ext == ".pdf":
        return head.startswith(b"%PDF-")
    if ext in (".jpg", ".jpeg"):
        return head[:3] == b"\xff\xd8\xff"
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if ext == ".bmp":
        return head[:2] == b"BM"
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    # 纯文本没有 magic 可判：交给下面的可打印性兜底
    if ext in (".txt", ".md"):
        return _looks_like_text(head)
    return True


def _looks_like_text(head: bytes) -> bool:
    """纯文本没有 magic，只能判「像不像文本」。

    口径是「排除法」而不是「ASCII 占比」：知识库正文大量是 UTF-8 中文，其字节全都
    >127，用可打印 ASCII 比例判会把正常中文文档当二进制拒掉。真正的二进制信号是
    NUL 和成片的控制字符（文本里 \t\n\r\f 之外的字节极罕见）。
    """
    if not head:
        return False
    if b"\x00" in head:
        return False
    allowed = {9, 10, 13, 12}          # \t \n \r \f
    controls = sum(1 for b in head if b < 32 and b not in allowed)
    return controls / len(head) < 0.05


async def read_limited(file: UploadFile, max_mb: int) -> bytes:
    """分块读取请求体，超过 max_mb 立即 413。

    不用 `await file.read()`：那会先把整个 body 读进内存再判长度，判的是「已经爆了
    之后的大小」。这里边读边判，超阈值当轮就断开，攻击者无法用一个大文件占住内存。
    """
    limit = max_mb * 1024 * 1024
    chunk_size = 1024 * 1024
    buf = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        buf += chunk
        if len(buf) > limit:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过 {max_mb}MB 上限（请拆分或压缩后上传）",
            )
    return bytes(buf)


def validate_upload(content: bytes, filename: str, allowed_ext: set[str],
                    max_mb: int) -> str:
    """校验并返回规范化的小写扩展名（含点）；不合法直接 400/413。"""
    if not content:
        raise HTTPException(status_code=400, detail="空文件")
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过 {max_mb}MB 上限")

    ext = Path(filename or "").suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {ext or '(无扩展名)'}；仅支持 "
                   + "、".join(sorted(e.lstrip('.') for e in allowed_ext)),
        )
    if not sniff_magic(ext, content[:8192]):
        raise HTTPException(
            status_code=400,
            detail=f"文件内容与扩展名不符（不是有效的 {ext.lstrip('.')} 文件）",
        )
    return ext
