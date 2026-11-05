/**
 * 主题令牌组合式函数
 *
 * 统一封装「读取当前主题 CSS 变量」的响应式逻辑，供图表 / Canvas / 动态样式使用。
 * 底层复用 utils/themeTokens.js（取色实现不变），这里只补上"跟随主题切换自动重算"。
 *
 * 用法：
 *   const { mode, tokens } = useThemeTokens()
 *   // tokens.value.text / .muted / .border / .panel / .accent / .axis / .split
 */
import { computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { chartTokens, cssVar } from '@/utils/themeTokens'

export function useThemeTokens() {
  const theme = useThemeStore()

  /** 'light' | 'dark' —— 仅用于建立响应式依赖 */
  const mode = computed(() => theme.mode)

  /** 图表常用色集合，主题切换后自动重算 */
  const tokens = computed(() => chartTokens(mode.value))

  return { mode, tokens, cssVar }
}

export default useThemeTokens
