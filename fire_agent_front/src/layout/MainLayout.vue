<script setup>
/**
 * 主布局 — 左侧导航栏 + 右侧内容区
 *
 * V2 视觉重做（design/v2-shell）：
 *   - 侧栏 48 → 72px：图标 + 11px 文字，不再靠猜图标
 *   - Emoji / 字符按钮（☀ ☾ ⏻）→ 20px 线性 SVG（AppIcon）
 *   - iconfont 导航图标 → 内联 SVG，去外部字体依赖
 *   - 去金属渐变、去发光、去 scale(1.08) 弹跳；激活态只保留左侧 2px 实色条
 *   - 表面改为实色分层，无玻璃模糊
 *
 * 交互契约不变：导航项与顺序、路由跳转、主题切换、退出登录行为均保持原样。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { filterNavItems } from '@/router/navItems'
import AppIcon from '@/components/base/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()

/** 侧栏折叠态（本地状态，不持久化，不影响任何业务契约） */
const collapsed = ref(false)

const handleLogout = () => {
  auth.logoutRemote()
  router.replace('/login')
}

const handleToggleTheme = () => {
  theme.toggle()
}

// 导航项已外置到 router/navItems.js（阶段 5）：系统管理仅管理员可见
const navItems = computed(() => filterNavItems(auth.user?.role))

const userInitial = computed(() =>
  (auth.displayName || 'U').charAt(0).toUpperCase()
)

const roleLabel = computed(() => (auth.user?.role === 'admin' ? '管理员' : '值班员'))

/** 登录 / 注册 / 公开页组（/welcome 前缀）不显示侧栏（决策 D10：BlankLayout） */
const isBlank = computed(() => route.path === '/login' || route.path.startsWith('/welcome'))
</script>

<template>
  <div class="app-shell" :class="{ 'is-blank': isBlank }">
    <!-- 左侧导航栏 -->
    <aside class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
      <!-- 字标即门户入口：侧栏导航不含 welcome，这里给一条全局回首页的隐式路径 -->
      <router-link
        class="sidebar-brand"
        to="/welcome"
        data-tip="返回门户首页"
        aria-label="返回门户首页"
      >
        <span class="brand-cn" title="焰哨多Agent与可视化平台">焰哨</span>
        <span class="brand-en">FLAMESENTRY</span>
        <i class="brand-rule" aria-hidden="true"></i>
      </router-link>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: route.path === item.path }"
          :data-tip="item.label"
          :aria-current="route.path === item.path ? 'page' : undefined"
        >
          <AppIcon :name="item.icon" :size="20" />
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <button
        type="button"
        class="sidebar-collapse"
        :data-tip="collapsed ? '展开侧栏' : '收起侧栏'"
        :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
        :aria-expanded="!collapsed"
        @click="collapsed = !collapsed"
      >
        <AppIcon name="chevron-right" :size="16" :rotate="collapsed ? 0 : 180" />
        <span class="collapse-label">收起</span>
      </button>

      <!-- 用户信息 / 主题切换 / 退出 -->
      <div class="sidebar-foot">
        <div class="side-user">
          <router-link to="/profile" class="user-avatar" data-tip="个人中心" aria-label="个人中心">
            {{ userInitial }}
          </router-link>
          <span class="user-name" :data-tip="auth.displayName">{{ auth.displayName || '未登录' }}</span>
          <span class="user-role">{{ roleLabel }}</span>
        </div>
        <div class="side-actions">
          <button
            type="button"
            class="icon-btn"
            :data-tip="theme.mode === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
            :aria-label="theme.mode === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
            @click="handleToggleTheme"
          >
            <span class="ico-swap" :key="theme.mode">
              <AppIcon :name="theme.mode === 'dark' ? 'sun' : 'moon'" :size="16" />
            </span>
          </button>
          <button type="button" class="icon-btn" data-tip="退出登录" aria-label="退出登录" @click="handleLogout">
            <AppIcon name="logout" :size="16" />
          </button>
        </div>
      </div>
    </aside>

    <!-- 右侧内容区 -->
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  width: 100%;
  height: 100vh;
  height: 100dvh;
  background: var(--fs-bg-canvas);
  color: var(--fs-ink-900);
  overflow: hidden;
}

/* ==================== 侧栏 ==================== */

/* 登录 / 注册：BlankLayout，不渲染侧栏 */
.app-shell.is-blank .app-sidebar {
  display: none;
}

/* overflow 必须可见：折叠态的标签气泡要能溢出到内容区上方；
   文本外溢改由各标签自身的 max-width/height + 裁切承担 */
.app-sidebar {
  position: relative;
  z-index: 20;
  flex: none;
  width: var(--fs-sidebar-w);
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-right: 1px solid var(--fs-hairline);
  transition: width var(--fs-dur-panel) var(--fs-ease);
}

.app-sidebar.is-collapsed {
  width: 48px;
}

/* 折叠时标签「收起」而不是「消失」：高度归零 + 淡出，宽度动画与内容动画同拍 */
.brand-en,
.nav-label,
.collapse-label,
.user-name,
.user-role {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  transition:
    opacity var(--fs-dur-micro) var(--fs-ease),
    height var(--fs-dur-panel) var(--fs-ease),
    max-width var(--fs-dur-panel) var(--fs-ease);
}

/* 品牌区：字标 + 一道强调色短横（masthead），底部分隔线与右侧页头下缘同水平线 */
.sidebar-brand {
  position: relative;
  flex: none;
  height: var(--fs-topbar-h, 64px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: gap var(--fs-dur-panel) var(--fs-ease);
  /* 现在是门户入口链接：去掉下划线与浏览器默认色，字重/字色仍由 brand-cn / brand-en 承担 */
  text-decoration: none;
  color: inherit;
}
.sidebar-brand:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: -3px;
}
.brand-cn {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--fs-ink-900);
  transition: letter-spacing var(--fs-dur-panel) var(--fs-ease);
}
.sidebar-brand:hover .brand-cn {
  letter-spacing: 0.14em;
}
.brand-en {
  max-width: 100%;
  height: 10px;
  font-family: var(--fs-font-mono);
  font-size: 8px;
  font-weight: 500;
  line-height: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
}
.brand-rule {
  display: block;
  width: 18px;
  height: 1px;
  background: var(--fs-accent);
  opacity: 0.55;
  transform: scaleX(0);
  transform-origin: center;
  animation: brand-rule-in 0.6s 0.15s var(--fs-ease-out) forwards;
}
@keyframes brand-rule-in {
  to { transform: scaleX(1); }
}

.app-sidebar.is-collapsed .sidebar-brand { gap: 0; }
.app-sidebar.is-collapsed .brand-en { height: 0; opacity: 0; }
.app-sidebar.is-collapsed .brand-rule { width: 12px; }

/* 导航 */
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--fs-s3) 0;
  gap: 2px;
}

.nav-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 52px;
  text-decoration: none;
  color: var(--fs-ink-500);
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background var(--fs-dur-micro) var(--fs-ease),
    gap var(--fs-dur-panel) var(--fs-ease);
}
.nav-item:hover {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
}
/* 图标随 hover 抬 1px：命令轨的「按下去之前先浮起来」 */
.nav-item .app-icon {
  transition: transform var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.nav-item:hover .app-icon {
  transform: translateY(-1px);
}
.nav-item:active .app-icon {
  transform: translateY(0);
}

/* 激活态：左侧 2px 强调条（常驻节点 + scaleY 生长，路由切换时是「长出来」而非「跳出来」） */
.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 2px;
  height: 22px;
  background: var(--fs-accent);
  border-radius: 0 2px 2px 0;
  transform: translateY(-50%) scaleY(0);
  transition: transform var(--fs-dur-panel) var(--fs-ease);
}
.nav-item.active {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
}
.nav-item.active::before {
  transform: translateY(-50%) scaleY(1);
}
.nav-item.active .app-icon {
  color: var(--fs-accent);
}
.nav-label {
  max-width: 100%;
  /* 行盒需高于字号：11px 字号配 11px 行高会把中文字肩与 g/p/q 下伸部裁掉（折叠栏标签「字显示不全」的根因） */
  height: 15px;
  font-size: 11px;
  font-weight: 500;
  line-height: 15px;
  letter-spacing: 0.02em;
}
.nav-item.active .nav-label {
  font-weight: 600;
}
.app-sidebar.is-collapsed .nav-item { gap: 0; }
.app-sidebar.is-collapsed .nav-label { height: 0; opacity: 0; }

/* 折叠开关 */
.sidebar-collapse {
  position: relative;
  flex: none;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--fs-ink-400);
  cursor: pointer;
  border-top: 1px solid var(--fs-hairline);
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background var(--fs-dur-micro) var(--fs-ease),
    gap var(--fs-dur-panel) var(--fs-ease);
}
.sidebar-collapse:hover {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
}
.collapse-label {
  max-width: 32px;
  font-size: 10px;
  letter-spacing: 0.04em;
}
.app-sidebar.is-collapsed .sidebar-collapse { gap: 0; }
.app-sidebar.is-collapsed .collapse-label { max-width: 0; opacity: 0; }

/* 用户区块 */
.sidebar-foot {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--fs-s2);
  padding: var(--fs-s3) 0 var(--fs-s4);
  border-top: 1px solid var(--fs-hairline);
}
.side-user {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
  max-width: 100%;
  transition: gap var(--fs-dur-panel) var(--fs-ease);
}
.user-avatar {
  position: relative;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--fs-ink-700);
  background: var(--fs-bg-sunken);
  border: 1px solid var(--fs-hairline);
  border-radius: 50%;
  text-decoration: none;
  transition:
    border-color var(--fs-dur-micro) var(--fs-ease),
    color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
/* hover：强调色描边 + 同色 3px 柔光环（与输入框聚焦同一套语言） */
.user-avatar:hover {
  color: var(--fs-accent);
  border-color: var(--fs-accent);
  box-shadow: 0 0 0 3px var(--fs-accent-soft);
  transform: translateY(-1px);
}
.user-avatar:active { transform: translateY(0); }
.user-name {
  max-width: 100%;
  height: 14px;
  font-size: 11px;
  line-height: 14px;
  color: var(--fs-ink-700);
}
.user-role {
  height: 12px;
  font-size: 10px;
  line-height: 12px;
  letter-spacing: 0.04em;
  color: var(--fs-ink-400);
}
.app-sidebar.is-collapsed .side-user { gap: 0; }
.app-sidebar.is-collapsed .user-name,
.app-sidebar.is-collapsed .user-role { height: 0; opacity: 0; }

.side-actions {
  display: flex;
  gap: 2px;
}
.icon-btn {
  position: relative;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--fs-ink-500);
  cursor: pointer;
  border-radius: var(--fs-r-sm);
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.icon-btn:hover {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
}
.icon-btn:active {
  transform: translateY(0.5px);
}
/* 主题切换：图标换名时旋转淡入（:key 重挂载触发一次） */
.ico-swap {
  display: flex;
  animation: ico-swap var(--fs-dur-panel) var(--fs-ease-out) both;
}
@keyframes ico-swap {
  from { opacity: 0; transform: rotate(-50deg) scale(0.72); }
  to { opacity: 1; transform: none; }
}

/* ==================== 命令轨气泡（替代原生 title：零延迟、随主题、可读） ==================== */
.nav-item::after,
.sidebar-collapse::after,
.icon-btn::after,
.user-avatar::after,
.user-name::after {
  content: attr(data-tip);
  position: absolute;
  left: calc(100% + 10px);
  top: 50%;
  z-index: 60;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.5;
  letter-spacing: 0.02em;
  white-space: nowrap;
  color: var(--fs-ink-700);
  background: var(--fs-bg-raised);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm);
  box-shadow: var(--fs-e2);
  opacity: 0;
  transform: translateY(-50%) translateX(-4px);
  pointer-events: none;
  transition:
    opacity var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
/* 图标按钮：常驻气泡 */
.sidebar-collapse:hover::after,
.sidebar-collapse:focus-visible::after,
.icon-btn:hover::after,
.icon-btn:focus-visible::after,
.user-avatar:hover::after,
.user-avatar:focus-visible::after {
  opacity: 1;
  transform: translateY(-50%) translateX(0);
}
/* 导航项：只在折叠（标签被收起）时补偿 */
.app-sidebar.is-collapsed .nav-item:hover::after,
.app-sidebar.is-collapsed .nav-item:focus-visible::after {
  opacity: 1;
  transform: translateY(-50%) translateX(0);
}
/* 用户名：只在展开（可能被省略号截断）时补偿 */
.app-sidebar:not(.is-collapsed) .user-name:hover::after {
  opacity: 1;
  transform: translateY(-50%) translateX(0);
}
/* 空 data-tip 不画空气泡 */
[data-tip='']::after {
  content: none;
}

/* ==================== 内容区 ==================== */

.app-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

@media (prefers-reduced-motion: reduce) {
  .app-sidebar,
  .brand-en,
  .nav-label,
  .collapse-label,
  .user-name,
  .user-role,
  .sidebar-brand,
  .sidebar-collapse,
  .side-user,
  .nav-item,
  .nav-item::before,
  .nav-item .app-icon,
  .user-avatar,
  .icon-btn { transition: none; }
  .brand-rule { animation: none; transform: scaleX(1); }
  .ico-swap { animation: none; }
  .nav-item:hover .app-icon,
  .user-avatar:hover,
  .icon-btn:active { transform: none; }
}
</style>
