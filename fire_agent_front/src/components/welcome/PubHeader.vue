<script setup>
/**
 * 公开页组统一页头：品牌字标 / 五页导航 / 主题切换 / 进入 CTA
 *
 * - 导航高亮跟随当前路由（/welcome 及其子页）
 * - 滚动态由页面级 usePubMotion 通过 provide/inject 下发（收缩 + 磨砂底）
 * - CTA 文案随登录态切换：进入系统（已登录 → /dashboard）/ 进入指挥平台（未登录 → /login）
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import AppIcon from '@/components/base/AppIcon.vue'
import { usePubScrolled } from '@/composables/usePubMotion'
import { motionPref, motionAllowed, cycleMotionPref, setMotionPref } from '@/composables/useMotionPreference'

const props = defineProps({
  /** 总览页传 false：隐藏「返回上一页」，避免回到站外 */
  showBack: { type: Boolean, default: true },
})

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()
const scrolled = usePubScrolled()

/** 动效开关：三态循环 auto → on → off；aria-pressed 反映当前是否允许动效 */
const motionLabel = computed(() => {
  if (motionPref.value === 'on') return '已开启'
  if (motionPref.value === 'off') return '已关闭'
  return '跟随系统'
})
const onMotionToggle = () => cycleMotionPref()

/** 返回上一页：有站内历史则 back，否则回总览（不产生死链/离站跳转） */
const goBack = () => {
  const st = window.history.state
  if (st && st.back) router.back()
  else router.replace('/welcome')
}

const navItems = [
  { path: '/welcome', label: '总览' },
  { path: '/welcome/features', label: '能力' },
  { path: '/welcome/workflow', label: '工作流' },
  { path: '/welcome/technology', label: '技术' },
  { path: '/welcome/about', label: '关于' },
]

const isActive = (path) =>
  path === '/welcome' ? route.path === '/welcome' : route.path.startsWith(path)

const enterTarget = computed(() => (auth.isLoggedIn ? '/dashboard' : '/login'))
const enterLabel = computed(() => (auth.isLoggedIn ? '进入系统' : '进入指挥平台'))
</script>

<template>
  <header class="pub-nav" :class="{ 'is-scrolled': scrolled }">
    <div class="pub-nav__inner">
      <div class="pub-brand-row">
        <router-link to="/welcome" class="pub-brand qt-focus">
          <span class="pub-brand__cn">焰哨</span>
          <span class="pub-brand__en qt-eyebrow">FLAMESENTRY</span>
        </router-link>
        <button v-if="showBack" type="button" class="pub-back qt-focus" aria-label="返回上一页" title="返回上一页" @click="goBack">
          <AppIcon name="chevron-right" :size="13" :rotate="180" />
          返回
        </button>
        <button
          type="button"
          class="pub-motion qt-focus"
          :aria-pressed="String(motionAllowed)"
          :aria-label="`页面动效：当前${motionLabel}，点击切换`"
          title="页面动效：点击切换（跟随系统 / 已开启 / 已关闭）"
          @click="onMotionToggle"
        >动效 · {{ motionLabel }}</button>
        <!-- 系统已减少动效且处于 auto 时的手动开启入口（极简一行，不新增卡片） -->
        <button
          v-if="motionPref === 'auto' && !motionAllowed"
          type="button"
          class="pub-motion-hint qt-focus"
          aria-label="系统已开启减少动效，点此手动开启动效"
          @click="setMotionPref('on')"
        >系统已减 · 开启</button>
      </div>

      <nav class="pub-nav__links" aria-label="公开页导航">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="pub-nav__link qt-focus"
          :class="{ 'is-active': isActive(item.path) }"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="pub-nav__acts">
        <button
          type="button"
          class="pub-theme qt-focus"
          :title="theme.mode === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          :aria-label="theme.mode === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          @click="theme.toggle()"
        >
          <AppIcon :name="theme.mode === 'dark' ? 'sun' : 'moon'" :size="16" />
        </button>
        <router-link class="pub-cta qt-focus" :to="enterTarget">{{ enterLabel }}</router-link>
      </div>
    </div>
  </header>
</template>

<style scoped>
.pub-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--fs-bg-surface);
  border-bottom: 1px solid transparent;
  transition: background var(--fs-dur-panel) var(--fs-ease), border-color var(--fs-dur-panel) var(--fs-ease), box-shadow var(--fs-dur-panel) var(--fs-ease);
}
.pub-nav.is-scrolled {
  border-bottom-color: var(--fs-hairline);
  box-shadow: var(--fs-e1);
}
.pub-nav__inner {
  width: min(1200px, 100% - 48px);
  margin: 0 auto;
  height: 64px;
  display: flex;
  align-items: center;
  gap: var(--fs-s6);
  transition: height var(--fs-dur-panel) var(--fs-ease);
}
.pub-nav.is-scrolled .pub-nav__inner { height: 52px; }

.pub-brand-row { display: flex; align-items: center; gap: 14px; min-width: 0; }
.pub-brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
  text-decoration: none;
}
.pub-brand__cn {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--fs-ink-900);
  transition: font-size var(--fs-dur-panel) var(--fs-ease);
}
.pub-nav.is-scrolled .pub-brand__cn { font-size: 17px; }
/* 返回上一页：品牌右侧的小型幽灵按钮（qt 体系：发丝边 + 光照 hover） */
.pub-back {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 10px;
  font-size: 11px;
  color: var(--fs-ink-500);
  background: transparent;
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), border-color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.pub-back:hover {
  color: var(--fs-ink-900);
  border-color: var(--fs-hairline-strong);
  background: rgba(var(--fs-ink-900-rgb), 0.04);
}
.pub-back:hover svg { transform: translateX(-2px); }
.pub-back svg { transition: transform var(--fs-dur-micro) var(--fs-ease); }
/* 动效三态开关（跟随系统 / 已开启 / 已关闭）：mono 小按钮，不抢视觉 */
.pub-motion {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-500);
  background: transparent;
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), border-color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.pub-motion[aria-pressed="true"] { color: var(--fs-accent); border-color: rgba(var(--fs-accent-rgb), 0.4); }
.pub-motion:hover { color: var(--fs-ink-900); border-color: var(--fs-hairline-strong); background: rgba(var(--fs-ink-900-rgb), 0.04); }
/* 系统已减少动效时的手动开启提示（auto 态才出现） */
.pub-motion-hint {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 8px;
  font-size: 11px;
  color: var(--fs-accent);
  background: transparent;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  text-decoration: underline dashed;
  text-underline-offset: 3px;
}
.pub-motion-hint:hover { color: var(--fs-accent-hover); }

.pub-nav__links {
  margin-left: auto;
  display: flex;
  gap: var(--fs-s2);
}
.pub-nav__link {
  position: relative;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--fs-ink-500);
  text-decoration: none;
  border-radius: var(--fs-r-sm);
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.pub-nav__link:hover { color: var(--fs-ink-900); background: rgba(var(--fs-ink-900-rgb), 0.04); }
/* 悬停底边细线自左展开（与子页卡片 hover 同一语言；当前项由左侧锚点表达，不重复画线） */
.pub-nav__link:not(.is-active)::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 3px;
  height: 1px;
  background: var(--fs-accent);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.22s var(--fs-ease);
}
.pub-nav__link:not(.is-active):hover::after,
.pub-nav__link:not(.is-active):focus-visible::after { transform: scaleX(1); }
.pub-nav__link.is-active {
  color: var(--fs-ink-900);
  font-weight: 600;
  background: rgba(var(--fs-ink-900-rgb), 0.05);
}
/* 当前项左侧 2px 实色锚点（与内部侧栏激活语法同源） */
.pub-nav__link.is-active::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 50%;
  transform: translateY(-50%);
  width: 2px;
  height: 12px;
  border-radius: 1px;
  background: var(--fs-accent);
}

.pub-nav__acts { display: flex; align-items: center; gap: 10px; }
.pub-theme {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--fs-ink-500);
  border: 1px solid var(--fs-hairline);
  border-radius: 50%;
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), border-color var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.pub-theme svg { transition: transform 0.4s var(--fs-ease); }
.pub-theme:hover { color: var(--fs-ink-900); border-color: var(--fs-hairline-strong); }
.pub-theme:hover svg { transform: rotate(30deg); }
.pub-theme:active { transform: scale(0.94); }

.pub-cta {
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 16px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-decoration: none;
  color: var(--fs-on-accent);
  background: var(--fs-accent);
  border: none;
  border-radius: var(--fs-r-sm);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
  transition: background var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
/* 扫光与总览页主按钮同参：hover 一次 0.6s，active 下沉 */
.pub-cta::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, transparent 35%, rgba(255, 255, 255, 0.32) 50%, transparent 65%);
  transform: translateX(-160%);
  pointer-events: none;
}
.pub-cta:hover { background: var(--fs-accent-hover); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e2); }
.pub-cta:hover::before { animation: cta-sweep 0.6s var(--fs-ease); }
.pub-cta:active { transform: translateY(1px) scale(0.985); }
@keyframes cta-sweep { to { transform: translateX(160%); } }
html[data-motion-allowed="false"] .pub-cta:hover::before { animation: none; }
/* off（或 auto+系统减）：按钮/图标不做位移与旋转，只保留颜色与阴影 */
html[data-motion-allowed="false"] .pub-cta:active,
html[data-motion-allowed="false"] .pub-theme:active,
html[data-motion-allowed="false"] .pub-theme:hover svg { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .pub-cta:hover::before { animation: none; }
  html:not([data-motion="on"]) .pub-cta:active,
  html:not([data-motion="on"]) .pub-theme:active,
  html:not([data-motion="on"]) .pub-theme:hover svg { transform: none; }
}

@media (max-width: 760px) {
  .pub-nav__links { display: none; }
  .pub-brand__en { display: none; }
  .pub-back { height: 24px; padding: 0 8px; }
}
</style>
