/**
 * useReveal — 内部页轻量滚动显现（IntersectionObserver，零依赖）
 *
 * 约定：
 *   - 容器内 .rv-i 元素进入视口 80% 时加 .is-in（once 后 unobserve）
 *   - [data-reveal-group] 容器内的 .rv-i 按序 70ms 错峰，仅前 6 个有延迟
 *   - 只动 transform/opacity/filter（配合 qt.css .rv-i 过渡）
 *   - prefers-reduced-motion：直接全部 is-in，不建 observer
 *   - 卸载时 disconnect，路由离开零残留
 *
 * 用法：页面根节点加 ref，setup 里 useReveal(rootRef)。
 */
import { onMounted, onBeforeUnmount } from 'vue'

export function useReveal(rootRef) {
  let io = null
  onMounted(() => {
    const root = rootRef.value
    if (!root) return
    const els = Array.from(root.querySelectorAll('.rv-i'))
    if (!els.length) return
    const reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
    if (reduced || !('IntersectionObserver' in window)) {
      els.forEach((el) => el.classList.add('is-in'))
      return
    }
    root.querySelectorAll('[data-reveal-group]').forEach((group) => {
      group.querySelectorAll('.rv-i').forEach((el, i) => {
        if (i < 6) el.style.transitionDelay = `${i * 70}ms`
      })
    })
    io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return
        en.target.classList.add('is-in')
        io.unobserve(en.target)
      })
    }, { threshold: 0.2, rootMargin: '0px 0px -8% 0px' })
    els.forEach((el) => io.observe(el))
  })
  onBeforeUnmount(() => {
    io?.disconnect()
    io = null
  })
}
