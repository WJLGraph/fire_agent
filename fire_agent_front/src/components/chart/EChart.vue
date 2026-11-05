<script setup>
/**
 * EChart — 全站唯一的 ECharts 容器（P0-2 统一出口）
 *
 * 抽走的职责（原先在 views/chart/*.vue 内各写一份）：
 *   init / dispose / ResizeObserver / 主题 mode 变化重建 / loading 态 / click 事件
 *
 * 保留在调用方的职责（★ 契约）：
 *   option 的计算逻辑仍在各图内部，一字不改；本组件只负责把 option 交给实例。
 *
 * 用法：
 *   <EChart :option="option" :loading="isLoading" @ready="ins => chart = ins" @click="onClick" />
 */
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'
import { chartTokens } from '@/utils/themeTokens'
import useResizeObserver from '@/composables/useResizeObserver'

/**
 * 顶刊级图表默认层（§10.7）
 *
 * 只补「调用方没写」的非数据元素默认值，调用方显式写的永远优先：
 *   - Tooltip：surface + 1px 发丝边 + e2，去掉 ECharts 默认深色块
 *   - 坐标轴：隐藏轴线与刻度；仅 y 轴保留 1px 虚线网格；轴标签 11px ink-500
 *   - Legend：8px 方点 + 弱化文字
 * 数据本身（series / 颜色 / 标签格式）完全不介入。
 */
function withChartDefaults(option, t) {
  if (!option) return option
  const out = { ...option }

  if (out.tooltip) {
    const base = {
      backgroundColor: t.panel,
      borderColor: t.border,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: t.text, fontSize: 12 },
      extraCssText: 'box-shadow: 0 2px 8px rgba(16,18,20,.12); border-radius: 6px;',
    }
    out.tooltip = {
      ...base,
      ...out.tooltip,
      textStyle: { ...base.textStyle, ...(out.tooltip.textStyle || {}) },
    }
  }

  const patchAxis = (ax, isX) => {
    if (!ax) return ax
    const d = {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: t.muted, fontSize: 11 },
      splitLine: { show: !isX, lineStyle: { color: t.split, type: 'dashed', width: 1 } },
    }
    return {
      ...d,
      ...ax,
      axisLine: { ...d.axisLine, ...(ax.axisLine || {}) },
      axisTick: { ...d.axisTick, ...(ax.axisTick || {}) },
      axisLabel: { ...d.axisLabel, ...(ax.axisLabel || {}) },
      splitLine: { ...d.splitLine, ...(ax.splitLine || {}) },
    }
  }
  ;['xAxis', 'yAxis'].forEach((key) => {
    const v = out[key]
    if (!v) return
    const isX = key === 'xAxis'
    out[key] = Array.isArray(v) ? v.map((a) => patchAxis(a, isX)) : patchAxis(v, isX)
  })

  if (out.legend) {
    const arr = Array.isArray(out.legend) ? out.legend : [out.legend]
    const patched = arr.map((l) => ({
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 12,
      icon: 'roundRect',
      textStyle: { color: t.muted, fontSize: 11 },
      ...l,
      textStyle: { color: t.muted, fontSize: 11, ...(l.textStyle || {}) },
    }))
    out.legend = Array.isArray(out.legend) ? patched : patched[0]
  }

  return out
}

const props = defineProps({
  /** ECharts 配置对象（由调用方 computed 产出） */
  option: { type: Object, required: true },
  /** 加载态 */
  loading: { type: Boolean, default: false },
  /** 容器高度，默认撑满父容器。传空字符串表示不写内联高度，完全交给外部 class 控制 */
  height: { type: String, default: '100%' },
})

/** 高度内联样式（留空时不输出，避免覆盖外部 flex 布局） */
const boxStyle = computed(() => (props.height ? { height: props.height } : {}))

const emit = defineEmits(['ready', 'click'])

const chartRef = ref(null)
let instance = null

const theme = useThemeStore()

/** 建立实例并挂载事件；已存在则先 dispose（与现有各图 rebuild 行为一致） */
const build = () => {
  if (!chartRef.value) return
  if (instance) {
    instance.dispose()
    instance = null
  }
  instance = echarts.init(chartRef.value)
  instance.setOption(withChartDefaults(props.option, chartTokens()))
  instance.on('click', (params) => emit('click', params))
  syncLoading()
  emit('ready', instance)
}

const syncLoading = () => {
  if (!instance) return
  if (props.loading) {
    instance.showLoading('default', {
      text: '加载中',
      color: chartTokens().accent,
      textColor: chartTokens().text,
      maskColor: 'transparent',
      zlevel: 0,
    })
  } else {
    instance.hideLoading()
  }
}

const resize = () => instance && instance.resize()

// 容器尺寸监听（ResizeObserver 优先，不支持时降级 window.resize）
useResizeObserver(chartRef, resize)

// option 变化（数据/主题 token 重算）→ setOption 全量替换
watch(
  () => props.option,
  (option) => {
    if (!instance) return
    instance.setOption(withChartDefaults(option, chartTokens()), { notMerge: true })
  },
  { deep: true }
)

// 主题切换 → 与现有实现一致：重建实例（避免调色板残留）
watch(
  () => theme.mode,
  () => nextTick(build)
)

watch(() => props.loading, syncLoading)

onMounted(() => nextTick(build))

onUnmounted(() => {
  if (instance) {
    instance.dispose()
    instance = null
  }
})

defineExpose({
  /** 手动 resize（父容器动画结束后可能需要） */
  resize,
  /** 取底层实例（需要 getDataURL 导出等场景） */
  getInstance: () => instance,
})
</script>

<template>
  <div ref="chartRef" class="echart-box" :style="boxStyle" />
</template>

<style scoped>
.echart-box {
  width: 100%;
  min-width: 0;
}
</style>
