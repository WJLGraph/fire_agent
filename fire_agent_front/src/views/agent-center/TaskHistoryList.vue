<script setup>
/**
 * Agent 协作中心 · 历史任务（hist-item 卡片常驻列表同构）
 *
 * 历史数据由父组件持有（localStorage + 后端双源同步），这里只负责渲染与事件上抛。
 * 列表带本地分页（每页 3 条）：历史堆积后左列不至于无限拉长，
 * 翻页器与报告中心左栏同款（el-pagination small · prev/pager/next）。
 *
 * 卡片视觉（发丝环 + 左沿 2px 强调竖轨 + 悬停位移 + 选中 accent 环 + meta 行排版）
 * 与知识库「问答任务」、智能查询「查询历史」共用同一套规范，仅行高/截断行数按各自内容不同。
 */
import { ref, computed, watch } from 'vue'
// LLM 供应商友好名映射（阶段 5：提取到 utils/llmProviders.js，与 AgentPipeline 共用）
import { providerName } from '@/utils/llmProviders'

const props = defineProps({
  taskHistory: { type: Array, default: () => [] },
  activeId: { type: [String, Number], default: null },
})

const emit = defineEmits(['load', 'delete', 'cancel', 'retry'])

// ====== 历史状态展示辅助 ======
const historyStatusClass = (s) => ({
  completed: 'ok',
  failed: 'fail',
  cancelled: 'cancel',
  awaiting_approval: 'appr',
}[s] || 'wait')
const historyStatusText = (s) => ({
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  awaiting_approval: '待审批',
  running: '执行中',
  pending: '排队中',
}[s] || '执行中')
// 进行中（可取消）；已结束（可重试/删除）
const isActive = (s) => s === 'running' || s === 'pending' || s === 'awaiting_approval'
const canRetry = (s) => s === 'failed' || s === 'cancelled' || s === 'completed'

// 紧凑时间（去年份）：created_at "2026-11-02 12:59:31" → "11-02 12:59"，meta 行不再截断
const shortTime = (t) => {
  const m = String(t || '').match(/\d{4}-(\d{2}-\d{2})[T ](\d{2}:\d{2})/)
  return m ? `${m[1]} ${m[2]}` : String(t || '')
}

// 选中态（当前回显的那条）：与知识库问答历史 / 智能查询历史同款高亮
const isOn = (item) => props.activeId !== null && String(item.id) === String(props.activeId)

// ====== 本地分页（每页 3 条） ======
const PAGE_SIZE = 3
const currentPage = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(props.taskHistory.length / PAGE_SIZE)))
const pagedItems = computed(() =>
  props.taskHistory.slice((currentPage.value - 1) * PAGE_SIZE, currentPage.value * PAGE_SIZE)
)

const goPage = (p) => {
  currentPage.value = Math.min(Math.max(1, p), totalPages.value)
}

// 新任务入列（长度增加）→ 回到第 1 页看到最新；删除导致页码越界 → 收回最后一页
watch(
  () => props.taskHistory.length,
  (n, o) => {
    if (n > o) currentPage.value = 1
    else if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
  }
)
</script>

<template>
  <section class="th">
    <div class="th__sec">
      <span class="th__t">历史任务</span>
      <span class="th__n">{{ taskHistory.length }}</span>
      <span class="th__sp"></span>
    </div>

    <div v-if="taskHistory.length === 0" class="th__empty">暂无任务记录，执行一次分析后自动归档</div>

    <template v-else>
      <div class="th__list">
        <div
          v-for="item in pagedItems"
          :key="item.id"
          class="hist-item"
          :class="{ 'is-on': isOn(item) }"
          @click="emit('load', item)"
        >
          <!-- 行内操作：悬停浮现在卡片右上角，不再挤占 meta 行 -->
          <div class="hist-item__acts" @click.stop>
            <button
              v-if="isActive(item.status)"
              class="th__act th__cancel"
              title="取消任务"
              @click.stop="emit('cancel', item)"
            >
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M6 6h8v8H6z"/></svg>
            </button>
            <button
              v-else-if="canRetry(item.status)"
              class="th__act"
              title="按相同问题重新发起任务"
              @click.stop="emit('retry', item)"
            >
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16.4 8.4A6.6 6.6 0 1 0 10 16.6a6.6 6.6 0 0 0 4.6-1.9"/><path d="M16.6 3.6v5h-5"/></svg>
            </button>
            <button class="th__del" title="删除该记录" @click.stop="emit('delete', item)">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5.5h13"/><path d="M8 2.8h4"/><path d="M5.2 5.5 5.9 17h8.2l.7-11.5"/><path d="M8.4 8.4v5.4M11.6 8.4v5.4"/></svg>
            </button>
          </div>

          <div class="hist-item__t" :title="item.query">{{ item.query }}</div>
          <div class="hist-item__m">
            <span class="hist-item__time" :title="item.time">{{ shortTime(item.time) }}</span>
            <span
              v-if="item.llm_model || item.llm_provider"
              class="hist-item__model"
              :title="'生成模型：' + (item.llm_model || providerName(item.llm_provider))"
            >{{ item.llm_model || providerName(item.llm_provider) }}</span>
            <span
              v-else-if="item.status === 'completed' && !item.llm_used"
              class="hist-item__model tpl"
              title="模板生成（无 LLM 参与）"
            >模板</span>
            <span class="hist-item__sp"></span>
            <span
              v-if="item.progress"
              class="hist-item__steps"
              :title="`已执行 ${item.progress.done}/${item.progress.total} 步`"
            >{{ item.progress.done }}/{{ item.progress.total }}</span>
            <span
              v-else-if="item.result && item.result.steps"
              class="hist-item__steps"
            >{{ item.result.steps.length }} 步</span>
            <span class="hist-item__st" :class="historyStatusClass(item.status)">
              <i></i>{{ historyStatusText(item.status) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 翻页器（与报告中心左栏同款：el-pagination small · prev/pager/next） -->
      <div v-if="totalPages > 1" class="th__pager">
        <el-pagination
          size="small"
          layout="prev, pager, next"
          :total="taskHistory.length"
          :page-size="PAGE_SIZE"
          :current-page="currentPage"
          @current-change="goPage"
        />
      </div>
    </template>
  </section>
</template>

<style scoped>
.th {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

/* sec-t 同构：标题 + 计数 + 延伸发丝线 */
.th__sec {
  display: flex;
  align-items: center;
  gap: 6px;
}
.th__t {
  position: relative;
  padding-left: 9px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
.th__t::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 2px;
  height: 11px;
  margin-top: -5.5px;
  border-radius: 1px;
  background: var(--fs-accent);
}
.th__n {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
}
.th__sp { flex: 1; height: 1px; background: var(--fs-hairline); }

/* hist-item 卡片（与知识库问答历史 / 智能查询历史共用同一套规范，仅行高不同） */
.th__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 241px; /* 恰好一页（3×75 + 2×8）：末页条数不足时翻页器位置不跳 */
  /* 容器高度已锁死为一页，任何滚动条都是异常（入场 translateY 的 8px 位移也会顶出滚动条）：直接裁切 */
  overflow: hidden;
  padding-right: 2px; /* 给悬停 2px 位移留出余量 */
}
.hist-item {
  position: relative;
  box-sizing: border-box;
  flex-shrink: 0; /* 行高固定：装不下宁可分页也不压扁 */
  height: 75px; /* 固定行高：padding 16 + 文本 36（2 行）+ meta 上边距 5 + meta 18 */
  padding: 8px 12px;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  overflow: hidden;
  transition: background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
/* 左沿 2px 强调竖轨：静息收起、悬停/选中展开（「可点开回看」的确定性暗示，三页同款） */
.hist-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--fs-accent);
  transform: scaleY(0);
  transform-origin: center;
  transition: transform 0.32s var(--fs-ease);
}
.hist-item:hover {
  background-color: var(--fs-bg-sunken);
  transform: translateX(2px);
}
.hist-item:hover::before { transform: scaleY(1); }
.hist-item:active { transform: translateX(2px) scale(0.995); }
/* 选中条目：accent 环 + 竖轨常驻 */
.hist-item.is-on { box-shadow: inset 0 0 0 1px var(--fs-accent); }
.hist-item.is-on::before { transform: scaleY(1); }

/* 行内操作浮层：悬停显示在右上角，meta 行不再拥挤 */
.hist-item__acts {
  position: absolute;
  top: 7px;
  right: 7px;
  display: flex;
  gap: 4px;
  padding: 3px 4px;
  border-radius: var(--fs-r-sm, 6px);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline), 0 1px 4px rgb(0 0 0 / 6%);
  opacity: 0;
  transform: translateY(-2px);
  transition: opacity var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.hist-item:hover .hist-item__acts { opacity: 1; transform: none; }
.hist-item__t {
  height: 36px; /* 固定 2 行（12px × 1.5 × 2）：单行/双行条目等高，翻页不跳动 */
  font-size: 12px;
  color: var(--fs-ink-700);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hist-item__m {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 5px;
  min-width: 0; /* 允许子项收缩，窄列（<1440px 时列宽 300px）不横向溢出 */
}
.hist-item__time {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 0 1 auto;
  min-width: 0;
  max-width: 108px;
}
.hist-item__model {
  height: 16px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.02em;
  max-width: 104px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  flex-shrink: 1;
  min-width: 0;
}
.hist-item__model.tpl {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-family: inherit;
}
.hist-item__sp { flex: 1; }
.hist-item__steps {
  font-size: 10px;
  color: var(--fs-ink-400);
  white-space: nowrap;
  flex-shrink: 0;
}
.hist-item__st {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--fs-ink-400);
  white-space: nowrap;
  flex-shrink: 0;
}
.hist-item__st i {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: currentColor;
}
.hist-item__st.ok { color: var(--fs-success); }
.hist-item__st.fail { color: var(--fs-danger); }
.hist-item__st.cancel { color: var(--fs-ink-400); }
.hist-item__st.appr { color: var(--fs-accent); }
.hist-item__st.wait { color: var(--fs-warning); }
/* 未归档条目（排队/执行中、待审批）状态点呼吸：一眼区分「还在跑」与「已结束」 */
.hist-item__st.appr i,
.hist-item__st.wait i { animation: th-dot 1.6s ease-in-out infinite; }
@keyframes th-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.72); }
}

/* 行内操作（取消 / 重试 / 删除）：位于悬停浮层内，透明底 + 悬停着色；尺寸/着色与另两页的删除键一致 */
.th__act {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.th__act svg { width: 11px; height: 11px; }
.th__act:hover { color: var(--fs-accent); background: var(--fs-accent-soft); }
.th__act:active { transform: scale(0.9); }
.th__cancel:hover {
  color: var(--fs-danger);
  background: color-mix(in srgb, var(--fs-danger) 12%, transparent);
}

/* 删除按钮 */
.th__del {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.th__del svg { width: 11px; height: 11px; }
.th__del:hover { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 12%, transparent); }
.th__del:active { transform: scale(0.9); }

/* ===== 翻页器（el-pagination small，与报告中心左栏同款） ===== */
.th__pager {
  padding: 4px 0 0;
  display: flex;
  justify-content: center;
}
.th__pager :deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--fs-ink-500);
  --el-pagination-button-color: var(--fs-ink-500);
  --el-pagination-button-disabled-color: var(--fs-ink-400);
  --el-pagination-hover-color: var(--fs-accent);
  --el-pagination-font-size: 12px;
  font-family: var(--fs-font-mono);
}
.th__pager :deep(.el-pager li) {
  min-width: 24px;
  height: 24px;
  border-radius: var(--fs-r-xs, 3px);
  background: transparent;
}
.th__pager :deep(.el-pager li.is-active) {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
}
.th__pager :deep(.el-pagination .btn-prev),
.th__pager :deep(.el-pagination .btn-next) {
  background: transparent;
}

/* 空态 */
.th__empty {
  padding: 14px 10px;
  text-align: center;
  font-size: 11px;
  line-height: 1.6;
  color: var(--fs-ink-400);
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
}
/* ==================== V7 入场微动效：历史任务卡错峰（仅前 6 个有延迟；reduced 静态） ====================
   用 backwards 而非 both：both 的 forwards 填充会把 transform: none 永久留在卡片上，
   动画值优先级高于普通声明，悬停 translateX(2px) 会被吃掉；基线即终态，backwards 足够。 */
.th__list > * { animation: th-in 0.38s var(--fs-ease-out) backwards; }
.th__list > :nth-child(1) { animation-delay: 0s; }
.th__list > :nth-child(2) { animation-delay: 0.06s; }
.th__list > :nth-child(3) { animation-delay: 0.12s; }
.th__list > :nth-child(4) { animation-delay: 0.18s; }
.th__list > :nth-child(5) { animation-delay: 0.24s; }
.th__list > :nth-child(n + 7) { animation-delay: 0.3s; }
@keyframes th-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .th__list > * { animation: none; }
  html:not([data-motion="on"]) .hist-item__st.appr i,
  html:not([data-motion="on"]) .hist-item__st.wait i { animation: none; }
  html:not([data-motion="on"]) .hist-item:hover,
  html:not([data-motion="on"]) .hist-item:active,
  html:not([data-motion="on"]) .th__act:active,
  html:not([data-motion="on"]) .th__del:active { transform: none; }
  html:not([data-motion="on"]) .hist-item:hover::before { transform: scaleY(0); }
}
html[data-motion-allowed="false"] .th__list > *,
html[data-motion-allowed="false"] .hist-item__st.appr i,
html[data-motion-allowed="false"] .hist-item__st.wait i { animation: none; }
html[data-motion-allowed="false"] .hist-item:hover,
html[data-motion-allowed="false"] .hist-item:active,
html[data-motion-allowed="false"] .th__act:active,
html[data-motion-allowed="false"] .th__del:active { transform: none; }
html[data-motion-allowed="false"] .hist-item:hover::before { transform: scaleY(0); }
</style>
