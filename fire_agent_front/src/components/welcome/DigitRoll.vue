<script setup>
/**
 * DigitRoll — 逐位数字滚轮（公开页数据带专用）
 *
 * - 每位一条 0–9 纵向数字条，CSS translateY 滚动，到位精确停在终值
 * - 列数由「兜底终值」的格式决定（含千分位逗号位恒占位），位宽恒定不抖动
 * - tabular-nums 等宽；value 非法时回落 fallback，永不出现 NaN/undefined
 * - reduced-motion：transition 置 none，直接显示终值（见样式尾部）
 */
import { ref, watch, computed } from 'vue'

const props = defineProps({
  /** 当前数值（非法自动回落 fallback） */
  value: { type: Number, default: 0 },
  /** 兜底终值：决定列数与非法回落 */
  fallback: { type: Number, required: true },
  /** 无障碍标签 */
  label: { type: String, default: '' },
})

const fmt = (n) => {
  const v = Number(n)
  const safe = Number.isFinite(v) && v > 0 ? Math.round(v) : Math.round(Number(props.fallback))
  return safe.toLocaleString('en-US')
}

/** 列骨架由兜底终值决定（恒定位宽），初始各位显示 0 */
const cols = ref(
  fmt(props.fallback).split('').map((ch) => ({ ch: ch === ',' ? ',' : '0', sep: ch === ',' })),
)
const shown = ref('0')

watch(
  () => props.value,
  (v) => {
    const t = fmt(v)
    shown.value = t
    cols.value = t.split('').map((ch) => ({ ch, sep: ch === ',' }))
  },
  { immediate: true },
)

const aria = computed(() => props.label || shown.value)
</script>

<template>
  <span class="droll" role="img" :aria-label="aria">
    <span
      v-for="(c, i) in cols"
      :key="i"
      class="droll__col"
      :class="{ 'is-sep': c.sep }"
      :style="{ transitionDelay: `${i * 60}ms` }"
    >
      <span v-if="c.sep" class="droll__sep">{{ c.ch }}</span>
      <span v-else class="droll__win">
        <i
          class="droll__strip"
          :style="{ transform: `translateY(-${(Number(c.ch) || 0) * 10}%)`, transitionDelay: `${i * 60}ms` }"
        ><b v-for="d in 10" :key="d">{{ d - 1 }}</b></i>
      </span>
    </span>
  </span>
</template>

<style scoped>
.droll {
  display: inline-flex;
  align-items: baseline;
  font-variant-numeric: tabular-nums;
}
.droll__col { display: inline-block; }
.droll__sep { display: inline-block; }
.droll__win {
  display: inline-block;
  height: 1em;
  overflow: hidden;
}
.droll__strip {
  display: flex;
  flex-direction: column;
  transition: transform 1s cubic-bezier(0.22, 0.61, 0.36, 1);
  will-change: transform;
}
.droll__strip b {
  height: 1em;
  line-height: 1em;
  text-align: center;
  font-weight: inherit;
}
/* off（或 auto+系统减）时不滚动，直接显示终值；on 覆盖系统 reduce */
html[data-motion-allowed="false"] .droll__strip { transition: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .droll__strip { transition: none; }
}
</style>
