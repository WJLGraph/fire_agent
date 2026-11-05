<script setup>
/**
 * 智能查询 · 结果面板（v0 sq-panel 同构）
 *
 * 头部：标题 + rows 徽标 + seg 摘要/表格/图表/地图 + 语音播报 + 导出 CSV
 * 摘要注记条（sq-panel__note，3 行截断）+ 各 Tab 内容区。
 * 受控组件：结果数据、当前 Tab、图表 option 由父组件持有（Tab 用 v-model:activeTab 双向）。
 */
import EChart from '@/components/chart/EChart.vue'
import { speakState, speakText } from '@/utils/speech'
import QueryResultMap from './QueryResultMap.vue'

const props = defineProps({
  result: { type: Object, required: true },
  activeTab: { type: String, default: 'summary' },
  chartOption: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:activeTab'])

const setTab = (tab) => emit('update:activeTab', tab)

// ====== 表格语义化：已知字段映射中文表头 + 数值列判定，未知字段回退原样（不做大写变换） ======
const COL_LABELS = {
  // 历史火点
  id: 'ID',
  acq_date: '日期',
  acq_time: '时刻',
  frp: 'FRP (MW)',
  confidence: '置信度',
  conf: '等级',
  longitude: '经度',
  latitude: '纬度',
  city: '州市',
  county: '区县',
  address: '位置',
  // 预测火险（predict_daily / predict_month）
  year: '年份',
  month: '月份',
  day: '日期',
  date: '日期',
  view_mode: '视图',
  base_fire_index: '基准指数',
  final_fire_index: '火险指数',
  fire_level: '火险等级',
  pred_fire_count: '预测火点',
  pred_fire_risk: '风险评分',
  risk_score: '风险评分',
  risk_level: '风险等级',
  region: '州市',
}
const NUM_COLS = new Set([
  'id', 'frp', 'confidence', 'longitude', 'latitude',
  'year', 'month', 'day', 'base_fire_index', 'final_fire_index',
  'fire_level', 'pred_fire_count', 'pred_fire_risk', 'risk_score',
])
const colLabel = (c) => COL_LABELS[c] || c
const isNum = (c) => NUM_COLS.has(c)
const isConf = (c) => c === 'conf'
const confKind = (v) => (String(v).toLowerCase() === 'high' ? 'high' : 'low')

// ====== 导出 CSV（前端直出：BOM + 全字段转义，空表格不出手） ======
const exportCsv = () => {
  const rows = props.result.tableData || []
  if (!rows.length) return
  const cols = Object.keys(rows[0])
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = '\ufeff' + [
    cols.join(','),
    ...rows.map(r => cols.map(c => esc(r[c])).join(',')),
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  a.href = URL.createObjectURL(blob)
  a.download = `查询结果_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <section class="sq-panel">
    <!-- 头部：标题 + rows + seg tabs + 播报 + 导出 -->
    <div class="sq-panel__hd">
      <span class="sq-panel__t">查询结果</span>
      <span class="sq-panel__rows">{{ result.total }} rows</span>
      <span class="sq-panel__sp"></span>
      <div class="sq-seg" role="tablist" aria-label="结果视图">
        <button
          class="sq-seg__i"
          :class="{ 'is-on': activeTab === 'summary' }"
          @click="setTab('summary')"
        >摘要</button>
        <button
          class="sq-seg__i"
          :class="{ 'is-on': activeTab === 'table' }"
          :disabled="result.tableData.length === 0"
          @click="setTab('table')"
        >表格</button>
        <button
          class="sq-seg__i"
          :class="{ 'is-on': activeTab === 'chart' }"
          :disabled="!result.chartData || !result.chartData.labels"
          @click="setTab('chart')"
        >图表</button>
        <button
          class="sq-seg__i"
          :class="{ 'is-on': activeTab === 'map' }"
          :disabled="!result.geoData"
          @click="setTab('map')"
        >地图</button>
      </div>
      <button
        class="sq-hd-btn"
        :class="{ speaking: speakState.speaking || speakState.loading }"
        title="语音播报查询摘要"
        @click="speakText(`${result.summary}，共${result.total}条记录。`)"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8v4h2.6l3.4 3V5L6.6 8z"/><path d="M13.2 7.6a3.6 3.6 0 0 1 0 4.8"/></svg>
        {{ speakState.speaking || speakState.loading ? '停止' : '播报' }}
      </button>
      <button
        class="sq-hd-btn"
        :disabled="!result.tableData.length"
        title="导出表格数据为 CSV"
        @click="exportCsv"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3v8.6"/><path d="m6.4 8.2 3.6 3.6 3.6-3.6"/><path d="M3.5 15.4v1.1h13v-1.1"/></svg>
        导出 CSV
      </button>
    </div>

    <!-- 摘要注记条（3 行截断，悬停 title 看全文） -->
    <div class="sq-panel__note" :title="result.summary">{{ result.summary }}</div>

    <!-- 摘要 Tab：全文 -->
    <div v-if="activeTab === 'summary'" class="sq-panel__bd sq-panel__bd--scroll">
      <div class="sq-summary-full">{{ result.summary }}</div>
    </div>

    <!-- 表格 Tab -->
    <div v-else-if="activeTab === 'table'" class="sq-panel__bd sq-panel__bd--fill">
      <div class="table-wrap">
        <el-table
          :data="result.tableData"
          height="100%"
          size="small"
          class="result-table"
          empty-text="本次查询没有返回表格数据"
        >
          <el-table-column
            v-for="col in Object.keys(result.tableData[0] || {})"
            :key="col"
            :prop="col"
            :label="colLabel(col)"
            :min-width="isNum(col) ? 96 : 84"
            :align="isNum(col) ? 'right' : 'left'"
            :class-name="isNum(col) ? 'num-cell' : ''"
            show-overflow-tooltip
          >
            <!-- conf 列：彩色徽标（high=danger 点 / low=中性点） -->
            <template v-if="isConf(col)" #default="{ row }">
              <span class="conf-badge" :class="confKind(row[col])"><i></i>{{ row[col] }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 图表 Tab -->
    <div v-else-if="activeTab === 'chart'" class="sq-panel__bd sq-panel__bd--fill">
      <EChart
        class="chart-container"
        :height="''"
        :option="chartOption"
      />
    </div>

    <!-- 地图 Tab（Tab 挂载即渲染，等价于原 nextTick(renderMap())） -->
    <div v-else-if="activeTab === 'map'" class="sq-panel__bd sq-panel__bd--fill">
      <QueryResultMap :geo-data="result.geoData" />
    </div>
  </section>
</template>

<style scoped>
/* v0 sq-panel：表面卡 + inset 发丝环 */
.sq-panel {
  flex: 1 1 auto;
  min-height: 420px;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease);
  animation: rp-in 0.42s var(--fs-ease-out) both;
}
.sq-panel:hover { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
@keyframes rp-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}

/* 头部 */
.sq-panel__hd {
  flex-shrink: 0;
  min-height: 48px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.sq-panel__t {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
  color: var(--fs-ink-900);
}
.sq-panel__t::before {
  content: '';
  width: 2px;
  height: 12px;
  border-radius: 1px;
  background-color: var(--fs-hairline-strong);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.sq-panel:hover .sq-panel__t::before { background-color: var(--fs-accent); }
.sq-panel__rows {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
  white-space: nowrap;
}
.sq-panel__sp { flex: 1; }

/* seg（v0 .seg 同构：sunken 轨道 + 浮起激活） */
.sq-seg {
  display: inline-flex;
  padding: 2px;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-sm, 6px);
}
.sq-seg__i {
  height: 24px;
  padding: 0 10px;
  border: none;
  background: transparent;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: var(--fs-ink-500);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.sq-seg__i:hover:not(:disabled):not(.is-on) { color: var(--fs-ink-900); }
.sq-seg__i.is-on {
  background: var(--fs-bg-surface);
  color: var(--fs-ink-900);
  font-weight: 600;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14), var(--fs-e1);
}
.sq-seg__i:disabled { opacity: 0.4; cursor: not-allowed; }

/* 头部小按钮（播报 / 导出） */
.sq-hd-btn {
  height: 26px;
  padding: 0 9px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.sq-hd-btn svg { width: 12px; height: 12px; }
.sq-hd-btn:hover:not(:disabled) { color: var(--fs-ink-900); background-color: var(--fs-bg-sunken); }
.sq-hd-btn:active:not(:disabled) { transform: translateY(0.5px); }
.sq-hd-btn.speaking { color: var(--fs-danger); }
.sq-hd-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* 摘要注记条 */
.sq-panel__note {
  flex-shrink: 0;
  padding: 12px 16px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--fs-ink-500);
  border-bottom: 1px solid var(--fs-hairline);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: background-color var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.sq-panel__note:hover {
  background-color: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
}

/* Tab 内容 */
.sq-panel__bd {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.sq-panel__bd--scroll {
  overflow-y: auto;
  padding: 16px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
.sq-panel__bd--fill { padding: 4px; }
.sq-summary-full {
  font-size: 13px;
  line-height: 1.8;
  color: var(--fs-ink-700);
  white-space: pre-wrap;
}

/* 表格：外层不再滚动，由表格自身接管，消除双重滚动条 */
.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.result-table {
  width: 100%;
  height: 100%;
}

/* 图表 */
.chart-container {
  flex: 1;
  min-height: 0;
  width: 100%;
}

/* 表格令牌（三线表气质：mono 表头 + 发丝行线，无斑马纹） */
.result-table :deep(.el-table) {
  --el-table-bg-color: transparent !important;
  --el-table-tr-bg-color: transparent !important;
  --el-table-header-bg-color: var(--fs-bg-sunken) !important;
  --el-table-row-hover-bg-color: var(--fs-bg-sunken) !important;
  color: var(--fs-ink-900) !important;
}
/* 行高舒展但不空旷 */
.result-table :deep(.el-table__cell) {
  padding: 8px 0;
}
.result-table :deep(.el-table .cell) {
  padding: 0 14px;
  line-height: 1.45;
}
/* 表头：小号 + 字距（中文语义表头，未知字段回退原样不做大写变换） */
.result-table :deep(th.el-table__cell) {
  background: var(--fs-bg-sunken) !important;
  color: var(--fs-ink-500) !important;
  font-family: var(--fs-font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  border-bottom: 1px solid var(--fs-hairline-strong) !important;
  white-space: nowrap;
}
.result-table :deep(td.el-table__cell) {
  background: transparent !important;
  color: var(--fs-ink-700) !important;
  border-bottom: 1px solid var(--fs-hairline) !important;
  font-size: 12px;
}
/* 行悬停读数：底色浮起 + 文字加浓，配合全局首列 2px 强调轨定位当前行 */
.result-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: var(--fs-bg-sunken) !important;
  color: var(--fs-ink-900) !important;
}
/* 数值列：等宽 + 表格数字（右对齐由列 align 控制） */
.result-table :deep(.num-cell .cell) {
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  color: var(--fs-ink-900);
}
/* FRP 等关键数值弱强调：非表头的首列数字保持中性，避免彩色噪音 */

/* conf 徽标：high = 危险色点 / low = 中性点 */
.conf-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 18px;
  padding: 0 8px;
  border-radius: 999px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.05em;
  white-space: nowrap;
}
.conf-badge i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}
.conf-badge.high {
  color: var(--fs-danger);
  background: color-mix(in srgb, var(--fs-danger) 10%, transparent);
}
.conf-badge.high i { background: var(--fs-danger); }
.conf-badge.low {
  color: var(--fs-ink-500);
  background: var(--fs-bg-sunken);
}
.conf-badge.low i { background: var(--fs-ink-400); }

/* 动效三态闸门 */
html[data-motion-allowed="false"] .sq-panel { animation: none; }
html[data-motion-allowed="false"] .sq-hd-btn:active:not(:disabled) { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .sq-panel { animation: none; }
  html:not([data-motion="on"]) .sq-hd-btn:active:not(:disabled) { transform: none; }
}
</style>
