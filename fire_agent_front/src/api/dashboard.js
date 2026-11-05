/**
 * 大屏数据 API 服务
 * 通过 Vite proxy 将 /api 请求转发到后端 localhost:8000
 */
import { API_V1 } from '@/utils/config'
import { authFetch, withQuery } from '@/api/http'

const API_BASE = `${API_V1}/dashboard`

// 必须走 authFetch：/history-fires 与 /predict-risks 现在要求登录态（安全加固 2.2），
// 早先这里是裸 fetch，不带 Authorization 头 → 后端 401 → 页面 catch → 一直显示本地降级数据
async function request(url, params = {}) {
  const res = await authFetch(withQuery(`${API_BASE}${url}`, params))
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  const json = await res.json()
  if (json.code !== 200) throw new Error(json.message || 'API error')
  return json.data
}

/**
 * 查询历史火点
 * @param {Object} opts - { start_date, end_date, city, confidence, page, page_size }
 * @returns {Promise<{ total: number, page: number, page_size: number, items: Array }>}
 */
export function fetchHistoryFires(opts = {}) {
  return request('/history-fires', opts)
}

/**
 * 查询预测火险
 * @param {Object} opts - { year, month, day, view_mode, city }
 * @returns {Promise<{ total: number, items: Array }>}
 */
export function fetchPredictRisks(opts = {}) {
  return request('/predict-risks', opts)
}

/**
 * 大屏摘要统计（后端刻意保持匿名可访问；带 token 时照带，不影响结果）
 * @returns {Promise<{ total_fire_points: number, high_risk_count: number, avg_frp: number, top_cities: Array }>}
 */
export function fetchSummary(opts = {}) {
  return request('/summary', opts)
}