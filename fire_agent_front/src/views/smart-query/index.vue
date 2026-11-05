<script setup>
/**
 * 智能查询页 — 自然语言 → 结构化查询 → 结果展示（摘要/表格/图表/地图）
 *
 * 调用后端 API: POST /api/v1/query/execute
 *
 * 视觉 V2（visual-v0 smartquery 屏同构）：
 *   - 页头改 v0 page-head（64px 单行：标题 + 副题 + 右侧状态徽标）
 *   - 左栏（340px）：提问输入 + 示例胶囊 + 查询历史（hist-item 卡片常驻）
 *   - 右主区（bg-canvas 居中列）：QueryAgent 解析卡 → 结果 KPI → 结果面板
 *   - 空态改 v0 empty（虚线发丝框）
 * 逻辑（查询状态机 / 历史回显 / 语音 ASR / 图表 option）未做任何修改。
 */
import BackHomeButton from '@/components/base/BackHomeButton.vue'
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  fetchHistory,
  fetchHistoryDetail,
  clearHistory as clearHistoryApi,
  deleteHistoryItem as deleteHistoryItemApi,
  execute,
} from '@/api/query'
import { chartTokens } from '@/utils/themeTokens'
import { useThemeStore } from '@/stores/theme'
import { recordState, startRecord, cleanupSpeech } from '@/utils/speech'
import QueryHistoryRail from './QueryHistoryRail.vue'
import QueryInputPanel from './QueryInputPanel.vue'
import QueryParsePanel from './QueryParsePanel.vue'
import QueryResultPanel from './QueryResultPanel.vue'

// ====== 状态 ======
const queryText = ref('')
const loading = ref(false)
const activeTab = ref('summary')
const queryHistory = ref([])
// 当前回显的历史条目（选中态高亮，与知识库问答历史同款）
const activeHistoryId = ref(null)

// 查询结果
const currentResult = reactive({
  summary: '',
  tableData: [],
  chartData: null,
  chartType: '',
  geoData: null,
  total: 0,
  parseMethod: '', // llm / keyword
})
const parsedInfo = ref(null) // QueryAgent 解析结果（intent/params/method/explanation）

// ====== 查询历史（后端数据库持久化，按用户隔离） ======
const loadHistory = async () => {
  try {
    const json = await fetchHistory()
    if (json.code === 200) {
      queryHistory.value = json.data || []
    }
  } catch {
    /* 静默 */
  }
}

// ====== 执行查询 ======
const handleQuery = async () => {
  const text = queryText.value.trim()
  if (!text) {
    ElMessage.warning('请输入查询内容')
    return
  }

  loading.value = true
  activeHistoryId.value = null // 新查询：历史高亮让位给当前结果
  currentResult.summary = ''
  currentResult.tableData = []
  currentResult.chartData = null
  currentResult.chartType = ''
  currentResult.geoData = null
  currentResult.parseMethod = ''
  parsedInfo.value = null

  try {
    const json = await execute(text)

    if (json.code !== 200) {
      ElMessage.error('查询失败: ' + json.message)
      return
    }

    const data = json.data
    // QueryAgent 解析结果（完整保留 intent/params/method/explanation 供前端展示）
    parsedInfo.value = data.parsed || null
    const result = data.result

    currentResult.summary = result.summary || '无摘要'
    currentResult.tableData = result.table_data || []
    currentResult.chartData = result.chart_data || null
    currentResult.chartType = result.chart_type || ''
    currentResult.geoData = result.geo_data || null
    currentResult.parseMethod = data.parsed.method || 'keyword'
    currentResult.total = result.total || 0

    // 历史由后端自动保存（同文本去重），这里仅刷新列表
    loadHistory()

    // 切换到摘要 tab（图表 tab 由用户主动点击时才会挂载 EChart 渲染）
    activeTab.value = 'summary'
  } catch (e) {
    ElMessage.error('网络错误，请确认后端服务已启动: ' + e.message)
  } finally {
    loading.value = false
  }
}

// ====== 点击示例查询 ======
const handleExample = (example) => {
  queryText.value = example
  handleQuery()
}

// ====== 点击历史：直接回显数据库存储的结果，不重新查询 ======
const applyResult = (data) => {
  parsedInfo.value = data.parsed || null
  const result = data.result
  currentResult.summary = result.summary || '无摘要'
  currentResult.tableData = result.table_data || []
  currentResult.chartData = result.chart_data || null
  currentResult.chartType = result.chart_type || ''
  currentResult.geoData = result.geo_data || null
  currentResult.parseMethod = (data.parsed && data.parsed.method) || 'keyword'
  currentResult.total = result.total || 0
  activeTab.value = 'summary'
}

const handleHistoryClick = async (item) => {
  queryText.value = item.text
  activeHistoryId.value = item.id // 回显态：卡片 accent 环 + 竖轨（与知识库/Agent 中心一致）
  try {
    const json = await fetchHistoryDetail(item.id)
    if (json.code === 200 && json.data.result) {
      // 直接回显存储结果（不触发后端重新查询）
      parsedInfo.value = null
      currentResult.summary = ''
      currentResult.tableData = []
      currentResult.chartData = null
      currentResult.chartType = ''
      currentResult.geoData = null
      applyResult(json.data.result)
      return
    }
  } catch {
    /* 接口失败则回退为重新查询 */
  }
  // 旧记录无存储结果（升级前的数据），回退为重新执行查询
  handleQuery()
}

// ====== 清除历史 ======
const clearHistory = async () => {
  try {
    const json = await clearHistoryApi()
    if (json.code === 200) {
      queryHistory.value = []
    }
  } catch {
    /* 静默 */
  }
}

// ====== 单条删除历史（与知识库/Agent/报告三页保持一致） ======
const deleteHistoryItem = async (item) => {
  try {
    const json = await deleteHistoryItemApi(item.id)
    if (json.code === 200) {
      queryHistory.value = queryHistory.value.filter(h => h.id !== item.id)
    }
  } catch {
    /* 静默 */
  }
}

// ====== 语音输入（ASR）：识别完成自动执行查询 ======
const handleMicClick = () => {
  if (recordState.recording) {
    startRecord() // 录音中再次调用 = 停止并识别
    return
  }
  startRecord((text) => {
    queryText.value = text
    handleQuery()
  })
}

// ====== 结果 KPI（v0 sq-kpis 四格：记录总数 / 解析方式 / 可用视图 / 历史查询） ======
const resultKpis = computed(() => {
  const dims = [
    currentResult.tableData.length > 0 && '表格',
    currentResult.chartData && currentResult.chartData.labels && '图表',
    currentResult.geoData && '地图',
  ].filter(Boolean)
  return [
    { v: (currentResult.total || 0).toLocaleString(), k: '记录总数' },
    { v: currentResult.parseMethod === 'llm' ? 'LLM 解析' : (currentResult.parseMethod ? '关键词' : '—'), k: '解析方式' },
    { v: dims.length ? dims.join(' / ') : '—', k: '可用视图' },
    { v: String(queryHistory.value.length), k: '历史查询' },
  ]
})

// ====== 图表 option ======
// 阶段 3：图表实例交给 components/chart/EChart 管理（init / dispose / resize / 主题重建），
//         这里只负责产出 option —— 原 renderChart 内的配置逻辑一字未改，仅由函数改为 computed。
const theme = useThemeStore()
const tokens = computed(() => chartTokens(theme.mode))

const chartOption = computed(() => {
  if (!currentResult.chartData || !currentResult.chartData.labels) return {}

  const labels = currentResult.chartData.labels
  const values = currentResult.chartData.values
  const t = tokens.value // 主题取色：文字/坐标轴/浮层跟随浅色/深色主题

  let option = {}

  if (currentResult.chartType === 'pie') {
    option = {
      tooltip: { trigger: 'item', backgroundColor: t.panel, borderColor: t.border, textStyle: { color: t.text } },
      legend: { textStyle: { color: t.muted }, bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['35%', '60%'],
        center: ['50%', '45%'],
        itemStyle: {
          borderRadius: 4,
          borderColor: t.panel,
          borderWidth: 2,
        },
        label: { color: t.text, fontSize: 11 },
        data: labels.map((name, i) => ({
          name,
          value: values[i] || 0,
          itemStyle: { color: ['#22d3ee', '#4ade80', '#facc15', '#fb923c', '#ef4444'][i % 5] },
        })),
      }],
    }
  } else {
    option = {
      tooltip: {
        trigger: 'axis',
        backgroundColor: t.panel,
        borderColor: t.border,
        textStyle: { color: t.text },
      },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: t.axis, fontSize: 10, rotate: labels.length > 8 ? 45 : 0 },
        axisLine: { lineStyle: { color: t.border } },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: t.axis, fontSize: 10 },
        splitLine: { lineStyle: { color: t.split } },
      },
      series: [{
        type: currentResult.chartType === 'bar' ? 'bar' : 'line',
        data: values,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#0ea5e9' },
            { offset: 1, color: '#22d3ee' },
          ]),
          borderRadius: [3, 3, 0, 0],
        },
        lineStyle: { color: '#0ea5e9', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(14,165,233,0.3)' },
            { offset: 1, color: 'rgba(14,165,233,0.02)' },
          ]),
        },
        smooth: true,
      }],
    }
  }

  return option
})

onMounted(() => {
  loadHistory()
})
onUnmounted(() => {
  cleanupSpeech() // 停止语音播报/录音
})
</script>

<template>
  <div class="sq-page">
    <!-- ===== 页头（v0 page-head 同构：64px 单行） ===== -->
    <header class="sq-head">
      <div class="sq-head__t">
        <h1 class="sq-head__h1">智能查询</h1>
        <p class="sq-head__sub">自然语言提问 · QueryAgent 解析 → 摘要 / 表格 / 图表 / 地图</p>
      </div>
      <BackHomeButton />
      <span class="sq-head__sp"></span>
      <span class="sq-head__badge mono">qwen-plus · LLM / keyword 双通道</span>
      <span class="sq-head__live"><i class="sq-head__dot"></i>QueryAgent 就绪</span>
    </header>

    <!-- ===== 主体：左栏（提问 + 历史）/ 右主区（解析 + KPI + 结果） ===== -->
    <div class="sq-body">
      <!-- 左栏 -->
      <aside class="sq-side">
        <div class="sq-side__scroll">
          <!-- 输入区（提问 + 示例胶囊） -->
          <QueryInputPanel
            v-model="queryText"
            :loading="loading"
            :recording="recordState.recording"
            @query="handleQuery"
            @mic="handleMicClick"
            @example="handleExample"
          />

          <!-- 查询历史（hist-item 卡片常驻列表） -->
          <QueryHistoryRail
            :items="queryHistory"
            :active-id="activeHistoryId"
            @select="handleHistoryClick"
            @remove="deleteHistoryItem"
            @clear="clearHistory"
          />
        </div>
      </aside>

      <!-- 右主区 -->
      <div class="sq-main">
        <div class="sq-main__scroll">
          <!-- QueryAgent 解析过程 -->
          <QueryParsePanel v-if="parsedInfo" :parsed-info="parsedInfo" />

          <!-- 结果 KPI（v0 sq-kpis 四格） -->
          <div v-if="currentResult.summary" class="sq-kpis">
            <div v-for="k in resultKpis" :key="k.k" class="sq-kpi">
              <span class="sq-kpi__v">{{ k.v }}</span>
              <span class="sq-kpi__k">{{ k.k }}</span>
            </div>
          </div>

          <!-- 结果区 -->
          <QueryResultPanel
            v-if="currentResult.summary"
            v-model:active-tab="activeTab"
            :result="currentResult"
            :chart-option="chartOption"
          />

          <!-- 空态（v0 empty：虚线发丝框） -->
          <div v-else class="sq-empty">
            <svg class="sq-empty__ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <circle cx="9" cy="9" r="5.5"/><path d="m13.2 13.2 3.3 3.3"/>
            </svg>
            输入查询内容，系统将自动分析数据并展示结果
            <span class="sq-empty__hint">支持自然语言：州市 / 时间窗口 / 置信度 / TopN 均可自由组合</span>
            <button class="sq-empty__btn" @click="handleMicClick">
              {{ recordState.recording ? '停止录音' : '试试语音提问' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sq-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fs-bg-canvas);
  /* 指挥台网格底纹（hairline 级，随亮暗主题取色） */
  background-image:
    linear-gradient(rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px);
  background-size: 48px 48px;
  color: var(--fs-ink-900);
  overflow: hidden;
}

/* ===== 页头（v0 page-head） ===== */
.sq-head {
  flex-shrink: 0;
  height: var(--fs-topbar-h, 64px);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--fs-bg-surface);
  border-bottom: 1px solid var(--fs-hairline);
}
.sq-head__t { min-width: 0; }
.sq-head__h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.2;
  color: var(--fs-ink-900);
}
.sq-head__sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--fs-ink-500);
}
.sq-head__sp { flex: 1; }
.sq-head__badge {
  font-family: var(--fs-font-mono);
  font-size: 11px;
  color: var(--fs-ink-500);
  white-space: nowrap;
}
.sq-head__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  font-size: 11px;
  color: var(--fs-ink-700);
  white-space: nowrap;
}
.sq-head__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--fs-success);
}

/* ===== 主体 ===== */
.sq-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.sq-side {
  flex: none;
  width: 340px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--fs-bg-surface);
  border-right: 1px solid var(--fs-hairline);
  overflow: hidden;
}
.sq-side__scroll {
  flex: 1;
  min-height: 0;
  overflow: hidden; /* 整列不滚动：输入区定高，历史区弹性 + 内部铺满，翻页器常显沉底 */
  /* 顶部 24px 与页头留出呼吸、左右 16px 与知识库/Agent 中心左列对齐；底部回收 6px 让给历史区 */
  padding: 24px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sq-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-canvas);
}
.sq-main__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  width: 100%;
  max-width: 980px;
  margin: 0 auto;
  padding: 20px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

/* ===== 结果 KPI（v0 sq-kpis 四格） ===== */
.sq-kpis {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.sq-kpi {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-left: 1px solid var(--fs-hairline);
  min-width: 0;
}
.sq-kpi:first-child { border-left: none; }
.sq-kpi__v {
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
  color: var(--fs-ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sq-kpi__k {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--fs-ink-500);
}

/* ===== 空态（v0 empty：虚线发丝框） ===== */
.sq-empty {
  flex: 1;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-md, 10px);
  color: var(--fs-ink-500);
  font-size: 13px;
  text-align: center;
}
.sq-empty__ic {
  width: 22px;
  height: 22px;
  color: var(--fs-ink-400);
}
.sq-empty__hint {
  font-size: 11px;
  color: var(--fs-ink-400);
}
.sq-empty__btn {
  margin-top: 8px;
  height: 28px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  font-weight: 500;
  color: var(--fs-ink-700);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.sq-empty__btn:hover {
  color: var(--fs-accent);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
  transform: translateY(-1px);
}
.sq-empty__btn:active {
  box-shadow: inset 0 0 0 1px var(--fs-accent);
  transform: translateY(0.5px);
}

/* ===== 入场微动效（挂载即播，基线即终态；三态闸门可关） ===== */
.sq-kpi { animation: sqk-in 0.42s var(--fs-ease-out) both; }
.sq-kpi:nth-child(1) { animation-delay: 0ms; }
.sq-kpi:nth-child(2) { animation-delay: 55ms; }
.sq-kpi:nth-child(3) { animation-delay: 110ms; }
.sq-kpi:nth-child(4) { animation-delay: 165ms; }
@keyframes sqk-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.sq-main, .sq-side { animation: panel-in 0.5s var(--fs-ease-out) both; }
.sq-side { animation-delay: 0.08s; }
@keyframes panel-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
}
html[data-motion-allowed="false"] .sq-main,
html[data-motion-allowed="false"] .sq-side,
html[data-motion-allowed="false"] .sq-kpi { animation: none; }
html[data-motion-allowed="false"] .sq-empty__btn:hover,
html[data-motion-allowed="false"] .sq-empty__btn:active { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .sq-main,
  html:not([data-motion="on"]) .sq-side,
  html:not([data-motion="on"]) .sq-kpi { animation: none; }
  html:not([data-motion="on"]) .sq-empty__btn:hover,
  html:not([data-motion="on"]) .sq-empty__btn:active { transform: none; }
}
</style>
