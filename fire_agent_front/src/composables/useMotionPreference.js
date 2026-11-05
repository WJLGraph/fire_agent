/**
 * useMotionPreference — 公开页组三态动效偏好（模块级单例，跨页共享）
 *
 * 三态：auto（默认，遵循系统 prefers-reduced-motion）/ on（强制开启）/ off（强制静态）
 * - 持久化 localStorage `wl-motion-pref`；默认 auto，尊重无障碍
 * - motionAllowed：响应式「当前是否允许动效」，供全部 JS 开关统一接入
 * - 同步 <html data-motion="auto|on|off"> 与 <html data-motion-allowed="true|false">：
 *   CSS 降级规则用 data-motion-allowed 精确控制（on 可覆盖系统 reduce）；
 *   原有 @media reduce 规则保留 html:not([data-motion="on"]) 形式兜底（JS 未就绪时）
 * - 监听系统偏好变化，auto 模式下实时生效
 */
import { ref, computed, watchEffect } from 'vue'

const KEY = 'wl-motion-pref'
const VALID = ['auto', 'on', 'off']

const readPref = () => {
  try {
    const v = localStorage.getItem(KEY)
    return VALID.includes(v) ? v : 'auto'
  } catch {
    return 'auto'
  }
}

const prefersReducedMQ = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null
const systemReduced = ref(!!(prefersReducedMQ && prefersReducedMQ.matches))

if (prefersReducedMQ) {
  const onSysChange = (e) => { systemReduced.value = e.matches }
  if (prefersReducedMQ.addEventListener) prefersReducedMQ.addEventListener('change', onSysChange)
  else if (prefersReducedMQ.addListener) prefersReducedMQ.addListener(onSysChange)
}

export const motionPref = ref(readPref())

/** 当前是否允许动效（唯一裁决出口：on 强制开 / off 强制关 / auto 随系统） */
export const motionAllowed = computed(() => {
  if (motionPref.value === 'on') return true
  if (motionPref.value === 'off') return false
  return !systemReduced.value
})

export const setMotionPref = (p) => {
  if (!VALID.includes(p)) return
  motionPref.value = p
  try { localStorage.setItem(KEY, p) } catch { /* 隐私模式等：仅内存生效 */ }
}

/** 循环切换 auto → on → off → auto */
export const cycleMotionPref = () => {
  const next = motionPref.value === 'auto' ? 'on' : motionPref.value === 'on' ? 'off' : 'auto'
  setMotionPref(next)
  return next
}

// <html> 属性同步：CSS 选择器入口（data-motion=原始三态；data-motion-allowed=裁决结果）
watchEffect(() => {
  const el = document.documentElement
  el.dataset.motion = motionPref.value
  el.dataset.motionAllowed = String(motionAllowed.value)
})
