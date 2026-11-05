<script setup>
/**
 * 历史火险等级饼图（左上）
 * 数据：parseGeoData() → confidenceCounts { high / low }
 * 全屏：点击右上角按钮，Teleport 弹窗，图表+表格左右分栏
 *
 * 阶段 3：echarts init/dispose/resize/主题重建 交由 components/chart/EChart，
 *         全屏 + 分页表格交由 components/chart/ChartFullscreenDialog。
 * ★ option / maxOption 计算逻辑保持原样，未作任何改动。
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

// 表格数据（用 computed 确保响应式更新）
const tableData = computed(() => geoData.value.rawFeatures || [])

// 全屏状态
const isMaximized = ref(false)

// 全屏表格列定义（置信度列由 #conf 插槽自定义渲染，保持原有 el-tag 表现）
const tableColumns = [
  { prop: 'acq_date', label: '日期', minWidth: 120, sortable: true },
  { prop: 'conf', label: '置信度', minWidth: 100, slot: 'conf' },
  { prop: 'latitude', label: '纬度', minWidth: 100 },
  { prop: 'longitude', label: '经度', minWidth: 100 },
]

// ECharts 配置：环形饼图，高/低置信度两段（computed：数据/主题变化时自动更新）
const option = computed(() => {
  const t = tokens.value
  const counts = geoData.value.confidenceCounts || { high: 0, low: 0 }
  return {
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'item',
    backgroundColor: t.panel,
    borderColor: t.border,
    borderWidth: 1,
    textStyle: { color: t.text, fontSize: 12 },
    formatter: '{b}: {c} ({d}%)'
  },
  legend: {
    bottom: '5%',
    left: 'center',
    textStyle: { color: t.muted, fontSize: 11 }
  },
  series: [{
    name: '火险置信度分布',
    type: 'pie',
    radius: ['40%', '70%'],
    avoidLabelOverlap: false,
    itemStyle: {
      borderRadius: 0,
      borderColor: t.border,
      borderWidth: 1
    },
    label: {
      show: false,
      position: 'center'
    },
    emphasis: {
      label: {
        show: true,
        fontSize: 14,
        fontWeight: 600,
        color: t.text
      }
    },
    labelLine: {
      show: false
    },
    data: [
      { value: counts.high ?? 0, name: '高置信度', itemStyle: { color: '#dc2626' } },
      { value: counts.low ?? 0, name: '低置信度', itemStyle: { color: '#eab308' } }
    ]
  }]
  }
})

// 全屏图配置（显示外部标签），与小图逻辑保持一致仅具 presentation 差异
const maxOption = computed(() => {
  const t = tokens.value
  const opt = JSON.parse(JSON.stringify(option.value))
  if (opt.series && opt.series[0]) {
    opt.series[0].label = {
      show: true,
      position: 'outside',
      color: t.text,
      formatter: '{b}: {c} ({d}%)',
      fontSize: 13
    }
    opt.series[0].labelLine = {
      show: true,
      lineStyle: { color: t.border }
    }
  }
  opt.legend = {
    bottom: '5%',
    left: 'center',
    textStyle: { color: t.muted, fontSize: 13 }
  }
  return opt
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
      title="火险置信度分布详情"
      :option="maxOption"
      :columns="tableColumns"
      :rows="tableData"
    >
      <template #conf="{ row }">
        <el-tag :type="row.conf === 'high' ? 'danger' : 'success'" effect="light">
          {{ row.conf === 'high' ? 'High' : 'Low' }}
        </el-tag>
      </template>
    </ChartFullscreenDialog>
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
