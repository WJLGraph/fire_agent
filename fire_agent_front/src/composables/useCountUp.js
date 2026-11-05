/**
 * 数字滚动动画（visual-v0 §10.6 KPI count-up）
 *
 * 对「纯数字（可含千分位逗号）」做 rAF 补间；非数字值原样透传。
 * 用法：const text = useCountUp(() => props.value)
 */
import { ref, watch } from 'vue'

export function useCountUp(getter, { duration = 700 } = {}) {
  const display = ref('')

  const isNumeric = (v) => /^[\d,]+$/.test(String(v ?? ''))

  watch(getter, (target) => {
    if (!isNumeric(target)) {
      display.value = target ?? ''
      return
    }
    const to = Number(String(target).replace(/,/g, ''))
    const from = Number(String(display.value).replace(/,/g, '')) || 0
    if (from === to) {
      display.value = target
      return
    }
    const t0 = performance.now()
    const fmt = (n) => n.toLocaleString()
    const step = (now) => {
      const p = Math.min((now - t0) / duration, 1)
      // easeOutCubic：从容收尾，符合 §10 动效规范（不做快而急的动画）
      const eased = 1 - Math.pow(1 - p, 3)
      display.value = fmt(Math.round(from + (to - from) * eased))
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, { immediate: true })

  return display
}
