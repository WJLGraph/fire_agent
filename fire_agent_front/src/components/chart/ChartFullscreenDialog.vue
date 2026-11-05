<script setup>
/**
 * ChartFullscreenDialog — 图表全屏详情（左图 + 右分页表格）
 *
 * 统一替代 views/chart/ 四份几乎逐行复制的全屏模板。
 *
 * ★ 契约保持原样：
 *   - Teleport to body；整屏遮罩；标题在左、关闭按钮在右上（与原模板一致）
 *   - 分页默认值 pageSize = 20，可选 20/50/100/200/500
 *   - 翻页 300ms 加载态（与现有 handleCurrentChange 行为一致）
 *
 * v0 视觉规范（§10）：
 *  - 页头：标题 16px/600 + 记录数 mono 徽标 + 幽灵关闭按钮（非 primary 实心圆）；
 *  - 左图右表两块均「表面 + 发丝线」，表格去 stripe/border，仅保留表头分隔线；
 *  - 表头 11px/600 字距 0.06em，行悬停轻微沉色，分页条顶部发丝线。
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Close } from '@element-plus/icons-vue'
import EChart from '@/components/chart/EChart.vue'

const props = defineProps({
  /** 全屏开关（v-model） */
  modelValue: { type: Boolean, default: false },
  /** 全屏标题 */
  title: { type: String, default: '图表详情' },
  /** ECharts option（与 EChart 组件共用同一份 option） */
  option: { type: Object, default: () => ({}) },
  /** 表格列：[{ prop, label, minWidth, sortable, formatter }] */
  columns: { type: Array, default: () => [] },
  /** 表格数据 */
  rows: { type: Array, default: () => [] },
  /** 表格加载态 */
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const currentPage = ref(1)
const pageSize = ref(20)
const isLoading = ref(false)

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return props.rows.slice(start, start + pageSize.value)
})

// 与现有实现一致：翻页给一个短暂的加载态反馈
const handleCurrentChange = () => {
  isLoading.value = true
  setTimeout(() => { isLoading.value = false }, 300)
}

const handleSizeChange = () => {
  currentPage.value = 1
}

const close = () => emit('update:modelValue', false)

// Esc 退出全屏
const onKeydown = (e) => {
  if (e.key === 'Escape' && props.modelValue) close()
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

// 每次打开回到第一页（避免上次翻页状态残留）
watch(
  () => props.modelValue,
  (open) => {
    if (open) currentPage.value = 1
  }
)
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="cfsd-view">
      <div class="cfsd-header">
        <div class="cfsd-head-l">
          <span class="cfsd-title">{{ title }}</span>
          <span class="cfsd-count">{{ rows.length }} 条记录</span>
        </div>
        <button class="cfsd-close" title="退出全屏 (Esc)" @click="close">
          <el-icon size="16"><Close /></el-icon>
          <span>退出全屏</span>
        </button>
      </div>

      <div class="cfsd-body">
        <div class="cfsd-chart">
          <EChart v-if="modelValue" :option="option" />
        </div>

        <div class="cfsd-table">
          <div class="cfsd-table-wrap">
            <el-table
              v-loading="loading || isLoading"
              :data="paginatedData"
              height="100%"
              :header-cell-style="{
                background: 'transparent',
                color: 'var(--fs-ink-500)',
                fontWeight: '600',
                fontSize: '11px',
                letterSpacing: '0.06em',
                borderBottom: '1px solid var(--fs-hairline-strong)',
              }"
              :cell-style="{ fontSize: '12px' }"
            >
              <el-table-column
                v-for="col in columns"
                :key="col.prop"
                :prop="col.prop"
                :label="col.label"
                :min-width="col.minWidth"
                :sortable="!!col.sortable"
                :formatter="col.formatter"
              >
                <!-- 单元格自定义：col.slot 指向父组件传入的具名插槽（如置信度标签） -->
                <template v-if="col.slot" #default="scope">
                  <slot :name="col.slot" :row="scope.row" :col="col" :$index="scope.$index" />
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="cfsd-pagination">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[20, 50, 100, 200, 500]"
              :total="rows.length"
              popper-style="z-index: 99999"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cfsd-view {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 2000;
  background: var(--fs-bg-canvas);
  padding: var(--fs-s6, 24px);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  animation: cfsdIn 0.22s var(--fs-ease, ease-out);
}
@keyframes cfsdIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: none; }
}

/* 页头：标题 + 记录数 + 幽灵关闭（v0 page-head 同构） */
.cfsd-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--fs-s5, 20px);
  flex-shrink: 0;
}
.cfsd-head-l {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}
.cfsd-title {
  font-size: 16px;
  color: var(--fs-ink-900);
  font-weight: 600;
  letter-spacing: 0.03em;
}
.cfsd-count {
  font-family: var(--fs-font-mono);
  font-size: 11px;
  color: var(--fs-ink-500);
  padding: 2px 8px;
  background: var(--fs-bg-sunken);
  border-radius: 999px;
  font-variant-numeric: tabular-nums;
}
.cfsd-close {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.cfsd-close:hover {
  color: var(--fs-ink-900);
  border-color: var(--fs-hairline-strong);
}

.cfsd-body {
  flex: 1;
  display: flex;
  gap: var(--fs-s5, 20px);
  overflow: hidden;
}

/* 左图：表面 + 发丝线，无阴影装饰 */
.cfsd-chart {
  width: 40%;
  height: 100%;
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md, 10px);
  overflow: hidden;
}

/* 右表：同语表面；去 stripe/border，仅表头分隔线 */
.cfsd-table {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md, 10px);
  padding: 0;
}

.cfsd-table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 4px 12px 0;
}

.cfsd-pagination {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid var(--fs-hairline);
}

/* 表格随主题走：透明底 + 发丝行线 + 轻悬停 */
.cfsd-table :deep(.el-table) {
  background-color: transparent;
  color: var(--fs-ink-900);
  --el-table-border-color: var(--fs-hairline);
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: var(--fs-bg-sunken);
}
.cfsd-table :deep(.el-table td.el-table__cell),
.cfsd-table :deep(.el-table th.el-table__cell) {
  background-color: transparent;
  border-bottom: 1px solid var(--fs-hairline);
}
.cfsd-table :deep(.el-table--border .el-table__cell),
.cfsd-table :deep(.el-table__cell) {
  border-right: none;
}
</style>
