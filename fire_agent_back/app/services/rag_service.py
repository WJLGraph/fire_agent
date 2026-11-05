"""
RAG 知识库服务 — 文档上传、切分、向量化、检索增强问答

Agent 风格：RagAgent 通过本服务完成「向量召回 + 关键词召回」混合检索，
并输出检索过程元数据（命中片段、向量分、关键词分、来源文档），供前端展示。
"""
import os
import re
import json
import uuid
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm import get_llm, get_embedding, llm_available
from app.core.llm_invoker import invoke_llm, stream_llm
from app.core.reranker import rerank
from app.models.kb_document import KbDocument, KbChunk

# 中文停用词（检索时过滤，避免"的/了/什么"这类词拉低命中）
_STOP_WORDS = set(
    "的 了 是 在 和 与 及 或 中 有 用 把 被 让 给 对 从 向 为 就 都 也 还 又 很 更 最 "
    "吗 呢 啊 吧 呀 哦 喔 嗯 啥 哪 什么 怎么 怎样 如何 为什么 哪些 哪个 是否 可以 "
    "请 帮 我 你 他 她 它 们 这 那 该 此 其 以及 一个 一种 一些 进行 应该 需要 必须 "
    "提供 了解 查询 回答 说明 相关".split()
)
# 疑问/句式通用词：仅出现在此类词中的 n-gram 无检索价值
_QUESTION_WORDS = set(
    "应该 采取 什么 措施 如何 怎样 怎么 为什么 是否 可以 需要 必须 进行 提供 说明 回答 "
    "请 帮 我 一个 一种 一些 哪些 哪个 情况 时候 原因 方面 处理 应对 办法 方式 步骤".split()
)

# 中文数字 → 阿拉伯数字
_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _num2cn(n: int) -> str:
    """阿拉伯数字转中文数字（仅 1-10，用于"4级"→"四级"归一化）"""
    mapping = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
               6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}
    return mapping.get(n, str(n))


class _ThinkFilter:
    """流式拆分 <think>…</think> 推理片段（qwen3 / DeepSeek-R1 系模型会输出思考过程）

    标签可能被切分在相邻 chunk 中（如 "<th" + "ink>"），用有状态过滤器处理：
    - 思考内容捕获到 _think（供前端「思考过程」折叠面板展示），增量只放行最终回答；
    - 尾部保留可能是未完整标签前缀的字符，待下一个 chunk 拼接后重新判定。
    """

    _OPEN, _CLOSE = "<think>", "</think>"

    def __init__(self):
        self._in_think = False
        self._buf = ""
        self._emitted: list[str] = []
        self._think: list[str] = []
        self._think_delta = ""   # 未推送的思考增量（take_think_delta 取走）

    @staticmethod
    def _partial_len(buf: str, tag: str) -> int:
        """buf 尾部可能是 tag 前缀的最大长度（0 = 无可疑前缀，可整体放行）"""
        for k in range(min(len(buf), len(tag) - 1), 0, -1):
            if tag.startswith(buf[-k:]):
                return k
        return 0

    def feed(self, text: str) -> str:
        """喂入一个增量，返回本次应输出的干净文本（可能为空）"""
        self._buf += text
        out: list[str] = []
        while self._buf:
            if self._in_think:
                end = self._buf.find(self._CLOSE)
                if end >= 0:
                    self._push_think(self._buf[:end])
                    self._buf = self._buf[end + len(self._CLOSE):]
                    self._in_think = False
                    continue
                keep = self._partial_len(self._buf, self._CLOSE)
                if keep:
                    self._push_think(self._buf[:len(self._buf) - keep])
                    self._buf = self._buf[len(self._buf) - keep:]
                else:
                    self._push_think(self._buf)
                    self._buf = ""
                break
            start = self._buf.find(self._OPEN)
            if start >= 0:
                out.append(self._buf[:start])
                self._buf = self._buf[start + len(self._OPEN):]
                self._in_think = True
                continue
            keep = self._partial_len(self._buf, self._OPEN)
            if keep:
                out.append(self._buf[:-keep])
                self._buf = self._buf[-keep:]
            else:
                out.append(self._buf)
                self._buf = ""
            break
        chunk = "".join(out)
        if chunk:
            self._emitted.append(chunk)
        return chunk

    def _push_think(self, s: str) -> None:
        """思考增量入账（_think 供终态落库；_think_delta 供流式逐段推送前端）"""
        if not s:
            return
        self._think.append(s)
        self._think_delta += s

    def take_think_delta(self) -> str:
        """取走自上次调用以来新增的思考增量（流式"深度思考中"展示）"""
        d, self._think_delta = self._think_delta, ""
        return d

    def finish(self) -> str:
        """流结束：吐出扣留的尾巴；若中断在思考中，剩余内容归入思考（不再放行正文）"""
        tail, self._buf = self._buf, ""
        if self._in_think:
            if tail:
                self._push_think(tail)
            return ""
        if tail:
            self._emitted.append(tail)
        return tail

    def text(self) -> str:
        """全部干净文本（供终态落库）"""
        return "".join(self._emitted)

    def think_text(self) -> str:
        """捕获到的思考过程（供前端折叠面板展示）"""
        return "".join(self._think).strip()


_THINK_OPEN_RE = re.compile(r"<think>([\s\S]*?)</think>\s*")


def _split_think(text: str) -> tuple[str, str]:
    """拆分推理内容与最终回答 → (reasoning, answer)

    兼容三种形态（qwen3 / DeepSeek 系模型，含历史脏数据）：
    - 成对 ``<think>…</think>``        → 思考入 reasoning，其余入 answer；
    - 未闭合 ``<think>…``（流中断）    → 其后内容入 reasoning，前置文字保留在 answer；
    - 孤立 ``</think>``（开头标签缺失的旧数据）→ 之前全部视作思考，之后为回答。
    """
    if not text:
        return "", ""
    clean = str(text)
    reasoning: list[str] = []

    def _capture(m: "re.Match") -> str:
        reasoning.append(m.group(1).strip())
        return ""

    clean = _THINK_OPEN_RE.sub(_capture, clean)
    if "<think>" in clean:
        idx = clean.find("<think>")
        reasoning.append(clean[idx + len("<think>"):].strip())
        clean = clean[:idx]
    elif "</think>" in clean:
        pre, _, post = clean.partition("</think>")
        reasoning.append(pre.strip())
        clean = post
    return "\n".join(r for r in reasoning if r), clean.strip()


def _strip_think(text: str) -> str:
    """仅取剥离思考后的正文（播报/落库等场景）"""
    return _split_think(text)[1]


def _extract_keywords(text: str) -> list[str]:
    """提取中文检索关键词：
    1. 英文/数字整体保留
    2. "4级" → "四级" 归一化（提升数字等级命中率）
    3. 2 字词为主（最可靠），3 字词补充
    4. 过滤停用词与疑问句式词
    """
    # 数字等级归一化：4级 → 四级
    text = re.sub(r"([0-9]+)级", lambda m: _num2cn(int(m.group(1))) + "级", text)
    text = re.sub(r"([一二三四五六七八九十])级", lambda m: m.group(1) + "级", text)

    words = set()
    for m in re.finditer(r"[A-Za-z0-9]+", text):
        words.add(m.group(0).lower())

    for seg in re.split(r"[^\u4e00-\u9fa5]+", text):
        seg = seg.strip()
        if len(seg) < 2:
            continue
        # 2 字词（主）+ 3 字词（辅）+ 完整短语
        for n in (2, 3):
            for i in range(len(seg) - n + 1):
                w = seg[i:i + n]
                if w not in _STOP_WORDS and not any(q in w for q in _QUESTION_WORDS):
                    words.add(w)
        if len(seg) <= 4 and seg not in _STOP_WORDS and not any(q in seg for q in _QUESTION_WORDS):
            words.add(seg)

    return [w for w in words if len(w) >= 2]


def _parse_embedding(raw) -> np.ndarray | None:
    """解析数据库中存储的向量（JSON 字符串）"""
    if not raw:
        return None
    try:
        if isinstance(raw, (list, tuple)):
            arr = np.asarray(raw, dtype=float)
        else:
            arr = np.asarray(json.loads(raw), dtype=float)
        if arr.ndim != 1 or arr.size == 0:
            return None
        return arr
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """余弦相似度"""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# Adaptive RAG（P1 #10）：复杂度判定线索（短查询且不含这些线索 → simple 直通）
_COMPLEX_HINTS = ("为什么", "如何", "怎么", "对比", "分析", "建议", "哪些", "区别", "措施", "方案", "流程", "应该")


def _classify_query_complexity(query: str) -> str:
    """简单规则分类：simple（直通检索一次）/ complex（多轮改写检索环）"""
    if len(query) < 12 and not any(h in query for h in _COMPLEX_HINTS):
        return "simple"
    return "complex"


class RagService:
    """RAG 知识库服务"""

    def __init__(self, db: Session):
        self.db = db
        self.llm = get_llm()
        self.embed = get_embedding()

    # ──────────────────────────────────────
    # 文档管理
    # ──────────────────────────────────────

    def upload_document(self, file_bytes: bytes, filename: str, category: str = "other", user_id: int = None) -> dict:
        """上传文档，保存文件并入库（user_id 记录归属用户，实现数据隔离）"""
        # 确保上传目录存在
        upload_dir = Path(settings.KB_UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_id = str(uuid.uuid4())[:8]
        ext = Path(filename).suffix
        save_path = upload_dir / f"{file_id}{ext}"
        with open(save_path, "wb") as f:
            f.write(file_bytes)

        # 提取文本（返回 (文本, 错误信息)，文本为 None 表示失败）
        content, extract_err = self._extract_text(save_path, ext)

        # 创建文档记录
        doc = KbDocument(
            user_id=user_id,
            title=filename,
            category=category,
            source_path=str(save_path),
            file_type=ext.lstrip("."),
            status="processing",
        )
        self.db.add(doc)
        self.db.flush()

        # 切分并向量化
        if content and content.strip():
            chunks = self._chunk_text(content, doc.id)
            for chunk in chunks:
                self.db.add(chunk)
            doc.status = "ready"
            doc.summary = content[:200] + "..." if len(content) > 200 else content
            chunk_count = len(chunks)
        else:
            doc.status = "failed"
            doc.summary = extract_err or "文本提取失败：该文件可能是扫描件（无文字层）或格式不受支持，请改用可复制的 PDF/TXT/MD 文档。"
            chunk_count = 0

        self.db.commit()
        return {"id": doc.id, "title": doc.title, "status": doc.status,
                "chunks": chunk_count, "error": None if doc.status == "ready" else doc.summary}

    def list_documents(self, user_id: int = None, is_admin: bool = False) -> list[dict]:
        """文档列表（普通用户仅自己的，管理员可见全部）"""
        q = self.db.query(KbDocument)
        if not is_admin:
            q = q.filter(KbDocument.user_id == user_id)
        docs = q.order_by(KbDocument.created_at.desc()).all()
        return [
            {"id": d.id, "title": d.title, "category": d.category, "status": d.status, "summary": d.summary,
             "file_type": d.file_type, "chunk_count": len(d.chunks) if d.chunks else 0,
             "created_at": str(d.created_at) if d.created_at else ""}
            for d in docs
        ]

    def get_document_content(self, doc_id: int, user_id: int = None, is_admin: bool = False) -> tuple | None:
        """文档全文阅读：按分片序号拼接正文，返回 (标题, 正文, 分片数)；无权限/不存在返回 None"""
        from app.models.kb_document import KbDocument, KbChunk

        doc = (
            self.db.query(KbDocument)
            .filter(KbDocument.id == doc_id)
            .first()
        )
        if not doc:
            return None
        if not is_admin and doc.user_id not in (None, user_id):
            return None
        chunks = (
            self.db.query(KbChunk)
            .filter(KbChunk.document_id == doc_id)
            .order_by(KbChunk.chunk_index.asc())
            .all()
        )
        text = "\n\n".join((c.content or "").strip() for c in chunks if (c.content or "").strip())
        return doc.title, text, len(chunks)

    def get_document_file(self, doc_id: int, user_id: int = None, is_admin: bool = False) -> tuple | None:
        """原始文件阅读：返回 (标题, 源文件路径, 文件类型)；无权限/不存在/文件缺失返回 None"""
        from app.models.kb_document import KbDocument

        doc = self.db.query(KbDocument).filter(KbDocument.id == doc_id).first()
        if not doc:
            return None
        if not is_admin and doc.user_id not in (None, user_id):
            return None
        if not doc.source_path or not Path(doc.source_path).exists():
            return None
        return doc.title, doc.source_path, (doc.file_type or "").lower()

    def delete_document(self, doc_id: int, user_id: int = None, is_admin: bool = False) -> bool:
        """删除文档（仅本人或管理员）"""
        doc = self.db.query(KbDocument).get(doc_id)
        if not doc:
            return False
        if not is_admin and doc.user_id != user_id:
            return False
        # 删除文件
        if doc.source_path and os.path.exists(doc.source_path):
            os.remove(doc.source_path)
        # 删除关联分片
        self.db.query(KbChunk).filter(KbChunk.document_id == doc_id).delete()
        self.db.delete(doc)
        self.db.commit()
        return True

    # ──────────────────────────────────────
    # 检索与问答
    # ──────────────────────────────────────

    def retrieve(self, query: str, top_k: int = None, user_id: int = None, is_admin: bool = False) -> dict:
        """混合检索（P1 #9）：关键词/向量双通道 Top60 → RRF 融合 → Rerank 精排

        用户隔离：普通用户只检索自己的文档分片，管理员检索全部。
        Rerank 失败/关闭时自动降级为 RRF 融合原序，不阻断检索。

        Returns:
            {
              "items": [ {id, document_id, document_title, content, score, vector_score, keyword_score, rerank_score?, ...} ],
              "total_chunks": 知识库分片总数,
              "matched_chunks": 融合候选数,
              "method": "hybrid" | "keyword" | "none"（精排成功时追加 "+rerank" 后缀）,
              "reranked": 是否经过 Rerank 精排,
              "keywords": [命中的关键词],
              "vector_enabled": 是否有向量可用,
            }
        """
        k = top_k or settings.KB_TOP_K
        # 可见文档（普通用户仅自己的，管理员全部）
        doc_q = self.db.query(KbDocument)
        if not is_admin:
            doc_q = doc_q.filter(KbDocument.user_id == user_id)
        total_docs = doc_q.count()
        failed_docs = doc_q.filter(KbDocument.status == "failed").count()
        failed_doc_titles = [d.title for d in doc_q.filter(KbDocument.status == "failed").all()]

        q = self.db.query(KbChunk)
        if not is_admin:
            q = q.join(KbDocument, KbChunk.document_id == KbDocument.id)\
                 .filter(KbDocument.user_id == user_id)
        chunks = q.filter(KbChunk.content.isnot(None)).all()

        if not chunks:
            return {
                "items": [], "total_chunks": 0, "matched_chunks": 0,
                "method": "none", "reranked": False, "keywords": [], "vector_enabled": False,
                "total_docs": total_docs, "failed_docs": failed_docs,
                "failed_doc_titles": failed_doc_titles,
            }

        # 1) 中文分词
        query_words = _extract_keywords(query)
        kw2 = [w for w in query_words if len(w) == 2]
        kw3 = [w for w in query_words if len(w) >= 3]

        # 2) 问题向量（用于余弦检索）
        query_vec = None
        vector_enabled = False
        if self.embed:
            try:
                qv = self.embed.embed_query(query)
                query_vec = np.asarray(qv, dtype=float)
                vector_enabled = True
            except Exception:
                query_vec = None

        # 3) 逐分片打分（全量打分，通道截断放在融合阶段）
        scored = []
        for c in chunks:
            content_lower = c.content.lower()
            # —— 关键词分：2 字词命中权重更高 ——
            hits2 = sum(1 for w in kw2 if w in content_lower)
            hits3 = sum(1 for w in kw3 if w in content_lower)
            kw_total = max(len(kw2) * 2 + len(kw3), 1)
            keyword_score = (hits2 * 2 + hits3) / kw_total

            # —— 向量分（余弦相似度） ——
            vec_score = 0.0
            if query_vec is not None:
                emb = _parse_embedding(c.embedding)
                if emb is not None:
                    vec_score = _cosine(query_vec, emb)

            # 任一命中即进入候选池
            if (hits2 + hits3) > 0 or vec_score > 0.05:
                scored.append({
                    "id": c.id,
                    "document_id": c.document_id,
                    "document_title": self._doc_title(c.document_id),
                    "content": c.content,
                    "keyword_score": round(keyword_score, 3),
                    "vector_score": round(vec_score, 3),
                    "score": round(max(keyword_score, vec_score), 3),
                })

        # 4) 双通道 Top60 → RRF 融合（rrf = Σ 1/(60+rank)，两通道命中叠加增益）
        _RRF_K = 60
        kw_ranked = sorted([x for x in scored if x["keyword_score"] > 0],
                           key=lambda x: -x["keyword_score"])[:60]
        vec_ranked = sorted([x for x in scored if x["vector_score"] > 0.05],
                            key=lambda x: -x["vector_score"])[:60]
        pool: dict = {}
        for rank, x in enumerate(kw_ranked):
            x["rrf_score"] = 1.0 / (_RRF_K + rank + 1)
            pool[x["id"]] = x
        for rank, x in enumerate(vec_ranked):
            obj = pool.setdefault(x["id"], x)
            obj["rrf_score"] = obj.get("rrf_score", 0.0) + 1.0 / (_RRF_K + rank + 1)
        candidates = sorted(pool.values(), key=lambda x: -x["rrf_score"])
        results = candidates

        # 5) Rerank 精排（qwen3-rerank；关闭/失败自动降级 RRF 原序）
        reranked = False
        if candidates:
            rr = rerank(query, [c["content"] for c in candidates], top_n=k)
            if rr:
                top = []
                for r in rr:
                    idx = r["index"]
                    if 0 <= idx < len(candidates):
                        item = dict(candidates[idx])
                        item["rerank_score"] = round(r["relevance_score"], 3)
                        item["score"] = item["rerank_score"]  # 展示用相关度统一为精排分
                        top.append(item)
                if top:
                    candidates = top
                    reranked = True
        top = candidates[:k]

        # 6) 严格匹配无结果 → 字符 bigram 包含度兜底
        #    解决「文档已上传但换个说法问不到」：只要查询与分片存在有意义的共同字组，
        #    就返回最相关分片并保留来源引用，避免误报"未检索到"。
        if not top and chunks:
            q_bi = [query[i:i + 2] for i in range(len(query) - 1)]
            # 仅保留中文/字母数字 bigram，且过滤停用词与纯符号
            q_bi = [
                b for b in q_bi
                if re.search(r"[\u4e00-\u9fa5A-Za-z0-9]", b)
                and b.lower() not in _STOP_WORDS
                and b not in _STOP_WORDS
            ]
            if q_bi:
                scored_bigram = []
                for c in chunks:
                    cl = c.content.lower()
                    hits = sum(1 for b in q_bi if b.lower() in cl)
                    if hits:
                        scored_bigram.append({
                            "id": c.id,
                            "document_id": c.document_id,
                            "document_title": self._doc_title(c.document_id),
                            "content": c.content,
                            "keyword_score": round(hits / len(q_bi), 3),
                            "vector_score": 0.0,
                            "score": round(hits / len(q_bi), 3),
                            "overlap_hits": hits,
                        })
                scored_bigram.sort(key=lambda x: -x["score"])
                if scored_bigram and scored_bigram[0]["score"] >= 0.12:
                    top = scored_bigram[:k]
                    results = scored_bigram

        # 7) 汇总方法标识
        if reranked:
            method = ("hybrid" if (results and vector_enabled) else "keyword") + "+rerank"
        elif results and vector_enabled:
            method = "hybrid"
        elif results:
            method = "keyword"
        else:
            method = "none"

        return {
            "items": top,
            "total_chunks": len(chunks),
            "matched_chunks": len(results),
            "method": method,
            "reranked": reranked,
            "keywords": query_words,
            "vector_enabled": vector_enabled,
            "total_docs": total_docs,
            "failed_docs": failed_docs,
            "failed_doc_titles": failed_doc_titles,
        }

    # ──────────────────────────────────────
    # 回答生成（answer / answer_stream 共用部分，P2#18 抽取）
    # ──────────────────────────────────────

    def _adaptive_retrieve(self, query: str, top_k: int = None, user_id: int = None, is_admin: bool = False):
        """P1 #10 Adaptive RAG 检索环（answer 与 answer_stream 共用）

        simple 直通一次；complex 最多 3 轮「检索 → 命中不足 → LLM 改写查询」环。
        返回 (context, 实际使用的 query, rewritten_query, rounds, complexity)。
        """
        rewritten_query = ""
        rounds = 0
        complexity = _classify_query_complexity(query)
        context = self.retrieve(query, top_k, user_id=user_id, is_admin=is_admin)
        if complexity == "complex" and llm_available():
            for i in range(2):  # 最多 3 轮检索（初次 + 2 次改写）
                items = context.get("items", [])
                top_score = items[0].get("score", 0) if items else 0
                if len(items) >= 3 or (items and top_score >= 0.5):
                    break
                # 命中不足 → LLM 改写查询后重检
                rewrite_res = None
                try:
                    rewrite_res = invoke_llm(
                        f"请将下面的知识库检索查询改写为更容易命中文档的表述"
                        f"（保留核心关键词，去掉口语化词，不超过60字，仅输出改写后的查询）：\n{query}",
                        temperature=0.2, max_tokens=80)
                except Exception:
                    rewrite_res = None
                if rewrite_res is None or not rewrite_res.text.strip():
                    break
                rewritten_query = rewrite_res.text.strip().splitlines()[0][:100]
                if rewritten_query == query:
                    break
                query = rewritten_query
                context = self.retrieve(query, top_k, user_id=user_id, is_admin=is_admin)
                rounds += 1
        return context, query, rewritten_query, rounds, complexity

    @staticmethod
    def _retri_meta(context: dict, complexity: str, rewritten_query: str, rounds: int) -> dict:
        return {
            "total_chunks": context.get("total_chunks", 0),
            "matched_chunks": context.get("matched_chunks", 0),
            "method": context.get("method", "none"),
            "reranked": context.get("reranked", False),
            "keywords": context.get("keywords", []),
            "vector_enabled": context.get("vector_enabled", False),
            "complexity": complexity,
            "rewritten_query": rewritten_query,
            "rounds": rounds,
            "total_docs": context.get("total_docs", 0),
            "failed_docs": context.get("failed_docs", 0),
            "failed_doc_titles": context.get("failed_doc_titles", []),
        }

    @staticmethod
    def _rag_prompt(query: str, refs: list) -> str:
        context_text = "\n\n".join(
            [f"[来源 {i + 1}（文档：{r.get('document_title', '未知')}）]: {r['content']}" for i, r in enumerate(refs)]
        )
        return f"""你是一个森林火险知识助手（RagAgent）。请严格根据下面的参考文档回答用户问题。

要求：
1. 回答必须基于参考文档中的内容，不得编造文档中不存在的信息；
2. 来源引用必须规范：每一个来自文档的事实、数据或结论，句末都要紧跟固定格式的角标
   [来源N]（N 为参考文档编号，如 [来源1]；一句话引用多个来源写 [来源1][来源2]）。
   禁止用「根据文档」「资料显示」等文字代替角标，也不要遗漏；
3. 如果参考文档无法覆盖问题，请明确说明"知识库文档中未找到该信息"；
4. 用简洁、专业的中文回答，适合用分点/小标题时使用 markdown 组织；
5. 直接输出最终回答，不要输出思考过程或 <think> 内容。

参考文档：
{context_text}

用户问题：{query}

回答："""

    def answer(self, query: str, context: dict = None, top_k: int = None,
               user_id: int = None, is_admin: bool = False) -> dict:
        """基于检索结果生成回答（带 RagAgent 检索过程元数据）

        P1 #10 Adaptive RAG：未传入 context 时按查询复杂度自适应检索——
        simple 直通一次；complex 最多 3 轮「检索 → 命中不足 → LLM 改写查询」环。
        传入 context 则直接使用（跳过自适应环，保持旧契约）。
        P2#18：user_id/is_admin 透传检索层（用户数据隔离硬约束）。
        """
        if context is None:
            context, query, rewritten_query, rounds, complexity = self._adaptive_retrieve(
                query, top_k, user_id=user_id, is_admin=is_admin)
        else:
            rewritten_query = ""
            rounds = 0
            complexity = "preset"
        refs = context.get("items", [])
        retri_meta = self._retri_meta(context, complexity, rewritten_query, rounds)

        # 未命中任何片段 → 明确告知原因，不让 LLM 凭空发挥
        if not refs:
            failed_titles = retri_meta.get("failed_doc_titles") or []
            failed_hint = ""
            if failed_titles:
                names = "、".join(failed_titles[:5])
                failed_hint = (f"\n\n注意：知识库中有 {len(failed_titles)} 个文档提取失败"
                               f"（{names}），可能是扫描件/图片型 PDF 或无文字层，"
                               "请删除后重新上传可复制的 PDF、TXT 或 Markdown 文档。")
            if retri_meta["total_chunks"] == 0:
                if retri_meta["failed_docs"] > 0:
                    hint = (f"当前可见知识库中有 {retri_meta['failed_docs']} 个文档文本提取失败，"
                            "没有可检索的文字内容。" + failed_hint)
                elif retri_meta["total_docs"] == 0:
                    hint = "当前知识库中还没有可检索的文档。请先在上方「文档管理」上传相关文档。"
                else:
                    hint = "当前可见知识库暂无可检索的分片（文档可能正在处理中）。" + failed_hint
            else:
                hint = ("RagAgent 在知识库中未检索到与问题相关的内容。\n\n"
                        "建议：\n1. 换一种更具体的表述再提问；\n"
                        "2. 确认问题关键词与已上传文档内容相关。" + failed_hint)

            return {
                "answer": hint,
                "references": [],
                "llm_used": False,
                "retrieval": retri_meta,
            }

        # LLM 不可用 → 直接返回检索到的片段
        if not llm_available():
            return {
                "answer": "LLM 未配置，RagAgent 仅返回检索到的相关片段（未生成 AI 回答）。",
                "references": refs,
                "llm_used": False,
                "retrieval": retri_meta,
            }

        # 构建 Prompt：注入完整片段内容 + 来源文档
        context_text = "\n\n".join(
            [f"[来源 {i + 1}（文档：{r.get('document_title', '未知')}）]: {r['content']}" for i, r in enumerate(refs)]
        )
        prompt = f"""你是一个森林火险知识助手（RagAgent）。请严格根据下面的参考文档回答用户问题。

要求：
1. 回答必须基于参考文档中的内容，不得编造文档中不存在的信息；
2. 在回答中引用对应的来源编号，例如「根据[来源1]…」；
3. 如果参考文档无法覆盖问题，请明确说明"知识库文档中未找到该信息"；
4. 用简洁、专业的中文回答。

参考文档：
{context_text}

用户问题：{query}

回答："""

        llm_result = None
        reasoning = ""
        try:
            llm_result = invoke_llm(prompt, temperature=0.1)
        except Exception as e:
            answer = f"RagAgent 调用 LLM 失败，已返回原始检索片段。\n\n检索到 {len(refs)} 个相关片段，详见下方引用来源。（{e}）"
        else:
            if llm_result is not None:
                reasoning, answer = _split_think(llm_result.text)
            else:
                answer = (f"RagAgent 调用 LLM 失败（所有模型通道均不可用），已返回原始检索片段。\n\n"
                          f"检索到 {len(refs)} 个相关片段，详见下方引用来源。")

        return {
            "answer": answer,
            "reasoning": reasoning,
            "references": refs,
            "llm_used": True,
            "llm_model": (llm_result.model if llm_result else "") or "",
            "llm_degraded": bool(llm_result.degraded) if llm_result else False,
            "retrieval": retri_meta,
        }

    def answer_stream(self, query: str, top_k: int = None,
                      user_id: int = None, is_admin: bool = False):
        """流式问答（P2#18）：yield SSE 事件字典流，供 /rag/ask/stream 逐帧转发

        事件流：
          {"type": "meta", "retrieval": {...}}   检索元信息（先行推送）
          {"type": "delta", "text": str}         回答增量（逐 token）
          {"type": "llm_meta", ...}              LLM 审计（provider/degraded，可忽略）
          {"type": "done", "result": {...}}      终态：完整结果（与 /ask 契约一致，落库以此为准）

        边界：未命中/LLM 不可用/流式失败 → 不出 delta，直接 yield done（复用非流式
        answer 的兜底语义，传入 context 跳过自适应检索避免二次检索）。
        """
        context, query, rewritten_query, rounds, complexity = self._adaptive_retrieve(
            query, top_k, user_id=user_id, is_admin=is_admin)
        refs = context.get("items", [])
        retri_meta = self._retri_meta(context, complexity, rewritten_query, rounds)
        yield {"type": "meta", "retrieval": retri_meta}

        # 未命中或 LLM 不可用 → 与非流式 answer 同语义的兜底结果
        if not refs or not llm_available():
            yield {"type": "done",
                   "result": self.answer(query, context=context, top_k=top_k,
                                         user_id=user_id, is_admin=is_admin)}
            return

        prompt = self._rag_prompt(query, refs)
        think = _ThinkFilter()          # 流式过滤 <think>…</think>（标签跨 chunk 安全）
        reasoning_field: list[str] = []  # reasoning 字段思考增量（AMD/vLLM 端点）
        buf: list[str] = []
        streamed_ok = False
        model_name, degraded = "", False
        try:
            # reasoning_effort=low 限思；max_tokens 需容纳思考+正文（实测 MiniCPM 思考 ~770 字），
            # 防思考吃满额度导致正文为空
            for chunk in stream_llm(prompt, temperature=0.1, max_tokens=2400,
                                    reasoning_effort="low"):
                ctype = chunk.get("type")
                if ctype == "think":
                    # 思考型模型 reasoning 字段增量（AMD/vLLM 端点），直接透传前端
                    reasoning_field.append(chunk.get("text", ""))
                    yield {"type": "think", "text": chunk.get("text", "")}
                elif ctype == "delta":
                    clean = think.feed(chunk.get("text", ""))
                    think_delta = think.take_think_delta()
                    if think_delta:
                        # 思考过程增量（qwen3 / DeepSeek 系模型的 <think> 段）：
                        # 前端"深度思考中…"折叠面板实时展示
                        yield {"type": "think", "text": think_delta}
                    if clean:
                        buf.append(clean)
                        yield {"type": "delta", "text": clean}
                elif ctype == "meta":
                    streamed_ok = True
                    model_name = chunk.get("model") or ""
                    degraded = bool(chunk.get("degraded"))
                    yield {"type": "llm_meta", "provider": chunk.get("provider"),
                           "model": model_name, "degraded": degraded}
                    break
                elif ctype == "error":
                    break
        except Exception:
            streamed_ok = False

        if streamed_ok:
            tail = think.finish()       # 吐出扣留的疑似标签尾巴
            think_tail = think.take_think_delta()
            if think_tail:
                yield {"type": "think", "text": think_tail}
            if tail:
                buf.append(tail)
                yield {"type": "delta", "text": tail}
            yield {"type": "done",
                   "result": {"answer": "".join(buf),
                              "reasoning": "\n".join([t for t in (think.think_text(), "".join(reasoning_field)) if t]),
                              "references": refs, "llm_used": True, "llm_model": model_name,
                              "llm_degraded": degraded, "retrieval": retri_meta}}
        else:
            # 流式失败 → 回退非流式（invoke_llm 完整重试链），保证用户总能拿到回答
            yield {"type": "done",
                   "result": self.answer(query, context=context, top_k=top_k,
                                         user_id=user_id, is_admin=is_admin)}

    # ──────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────

    def _doc_title(self, doc_id: int) -> str:
        """根据分片 document_id 查文档标题（带缓存）"""
        if not hasattr(self, "_title_cache"):
            self._title_cache = {}
        if doc_id not in self._title_cache:
            doc = self.db.query(KbDocument).filter(KbDocument.id == doc_id).first()
            self._title_cache[doc_id] = doc.title if doc else "未知文档"
        return self._title_cache[doc_id]

    def _extract_text(self, file_path: Path, ext: str) -> tuple:
        """提取文档文本，返回 (文本, 错误信息)；文本为 None 表示提取失败

        失败时返回具体原因，供前端展示（区分扫描件/无文字层/格式问题等）。
        """
        ext = ext.lower()
        try:
            if ext == ".txt":
                return file_path.read_text(encoding="utf-8"), None
            elif ext == ".md":
                from markdown import markdown
                import re
                html = markdown(file_path.read_text(encoding="utf-8"))
                return re.sub(r"<[^>]+>", "", html), None
            elif ext == ".pdf":
                return self._extract_pdf(file_path), None
            else:
                return file_path.read_text(encoding="utf-8", errors="ignore"), None
        except Exception as e:
            return None, f"文本提取失败：{e}"

    @staticmethod
    def _normalize_pdf_text(raw) -> str:
        """把各 PDF 库返回的文本统一成 str（兼容 bytes 返回）"""
        if raw is None:
            return ""
        if isinstance(raw, bytes):
            for enc in ("utf-8", "gbk", "gb18030"):
                try:
                    return raw.decode(enc)
                except (UnicodeDecodeError, ValueError):
                    continue
            return ""
        return str(raw)

    @staticmethod
    def _is_garbled_cn(text: str) -> bool:
        """检测 GB/T 国家标准 PDF 的乱码文字层

        这类 PDF（国家标准全文公开系统）使用自定义字体编码，提取出的文本
        会出现大量生僻字形（犐犆犛犌犅犜…，位于 U+7280-U+72FF 牛部字）以及
        高密度标点符号（!"#$%&'()*…）替代中文字符，导致关键词/向量检索全部失效。
        返回 True 表示判定为乱码文本。
        """
        if not text or len(text.strip()) < 20:
            return True
        total = len(text)
        rare = sum(1 for ch in text if "\u7280" <= ch <= "\u72ff")
        punct = sum(1 for ch in text if ch in "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        if rare / total > 0.03:
            return True
        if punct / total > 0.35 and cjk / total < 0.35:
            return True
        if rare / total > 0.01 and cjk / total < 0.2:
            return True
        return False

    @staticmethod
    def _ocr_pdf_rapid(file_path: Path, max_pages: int = 60) -> str:
        """RapidOCR 逐页识别（本地轻量引擎，OCR 链路最后兜底）

        适用于：GB/T 国家标准 PDF（自定义字体编码导致文字层乱码）、扫描件。
        RapidOCR 基于 ONNX 离线推理，无需联网、无需系统级 Tesseract。
        """
        import pymupdf  # PyMuPDF（新 API，替代已弃用的 fitz）
        from rapidocr_onnxruntime import RapidOCR

        ocr = RapidOCR()
        doc = pymupdf.open(str(file_path))
        pages_text = []
        try:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    pages_text.append(f"[提示：文档超过 {max_pages} 页，仅 OCR 前 {max_pages} 页]")
                    break
                # 2x 缩放渲染保证中文小字号可识别
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                result, _ = ocr(img_bytes)
                if result:
                    # 按 OCR 返回的行顺序拼接
                    pages_text.append("\n".join(line[1] for line in result))
        finally:
            doc.close()
        return "\n".join(pages_text)

    @staticmethod
    def _ocr_pdf_paddle(file_path: Path, max_pages: int = 60) -> str:
        """PaddleOCR 逐页识别（本地增强引擎，OCR 链路首选）

        可选依赖：pip install paddleocr paddlepaddle（未安装时抛出 ImportError，
        由调用方跳过，不影响 RapidOCR 与云端 MinerU 链路）。
        同时兼容 PaddleOCR 2.x（ocr(img, cls=True)）与 3.x（predict(img)）。
        """
        import pymupdf
        import numpy as np
        from paddleocr import PaddleOCR

        try:
            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)  # 2.x
        except (TypeError, ValueError):
            # 3.x：PDF 页面已正向渲染，关闭文档方向分类与去畸变以提速
            # enable_mkldnn=False：规避 Windows + Paddle 3.x 的 oneDNN
            # ConvertPirAttribute2RuntimeAttribute 崩溃（CPU 推理回退到原生实现）
            ocr = PaddleOCR(
                lang="ch",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                enable_mkldnn=False,
            )

        doc = pymupdf.open(str(file_path))
        pages_text = []
        try:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    pages_text.append(f"[提示：文档超过 {max_pages} 页，仅 OCR 前 {max_pages} 页]")
                    break
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                # PyMuPDF 输出 RGB(A)，PaddleOCR 期望 BGR
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = img[:, :, :3]
                img = img[:, :, ::-1]

                if hasattr(ocr, "predict"):  # 3.x
                    result = ocr.predict(img)
                    for page_res in result or []:
                        # 3.x 返回 OCRResult（dict-like），兼容 dict 与对象两种形态
                        texts = page_res.get("rec_texts") if hasattr(page_res, "get") else None
                        if texts:
                            pages_text.append("\n".join(str(t) for t in texts))
                else:  # 2.x
                    result = ocr.ocr(img, cls=True)
                    for line in (result[0] if result else []) or []:
                        pages_text.append(line[1][0])
        finally:
            doc.close()
        return "\n".join(pages_text)

    @staticmethod
    def _extract_pdf(file_path: Path) -> str:
        """PDF 文本提取：pdfplumber → pypdf → PyMuPDF → PaddleOCR → AMD MinerU(可选) → RapidOCR

        前三个库提取文字层并做乱码/空文本检测；全部失败时走图像 OCR：
        先本地 PaddleOCR（增强引擎，未安装自动跳过），再由 OCR_PROVIDER=amd
        决定是否调用云端 MinerU2.5-Pro 增强，最后用本地 RapidOCR 轻量兜底。
        """
        reasons = []
        for extractor in ("pdfplumber", "pypdf", "fitz"):
            text = ""
            try:
                if extractor == "pdfplumber":
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        text = "\n".join(
                            RagService._normalize_pdf_text(page.extract_text()) for page in pdf.pages
                        )
                elif extractor == "pypdf":
                    from pypdf import PdfReader
                    reader = PdfReader(str(file_path))
                    text = "\n".join(
                        RagService._normalize_pdf_text(page.extract_text()) for page in reader.pages
                    )
                else:
                    import pymupdf  # PyMuPDF（新 API，替代已弃用的 fitz）
                    doc = pymupdf.open(str(file_path))
                    text = "\n".join(
                        RagService._normalize_pdf_text(page.get_text()) for page in doc
                    )
                    doc.close()
            except Exception as e:
                reasons.append(f"{extractor}: {e}")
                continue

            if not (text and text.strip()):
                reasons.append(f"{extractor}: 无文字")
                continue
            if len(text.strip()) < 20:
                reasons.append(f"{extractor}: 文字过少（疑似扫描件）")
                continue
            if RagService._is_garbled_cn(text):
                reasons.append(f"{extractor}: 乱码")
                continue
            return text

        # ===== 文字层全部不可用 → OCR：PaddleOCR → MinerU2.5-Pro（可选）→ RapidOCR =====
        # 顺序按部署偏好：先本地能力最强的 PaddleOCR，再云端 MinerU 增强，
        # RapidOCR 作为最后的轻量兜底。
        try:
            ocr_text = RagService._ocr_pdf_paddle(file_path)
        except ImportError:
            reasons.append("paddleocr: 未安装")
        except Exception as e:
            reasons.append(f"paddleocr: {str(e)[:120]}")
        else:
            if ocr_text and len(ocr_text.strip()) >= 20 and not RagService._is_garbled_cn(ocr_text):
                return ocr_text
            reasons.append("paddleocr: 识别结果为空")

        if settings.OCR_PROVIDER == "amd":
            try:
                from app.core.llm import amd_ocr_pdf
                ocr_text = amd_ocr_pdf(file_path)
                if ocr_text and len(ocr_text.strip()) >= 20 and not RagService._is_garbled_cn(ocr_text):
                    return ocr_text
                reasons.append(f"amd-ocr({settings.OCR_MODEL}): 识别结果为空")
            except Exception as e:
                reasons.append(f"amd-ocr({settings.OCR_MODEL}): {str(e)[:120]}")
        else:
            reasons.append("amd-ocr: 未启用（OCR_PROVIDER!=amd）")

        try:
            ocr_text = RagService._ocr_pdf_rapid(file_path)
        except ImportError:
            reasons.append("rapidocr: 未安装")
        except Exception as e:
            reasons.append(f"rapidocr: {str(e)[:120]}")
        else:
            if ocr_text and len(ocr_text.strip()) >= 20 and not RagService._is_garbled_cn(ocr_text):
                return ocr_text
            reasons.append("rapidocr: 识别结果为空")

        joined = "；".join(reasons)
        if "乱码" in joined:
            raise ValueError(
                "该 PDF 为 GB/T 国家标准全文文件（文字层使用自定义字体编码，提取后为乱码），"
                "且 OCR 识别失败或未安装 OCR 组件"
                "（pip install rapidocr-onnxruntime，可选 paddleocr paddlepaddle）。"
                "请安装 OCR 组件后重新上传，或直接上传 TXT / Markdown 文档。"
            )
        if "扫描件" in joined or "无文字" in joined:
            raise ValueError(
                "该 PDF 提取到极少量文字（疑似扫描件/图片型 PDF，无文字层），"
                "且 OCR 识别失败。请改用带文字层的 PDF，或直接上传 TXT / Markdown 文档。"
            )
        raise ValueError(f"PDF 文本提取失败，无可用文字（{joined}）")

    def _chunk_text(self, text: str, doc_id: int) -> list[KbChunk]:
        """切分文本并生成向量"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.KB_CHUNK_SIZE,
            chunk_overlap=settings.KB_CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "，", " ", ""],
        )
        chunks = splitter.split_text(text)

        # 生成向量（如果 LLM 可用）
        embeddings = None
        if self.embed:
            try:
                embeddings = self.embed.embed_documents(chunks)
            except Exception:
                embeddings = None

        result = []
        for i, content in enumerate(chunks):
            embedding_str = None
            if embeddings and i < len(embeddings):
                try:
                    # 统一存 JSON 数组，便于检索时解析为向量
                    embedding_str = json.dumps([float(x) for x in embeddings[i]])
                except (TypeError, ValueError):
                    embedding_str = None
            chunk = KbChunk(
                document_id=doc_id,
                chunk_index=i,
                content=content,
                token_count=len(content),
                embedding=embedding_str,
            )
            result.append(chunk)
        return result