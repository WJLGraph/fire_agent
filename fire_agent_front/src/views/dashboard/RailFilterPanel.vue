<script setup>
/**
 * 作战大屏 · 右栏筛选区（v0 rail-head：数据模式 seg + 时间粒度 + 日期/行政区 + 预警条）
 *
 * v0 视觉规范：
 *  - 无卡片边框，直接坐在右栏表面，底部发丝线与图表区分隔；
 *  - seg 激活态 = 表面浮起（bg-surface + e1 阴影 + 600 字重），非实心强调色；
 *  - 日期/行政区输入与 v0 .field 同语：inset 发丝线 + bg-surface + r-sm。
 *
 * 「历史火点 / 预测火险」seg 即数据模式开关：切换后地图（2D/3D）、右栏图表、
 * 顶栏 KPI、火险预警条全部联动（状态在父组件，经 displayFireData / fireWarning 派生）。
 * 受控组件：所有状态由父组件持有，交互通过事件上抛。
 */
import { ref } from 'vue'
import FireWarningBar from './FireWarningBar.vue'

defineProps({
  currentDataType: { type: String, required: true },  // 'history' | 'predict'
  predictViewMode: { type: String, required: true },  // 'daily' | 'monthly'
  searchDate: { type: String, default: '' },
  searchCity: { type: String, default: '' },
  cityOptions: { type: Array, default: () => [] },
  fireWarning: { type: Object, default: null },
})

const emit = defineEmits([
  'toggle-data-type',
  'update:predictViewMode',
  'update:searchDate',
  'update:searchCity',
  'search',
])

// ====== 日期可选范围 ======
// 历史火点：仅 2021–2025（与 Yunnan_fire.json 一致）
const HISTORY_FIRE_YEAR_MIN = 2021
const HISTORY_FIRE_YEAR_MAX = 2025
// 预测火险：仅 2025–2026
const PREDICT_YEAR_MIN = 2025
const PREDICT_YEAR_MAX = 2026

const disabledHistorySearchDate = (date) => {
  const y = date.getFullYear()
  return y < HISTORY_FIRE_YEAR_MIN || y > HISTORY_FIRE_YEAR_MAX
}
const disabledPredictSearchDate = (date) => {
  const y = date.getFullYear()
  return y < PREDICT_YEAR_MIN || y > PREDICT_YEAR_MAX
}

// 火险预警详情展开状态
const showFireWarningDetail = ref(false)
</script>

<template>
  <div class="rail-filter">
    <!-- 行 1：数据模式 seg + 时间粒度（v0 rail-head 同构） -->
    <div class="rf-row rf-row--head">
      <div class="rf-seg" role="group" aria-label="数据模式">
        <button
          type="button"
          class="rf-seg__i"
          :class="{ 'is-on': currentDataType === 'history' }"
          @click="emit('toggle-data-type', 'history')"
        >历史</button>
        <button
          type="button"
          class="rf-seg__i"
          :class="{ 'is-on': currentDataType === 'predict' }"
          @click="emit('toggle-data-type', 'predict')"
        >预测</button>
      </div>
      <span class="rf-sp"></span>
      <div v-if="currentDataType === 'predict'" class="rf-seg rf-seg--sub" role="group" aria-label="时间粒度">
        <button
          type="button"
          class="rf-seg__i"
          :class="{ 'is-on': predictViewMode === 'daily' }"
          @click="emit('update:predictViewMode', 'daily')"
        >逐日</button>
        <button
          type="button"
          class="rf-seg__i"
          :class="{ 'is-on': predictViewMode === 'monthly' }"
          @click="emit('update:predictViewMode', 'monthly')"
        >逐月</button>
      </div>
    </div>

    <!-- 行 2：日期 + 行政区 + 检索 -->
    <div class="rf-row">
      <!-- 历史 / 预测分两个 picker，避免 Element Plus 复用实例时仍沿用预测的年份禁用逻辑 -->
      <el-date-picker
        v-if="currentDataType === 'history'"
        key="picker-history-fire"
        :model-value="searchDate"
        type="date"
        placeholder="选择历史日期"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DD"
        :disabled-date="disabledHistorySearchDate"
        size="small"
        class="rf-el rf-date"
        @update:model-value="emit('update:searchDate', $event)"
      />
      <el-date-picker
        v-else
        key="picker-predict-risk"
        :model-value="searchDate"
        :type="predictViewMode === 'daily' ? 'date' : 'month'"
        :placeholder="predictViewMode === 'daily' ? '选择日期' : '选择月份'"
        :format="predictViewMode === 'daily' ? 'YYYY-MM-DD' : 'YYYY-MM'"
        :value-format="predictViewMode === 'daily' ? 'YYYY-MM-DD' : 'YYYY-MM'"
        :disabled-date="disabledPredictSearchDate"
        size="small"
        class="rf-el rf-date"
        @update:model-value="emit('update:searchDate', $event)"
      />
      <el-select
        :model-value="searchCity"
        placeholder="行政区"
        size="small"
        class="rf-el rf-city"
        filterable
        clearable
        @update:model-value="emit('update:searchCity', $event)"
      >
        <el-option v-for="city in cityOptions" :key="city" :label="city" :value="city" />
      </el-select>
      <el-button class="rf-btn" size="small" @click="emit('search')">检索</el-button>
    </div>

    <!-- 行 3：火险预警摘要（仅预测模式） -->
    <FireWarningBar
      v-if="currentDataType === 'predict' && fireWarning"
      :fire-warning="fireWarning"
      v-model:show-detail="showFireWarningDetail"
    />
  </div>
</template>

<style lang="scss" scoped>
/* v0 rail-head：无卡片边框，坐在右栏表面，底部发丝线分隔 */
.rail-filter {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: var(--fs-s4, 16px) var(--fs-s4, 16px) var(--fs-s3, 12px);
  border-bottom: 1px solid var(--fs-hairline);
  min-width: 0;
}
.rf-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.rf-row--head { justify-content: flex-start; }
.rf-sp { flex: 1; }

/* v0 seg：激活态 = 表面浮起（bg-surface + 阴影 + 600），非实心强调色 */
.rf-seg {
  display: inline-flex;
  padding: 2px;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-sm, 6px);
}
.rf-seg__i {
  position: relative;
  height: 26px;
  padding: 0 12px;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--fs-ink-500);
  background: transparent;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  cursor: pointer;
  transition:
    color var(--fs-dur-micro, 160ms) var(--fs-ease),
    background var(--fs-dur-micro, 160ms) var(--fs-ease),
    box-shadow var(--fs-dur-micro, 160ms) var(--fs-ease),
    transform var(--fs-dur-micro, 160ms) var(--fs-ease);
}
.rf-seg__i:hover { color: var(--fs-ink-900); }
.rf-seg__i:active { transform: scale(0.97); }
.rf-seg__i.is-on {
  background: var(--fs-bg-surface);
  color: var(--fs-ink-900);
  /* 顶部 1px 镜面高光：让浮起的激活片有厚度，不使用彩色发光 */
  box-shadow: var(--fs-e1), inset 0 1px 0 rgba(255, 255, 255, 0.14);
  font-weight: 600;
}

/* 输入控件：v0 .field 同语（inset 发丝线 + bg-surface） */
.rf-el {
  flex: 1;
  min-width: 0;
}
.rf-date {
  :deep(.el-input__wrapper) {
    background: var(--fs-bg-surface);
    box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
    border-radius: var(--fs-r-sm, 6px);
  }
  :deep(.el-input__inner) {
    color: var(--fs-ink-900);
    font-size: 12px;
    font-family: var(--fs-font-mono);
    font-variant-numeric: tabular-nums;
  }
}
.rf-city {
  flex: 0 0 96px;
  :deep(.el-select__wrapper) {
    background: var(--fs-bg-surface);
    box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
    border-radius: var(--fs-r-sm, 6px);
    min-height: 24px;
  }
  :deep(.el-select__placeholder),
  :deep(.el-select__selected-item) {
    color: var(--fs-ink-900);
    font-size: 12px;
  }
}
.rf-btn {
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--fs-accent);
  border-color: var(--fs-accent);
  color: var(--fs-on-accent);
  font-weight: 500;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.rf-btn:hover,
.rf-btn:focus-visible {
  background: var(--fs-accent-hover);
  border-color: var(--fs-accent-hover);
  color: var(--fs-on-accent);
}
/* hover 扫光：与全局主按钮同一语言（单次 0.62s，静止态不可见） */
.rf-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.22) 50%, transparent 62%);
  transform: translateX(-130%);
}
.rf-btn:hover:not(.is-disabled)::after {
  animation: rf-sheen 0.62s var(--up-ease, cubic-bezier(0.32, 0.72, 0, 1));
}
@keyframes rf-sheen {
  to { transform: translateX(130%); }
}

/* 动效三态闸门：扫光与按压反馈在 off / 系统 reduce 下关闭 */
html[data-motion-allowed="false"] .rf-btn::after { animation: none; }
html[data-motion-allowed="false"] .rf-seg__i { transition: color var(--fs-dur-micro, 160ms) var(--fs-ease), background var(--fs-dur-micro, 160ms) var(--fs-ease); }
html[data-motion-allowed="false"] .rf-seg__i:active { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .rf-btn::after { animation: none; }
  html:not([data-motion="on"]) .rf-seg__i:active { transform: none; }
}
</style>
