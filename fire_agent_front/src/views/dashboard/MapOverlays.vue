<script setup>
/**
 * 作战大屏 · 地图浮层（visual-v0 §10.7：map-legend 图例 + map-src 数据源徽标）
 *
 * 图例随数据模式切换：预测=火险五级色带；历史=置信度高/低。
 * 徽标显示 DataAgent 数据源与同步状态。均为纯展示，无交互。
 */
import { computed } from 'vue'
import { RISK_COLORS } from '@/utils/riskLevel'

const props = defineProps({
  currentDataType: { type: String, required: true },  // 'history' | 'predict'
  dataSource: { type: String, required: true },       // loading / api / local
  apiLoading: { type: Boolean, default: false },
  syncedAt: { type: String, default: '' },            // 'HH:MM'
  srcShift: { type: Boolean, default: false },        // AI 识别抽屉展开时右移避让
})

const riskLevels = computed(() => [
  { c: RISK_COLORS[0], t: '正常' },
  { c: RISK_COLORS[1], t: '注意' },
  { c: RISK_COLORS[2], t: '警告' },
  { c: RISK_COLORS[3], t: '高度' },
  { c: RISK_COLORS[4], t: '极度' },
])

const srcText = computed(() => {
  if (props.apiLoading || props.dataSource === 'loading') return '同步数据中…'
  return props.dataSource === 'api' ? `后端数据${props.syncedAt ? ' · 已同步 ' + props.syncedAt : ''}` : '本地降级数据'
})
</script>

<template>
  <!-- 数据源徽标：左下（识别抽屉展开时右移避让，不遮挡） -->
  <div class="map-src" :class="{ 'map-src--shift': srcShift }">
    <span
      class="map-src__dot"
      :class="{
        'is-loading': apiLoading || dataSource === 'loading',
        'is-local': dataSource === 'local',
        'mo-loop': apiLoading || dataSource === 'loading',
      }"
    ></span>
    {{ srcText }}
  </div>

  <!-- 火险等级图例：右下（坐标读数上方）；切换数据模式时重挂载以重播入场 -->
  <div class="map-legend" :key="currentDataType">
    <template v-if="currentDataType === 'predict'">
      <span class="map-legend__t">火险等级</span>
      <span v-for="lv in riskLevels" :key="lv.t" class="map-legend__i">
        <i :style="{ background: lv.c }"></i>{{ lv.t }}
      </span>
    </template>
    <template v-else>
      <span class="map-legend__t">置信度</span>
      <span class="map-legend__i"><i style="background: var(--fs-risk-4)"></i>高</span>
      <span class="map-legend__i"><i style="background: var(--fs-ink-400)"></i>低</span>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.map-src {
  position: absolute;
  left: 56px;
  top: 12px;
  z-index: 30;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: var(--fs-e1);
  pointer-events: none;
  transition: left 0.3s var(--fs-ease, ease);
  animation: mo-in-top 0.4s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) 0.08s both;
}
/* 抽屉展开：右移至抽屉右缘之外（8 + min(330px,26vw) + 16） */
.map-src--shift {
  left: calc(min(330px, 26vw) + 24px);
}
.map-src__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--fs-success);
  flex-shrink: 0;
}
.map-src__dot.is-local { background: var(--fs-warning); }
.map-src__dot.is-loading {
  background: var(--fs-accent);
  animation: srcPulse 1s ease-in-out infinite;
}
@keyframes srcPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.map-legend {
  position: absolute;
  right: 12px;
  bottom: 44px;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 9px 12px;
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: var(--fs-e1);
  pointer-events: none;
  animation: mo-in-bottom 0.4s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) 0.14s both;
}
.map-legend__t {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--fs-ink-500);
  margin-bottom: 1px;
}
.map-legend__i {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--fs-ink-900);
  animation: mo-item-in 0.3s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) both;
  i {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
    box-shadow: inset 0 0 0 1px rgba(var(--fs-ink-900-rgb), 0.12);
    transition: transform var(--fs-dur-micro, 160ms) var(--fs-ease);
  }
}
/* 色块逐行错峰升起（__t 占第 1 个子元素，故偏移 1） */
@for $n from 1 through 5 {
  .map-legend__i:nth-child(#{$n + 1}) {
    animation-delay: #{0.2 + $n * 0.05}s;
  }
}

/* ==================== 入场关键帧（终态即基线） ==================== */
@keyframes mo-in-top {
  from { opacity: 0; translate: 0 -6px; }
  to   { opacity: 1; translate: 0 0; }
}
@keyframes mo-in-bottom {
  from { opacity: 0; translate: 0 6px; }
  to   { opacity: 1; translate: 0 0; }
}
@keyframes mo-item-in {
  from { opacity: 0; translate: 4px 0; }
  to   { opacity: 1; translate: 0 0; }
}

/* 动效三态闸门：off / 系统 reduce 下静态呈现终态（徽标脉冲点由 .mo-loop 统一降级） */
html[data-motion-allowed="false"] .map-src,
html[data-motion-allowed="false"] .map-legend,
html[data-motion-allowed="false"] .map-legend__i { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .map-src,
  html:not([data-motion="on"]) .map-legend,
  html:not([data-motion="on"]) .map-legend__i { animation: none; }
}
</style>
