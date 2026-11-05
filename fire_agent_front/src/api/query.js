/**
 * 智能查询 API — /api/v1/query/*
 *
 * 迁移自 views/smart-query/index.vue（URL 与参数结构逐字保持一致）
 * 返回完整响应信封 { code, message, data }，业务分支仍由页面按原逻辑处理。
 */
import { get, post, del } from '@/api/http'
import { API_V1 } from '@/utils/config'

const BASE = `${API_V1}/query`

/** GET /query/history — 查询历史列表 */
export function fetchHistory() {
  return get(`${BASE}/history`)
}

/** GET /query/history/{id} — 单条历史详情 */
export function fetchHistoryDetail(id) {
  return get(`${BASE}/history/${id}`)
}

/** DELETE /query/history — 清空历史 */
export function clearHistory() {
  return del(`${BASE}/history`)
}

/** DELETE /query/history/{id} — 删除单条历史 */
export function deleteHistoryItem(id) {
  return del(`${BASE}/history/${id}`)
}

/** POST /query/execute — 执行自然语言查询，body: { query } */
export function execute(query) {
  return post(`${BASE}/execute`, { query })
}
