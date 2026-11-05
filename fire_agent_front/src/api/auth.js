/**
 * 认证 API — /api/v1/auth/*
 *
 * 说明：/login 与 /register 仍由 stores/auth.js 负责（除发请求外还要持久化 token 与用户信息，
 * 属状态职责，不迁入 api 层）；本模块承载个人中心的资料与密码修改。
 */
import { put } from '@/api/http'
import { API_V1 } from '@/utils/config'

const BASE = `${API_V1}/auth`

/** PUT /auth/me — 更新个人资料（邮箱） */
export function updateMe(email) {
  return put(`${BASE}/me`, { email })
}

/**
 * PUT /auth/me/password — 修改密码
 * @param {{ old_password: string, new_password: string }} payload
 */
export function changePassword(payload) {
  return put(`${BASE}/me/password`, {
    old_password: payload.old_password,
    new_password: payload.new_password,
  })
}
