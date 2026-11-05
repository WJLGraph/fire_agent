/**
 * 知识库 RAG API — /api/v1/rag/*
 *
 * 迁移自 views/knowledge-base/index.vue（URL 与参数结构逐字保持一致）
 *
 * 流式说明：/ask/stream 走 fetch + reader（EventSource 不支持 POST），
 * 本模块只负责发出请求并返回原始 Response，逐帧解析逻辑保留在页面，行为不变。
 */
import { get, post, del, postFormJson, postFormWithProgress, postStream } from '@/api/http'
import { API_V1 } from '@/utils/config'

const BASE = `${API_V1}/rag`

/** GET /rag/documents — 文档列表 */
export function fetchDocuments() {
  return get(`${BASE}/documents`)
}

/** POST /rag/documents — 上传文档，body: FormData{ file, category }；onProgress(loaded, total) 上传字节进度 */
export function uploadDocument(formData, onProgress) {
  if (onProgress) {
    return postFormWithProgress(`${BASE}/documents`, formData, { onProgress })
  }
  return postFormJson(`${BASE}/documents`, formData)
}

/** DELETE /rag/documents/{id} — 删除文档 */
export function deleteDocument(id) {
  return del(`${BASE}/documents/${id}`)
}

/** GET /rag/documents/{id}/content — 文档全文（按分片拼接），供阅读 */
export function fetchDocumentContent(id) {
  return get(`${BASE}/documents/${id}/content`)
}

/** POST /rag/ask — 非流式问答，body: { query, top_k } */
export function ask(query, topK = 5) {
  return post(`${BASE}/ask`, { query, top_k: topK })
}

/**
 * POST /rag/ask/stream — 流式问答（SSE over fetch）
 * @param {Object} [options] 透传 fetch（如 { signal } 供任务进程「终止」断开连接）
 * @returns {Promise<Response>} 原始响应，由调用方读取 reader 逐帧解析
 */
export function askStream(query, topK = 5, options = {}) {
  return postStream(`${BASE}/ask/stream`, { query, top_k: topK }, options)
}

/** GET /rag/history — 问答历史列表 */
export function fetchHistory() {
  return get(`${BASE}/history`)
}

/** GET /rag/history/{id} — 单条问答历史 */
export function fetchHistoryDetail(id) {
  return get(`${BASE}/history/${id}`)
}

/** DELETE /rag/history — 清空问答历史 */
export function clearHistory() {
  return del(`${BASE}/history`)
}

/** DELETE /rag/history/{id} — 删除单条问答历史 */
export function deleteHistoryItem(id) {
  return del(`${BASE}/history/${id}`)
}
