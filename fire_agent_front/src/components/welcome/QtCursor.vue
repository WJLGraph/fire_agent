<script setup>
/**
 * QtCursor — 公开页自定义光标层（桌面端专属）
 *
 * 手法：双层跟随（本体的点即时、外环 lerp 缓动）+ 交互态变形
 * （hover 可点元素时外环放大转强调色），克制不遮蔽：保留系统光标，
 * 环只作伴随层，不牺牲表单与链接可用性。
 *
 * 启用条件（不满足则整组件不渲染）：
 *   - (pointer: fine)  → 触屏自动禁用
 *   - 非 prefers-reduced-motion
 * 生命周期：rAF 循环 + 被动监听；卸载全量移除。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { motionAllowed } from '@/composables/useMotionPreference'

const enabled = ref(false)
const dotRef = ref(null)
const ringRef = ref(null)
const labelRef = ref(null)

let raf = 0
let px = -100, py = -100   // pointer 真实位置
let rx = -100, ry = -100   // 外环缓动位置
let scale = 1, targetScale = 1
let hot = false
let cardHot = false

const onPointerMove = (e) => {
  px = e.clientX
  py = e.clientY
}
const onOver = (e) => {
  const t = e.target
  const el = t && t.closest
    ? t.closest('a, button, [data-cursor], .qt-spot, .magnetic, summary')
    : null
  hot = !!el
  // 卡片类（qt-spot）→ 外环带「查看」短标签；链接/按钮 → 外环放大 + 本体点实心
  cardHot = !!(el && el.classList && el.classList.contains('qt-spot'))
  targetScale = hot ? 1.7 : 1
  if (labelRef.value) {
    labelRef.value.classList.toggle('is-on', cardHot)
  }
}
const tick = () => {
  rx += (px - rx) * 0.16
  ry += (py - ry) * 0.16
  scale += (targetScale - scale) * 0.14
  if (dotRef.value) {
    dotRef.value.style.transform = `translate3d(${px}px, ${py}px, 0) translate(-50%, -50%) scale(${hot ? 1.6 : 1})`
    dotRef.value.classList.toggle('is-solid', hot)
  }
  if (ringRef.value) {
    ringRef.value.style.transform = `translate3d(${rx}px, ${ry}px, 0) translate(-50%, -50%) scale(${scale.toFixed(3)})`
    ringRef.value.classList.toggle('is-hot', hot)
  }
  if (labelRef.value) {
    labelRef.value.style.transform = `translate3d(${rx + 18}px, ${ry + 18}px, 0)`
  }
  raf = requestAnimationFrame(tick)
}

onMounted(() => {
  const fine = window.matchMedia && window.matchMedia('(pointer: fine)').matches
  if (!fine) return
  enabled.value = true
  // 首帧定位到视口外，避免初始闪跳
  document.addEventListener('pointermove', onPointerMove, { passive: true })
  document.addEventListener('pointerover', onOver, { passive: true })
  raf = requestAnimationFrame(tick)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerover', onOver)
  if (raf) cancelAnimationFrame(raf)
})
</script>

<template>
  <!-- 挂载需要 pointer:fine；显隐随 motionAllowed 响应式切换（开关切换即时生效） -->
  <div v-if="enabled && motionAllowed" class="qcur" aria-hidden="true">
    <i ref="ringRef" class="qcur__ring"></i>
    <i ref="dotRef" class="qcur__dot"></i>
    <span ref="labelRef" class="qcur__label qt-eyebrow">查看</span>
  </div>
</template>

<style scoped>
.qcur {
  position: fixed;
  inset: 0;
  z-index: 90;
  pointer-events: none;
}
.qcur__dot,
.qcur__ring {
  position: absolute;
  top: 0;
  left: 0;
  border-radius: 50%;
  will-change: transform;
}
.qcur__dot {
  width: 5px;
  height: 5px;
  background: var(--fs-accent);
}
/* hover 可点元素：本体点变实心放大（CTA/链接态） */
.qcur__dot.is-solid { box-shadow: 0 0 0 2px rgba(var(--fs-accent-rgb), 0.25); }
.qcur__ring {
  width: 30px;
  height: 30px;
  border: 1px solid var(--fs-hairline-strong);
  background: rgba(var(--fs-bg-surface-rgb), 0.08);
  transition: border-color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.qcur__ring.is-hot {
  border-color: var(--fs-accent);
  background: rgba(var(--fs-accent-rgb), 0.06);
}
/* 卡片态短标签「查看」 */
.qcur__label {
  position: absolute;
  top: 0;
  left: 0;
  padding: 3px 8px;
  border-radius: var(--fs-r-xs);
  color: var(--fs-on-accent);
  background: var(--fs-accent);
  white-space: nowrap;
  opacity: 0;
  transform-origin: right bottom;
  transition: opacity var(--fs-dur-micro) var(--fs-ease);
}
.qcur__label.is-on { opacity: 1; }
/* off（或 auto+系统减）时整个光标层不渲染/不启用 */
html[data-motion-allowed="false"] .qcur { display: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .qcur { display: none; }
}
</style>
