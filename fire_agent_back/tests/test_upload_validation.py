"""上传校验回归（P1-1）。

运行：python -m pytest tests/test_upload_validation.py -q

覆盖：
- read_limited 边读边限体积（超限当轮就 413，不把整包读进内存）；
- validate_upload 的扩展名白名单 / magic bytes / 空文件；
- 知识库只放行解析器真能处理的类型（pdf/txt/md），伪装成 pdf 的二进制被挡。
"""
import pytest
from fastapi import HTTPException

from app.core.uploads import (
    KB_ALLOWED_EXT,
    KB_MAX_MB,
    read_limited,
    sniff_magic,
    validate_upload,
)


class _FakeUpload:
    """够喂 read_limited 的最小 UploadFile 替身：按预设分块吐出。"""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, size=-1):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def test_read_limited_streams_and_returns_bytes():
    import asyncio
    up = _FakeUpload([b"%PDF-1.7\n", b"hello"])
    out = asyncio.run(read_limited(up, 1))
    assert out == b"%PDF-1.7\nhello"


def test_read_limited_aborts_over_limit():
    """1MB 上限、每块 1MB：第二块一到就断开，不会继续读第三块。"""
    import asyncio
    up = _FakeUpload([b"x" * (1024 * 1024), b"x" * (1024 * 1024), b"should not be read"])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_limited(up, 1))
    assert exc.value.status_code == 413
    assert up._chunks == [b"should not be read"]  # 超限即断，剩余块没被消费


@pytest.mark.parametrize("ext,content", [
    (".pdf", b"%PDF-1.7 ..."),
    (".txt", b"yun nan fire season 2026"),
    (".md", b"# \xe7\x81\xab\xe9\x99\xa9\nbody text"),
])
def test_validate_upload_passes_whitelisted_types(ext, content):
    assert validate_upload(content, f"doc{ext}", KB_ALLOWED_EXT, KB_MAX_MB) == ext


def test_validate_upload_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as exc:
        validate_upload(b"GIF89a" + b"\x00" * 10, "x.gif", KB_ALLOWED_EXT, KB_MAX_MB)
    assert exc.value.status_code == 400


def test_validate_upload_rejects_spoofed_extension():
    """改名 .pdf 的 zip：magic 不符即拒，不能靠兜底分支把二进制喂进向量库。"""
    with pytest.raises(HTTPException) as exc:
        validate_upload(b"PK\x03\x04" + b"\x00" * 100, "evil.pdf", KB_ALLOWED_EXT, KB_MAX_MB)
    assert exc.value.status_code == 400
    assert "不符" in exc.value.detail


def test_validate_upload_rejects_empty_and_oversize():
    with pytest.raises(HTTPException) as exc:
        validate_upload(b"", "a.txt", KB_ALLOWED_EXT, KB_MAX_MB)
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc2:
        validate_upload(b"x" * (2 * 1024 * 1024), "a.txt", KB_ALLOWED_EXT, 1)
    assert exc2.value.status_code == 413


@pytest.mark.parametrize("ext,head,expected", [
    (".png", b"\x89PNG\r\n\x1a\n", True),
    (".png", b"GIF89a", False),
    (".jpg", b"\xff\xd8\xff\xe0", True),
    (".webp", b"RIFF\x00\x00\x00\x00WEBP", True),
    (".bmp", b"BM\x00\x00", True),
    (".gif", b"GIF87a", True),
    (".txt", b"plain text with \xe4\xb8\xad\xe6\x96\x87", True),
    (".txt", b"\x00\x01\x02\x03binary", False),   # NUL → 判为二进制
    (".exe", b"MZ\x90\x00", True),                 # 未登记类型不做假设，交给白名单
])
def test_sniff_magic(ext, head, expected):
    assert sniff_magic(ext, head) is expected
