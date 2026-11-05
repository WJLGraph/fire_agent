/**
 * 认证状态管理（Pinia）
 * - token 与用户信息写入 localStorage 持久化
 * - 提供 login / register / logout / logoutRemote / setToken
 *
 * 滑动会话（15h 空闲过期）：
 *   后端每次鉴权成功都会在响应头 `X-Token-Refresh` 里下发一张「重新计时」的新 token，
 *   由 api/http.js 的 authFetch 统一收下并调用 setToken() 落盘。
 *   因此 15h 是「距最后一次操作」的空闲时限，不是登录后的绝对时限。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { API_V1 } from '@/utils/config'

const API_BASE = `${API_V1}/auth`
const TOKEN_KEY = 'fire_agent_token'
const USER_KEY = 'fire_agent_user'

export const useAuthStore = defineStore('auth', () => {
    const token = ref(localStorage.getItem(TOKEN_KEY) || '')
    const user = ref(JSON.parse(localStorage.getItem(USER_KEY) || 'null'))

    const isLoggedIn = computed(() => !!token.value)
    const displayName = computed(() => user.value ?.username || '')

    function _persist() {
        if (token.value) localStorage.setItem(TOKEN_KEY, token.value)
        else localStorage.removeItem(TOKEN_KEY)
        if (user.value) localStorage.setItem(USER_KEY, JSON.stringify(user.value))
        else localStorage.removeItem(USER_KEY)
    }

    /** 滑动续期：后端下发的新 token 覆盖旧值（只换 token，不动 user） */
    function setToken(newToken) {
        if (typeof newToken === 'string' && newToken && newToken !== token.value) {
            token.value = newToken
            _persist()
        }
    }

    async function _request(path, body) {
        const res = await fetch(`${API_BASE}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
        const json = await res.json()
        if (!res.ok || json.code !== 200) {
            throw new Error(json ?.detail || json ?.message || '请求失败')
        }
        return json.data
    }

    async function login(username, password) {
        const data = await _request('/login', { username, password })
        token.value = data.access_token
        user.value = data.user
        _persist()
    }

    async function register(username, password, email = '') {
        const data = await _request('/register', { username, password, email })
        token.value = data.access_token
        user.value = data.user
        _persist()
    }

    /** 本地更新用户信息（个人中心保存后调用） */
    function updateUser(partial) {
        if (user.value) {
            user.value = { ...user.value, ...partial }
            _persist()
        }
    }

    /** 仅清本地会话。401 兜底用它——那时 token 已失效，不该再打后端。 */
    function logout() {
        token.value = ''
        user.value = null
        _persist()
    }

    /** 用户主动退出：先让后端吊销 token_version，再清本地，失败也要清。 */
    async function logoutRemote() {
        const t = token.value
        if (t) {
            try {
                await fetch(`${API_BASE}/logout`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${t}` },
                })
            } catch {
                // 网络不可达时仍然本地登出；服务端 token 会自然过期
            }
        }
        logout()
    }

    return { token, user, isLoggedIn, displayName, login, register, logout, logoutRemote, updateUser, setToken }
})