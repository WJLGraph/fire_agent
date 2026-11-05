/**
 * 主题 Store — 浅色 / 深色双主题切换
 *
 * 实现方式：在 <html> 上增删 `dark` class（见 style/gis-theme.css）
 *   - 无 class → 浅色（默认，主强调色 #2563eb 靛蓝）
 *   - html.dark → 深色（主强调色 #22d3ee 冰青）
 * 持久化到 localStorage，刷新后保持；首屏在 main.js 中提前应用，避免闪烁。
 */
import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'fire_agent_theme'
/** 视觉体系 v2 开关：localStorage 置 'off' 即整站回退到 gis-theme.css 旧视觉 */
const V2_KEY = 'fire_agent_theme_v2'

/** 把主题模式同步到 <html> 根节点 */
export function applyTheme(mode) {
  const root = document.documentElement
  if (mode === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
  root.classList.toggle('theme-v2', localStorage.getItem(V2_KEY) !== 'off')
}

export const useThemeStore = defineStore('theme', () => {
  /** 'light' | 'dark' */
  const mode = ref(localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light')
  applyTheme(mode.value)

  watch(mode, (val) => {
    applyTheme(val)
    localStorage.setItem(STORAGE_KEY, val)
  })

  const isDark = () => mode.value === 'dark'

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function setMode(val) {
    mode.value = val === 'dark' ? 'dark' : 'light'
  }

  return { mode, isDark, toggle, setMode }
})