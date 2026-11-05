<script setup>
/**
 * AppIcon — 内联 SVG 线性图标底座
 *
 * 目的：替换现存「Emoji / 字符当图标」的写法（MainLayout 的 ☀ ☾ ⏻ 等），
 * 统一 20px、stroke 1.5、round cap/join 的线性风格，跨平台字形一致。
 *
 * 用法：
 *   <AppIcon name="close" />
 *   <AppIcon name="mic" :size="16" />
 *
 * 约束：
 *   - 不引入任何图标库依赖，图标为手工精简路径
 *   - 纯装饰元素默认 aria-hidden，需要语义时由调用方包裹并补 title
 */
import { computed } from 'vue'

const props = defineProps({
  /** 图标名，见 ICONS 键名；未知名称降级为空图标（不报错、不白屏） */
  name: { type: String, required: true },
  /** 像素尺寸（正方形） */
  size: { type: [Number, String], default: 20 },
  /** 旋转角度（deg），由调用方控制（如 loading 旋转） */
  rotate: { type: [Number, String], default: 0 },
})

// 线性图标路径集合（24×24 视口，stroke 绘制）
const ICONS = {
  close: ['M6 6l12 12', 'M18 6L6 18'],
  refresh: ['M20 12a8 8 0 1 1-2.34-5.66', 'M20 4v4h-4'],
  download: ['M12 4v11', 'M7 11l5 5 5-5', 'M5 20h14'],
  external: ['M14 5h5v5', 'M19 5l-7 7', 'M18 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4'],
  mic: ['M12 4a3 3 0 0 1 3 3v4a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3z', 'M5 11a7 7 0 0 0 14 0', 'M12 18v3'],
  'mic-off': ['M9 9V7a3 3 0 0 1 5.83-1.03', 'M15 11.2V11a3 3 0 0 1-4.5 2.6', 'M5 11a7 7 0 0 0 11.2 5.6', 'M12 18v3', 'M4 4l16 16'],
  speaker: ['M4 10v4h3l4 3V7l-4 3H4z', 'M15.5 9.5a4 4 0 0 1 0 5', 'M18 7a7.5 7.5 0 0 1 0 10'],
  stop: ['M7 7h10v10H7z'],
  trash: ['M5 7h14', 'M9 7V5h6v2', 'M7 7l1 13h8l1-13', 'M11 11v6', 'M13 11v6'],
  expand: ['M9 4H4v5', 'M15 4h5v5', 'M15 20h5v-5', 'M9 20H4v-5'],
  collapse: ['M4 9h5V4', 'M20 9h-5V4', 'M20 15h-5v5', 'M4 15h5v5'],
  'chevron-right': ['M9 5l7 7-7 7'],
  'chevron-down': ['M5 9l7 7 7-7'],
  search: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z', 'M20 20l-4.2-4.2'],
  upload: ['M12 19V8', 'M7 12l5-5 5 5', 'M5 5h14'],
  play: ['M8 5l11 7-11 7z'],
  check: ['M5 13l4 4L19 7'],
  alert: ['M12 4l9 16H3L12 4z', 'M12 10v4', 'M12 17h.01'],
  layers: ['M12 3l9 5-9 5-9-5 9-5z', 'M3 13l9 5 9-5', 'M3 17l9 5 9-5'],
  ruler: ['M4 14.5L14.5 4l5.5 5.5L9.5 20H4v-5.5z', 'M8.5 8.5l2 2', 'M11.5 5.5l2 2', 'M5.5 11.5l2 2'],
  image: ['M4 5h16v14H4z', 'M4 15l4.5-4.5L13 15', 'M14 14l2.5-2.5L20 15', 'M9 9.5h.01'],
  user: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M5 20a7 7 0 0 1 14 0'],
  home: ['M4 11.2l8-6.8 8 6.8', 'M6.6 9.6V19h10.8V9.6', 'M10.2 19v-4.6h3.6V19'],
  logout: ['M14 5H7a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h7', 'M17 8l4 4-4 4', 'M21 12H10'],
  sun: ['M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M12 3v2', 'M12 19v2', 'M3 12h2', 'M19 12h2', 'M5.6 5.6l1.4 1.4', 'M17 17l1.4 1.4', 'M18.4 5.6L17 7', 'M7 17l-1.4 1.4'],
  moon: ['M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z'],

  /* ---- 导航与业务图标（V2：替换 iconfont 与 Emoji） ---- */
  map: ['M3 6.6 8 4.8l6.4 1.8L21 4.8v13.8l-6.6 1.8L8 18.6 3 20.4z', 'M8 4.8v13.8', 'M14.4 6.6v13.8'],
  crosshair: ['M12 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14z', 'M12 2v3', 'M12 19v3', 'M2 12h3', 'M19 12h3'],
  nodes: ['M12 12a2.6 2.6 0 1 0 0-5.2 2.6 2.6 0 0 0 0 5.2z', 'M5 6.4a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z', 'M19 6.4a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z', 'M5 22a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z', 'M19 22a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z', 'M6.8 7 10 10.8', 'M17.2 7 14 10.8', 'M6.8 17 10 13.2', 'M17.2 17 14 13.2'],
  file: ['M6 3h7l5 5v13H6z', 'M13 3v5h5', 'M9 12h6', 'M9 16h6'],
  sliders: ['M4 7h16', 'M4 12h16', 'M4 17h16', 'M9 7a2 2 0 1 0 4 0 2 2 0 0 0-4 0', 'M15 12a2 2 0 1 0 4 0 2 2 0 0 0-4 0', 'M7 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0'],
  flame: ['M12 3s5 4 5 8.4A5 5 0 1 1 7 11.4c0-1.8.9-3.2.9-3.2s.7 1.6 1.8 1.6c1.6 0 1.8-2.7 2.3-6.8z'],
  clock: ['M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16z', 'M12 7.5V12l3 2'],
}

const paths = computed(() => ICONS[props.name] || [])
const sizePx = computed(() => `${props.size}px`)
const styleObj = computed(() => (Number(props.rotate) ? { transform: `rotate(${props.rotate}deg)` } : null))
</script>

<template>
  <svg
    class="app-icon"
    :width="sizePx"
    :height="sizePx"
    :style="styleObj"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(d, i) in paths" :key="i" :d="d" />
  </svg>
</template>

<style scoped>
.app-icon {
  display: block;
  flex-shrink: 0;
  color: inherit;
  /* rotate 由调用方驱动（折叠箭头、loading），补一条减速过渡让角度变化「转过去」而不是「跳过去」 */
  transition: transform var(--fs-dur-panel, 280ms) var(--fs-ease, cubic-bezier(0.22, 1, 0.36, 1));
}
</style>
