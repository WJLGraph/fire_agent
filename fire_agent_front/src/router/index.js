/**
 * 多页面路由表
 *
 * 页面结构：
 *   /welcome*         → 对外公开页组（总览 / 能力 / 工作流 / 技术 / 关于，站点根路径 / 指向总览）
 *   /login           → 登录/注册
 *   /dashboard       → 作战大屏（现有 GIS 大屏）
 *   /smart-query     → 智能查询
 *   /knowledge-base  → 知识库 RAG 问答
 *   /agent-center    → Agent 协作中心
 *   /report-center   → 报告中心
 *   /profile         → 个人中心（资料/密码）
 *   /admin           → 系统管理（仅管理员）
 */
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { motionAllowed } from '@/composables/useMotionPreference'

const router = createRouter({
    history: createWebHistory(
        import.meta.env.BASE_URL),
    routes: [{
            path: '/',
            redirect: '/welcome'
        },
        {
            path: '/welcome',
            name: 'welcome',
            component: () =>
                import ('@/views/welcome/index.vue'),
            meta: { public: true }
        },
        {
            path: '/welcome/features',
            name: 'welcome-features',
            component: () =>
                import ('@/views/welcome/features.vue'),
            meta: { public: true }
        },
        {
            path: '/welcome/workflow',
            name: 'welcome-workflow',
            component: () =>
                import ('@/views/welcome/workflow.vue'),
            meta: { public: true }
        },
        {
            path: '/welcome/technology',
            name: 'welcome-technology',
            component: () =>
                import ('@/views/welcome/technology.vue'),
            meta: { public: true }
        },
        {
            path: '/welcome/about',
            name: 'welcome-about',
            component: () =>
                import ('@/views/welcome/about.vue'),
            meta: { public: true }
        },
        {
            path: '/login',
            name: 'login',
            component: () =>
                import ('@/views/login/index.vue'),
            meta: { public: true }
        },
        {
            path: '/dashboard',
            name: 'dashboard',
            component: () =>
                import ('@/views/dashboard/index.vue')
        },
        {
            path: '/smart-query',
            name: 'smart-query',
            component: () =>
                import ('@/views/smart-query/index.vue')
        },
        {
            path: '/knowledge-base',
            name: 'knowledge-base',
            component: () =>
                import ('@/views/knowledge-base/index.vue')
        },
        {
            path: '/agent-center',
            name: 'agent-center',
            component: () =>
                import ('@/views/agent-center/index.vue')
        },
        {
            path: '/report-center',
            name: 'report-center',
            component: () =>
                import ('@/views/report-center/index.vue')
        },
        {
            path: '/profile',
            name: 'profile',
            component: () =>
                import ('@/views/profile/index.vue')
        },
        {
            path: '/admin',
            name: 'admin',
            component: () =>
                import ('@/views/admin/index.vue'),
            meta: { requiresAdmin: true }
        }
    ]
})

/* ==================== 公开页组路由转场（View Transitions API，渐进增强） ====================
   仅 /welcome ↔ /welcome 子页间导航启用；旧页 200ms 淡出上移，新页 320ms clip-path 横向展开
   （按页面序号区分前进/后退方向，qt.css 消费 html[data-vt-dir]）。
   reduced-motion / 不支持 startViewTransition 时直接放行，无任何开销。
   带 data-no-vt 的元素（Hero/结尾 CTA 等）点击后直接导航，不包转场——
   用 pointerdown 捕获阶段打标记，beforeResolve 消费一次。 */
let vtBypass = false
window.addEventListener('pointerdown', (e) => {
    vtBypass = !!(e.target && e.target.closest && e.target.closest('[data-no-vt]'))
}, { capture: true, passive: true })

const PAGE_ORDER = ['/welcome', '/welcome/features', '/welcome/workflow', '/welcome/technology', '/welcome/about']

/* VT 页码标签：mono 标签 + 横向细线扫过（≤320ms，qt.css #vt-banner） */
const VT_NAMES = {
    '/welcome': 'PAGE 01 / OVERVIEW',
    '/welcome/features': 'PAGE 02 / CAPABILITIES',
    '/welcome/workflow': 'PAGE 03 / PIPELINE',
    '/welcome/technology': 'PAGE 04 / TECHNOLOGY',
    '/welcome/about': 'PAGE 05 / ABOUT',
}
const vtBanner = (to) => {
    let el = document.getElementById('vt-banner')
    if (!el) {
        el = document.createElement('div')
        el.id = 'vt-banner'
        el.setAttribute('aria-hidden', 'true')
        document.body.appendChild(el)
    }
    el.innerHTML = `<span class="vtb__tag">${VT_NAMES[to.path] || ''}</span><i class="vtb__line"></i>`
    el.classList.remove('is-on')
    void el.offsetWidth // 重触发动画
    el.classList.add('is-on')
}

router.beforeResolve((to, from) => {
    const inPublic = to.path.startsWith('/welcome') && from.path.startsWith('/welcome')
    if (!inPublic || to.path === from.path || vtBypass) { vtBypass = false; return }
    if (!document.startViewTransition) return
    if (!motionAllowed.value) return
    vtBanner(to)
    const ti = PAGE_ORDER.indexOf(to.path)
    const fi = PAGE_ORDER.indexOf(from.path)
    document.documentElement.dataset.vtDir = ti >= fi ? 'next' : 'prev'
    return new Promise((resolve) => {
        const transition = document.startViewTransition(() => resolve())
        transition.finished.finally(() => { delete document.documentElement.dataset.vtDir })
    })
})

router.beforeEach((to, from, next) => {
    // 登录页无需鉴权
    if (to.meta.public) {
        next()
        return
    }
    try {
        const auth = useAuthStore()
        if (!auth.isLoggedIn) {
            next({ path: '/login', query: to.path === '/' ? {} : { redirect: to.fullPath } })
            return
        }
        // 系统管理页仅管理员可访问
        const userRole = auth.user && auth.user.role
        if (to.meta.requiresAdmin && userRole !== 'admin') {
            ElMessage.warning('需要管理员权限')
            next('/dashboard')
            return
        }
    } catch {
        /* pinia 未初始化时放行 */
    }
    next()
})

export default router