<script setup>
/**
 * 预测火险等级频次柱状图（右下）
 * ★★★ 图表数据与 predictViewMode 同步：逐日用逐日数据，逐月用逐月数据 ★★★
 * 五色柱状图（与地图火险五色一致，取自 riskLevel.js），全屏含分页表格
 *
 * 阶段 3：echarts init/dispose/resize/主题重建 交由 components/chart/EChart，
 *         全屏 + 分页表格交由 components/chart/ChartFullscreenDialog。
 * ★ getOption 的内容改为 computed 产出，配置本身一字未改；
 *   原先依赖 watch(searchDate/viewMode) + watch(theme.mode) 手动重绘 + rAF 补布局，
 *   现在由响应式链路自动传导（tableData → levelDistribution → option），
 *   EChart 内部的 ResizeObserver 取代了原 resize 监听与双帧 layout。
 */
import { FullScreen } from '@element-plus/icons-vue'
import { ref, computed } from 'vue'
import predictMonthJson from '@/assets/predict_2025_2026_month.json'
import predictDailyJson from '@/assets/predict_2025_2026_daily.json'
import { RISK_COLORS } from '@/utils/riskLevel'
import { chartTokens } from '@/utils/themeTokens'
import { useThemeStore } from '@/stores/theme'
import { fireIndexToLevel, riskScoreToLevel } from '@/utils/riskLevel'
import EChart from '@/components/chart/EChart.vue'
import ChartFullscreenDialog from '@/components/chart/ChartFullscreenDialog.vue'

// 接收 searchDate、viewMode 和 predictData
const props = defineProps({
  searchDate: {
    type: String,
    default: ''
  },
  viewMode: {
    type: String,
    default: 'daily'
  },
  predictData: {
    type: Array,
    default: null
  }
})

// 主题 Store（切换主题时重建图表）
const theme = useThemeStore()
// chartTokens 内部不接受参数，传 theme.mode 只为建立响应式依赖（与其余三个图一致）
const tokens = computed(() => chartTokens(theme.mode))

// 全屏状态
const isMaximized = ref(false)

// ★★★ 根据 viewMode 切换数据源：逐日用逐日数据，逐月用逐月数据 ★★★
// 优先使用父组件传入的 predictData（API 数据），否则用本地 JSON
const tableData = computed(() => {
  const isDaily = props.viewMode === 'daily'

  // 如果父组件传入了 predictData，直接使用（已过滤好）
  if (props.predictData && props.predictData.length > 0) {
    return props.predictData.map(item => {
      const level = isDaily
        ? fireIndexToLevel(item.final_fire_index || item.Final_Fire_Index)
        : riskScoreToLevel(item.risk_score || item.Risk_Score)
      const displayDate = isDaily
        ? `${item.year || item.Year}-${String(Number(item.month || item.Month)).padStart(2, '0')}-${String(Number(item.day || item.Day)).padStart(2, '0')}`
        : `${item.year || item.Year}-${String(Number(item.month || item.Month)).padStart(2, '0')}`
      return {
        ...item,
        riskLevel: level,
        displayDate,
        _fireIndex: isDaily ? (item.final_fire_index || item.Final_Fire_Index) : (item.risk_score || item.Risk_Score),
        _predFireRisk: isDaily ? (item.pred_fire_count || item.Pred_Fire_Count) : (item.pred_fire_risk || item.Pred_Fire_Risk)
      }
    })
  }

  if (isDaily) {
    if (!props.searchDate) {
      return predictDailyJson.map(item => {
        const level = fireIndexToLevel(item.Final_Fire_Index)
        const y = String(item.Year)
        const m = String(Number(item.Month)).padStart(2, '0')
        const d = String(Number(item.Day)).padStart(2, '0')
        return {
          ...item,
          riskLevel: level,
          displayDate: `${y}-${m}-${d}`,
          _fireIndex: item.Final_Fire_Index,
          _predFireRisk: item.Pred_Fire_Count
        }
      })
    }
    const parts = props.searchDate.split('-').map(Number)
    const year = parts[0], month = parts[1], day = parts[2]
    return predictDailyJson
      .filter(item => Number(item.Year) === year && Number(item.Month) === month && Number(item.Day) === day)
      .map(item => {
        const level = fireIndexToLevel(item.Final_Fire_Index)
        const y = String(item.Year)
        const m = String(Number(item.Month)).padStart(2, '0')
        const d = String(Number(item.Day)).padStart(2, '0')
        return {
          ...item,
          riskLevel: level,
          displayDate: `${y}-${m}-${d}`,
          _fireIndex: item.Final_Fire_Index,
          _predFireRisk: item.Pred_Fire_Count
        }
      })
  } else {
    if (!props.searchDate) {
      return predictMonthJson.map(item => ({
        ...item,
        riskLevel: riskScoreToLevel(item.Risk_Score),
        displayDate: `${item.Year}-${String(item.Month).padStart(2, '0')}`,
        _fireIndex: item.Risk_Score,
        _predFireRisk: item.Pred_Fire_Risk
      }))
    }
    const parts = props.searchDate.split('-').map(Number)
    const year = parts[0], month = parts[1]
    return predictMonthJson
      .filter(item => Number(item.Year) === year && Number(item.Month) === month)
      .map(item => ({
        ...item,
        riskLevel: riskScoreToLevel(item.Risk_Score),
        displayDate: `${item.Year}-${String(item.Month).padStart(2, '0')}`,
        _fireIndex: item.Risk_Score,
        _predFireRisk: item.Pred_Fire_Risk
      }))
  }
})

// 按记录条数统计（非 Pred_Fire_Risk 求和），保证柱高与直觉一致
const levelDistribution = computed(() => {
  const counts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 }
  tableData.value.forEach(item => counts[item.riskLevel]++)
  return {
    xData: ['1级', '2级', '3级', '4级', '5级'],
    yData: [counts[1], counts[2], counts[3], counts[4], counts[5]]
  }
})

// 全屏表格列定义（label 随 viewMode 变化；三列由 #fireIndex / #predFireRisk / #riskLevel 插槽渲染）
const tableColumns = computed(() => [
  { prop: 'City', label: '城市', minWidth: 120 },
  { prop: 'displayDate', label: props.viewMode === 'daily' ? '日期' : '月份', minWidth: 100, sortable: true },
  { prop: '_fireIndex', label: props.viewMode === 'daily' ? '火险指数' : '火险评分', minWidth: 100, slot: 'fireIndex' },
  { prop: '_predFireRisk', label: '预测火点数', minWidth: 100, slot: 'predFireRisk' },
  { prop: 'riskLevel', label: '火险等级', minWidth: 100, slot: 'riskLevel' },
])

// 柱状图配置（拷贝 data，避免 ECharts 就地改写导致与全屏实例不同步）
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
    top: '15%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: [...levelDistribution.value.xData],
    axisLabel: { color: t.muted, fontSize: 11 },
    axisLine: { lineStyle: { color: t.border } }
  },
  yAxis: {
    type: 'value',
    name: '记录条数',
    nameTextStyle: { color: t.muted },
    axisLabel: { color: t.muted },
    splitLine: { lineStyle: { type: 'dashed', color: t.split } }
  },
  series: [{
    name: '该等级记录数',
    type: 'bar',
    data: [...levelDistribution.value.yData],
    itemStyle: {
      color: (params) => RISK_COLORS[params.dataIndex],
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
      title="预测火险等级频次分布详情"
      :option="option"
      :columns="tableColumns"
      :rows="tableData"
    >
      <template #fireIndex="{ row }">
        {{ row._fireIndex != null
          ? Number(row._fireIndex).toFixed(viewMode === 'daily' ? 1 : 4)
          : (viewMode === 'daily' ? '0.0' : '0.0000')
        }}
      </template>
      <template #predFireRisk="{ row }">
        {{ row._predFireRisk != null ? Math.round(Number(row._predFireRisk)) : 0 }}
      </template>
      <template #riskLevel="{ row }">
        <el-tag :type="row.riskLevel >= 4 ? 'danger' : (row.riskLevel >= 3 ? 'warning' : 'primary')">
          {{ row.riskLevel }}级
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
