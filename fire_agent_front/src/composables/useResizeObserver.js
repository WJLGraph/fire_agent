/**
 * 容器尺寸监听组合式函数
 *
 * 优先使用 ResizeObserver（精确到容器，优于 window.resize）；
 * 环境不支持时降级为 window resize，保证行为不劣化。
 *
 * 用法：
 *   const chartRef = ref(null)
 *   useResizeObserver(chartRef, () => chartInstance?.resize())
 *
 * @param {import('vue').Ref<HTMLElement|null>|HTMLElement} target 目标元素或其 ref
 * @param {(entry?: ResizeObserverEntry) => void} handler 尺寸变化回调
 */
import { onScopeDispose, watch, nextTick } from 'vue'

export function useResizeObserver(target, handler) {
  let observer = null
  let boundEl = null
  let fallbackHandler = null
  let stopWatch = null

  const resolveEl = () => {
    const t = target && typeof target === 'object' && 'value' in target ? target.value : target
    return t || null
  }

  const cleanup = () => {
    if (observer) {
      observer.disconnect()
      observer = null
    }
    if (fallbackHandler) {
      window.removeEventListener('resize', fallbackHandler)
      fallbackHandler = null
    }
    if (stopWatch) {
      stopWatch()
      stopWatch = null
    }
    boundEl = null
  }

  const bind = () => {
    const el = resolveEl()
    if (!el || el === boundEl) return
    cleanup()
    boundEl = el

    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => handler())
      observer.observe(el)
    } else {
      fallbackHandler = () => handler()
      window.addEventListener('resize', fallbackHandler)
    }
  }

  // 目标 ref 可能晚于 composable 挂载（v-if / Teleport 场景），用 watch 兜住
  if (target && typeof target === 'object' && 'value' in target) {
    stopWatch = watch(target, () => nextTick(bind), { immediate: false, flush: 'post' })
  }

  nextTick(bind)
  onScopeDispose(cleanup)

  return { bind, cleanup }
}

export default useResizeObserver
