/**
 * 报告中心 API — /api/v1/reports/*
 *
 * 迁移自 views/report-center/index.vue 与 views/agent-center/index.vue
 *
 * 注意：详情接口需要判断 404（报告不存在/无权限），故额外提供 fetchDetailRaw 返回原始 Response。
 */
import { get, getRaw, del, withQuery } from '@/api/http'
import { API_V1 } from '@/utils/config'

const BASE = `${API_V1}/reports`

/**
 * GET /reports/list — 报告列表
 * @param {{ page?: number, page_size?: number, report_type?: string }} params
 */
export function fetchList(params = {}) {
  const qs = new URLSearchParams({
    page: params.page,
    page_size: params.page_size,
  })
  if (params.report_type) qs.append('report_type', params.report_type)
  return get(`${BASE}/list?${qs.toString()}`)
}

/**
 * GET /reports/{id} — 报告详情
 * 返回完整信封；需要区分 404 时改用 fetchDetailRaw
 */
export function fetchDetail(id) {
  return get(`${BASE}/${id}`)
}

/** GET /reports/{id} — 返回原始 Response（供 404 分支判断） */
export function fetchDetailRaw(id) {
  return getRaw(`${BASE}/${id}`)
}

/** DELETE /reports/{id} — 删除报告 */
export function remove(id) {
  return del(`${BASE}/${id}`)
}

/** GET /reports/export/{id} — 导出（md / html），返回原始 Response 供 blob 下载 */
export function exportRaw(id, format = 'md') {
  return getRaw(`${BASE}/export/${id}?format=${format}`)
}

/** 构造导出 URL（供需要直接用 URL 的场景） */
export function buildExportUrl(id, format = 'md') {
  return withQuery(`${BASE}/export/${id}`, { format })
}
