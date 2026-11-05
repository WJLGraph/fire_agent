/**
 * HTTP 内核 — 全站唯一的网络出口底座
 *
 * 设计原则（重构阶段 1：契约冻结；阶段 5 收尾）
 *   - 认证逻辑（Bearer 头 / 401 登出跳转）由本文件的 `authFetch` 提供，行为与
 *     原 `utils/authFetch.js` 逐字一致（该文件已于阶段 5 内联后删除）
 *   - 只提供「发请求 + 拼参数」的糖，不吞掉业务码判断：
 *     api/*.js 返回完整响应信封 `{ code, message, data }`，由调用方按原有分支处理，
 *     以保证重构前后「网络请求 + 响应解析」结果完全等价。
 *
 * 约定：
 *   - 需要判断 HTTP 状态码的调用（如报告详情的 404）使用 getRaw/postRaw 拿原始 Response
 *   - 需要二进制（导出 blob）的调用同样使用 Raw 系列
 */
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { API_V1 } from '@/utils/config'

export { API_V1 }

/** 后端滑动会话续期头（见 app/core/session.py::REFRESH_HEADER） */
const REFRESH_HEADER = 'X-Token-Refresh'

/**
 * 真实活动判定
 *
 * 只有点击 / 键盘 / 滚轮 / 切回前台才算「用户在用」。页面里那些 10s 定时轮询
 * （Agent 状态、审批闸口…）不算——否则一个没人看的标签页会靠轮询把「15h 空闲
 * 过期」变成永不过期，这正是本次要修的问题。
 */
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'wheel', 'visibilitychange']
let lastActivityAt = Date.now()
if (typeof window !== 'undefined') {
  ACTIVITY_EVENTS.forEach((ev) => {
    const mark = () => { lastActivityAt = Date.now() }
    window.addEventListener(ev, mark, { passive: true, capture: true })
  })
}
/** 距上次真实活动超过这个窗口，就不再吸收续期 token（让票按 15h 自然过期） */
const IDLE_RENEW_LIMIT_MS = 10 * 60 * 1000

/**
 * 收下后端下发的续期 token
 *
 * 后端对每个「带合法 token」的请求都重新签发一张 15h 的票并通过该头返回，
 * 前端静默替换即可实现「15 小时内有活动 → 重新计时」。
 * 头不存在（未鉴权请求 / 旧后端）或当前处于空闲态时什么都不做。
 */
function consumeRefreshedToken(auth, headerValue) {
  if (!headerValue) return
  if (Date.now() - lastActivityAt > IDLE_RENEW_LIMIT_MS) return
  auth.setToken(headerValue)
}

/**
 * 带认证的 fetch：自动附加 Bearer token，401 时登出并跳转登录页
 * （行为与原 utils/authFetch.js 一致）
 */
export async function authFetch(url, options = {}) {
  const auth = useAuthStore()
  const headers = new Headers(options.headers || {})
  if (auth.token) {
    headers.set('Authorization', `Bearer ${auth.token}`)
  }
  const res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    auth.logout()
    const current = router.currentRoute.value
    if (current.path !== '/login') {
      router.replace({
        path: '/login',
        query: current.path === '/' ? {} : { redirect: current.fullPath },
      })
    }
    throw new Error('登录已过期，请重新登录')
  }
  consumeRefreshedToken(auth, res.headers.get(REFRESH_HEADER))
  return res
}

/** 解析 JSON 响应，code!==200 时抛错 */
export async function parseJson(res, fallbackMsg = '请求失败') {
  let json
  try {
    json = await res.json()
  } catch {
    throw new Error(fallbackMsg)
  }
  if (!res.ok || json.code !== 200) {
    throw new Error(json?.detail || json?.message || fallbackMsg)
  }
  return json
}

/** 拼接 query string，跳过 undefined / null / 空串（与 api/dashboard.js 现状一致） */
export function buildQuery(params = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.append(k, v)
  })
  return qs.toString()
}

/** 为 URL 附加 query string */
export function withQuery(url, params) {
  const qs = buildQuery(params)
  return qs ? `${url}?${qs}` : url
}

/** 合并默认 JSON 头与自定义头（自定义优先） */
function jsonHeaders(extra = {}) {
  return { 'Content-Type': 'application/json', ...extra }
}

// ==================== 原始 Response 系列（需自行处理状态码 / 二进制） ====================

export function getRaw(url, options = {}) {
  return authFetch(url, { ...options, method: options.method || 'GET' })
}

export function postRaw(url, body, options = {}) {
  return authFetch(url, {
    ...options,
    method: 'POST',
    headers: jsonHeaders(options.headers),
    body: JSON.stringify(body),
  })
}

export function putRaw(url, body, options = {}) {
  return authFetch(url, {
    ...options,
    method: 'PUT',
    headers: jsonHeaders(options.headers),
    body: JSON.stringify(body),
  })
}

export function deleteRaw(url, options = {}) {
  return authFetch(url, { ...options, method: 'DELETE' })
}

/** 上传 FormData（不设置 Content-Type，交给浏览器补 boundary） */
export function postForm(url, formData, options = {}) {
  return authFetch(url, { ...options, method: 'POST', body: formData })
}

/**
 * 上传 FormData（XHR 版，支持真实上传进度）
 *
 * fetch 不暴露上传进度，需要进度条的上传走本函数：
 *   - options.onProgress(loaded, total)：上传字节进度回调
 *   - 认证头 / 401 处理与 authFetch 一致
 *   - 返回解析后的响应信封 { code, message, data }，401/网络错误抛异常
 */
export function postFormWithProgress(url, formData, options = {}) {
  return new Promise((resolve, reject) => {
    const auth = useAuthStore()
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    if (auth.token) xhr.setRequestHeader('Authorization', `Bearer ${auth.token}`)
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && options.onProgress) options.onProgress(e.loaded, e.total)
    })
    xhr.addEventListener('load', () => {
      if (xhr.status === 401) {
        auth.logout()
        router.replace({ path: '/login' })
        reject(new Error('登录已过期，请重新登录'))
        return
      }
      consumeRefreshedToken(auth, xhr.getResponseHeader(REFRESH_HEADER))
      let json
      try {
        json = JSON.parse(xhr.responseText)
      } catch {
        reject(new Error('响应解析失败'))
        return
      }
      resolve(json)
    })
    xhr.addEventListener('error', () => reject(new Error('网络错误')))
    xhr.addEventListener('abort', () => reject(new Error('上传已取消')))
    xhr.send(formData)
  })
}

// ==================== JSON 系列（返回完整信封，不抛业务错） ====================

/** GET → json */
export async function get(url, params, options = {}) {
  const res = await getRaw(withQuery(url, params), options)
  return await res.json()
}

/** POST JSON → json */
export async function post(url, body, options = {}) {
  const res = await postRaw(url, body, options)
  return await res.json()
}

/** PUT JSON → json */
export async function put(url, body, options = {}) {
  const res = await putRaw(url, body, options)
  return await res.json()
}

/** DELETE → json */
export async function del(url, options = {}) {
  const res = await deleteRaw(url, options)
  return await res.json()
}

/** POST FormData → json */
export async function postFormJson(url, formData, options = {}) {
  const res = await postForm(url, formData, options)
  return await res.json()
}

/**
 * 流式请求（fetch + reader），返回原始 Response 供调用方逐帧解析
 * 注意：Agent 进度与 RAG 流式都走 fetch reader（见 api/agent.js::openTaskStream），
 *       这样鉴权统一走 Authorization 头，JWT 不会出现在 URL / 网关访问日志里
 */
export function postStream(url, body, options = {}) {
  return authFetch(url, {
    ...options,
    method: 'POST',
    headers: jsonHeaders(options.headers),
    body: JSON.stringify(body),
  })
}
