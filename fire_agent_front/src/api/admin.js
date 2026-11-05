/**
 * 系统管理 API — /api/v1/admin/*
 *
 * 迁移自 views/admin/index.vue（原本内联了一份 authFetch，此处统一走 api/http）
 *
 * 说明：部分调用需要判断 HTTP 状态码（用户列表的 403、改角色/删用户的 res.ok），
 * 故对应提供 *Raw 版本返回原始 Response，页面分支逻辑保持原样。
 */
import { get, getRaw, post, postRaw, putRaw, deleteRaw } from '@/api/http'
import { API_V1 } from '@/utils/config'

const BASE = `${API_V1}/admin`

/** GET /admin/status — 系统状态（DB / LLM 连通性） */
export function fetchStatus() {
  return get(`${BASE}/status`)
}

/** GET /admin/model-status — 每类模型的当前提供商/模型/配置状态与熔断器状态 */
export function fetchModelStatus() {
  return get(`${BASE}/model-status`)
}

/** GET /admin/config — 当前配置（密钥字段后端返回脱敏值） */
export function fetchConfig() {
  return get(`${BASE}/config`)
}

/**
 * POST /admin/config — 更新配置（后端只更新非空字段）
 * @param {object} payload 配置字段集合
 */
export function updateConfig(payload) {
  return post(`${BASE}/config`, payload)
}

/** GET /admin/logs — 系统日志，limit=100 */
export function fetchLogs() {
  return get(`${BASE}/logs?limit=100`)
}

/**
 * GET /admin/llm/models — 可用模型目录
 * @param {'aliyun'|'amd'|'longcat'} provider
 */
export function fetchLlmModels(provider) {
  return get(`${BASE}/llm/models?provider=${provider}`)
}

/** GET /admin/bailian/quota — 百炼账号免费额度快照 */
export function fetchBailianQuota() {
  return get(`${BASE}/bailian/quota`)
}

/** POST /admin/test/db — 测试数据库连接 */
export function testDatabase() {
  return postRaw(`${BASE}/test/db`, undefined)
}

/** POST /admin/test/llm — 测试 LLM 连接 */
export function testLlm() {
  return postRaw(`${BASE}/test/llm`, undefined)
}

// ==================== 用户管理（需管理员，需判状态码） ====================

/** GET /admin/users — 用户列表，返回原始 Response（页面需判 403） */
export function fetchUsersRaw() {
  return getRaw(`${BASE}/users`)
}

/** PUT /admin/users/{id}/role — 修改角色，返回原始 Response（页面需判 res.ok） */
export function changeRoleRaw(id, role) {
  return putRaw(`${BASE}/users/${id}/role`, { role })
}

/** DELETE /admin/users/{id} — 删除用户，返回原始 Response（页面需判 res.ok） */
export function removeUserRaw(id) {
  return deleteRaw(`${BASE}/users/${id}`)
}
