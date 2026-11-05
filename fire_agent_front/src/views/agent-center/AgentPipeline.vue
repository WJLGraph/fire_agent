<script setup>
import { ref, computed, watch } from 'vue'
import { providerName } from '@/utils/llmProviders'
import {
  composeThinkRounds,
  mergeThinkText,
  mergeThinkRounds,
  normalizeThinkRounds,
  streamNoteText,
  thinkLenText,
} from '@/utils/thinkText'
import AgentThinkPanel from '@/components/agent-center/AgentThinkPanel.vue'

const props = defineProps({
  pipelineSteps: { type: Array, required: true },
  /** 与 pipelineSteps 一一对应的状态数组：pending / running / completed / skipped / failed */
  stepStatuses: { type: Array, default: () => [] },
  /** 后端 agent_task_steps 行（{ step, agent, status, summary, output }），按 key 对齐注入审计详情 */
  traceSteps: { type: Array, default: () => [] },
  /** 报告生成中且模型正在深度思考（report_think 已到、正文未到）→ generate_report 行显示思考态 */
  reportThinking: { type: Boolean, default: false },
  /** 实时累积思考全文（全部轮次，含轻量轮次小标题） */
  liveThink: { type: String, default: '' },
  /** 实时累积思考轮次：[{ round, text }]，与落库 thinking_rounds 按轮次合并 */
  liveThinkRounds: { type: Array, default: () => [] },
  /** 报告正文是否已开始产出：正文开始后才自动收起流水线，思考阶段仍保持展开 */
  reportStarted: { type: Boolean, default: false },
  /** 问题 B 两段式：本轮思考进行中时思考宿主在「分析报告」流式卡，
   *  本节点面板此时隐藏（互斥，避免两处同时显示）；正文首个 delta 后自动迁回 */
  thinkInReport: { type: Boolean, default: false },
})

const statusOf = (i) => props.stepStatuses[i] || 'pending'

// ====== 折叠（中列高度规划：正文开始产出后自动收起流水线，把高度让给报告正文） ======
// 思考阶段不收起：第 5 节点的「思考过程」面板需要从首个增量起可见
const collapsed = ref(false)
let autoCollapsed = false
watch(
  () => [props.reportStarted, props.traceSteps],
  () => {
    if (autoCollapsed) return
    const gen = (props.traceSteps || []).find(s => s && s.step === 'generate_report')
    if (props.reportStarted || (gen && (gen.status || 'completed') === 'completed')) {
      collapsed.value = true
      autoCollapsed = true
    }
  },
  { immediate: true, deep: true },
)
const toggle = () => { collapsed.value = !collapsed.value }
// 新任务开始（步骤清空）→ 复位为展开态，下个任务重新自动收起
watch(() => props.traceSteps.length, (n, o) => {
  if (n === 0 && o > 0) { autoCollapsed = false; collapsed.value = false }
})

// 头部紧凑摘要：完成 x/N（N = 节点数，含人工审核时 7）· 总耗时
const doneCount = computed(() => props.stepStatuses.filter(s => s === 'completed').length)
const totalDuration = computed(() =>
  props.traceSteps.reduce((acc, s) => acc + (typeof s?.duration === 'number' ? s.duration : 0), 0))
const headSummary = computed(() => {
  if (!props.traceSteps.length) return ''
  const dur = totalDuration.value > 0 ? ` · ${totalDuration.value >= 100 ? Math.round(totalDuration.value) : totalDuration.value.toFixed(1)}s` : ''
  return `${doneCount.value}/${props.pipelineSteps.length}${dur}`
})

// ====== 步骤审计对齐（key → 后端步骤行） ======
const traceMap = computed(() => {
  const m = {}
  for (const st of props.traceSteps) {
    if (st && st.step) m[st.step] = st
  }
  return m
})
const traceOf = (key) => traceMap.value[key]

// ====== 步骤审计 chips（从 step.output 提取，紧凑标签展示；纯函数只读 output） ======
// token 数紧凑格式：1234 → 1.2k
const fmtTokens = (n) => (typeof n === 'number' && isFinite(n) ? (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)) : '')

const stepChips = (st) => {
  const o = st && st.output
  if (!o || typeof o !== 'object') return []
  const chips = []
  // LLM 模型名（优先）+ 供应商 + token 用量（parse_task / generate_report 等）
  const pName = o.llm_model || providerName(o.llm_provider)
  const tok = o.tokens && o.tokens.total_tokens
  const tokText = tok != null ? `${fmtTokens(tok)} tokens` : ''
  if (pName || tokText) chips.push({ cls: 'llm', text: [pName, tokText].filter(Boolean).join(' · ') })
  // LLM 降级
  if (o.llm_degraded === true) chips.push({ cls: 'warn', text: '降级' })
  // 数据查询：参数重试 / 无数据 / 命中总量 / 首城
  if (Array.isArray(o.attempts) && o.attempts.length > 1) chips.push({ cls: '', text: `重试 ${o.attempts.length} 次` })
  if (o.empty_reason) chips.push({ cls: 'warn', text: '无数据', tip: String(o.empty_reason) })
  if ('total' in o) chips.push({ cls: '', text: `查询 ${o.total} 条` })
  if (o.first_city) chips.push({ cls: '', text: `首城 ${o.first_city}` })
  // GIS：跳过 / 热点数
  if (o.skipped === true) chips.push({ cls: 'warn', text: '已跳过' })
  if ('total_hotspots' in o) chips.push({ cls: '', text: `热点 ${o.total_hotspots} 个` })
  // RAG：命中段数 + 检索方式
  if ('matched' in o) {
    const m = [o.matched != null ? `命中 ${o.matched} 段` : '', o.method || ''].filter(Boolean).join(' · ')
    if (m) chips.push({ cls: '', text: m })
  }
  // 报告长度
  if ('report_length' in o) chips.push({ cls: '', text: `${o.report_length} 字符` })
  // 需求 A/B：生成过程思考留存 + 流式中断标记（复读中断/思考超限/取消）
  if (o.thinking) chips.push({ cls: '', text: `思考 ${thinkLenText(String(o.thinking).length)}`, tip: '已留存思考过程，可在节点下方展开查看' })
  if (o.stream_note) chips.push({ cls: 'warn', text: streamNoteText(o.stream_note) })
  // 需求 C：历轮评审打回记录（第几轮 + 每轮原因，悬停可看完整列表）
  if (Array.isArray(o.review_history)) {
    const rejected = o.review_history.filter(r => r && r.passed === false)
    if (rejected.length) {
      chips.push({
        cls: 'danger',
        text: `打回 ${rejected.length} 轮`,
        tip: rejected.map(r => `第${r.round}轮：${(r.issues || []).join('；') || r.suggestion || '—'}`).join('\n'),
      })
    }
  }
  // 计划步数
  if (Array.isArray(o.plan)) chips.push({ cls: '', text: `计划 ${o.plan.length} 步` })
  // 质量评审三态：passed 通过 / returned 退回重写 / degraded 评审失败转人工（中性警告，非失败）
  const forced = o.forced === true || (o.review_result && o.review_result.forced === true)
  const reviewStatus = o.review_status ||
    (typeof o.passed === 'boolean' ? (o.passed ? 'passed' : (forced ? 'degraded' : 'returned')) : '')
  if (reviewStatus === 'degraded') {
    chips.push({ cls: 'warn', text: '评审未完成 · 转人工确认', tip: o.degraded_reason || o.suggestion || '' })
  } else if (reviewStatus === 'passed') {
    chips.push({ cls: 'ok', text: '评审通过' })
  } else if (reviewStatus === 'returned') {
    chips.push({ cls: 'danger', text: '评审退回' })
  } else if (forced) {
    chips.push({ cls: 'warn', text: '强制放行' })
  }
  if (Array.isArray(o.issues) && o.issues.length) {
    chips.push({ cls: 'warn', text: `${o.issues.length} 项问题`, tip: o.issues.join('；') })
  }
  // 错误
  if (o.error) chips.push({ cls: 'danger', text: '错误', tip: String(o.error) })
  // 本步耗时不再作为 chip：标题行右侧等宽对齐展示（见模板 tl-step__dur）
  return chips
}

const chipsOf = (key) => stepChips(traceOf(key))

// ====== 需求 A/B/C：生成报告节点「思考过程」面板（共用组件 AgentThinkPanel） ======
// 渲染/折叠/滚动/字数/状态标签全部收口到组件内；展开态由 useAgentStreamState 模块级共享，
// 报告区 ↔ 本节点两处宿主迁移时延续用户折叠选择。streamNoteText 由 utils/thinkText 统一提供。
const genTrace = computed(() => traceOf('generate_report'))
const genOutput = computed(() => (genTrace.value && genTrace.value.output) || {})

// 实时轮次 + 落库轮次按轮次号合并；旧字段 thinking 仅存最后一轮，并入最后一轮保留历史
const genThinking = computed(() => {
  const o = genOutput.value
  const liveRounds = normalizeThinkRounds(props.liveThinkRounds)
  let rounds = []
  if (Array.isArray(o.thinking_rounds) && o.thinking_rounds.length) {
    rounds = mergeThinkRounds(liveRounds, o.thinking_rounds)
  } else if (typeof o.thinking === 'string' && o.thinking.trim() && liveRounds.length) {
    const last = liveRounds[liveRounds.length - 1]
    rounds = mergeThinkRounds(liveRounds, [{ round: last.round, text: o.thinking }])
  }
  const live = String(props.liveThink || '')
  const persisted = typeof o.thinking === 'string' ? o.thinking : ''
  if (rounds.length) return mergeThinkText(live, composeThinkRounds(rounds))
  return mergeThinkText(live, persisted)
})
</script>

<template>
  <section class="pl">
    <div class="pl__sec" :class="{ 'is-clickable': traceSteps.length }" :title="collapsed ? '展开执行流水线' : '收起执行流水线'" @click="traceSteps.length && toggle()">
      <span class="pl__t">执行流水线</span>
      <span v-if="traceSteps.length" class="pl__n">{{ traceSteps.length }}</span>
      <span class="pl__sp"></span>
      <span v-if="headSummary" class="pl__sum mono">{{ headSummary }}</span>
      <svg v-if="traceSteps.length" class="pl__chev" :class="{ 'is-open': !collapsed }" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 8 4 4 4-4"/></svg>
    </div>

    <div v-show="!collapsed" class="timeline">
      <div
        v-for="(step, i) in pipelineSteps"
        :key="step.key"
        class="tl-step"
        :class="`is-${statusOf(i)}`"
      >
        <div class="tl-step__rail">
          <span class="tl-step__dot">
            <svg v-if="statusOf(i) === 'completed'" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m4.5 10.4 3.6 3.6 7.4-8"/></svg>
            <span v-else-if="statusOf(i) === 'failed'">✗</span>
            <span v-else-if="statusOf(i) === 'skipped'">⤼</span>
            <span v-else>{{ i + 1 }}</span>
          </span>
          <span class="tl-step__line"></span>
        </div>
        <div class="tl-step__body">
          <div class="tl-step__hd">
            <span class="tl-step__t">{{ step.label }}</span>
            <!-- 深度思考状态徽标：进行中/完成常驻显示（面板折叠也不丢状态） -->
            <span
              v-if="step.key === 'generate_report' && genThinking"
              class="tl-thinkbadge"
              :class="{ 'is-live': reportThinking || thinkInReport }"
            >{{ (reportThinking || thinkInReport) ? '深度思考中' : '深度思考完成' }}</span>
            <span
              v-if="traceOf(step.key) && typeof traceOf(step.key).duration === 'number'"
              class="tl-step__dur"
            >{{ traceOf(step.key).duration }}s</span>
          </div>
          <div class="tl-step__d">{{ step.agent }}<template v-if="statusOf(i) === 'running'"><template v-if="step.key === 'generate_report' && reportThinking"> · <span class="tl-step__think">深度思考中</span></template><template v-else-if="step.key === 'approval'"> · 待审核</template><template v-else> · 执行中…</template></template><template v-else-if="statusOf(i) === 'pending'"> · 待触发</template><template v-else-if="statusOf(i) === 'skipped'"> · 已跳过</template><template v-else-if="statusOf(i) === 'failed'"> · 失败</template></div>

          <!-- 审计详情（后端步骤行对齐注入：summary + chips） -->
          <template v-if="traceOf(step.key)">
            <div v-if="traceOf(step.key).summary" class="tl-step__sum">{{ traceOf(step.key).summary }}</div>
            <div v-if="chipsOf(step.key).length" class="tl-step__chips">
              <span
                v-for="(c, ci) in chipsOf(step.key)"
                :key="ci"
                class="tl-chip"
                :class="c.cls"
                :title="c.tip || ''"
              >{{ c.text }}</span>
            </div>
            <!-- 需求 A/B：思考过程只在本节点展示（实时增量与落库回填同一面板、同一来源）；
                 本轮思考进行中且正文未产出时宿主在「分析报告」流式卡（thinkInReport），此处隐藏。
                 面板标题恒为「思考过程 · N 字」，「深度思考中/完成」状态由上方徽标承担 -->
            <div v-if="step.key === 'generate_report' && genThinking && !thinkInReport" class="tl-thinkhost">
              <AgentThinkPanel :text="genThinking" :note="genOutput.stream_note || ''" />
            </div>
          </template>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.pl {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* sec-t 同构 */
.pl__sec {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pl__sec::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--fs-hairline);
  transition: background var(--fs-dur-micro) var(--fs-ease);
}
.pl__t {
  position: relative;
  padding-left: 9px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
  transition: color var(--fs-dur-micro) var(--fs-ease);
}
/* 指挥台小节标题刻度（全系统统一语言） */
.pl__t::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 2px;
  height: 11px;
  margin-top: -5.5px;
  border-radius: 1px;
  background: var(--fs-accent);
  transform: scaleY(1);
  transition: background var(--fs-dur-micro) var(--fs-ease);
}
.pl__n {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
}
.pl__sp { flex: 1; }
/* 折叠交互：头部可点击 + 紧凑摘要 + 旋转箭头 */
.pl__sec.is-clickable { cursor: pointer; user-select: none; }
.pl__sec.is-clickable:hover .pl__t { color: var(--fs-ink-900); }
.pl__sec.is-clickable:hover .pl__t::before { background: var(--fs-ink-900); }
.pl__sec.is-clickable:hover::after { background: var(--fs-hairline-strong); }
.pl__sec.is-clickable:hover .pl__chev { color: var(--fs-ink-700); }
.pl__sum {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-500);
  font-variant-numeric: tabular-nums;
}
.pl__chev {
  width: 14px;
  height: 14px;
  color: var(--fs-ink-400);
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
.pl__chev.is-open { transform: rotate(180deg); }

/* v0 timeline：裸放在中列画布上（无卡片包裹），轨道竖线贯穿 */
.timeline {
  display: flex;
  flex-direction: column;
}
.tl-step {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 12px;
}
.tl-step__rail {
  position: relative;
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.tl-step__dot {
  position: relative;
  flex: none;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  transition: background var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.tl-step__dot svg { width: 11px; height: 11px; }
.tl-step__line {
  flex: 1;
  width: 1px;
  min-height: 26px;
  margin: 4px 0;
  background: var(--fs-hairline-strong);
  transform: scaleY(1);
  transform-origin: top center;
  transition: background var(--fs-dur-micro) var(--fs-ease);
}
.tl-step:last-child .tl-step__line { display: none; }

/* 状态着色（v0 三态：done=success 描边环 / run=accent 描边+扩散环 / wait=灰） */
.tl-step.is-completed .tl-step__dot {
  color: var(--fs-success);
  background: color-mix(in srgb, var(--fs-success) 8%, var(--fs-bg-surface));
  box-shadow: inset 0 0 0 1px var(--fs-success);
}
.tl-step.is-completed .tl-step__line { background: var(--fs-success); }
.tl-step.is-running .tl-step__dot {
  color: var(--fs-on-accent);
  background: var(--fs-accent);
  box-shadow: inset 0 0 0 1px var(--fs-accent), 0 0 0 3px var(--fs-accent-soft);
}
.tl-step.is-running .tl-step__t { color: var(--fs-accent); }
.tl-step.is-running .tl-step__line { background: var(--fs-accent); }
.tl-step.is-running .tl-step__dot::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 999px;
  box-shadow: inset 0 0 0 1px var(--fs-accent);
  animation: pl-spread 1.2s var(--fs-ease, ease) infinite;
}
.tl-step.is-running .tl-step__line { background: var(--fs-accent); }
.tl-step.is-failed .tl-step__dot {
  color: var(--fs-danger);
  box-shadow: inset 0 0 0 1px var(--fs-danger);
}
.tl-step.is-skipped .tl-step__dot {
  color: var(--fs-ink-400);
  background: var(--fs-bg-sunken);
  box-shadow: none;
}
/* v0 同款扩散环脉冲（scale 1 → 1.7 淡出） */
@keyframes pl-spread {
  0%   { transform: scale(1); opacity: 0.6; }
  70%  { transform: scale(1.7); opacity: 0; }
  100% { transform: scale(1.7); opacity: 0; }
}

/* 步骤内容 */
.tl-step__body {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
  padding-bottom: 20px;
}
.tl-step:last-child .tl-step__body { padding-bottom: 2px; }
/* 标题行：名称 + 右对齐耗时（控制台式对齐，耗时不再挤进 chips） */
.tl-step__hd {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.tl-step__dur {
  margin-left: auto;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
}
.tl-step__t {
  font-size: 13px;
  font-weight: 500;
  color: var(--fs-ink-900);
  line-height: 1.4;
}
.tl-step.is-pending .tl-step__t,
.tl-step.is-skipped .tl-step__t { color: var(--fs-ink-400); font-weight: 400; }
.tl-step__d {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--fs-ink-500);
}
/* 深度思考中（思考型模型 <think> 段推送中）：accent 呼吸强调 */
.tl-step__think {
  color: var(--fs-accent);
  animation: pl-pulse 1.6s ease-in-out infinite;
}
@keyframes pl-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

/* 审计详情（原执行过程卡内容，注入节点内） */
.tl-step__sum {
  margin-top: 5px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--fs-ink-700);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3; /* 摘要含具体描述（用户要求），3 行内完整可读 */
  line-clamp: 3;
  -webkit-box-orient: vertical;
}
/* 审计 chips（mono 胶囊，可换行不溢出） */
.tl-step__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.tl-chip {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  line-height: 1.6;
  padding: 0 7px;
  border-radius: 999px;
  white-space: nowrap;
  color: var(--fs-ink-500);
  background: var(--fs-bg-canvas);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
/* 带悬停解释的 chip 给出 help 光标语义 */
.tl-chip[title] { cursor: help; }
.tl-chip:hover { color: var(--fs-ink-700); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.tl-chip.llm:hover { color: var(--fs-accent); }
.tl-chip.ok:hover { color: var(--fs-success); }
.tl-chip.warn:hover { color: var(--fs-warning); }
.tl-chip.danger:hover { color: var(--fs-danger); }
.tl-chip.llm {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  box-shadow: none;
}
.tl-chip.ok {
  color: var(--fs-success);
  background: color-mix(in srgb, var(--fs-success) 10%, transparent);
  box-shadow: none;
}
.tl-chip.warn {
  color: var(--fs-warning);
  background: color-mix(in srgb, var(--fs-warning) 10%, transparent);
  box-shadow: none;
}
.tl-chip.danger {
  color: var(--fs-danger);
  background: color-mix(in srgb, var(--fs-danger) 10%, transparent);
  box-shadow: none;
}

/* 思考面板宿主位（需求 A/B）：面板本体是共用组件 AgentThinkPanel，此处只留节点内间距 */
.tl-thinkhost { margin-top: 7px; }
/* 深度思考状态徽标：live=accent 脉动（思考中）；完成=muted 灰（常驻，折叠也不丢） */
.tl-thinkbadge {
  height: 18px;
  padding: 0 7px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-size: 10px;
  white-space: nowrap;
}
.tl-thinkbadge.is-live {
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  animation: tl-think-pulse 1.6s ease-in-out infinite;
}
@keyframes tl-think-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
/* ==================== V7 入场微动效（挂载即播一次，不干扰真实状态色） ====================
   流水线节点按顺序点亮（60ms 错峰，仅前 7 个）；状态类仍由业务驱动 */
.pl .tl-step { animation: node-in 0.38s var(--fs-ease-out) both; }
.pl .tl-step:nth-of-type(1) { animation-delay: 0s; }
.pl .tl-step:nth-of-type(2) { animation-delay: 0.06s; }
.pl .tl-step:nth-of-type(3) { animation-delay: 0.12s; }
.pl .tl-step:nth-of-type(4) { animation-delay: 0.18s; }
.pl .tl-step:nth-of-type(5) { animation-delay: 0.24s; }
.pl .tl-step:nth-of-type(6) { animation-delay: 0.3s; }
.pl .tl-step:nth-of-type(7) { animation-delay: 0.36s; }
@keyframes node-in {
  from { opacity: 0; transform: translateX(-6px); }
  to { opacity: 1; transform: none; }
}
/* 轨道竖线随节点错峰自上而下贯通（终态=常态，静态时可读） */
.pl .tl-step__line { animation: node-rail-in 0.42s var(--fs-ease-out) both; }
.pl .tl-step:nth-of-type(1) .tl-step__line { animation-delay: 0.1s; }
.pl .tl-step:nth-of-type(2) .tl-step__line { animation-delay: 0.16s; }
.pl .tl-step:nth-of-type(3) .tl-step__line { animation-delay: 0.22s; }
.pl .tl-step:nth-of-type(4) .tl-step__line { animation-delay: 0.28s; }
.pl .tl-step:nth-of-type(5) .tl-step__line { animation-delay: 0.34s; }
.pl .tl-step:nth-of-type(6) .tl-step__line { animation-delay: 0.4s; }
.pl .tl-step:nth-of-type(7) .tl-step__line { animation-delay: 0.46s; }
@keyframes node-rail-in {
  from { transform: scaleY(0); }
  to { transform: scaleY(1); }
}
/* 完成节点的对勾一次轻弹（终态=常态） */
.tl-step.is-completed .tl-step__dot svg { animation: dot-pop 0.3s var(--fs-ease-out) both; }
@keyframes dot-pop {
  0% { transform: scale(0.6); opacity: 0; }
  60% { transform: scale(1.12); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .pl .tl-step,
  html:not([data-motion="on"]) .pl .tl-step__line,
  html:not([data-motion="on"]) .tl-step.is-completed .tl-step__dot svg,
  html:not([data-motion="on"]) .tl-step.is-running .tl-step__dot::after,
  html:not([data-motion="on"]) .tl-step__think,
  html:not([data-motion="on"]) .tl-thinkbadge.is-live { animation: none; }
}
/* 手动关闭动效时三态一致：扩散环/呼吸/入场全静止，节点仍靠颜色表达状态 */
html[data-motion-allowed="false"] .pl .tl-step,
html[data-motion-allowed="false"] .pl .tl-step__line,
html[data-motion-allowed="false"] .tl-step.is-completed .tl-step__dot svg,
html[data-motion-allowed="false"] .tl-step.is-running .tl-step__dot::after,
html[data-motion-allowed="false"] .tl-step__think,
html[data-motion-allowed="false"] .tl-thinkbadge.is-live { animation: none; }
</style>
