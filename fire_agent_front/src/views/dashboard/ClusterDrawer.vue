<script setup>
/**
 * 作战大屏 · 火点/火险详情抽屉
 *
 * 地图点击聚合点后展示明细表格；历史模式与预测模式列不同。
 * 受控组件：显示状态以 v-model 双向绑定。
 */
defineProps({
  modelValue: { type: Boolean, default: false },
  clusterData: { type: Array, default: () => [] },
  currentDataType: { type: String, required: true }, // 'history' | 'predict'
  predictViewMode: { type: String, default: 'daily' }, // 'daily' | 'monthly'
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="currentDataType === 'history' ? '区域火点详细信息' : '预测区域火险详细信息'"
    direction="rtl"
    size="430px"
    :modal="false"
    :lock-scroll="false"
    class="fire-drawer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-table :data="clusterData" style="width: 100%" height="calc(100vh - 100px)">
      <!-- 历史数据列 -->
      <template v-if="currentDataType === 'history'">
        <el-table-column prop="acq_date" label="日期" min-width="100" />
        <el-table-column prop="acq_time" label="时间" min-width="70" />
        <el-table-column prop="frp" label="FRP" min-width="70" />
        <el-table-column prop="conf" label="置信度" min-width="80">
          <template #default="scope">
            <el-tag :type="scope.row.conf === 'high' ? 'danger' : 'success'" size="small">
              {{ scope.row.conf === 'high' ? '高' : (scope.row.conf === 'nominal' ? '中' : '低') }}
            </el-tag>
          </template>
        </el-table-column>
      </template>
      <!-- 预测数据列 -->
      <template v-else>
        <el-table-column prop="city" label="城市" min-width="100" show-overflow-tooltip />
        <el-table-column prop="acq_date" :label="predictViewMode === 'daily' ? '日期' : '月份'" min-width="90" />
        <el-table-column prop="fire_count" :label="predictViewMode === 'daily' ? '预测火点数(整数)' : '预测火点数量'" min-width="120" align="center" />
        <el-table-column label="火险等级" min-width="80" align="center">
          <template #default="scope">
            <el-tooltip
              effect="dark"
              :content="predictViewMode === 'daily'
                ? ('火险指数: ' + (scope.row.fire_index != null ? Number(scope.row.fire_index).toFixed(1) : ''))
                : ('火险评分: ' + (scope.row.risk_score ? scope.row.risk_score.toFixed(4) : '0.0000'))"
              placement="left"
            >
              <el-tag :type="scope.row.risk_level >= 4 ? 'danger' : (scope.row.risk_level >= 3 ? 'warning' : 'primary')" size="small">{{ scope.row.risk_level || 1 }}级</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
      </template>
    </el-table>
  </el-drawer>
</template>

<style lang="scss" scoped>
:deep(.fire-drawer) {
  --el-drawer-bg-color: var(--fs-bg-surface) !important;
  background-color: var(--fs-bg-surface) !important;
  color: var(--fs-ink-900) !important;
  border-left: 1px solid var(--fs-hairline) !important;

  .el-drawer__header {
    margin-bottom: 0;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--fs-hairline);
    color: var(--fs-ink-900);
    font-weight: 600;
  }

  .el-table {
    --el-table-bg-color: var(--fs-bg-surface) !important;
    --el-table-tr-bg-color: var(--fs-bg-surface) !important;
    --el-table-header-bg-color: var(--fs-bg-sunken, var(--fs-bg-canvas)) !important;
    --el-table-row-hover-bg-color: var(--fs-bg-sunken, rgba(var(--fs-risk-1-rgb), 0.1)) !important;
    color: var(--fs-ink-900) !important;
  }

  th.el-table__cell {
    background: var(--fs-bg-sunken, var(--fs-bg-canvas)) !important;
    color: var(--fs-accent) !important;
    font-family: ui-monospace, "Consolas", monospace;
    font-size: 12px;
    border-bottom: 1px solid var(--fs-hairline) !important;
  }

  td.el-table__cell {
    background-color: var(--fs-bg-surface, rgba(var(--fs-ink-900-rgb), 0.92)) !important;
    color: var(--fs-ink-900) !important;
    border-bottom: 1px solid var(--fs-hairline) !important;
    font-size: 12px;
  }

  .el-table__body tr:hover > td.el-table__cell {
    background-color: var(--fs-bg-sunken, rgba(var(--fs-risk-1-rgb), 0.08)) !important;
    color: var(--fs-ink-900) !important;
  }

  .el-table__inner-wrapper::before {
    height: 0 !important;
  }
}
</style>
