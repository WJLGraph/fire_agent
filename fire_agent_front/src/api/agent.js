/**
 * Agent 协作 API — /api/v1/agent/*
 *
 * 迁移自 views/agent-center/index.vue 与 components/SystemCapabilities.vue
 *
 * SSE 说明：任务进度用 fetch + Authorization（见 openTaskStream），
 * 不再把 JWT 放进查询参数——查询参数会落进 Nginx access log。
 */
import { authFetch, get, getRaw, post, del } from '@/api/http'
import { API_V1 } from '@/utils/config'

const BASE = `${API_V1}/agent`

/** GET /agent/status — Agent 与框架状态 */
export function fetchStatus() {
  return get(`${BASE}/status`)
}

/** GET /agent/capabilities — 系统能力清单 */
export function fetchCapabilities() {
  return get(`${BASE}/capabilities`)
}

/** POST /agent/tasks — 创建任务，body: { query } */
export function createTask(query) {
  return post(`${BASE}/tasks`, { query })
}

/** GET /agent/tasks — 任务历史列表（按用户隔离，时间倒序） */
export function fetchTasks() {
  return get(`${BASE}/tasks`)
}

/** GET /agent/tasks/{id} — 任务详情 */
export function fetchTaskDetail(id) {
  return get(`${BASE}/tasks/${id}`)
}

/** DELETE /agent/tasks/{id} — 删除任务 */
export function deleteTask(id) {
  return del(`${BASE}/tasks/${id}`)
}

/** POST /agent/tasks/{id}/cancel — 取消运行中/待审批任务 */
export function cancelTask(id) {
  return post(`${BASE}/tasks/${id}/cancel`, {})
}

/** POST /agent/tasks/{id}/retry — 以相同查询重新发起任务，返回新 task_id */
export function retryTask(id) {
  return post(`${BASE}/tasks/${id}/retry`, {})
}

/**
 * POST /agent/tasks/{id}/resume — HITL 审批决策
 * @param {string} id
 * @param {'approve'|'edit'|'reject'} action
 * @param {{ content?: string, comment?: string }} payload
 */
export function resumeTask(id, action, payload = {}) {
  return post(`${BASE}/tasks/${id}/resume`, {
    action,
    content: payload.content || '',
    comment: payload.comment || '',
  })
}

/**
 * 订阅任务进度 SSE（GET /agent/tasks/{id}/stream）
 *
 * 走 fetch + Authorization 头，不用 EventSource：EventSource 无法带自定义头，
 * 只能把 JWT 塞进查询参数，而查询参数会原样落进 Nginx / 网关的 access log，
 * 等于把 15 小时内有效的会话凭证写进一台与业务无关的日志系统。
 * 后端仍兼容 `?token=`（旧 bundle 的在途页面），但新前端不再使用。
 * @param {string|number} taskId
 * @param {{ signal?: AbortSignal }} options
 * @returns {Promise<Response>} 原始 Response，调用方用 body.getReader() 逐帧解析
 */
export function openTaskStream(taskId, options = {}) {
  return authFetch(`${BASE}/tasks/${taskId}/stream`, {
    method: 'GET',
    headers: { Accept: 'text/event-stream' },
    signal: options.signal,
  })
}

/** 原始请求入口（需要自行处理状态码时使用） */
export function fetchTaskDetailRaw(id) {
  return getRaw(`${BASE}/tasks/${id}`)
}
