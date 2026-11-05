<script setup>
/**
 * 历史火点频次柱状图（左下）
 * 数据：parseGeoData() → dailyCounts，按日期统计火点数量
 * 图表展示 Top 7 高频日期，全屏含分页表格
 *
 * 阶段 3：echarts init/dispose/resize/主题重建 交由 components/chart/EChart，
 *         全屏 + 分页表格交由 components/chart/ChartFullscreenDialog。
 * ★ option 计算逻辑保持原样，未作任何改动。
 */
import { FullScreen } from '@element-plus/icons-vue'
import { ref, computed, watch } from 'vue'
import { parseGeoData } from '@/utils/parseGeoData'
import { chartTokens } from '@/utils/themeTokens'
import { useThemeStore } from '@/stores/theme'
import EChart from '@/components/chart/EChart.vue'
import ChartFullscreenDialog from '@/components/chart/ChartFullscreenDialog.vue'

// 接收 fireData prop（由父组件传入 API 数据或本地数据）
const props = defineProps({
  fireData: {
    type: Object,
    default: null
  }
})

// 主题 Token：传入 mode 仅为建立响应式依赖，主题切换时重新读取 CSS 变量
const theme = useThemeStore()
const tokens = computed(() => chartTokens(theme.mode))

// 当 fireData 变化时重新解析
const rawGeo = ref(props.fireData ? parseGeoData(props.fireData) : parseGeoData())
watch(() => props.fireData, (val) => {
  rawGeo.value = val ? parseGeoData(val) : parseGeoData()
})

const geoData = computed(() => rawGeo.value)

// 全屏状态
const isMaximized = ref(false)
const tableData = computed(() => geoData.value.rawFeatures || [])

// 全屏表格列定义（供 ChartFullscreenDialog 渲染）
const tableColumns = [
  { prop: 'acq_date', label: '日期', minWidth: 120, sortable: true },
  { prop: 'acq_time', label: '时间', minWidth: 100 },
  { prop: 'latitude', label: '纬度', minWidth: 100 },
  { prop: 'longitude', label: '经度', minWidth: 100 },
]

// Top 7 高频日期（用 computed 确保响应式更新）
const top7Days = computed(() => {
  const counts = geoData.value.dailyCounts
  if (!counts || !Array.isArray(counts)) return []
  return [...counts].sort((a, b) => b.value - a.value).slice(0, 7)
})

// 柱状图配置（computed：数据/主题变化时自动更新）
const option = computed(() => {
  const t = tokens.value
  return {
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: t.panel,
    borderColor: t.border,
    borderWidth: 1,
    textStyle: { color: t.text, fontSize: 12 },
    axisPointer: { type: 'shadow' }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '10%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: top7Days.value.map(i => i.name),
    axisLabel: { color: t.muted, fontSize: 10, rotate: 28 },
    axisLine: { lineStyle: { color: t.border } }
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: t.muted },
    splitLine: { lineStyle: { type: 'dashed', color: t.split } }
  },
  series: [{
    name: '火点频次',
    type: 'bar',
    data: top7Days.value.map(i => i.value),
    itemStyle: {
      color: '#f97316',
      borderRadius: [0, 0, 0, 0]
    },
    label: {
      show: true,
      position: 'top',
      color: t.text
    }
  }]
  }
})

const toggleMaximize = () => {
  isMaximized.value = !isMaximized.value
}
</script>

<template>
  <div class="chart-wrapper">
    <!-- 正常模式 -->
    <div class="normal-view">
      <div class="expand-btn" @click="toggleMaximize">
        <el-icon size="20">
          <FullScreen />
        </el-icon>
      </div>
      <EChart class="chart-area" :option="option" />
    </div>

    <!-- 全屏模式（统一由 ChartFullscreenDialog 渲染：左图 + 右分页表格） -->
    <ChartFullscreenDialog
      v-model="isMaximized"
      title="高频火点日期详情"
      :option="option"
      :columns="tableColumns"
      :rows="tableData"
    />
  </div>
</template>

<style lang="scss" scoped>
.chart-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
}

.normal-view {
  width: 100%;
  height: 100%;
  position: relative;

  .expand-btn {
    position: absolute;
    top: 0;
    right: 0;
    cursor: pointer;
    color: var(--fs-ink-500, var(--fs-ink-500));
    z-index: 10;
    background: var(--fs-bg-raised);
    border: 1px solid var(--fs-hairline);
    border-radius: var(--fs-r-xs, 4px);
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;

    &:hover {
      background: var(--fs-accent-soft);
      box-shadow: var(--fs-e1);
    }
  }

  .chart-area {
    width: 100%;
    height: 100%;
  }
}
</style>
