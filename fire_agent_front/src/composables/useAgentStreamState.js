/**
 * Agent 协作中心 · 流式生成状态（模块级单例）
 *
 * 与知识库 useKbQa 同思路：报告生成有时耗时数分钟，切到其他页面再返回不能丢
 * 已累计的思考/正文缓冲（此前是组件内 ref，路由卸载即销毁——用户反馈修复）。
 * 任务 ID 本身有 localStorage 持久化，返回页面重新订阅 SSE 后，本状态无缝续显；
 * report_think / report_delta 的易失通道不重放，缓冲以本地留存为准继续追加。
 *
 * 思考按「任务」累积全部轮次（评审退回重写 / 用户驳回重写 / 取消后再次生成）：
 * - streamThinkRounds 为事实源（[{round, text}]），同轮追加、异轮追加；
 * - streamThink 为展示缓存（composeThinkRounds 拼接，第 2 轮起带轻量小标题）；
 * - 终态/审批回填时与落库轮次合并，取更长且前后缀对齐，避免同一段出现两遍。
 */
import { ref } from 'vue'
import { composeThinkRounds, mergeThinkRounds } from '@/utils/thinkText'

// 模块作用域：跨组件卸载存活
const streamReport = ref('')   // 报告增量累积缓冲
const streamRun = ref(0)       // 生成轮次（评审退回/驳回重写递增）
const streamActive = ref(false) // 流式生成中（generate_report 节点开始即点亮）
const streamThink = ref('')    // 思考过程展示文本（全部轮次累积）
const streamThinkRounds = ref([]) // 思考轮次事实源：[{ round, text, note? }]
// 缓冲归属的任务 id（模块级，跨路由卸载存活）：切页再回来时据此认出缓冲仍属于同一任务，
// 只有真的换任务才清。此前 loadHistoryTask 无条件清空 → 回来时开头一大段正文没了。
const streamTaskId = ref('')
// 本轮正文是否已开始产出：false 时思考宿主在「分析报告」区（思考+草稿同显）；
// 首个正文 delta 置 true（思考迁回第 5 节点）；新一轮思考（think_reset/新 run）复位。
// 用它替代「!streamReport」判断：第二轮开始时保留旧草稿不清空，也能正确表示"本轮正文未开始"
const bodyStarted = ref(false)

// ====== 思考面板展开态（模块级共享：报告区 ↔ 第 5 节点两处宿主互斥迁移时延续用户折叠选择） ======
const thinkPanelOpen = ref(false)  // 面板展开（默认收起，首个思考增量自动展开）
let thinkPanelTouched = false      // 用户手动折叠/展开过：之后不再自动展开

/** 用户点击标题行：标记手动操作并切换展开态 */
export function toggleThinkPanel() {
  thinkPanelTouched = true
  thinkPanelOpen.value = !thinkPanelOpen.value
}

/** 首个思考增量到达时自动展开（用户手动操作过则不再自动打开） */
export function autoOpenThinkPanel() {
  if (!thinkPanelTouched && !thinkPanelOpen.value) thinkPanelOpen.value = true
}

/** 新任务开始：清空本任务的思考轮次（轮次切换/终态回填不再清空） */
export function resetThinkState() {
  streamThinkRounds.value = []
  streamThink.value = ''
  bodyStarted.value = false
  thinkPanelOpen.value = false
  thinkPanelTouched = false
}

/**
 * 把流式缓冲绑定到某个任务；任务真的变化时才清空正文/轮次缓冲。
 * @returns {boolean} true=换了任务（已清空），false=同一任务（缓冲原样保留，续显）
 */
export function bindStreamTask(taskId) {
  const id = String(taskId ?? '')
  if (streamTaskId.value === id) return false
  streamTaskId.value = id
  streamReport.value = ''
  streamRun.value = 0
  streamActive.value = false
  resetThinkState()
  return true
}

/** 当前缓冲归属的任务（订阅/兜底路径判断是否同一任务用） */
export function currentStreamTask() {
  return streamTaskId.value
}

/** 本轮正文开始产出（首个 report_delta flush 时由 useTaskStream 调用） */
export function markBodyStarted() {
  bodyStarted.value = true
}

/** 本轮正文复位（新一轮思考开始：think_reset / 新 run 的思考首帧） */
export function resetBodyStarted() {
  bodyStarted.value = false
}

/**
 * 复读截断：以服务端截断版替换指定轮的实时思考（丢弃重复尾巴）。
 * 只接受更短的版本（防回填更长旧文本）；替换后重新展开面板让截断可见。
 */
export function truncateLiveThink(roundNo, text) {
  const rounds = streamThinkRounds.value
  const idx = rounds.findIndex(r => r.round === roundNo)
  const kept = String(text || '')
  if (idx < 0 || !kept || kept.length >= rounds[idx].text.length) return
  rounds[idx] = { ...rounds[idx], text: kept }
  streamThinkRounds.value = [...rounds]
  streamThink.value = composeThinkRounds(rounds)
  thinkPanelTouched = false
  autoOpenThinkPanel()
}

/**
 * 追加实时思考增量（report_think 帧）
 * @param {number} run 后端轮次号
 * @param {string} text 增量文本
 */
export function appendThinkChunk(run, text) {
  const chunk = String(text || '')
  if (!chunk) return
  const rounds = streamThinkRounds.value
  const wanted = Number(run)
  const roundNo = Number.isFinite(wanted) && wanted > 0
    ? wanted
    : (rounds.length ? rounds[rounds.length - 1].round : 1)
  const idx = rounds.findIndex(r => r.round === roundNo)
  if (idx >= 0) {
    // 同轮追加：直接拼接（流式 chunk 不重放，避免每帧全量重组）
    rounds[idx] = { ...rounds[idx], text: rounds[idx].text + chunk }
    if (idx === rounds.length - 1) streamThink.value += chunk
    else streamThink.value = composeThinkRounds(rounds)
    return
  }
  // 新轮次：紧接在第一段末尾，不覆盖、不清空。
  // 新一轮思考（评审退回/驳回重写）是新的推理会话：重置用户此前的手动折叠，
  // 让面板自动展开——否则"内容在涨但界面收着"，用户会误以为卡死；
  // 同时复位"正文已开始"标记：本轮正文未产出，思考宿主回「分析报告」区
  rounds.push({ round: roundNo, text: chunk })
  thinkPanelTouched = false
  autoOpenThinkPanel()
  bodyStarted.value = false
  streamThink.value = composeThinkRounds(rounds)
}

/**
 * 合并落库轮次（终态 / 审批 / 断线兜底回填）
 * 只在合并结果不短于当前展示时替换，避免回填造成闪断或回退。
 * @param {Array} rounds thinking_rounds 或 [{round,text}] / ["文本"]
 */
export function mergePersistedRounds(rounds) {
  const incoming = Array.isArray(rounds) ? rounds : []
  if (!incoming.length) return
  const merged = mergeThinkRounds(streamThinkRounds.value, incoming)
  const next = composeThinkRounds(merged)
  if (next.length >= streamThink.value.length) {
    streamThinkRounds.value = merged
    streamThink.value = next
  }
}

/**
 * 从任务步骤行回填思考（兼容旧字段 thinking / 新字段 thinking_rounds）
 * @param {Array} steps 后端 task detail 的 steps
 */
export function mergePersistedThinking(steps) {
  const gen = (steps || []).find(s => s && s.step === 'generate_report')
  const out = gen && gen.output
  if (!out) return
  if (Array.isArray(out.thinking_rounds) && out.thinking_rounds.length) {
    mergePersistedRounds(out.thinking_rounds)
    return
  }
  const old = out.thinking
  if (typeof old === 'string' && old.trim()) {
    // 旧字段只有最后一轮：并入当前最后一轮，保留此前轮次
    const rounds = streamThinkRounds.value
    const roundNo = rounds.length ? rounds[rounds.length - 1].round : 1
    mergePersistedRounds([{ round: roundNo, text: old }])
  }
}

export function useAgentStreamState() {
  return {
    streamReport,
    streamRun,
    streamActive,
    streamThink,
    streamThinkRounds,
    bodyStarted,
    thinkPanelOpen,
    resetThinkState,
  }
}
