<script setup>
/**
 * Agent 协作中心 — 任务执行 + 链路可视化 + 报告展示
 *
 * 后端 API: POST /api/v1/agent/tasks  (body: { query: string })
 *          GET  /api/v1/agent/status
 *          GET  /api/v1/agent/tasks/{id}/stream?token=<JWT>  (SSE)
 *
 * 视觉 V6：按 docs/design/visual-v0.html §agent 屏全面重做展示层——
 *   - 页头改 v0 page-head（64px 单行：标题 + 副题 + Agent 就绪徽标 + 运行状态 + 语音/刷新）
 *   - 三列通栏布局（v0 agent-body：左 340 任务输入+历史 / 中 流水线+报告 / 右 380 元信息+审批+能力）
 *   - 右列顶部新增「任务元信息」meta-list（任务 ID / 状态 / 模型 / 步骤数）
 *   - 空态改 v0 empty（虚线发丝框）
 * 业务流程（任务创建 / SSE 订阅 / HITL 审批 / 历史双源同步）零改动。
 */
import BackHomeButton from '@/components/base/BackHomeButton.vue'
import { ref, shallowRef, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { fetchStatus, createTask, fetchTaskDetail, fetchTasks, deleteTask, resumeTask, cancelTask, retryTask } from '@/api/agent'
import { fetchDetail as fetchReportDetail } from '@/api/report'
import { providerName } from '@/utils/llmProviders'
import { useAgentStreamState, mergePersistedThinking, bindStreamTask } from '@/composables/useAgentStreamState'
import { useTaskStream, toTaskResult } from '@/composables/useTaskStream'
import { speakState, recordState, startRecord, cleanupSpeech } from '@/utils/speech'
import SystemCapabilities from '@/components/SystemCapabilities.vue'
import TaskFormCard from './TaskFormCard.vue'
import TaskHistoryList from './TaskHistoryList.vue'
import AgentPipeline from './AgentPipeline.vue'
import AgentStreamView from './AgentStreamView.vue'
import AgentReportView from './AgentReportView.vue'
import ApprovalPanel from './ApprovalPanel.vue'
import TaskProcessDrawer from './TaskProcessDrawer.vue'

const auth = useAuthStore()

// 语音输入任务：识别完成自动执行
const handleMicClick = () => {
  if (recordState.recording) {
    startRecord() // 录音中再次调用 = 停止并识别
    return
  }
  startRecord((text) => {
    query.value = text
    handleExecute()
  })
}

// ====== 任务状态 ======
const query = ref('')
const running = ref(false)
// shallowRef：taskResult 整树（steps 含全部步骤行 output/thinking_rounds，数十 KB）
// 不需要深层响应式——所有写路径都是整体替换，避免 Vue 对大对象逐层代理/深度依赖收集
const taskResult = shallowRef(null)
const agentStatus = ref(null)
const activeStep = ref(-1)

// ====== HITL 审批状态（P1） ======
const currentTaskId = ref(null)
const approving = ref(false)
const cancelling = ref(false)            // 终止进行中：防重复提交/重复弹窗
const approvalMode = ref('approve')       // approve | edit | reject
const approvalEditContent = ref('')       // edit 模式的编辑内容
const approvalComment = ref('')           // reject 模式的驳回意见
// 审批决策已提交（approve/edit）：锁覆盖到终态确认；期间吞掉重复点击与
// 迟到/重放的 approval SSE 事件（不再把界面切回"等待审批"、不再重复弹提示）
const approvalHandled = ref(false)

// 审批相关派生态：草稿/评审意见来自后端 approval 步骤行（output.draft_report）
const approvalStep = computed(() => (taskResult.value?.steps || []).find(s => s.step === 'approval'))
// 已定稿：审批行 completed 且决策为通过/编辑通过（驳回重写中间态不算）
const approvalFinalized = computed(() => {
  const st = approvalStep.value
  const action = st?.output?.action
  return !!st && st.status === 'completed' && (action === 'approve' || action === 'edit')
})
// 审批卡可见（三来源任一即可，不依赖单一状态字段/单一事件）：
// 任务 awaiting_approval / approval 行 awaiting（详情轮询兜底来源）/ 已定稿只读态
const showApproval = computed(() =>
  !!approvalStep.value && (
    taskResult.value?.status === 'awaiting_approval' ||
    approvalStep.value.status === 'awaiting' ||
    approvalFinalized.value))
// 闸口已触发、等待人工决策：步骤行 status=awaiting 是唯一事实源（防止"待闸口触发"时误提交）
const gateReady = computed(() =>
  taskResult.value?.status === 'awaiting_approval' && approvalStep.value?.status === 'awaiting')
const draftReport = computed(() => approvalStep.value?.output?.draft_report || '')
const approvalReview = computed(() => approvalStep.value?.output?.review || {})

// ====== 审批闸口详情轮询兜底（不依赖 SSE approval 事件） ======
// 质量评审完成且任务仍在运行 → 每 2s 轻量拉详情（最多 10 次）：一旦出现 approval 行
// awaiting 或任务 awaiting_approval 立即渲染审批卡（SSE 事件丢失/延迟时不再干等）。
// SSE approval 事件到达 / 任务终态 / 切任务 / 组件卸载时停止。
let gatePollTimer = null
const stopGatePoll = () => {
  if (gatePollTimer) { clearInterval(gatePollTimer); gatePollTimer = null }
}
const startGatePoll = () => {
  if (gatePollTimer || !currentTaskId.value) return
  let tries = 0
  gatePollTimer = setInterval(async () => {
    tries += 1
    const tid = currentTaskId.value
    if (tries > 10 || !tid || !running.value) { stopGatePoll(); return }
    try {
      const d = await fetchTaskDetail(tid)
      if (d.code !== 200 || !d.data || currentTaskId.value !== tid) return
      const data = d.data
      const gateHit = data.status === 'awaiting_approval' ||
        (data.steps || []).some(s => s && s.step === 'approval' && s.status === 'awaiting')
      if (gateHit) {
        stopGatePoll()
        taskResult.value = toTaskResult(data) // 草稿/评审意见随详情注入，卡片立即可用
        mergePersistedThinking(data.steps)
        if (!approvalEditContent.value) approvalEditContent.value = draftReport.value
        ElMessage.warning('报告已生成，等待人工审批')
      } else if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        stopGatePoll()
      }
    } catch { /* 静默：下一轮重试 */ }
  }, 2000)
}
// 触发/停止的 watch 挂在下方 stepStatusMap 定义之后（watch 注册时同步执行一次
// getter，引用其后才声明的变量会 TDZ ReferenceError 导致 setup 崩溃、整页白屏）
// 待审批草稿全文直接放进中列「分析报告」区域（右列只留审批操作），不再挤在右下角小框
const approvalPreviewResult = computed(() => ({
  status: 'awaiting_approval',
  steps: taskResult.value?.steps || [],
  report: draftReport.value,
  llm_used: true,
}))

// ====== 报告流式渲染（SSE report_delta 打字机）======
// 通道易失：断线不重放历史 delta，终态完整内容以 DB 为准（report 事件兜底）
// 流式生成状态在 useAgentStreamState 模块单例：切页/返回不丢已累计的思考与正文缓冲
const { streamReport, streamRun, streamActive, streamThink, streamThinkRounds, bodyStarted, resetThinkState } = useAgentStreamState()
const showStreamReport = computed(() => streamActive.value)
// 流水线 generate_report 行的「深度思考中」指示：本轮思考进行中且正文尚未产出
// （用 bodyStarted 判断而非 !streamReport：第二轮开始时保留旧草稿，也能正确切思考宿主）
const reportThinking = computed(() => streamActive.value && !!streamThink.value && !bodyStarted.value)
// 两段式宿主切换：本轮思考进行中（正文未开始）时思考宿主在「分析报告」流式卡，
// 且与草稿区同显（思考在上、草稿在下）；正文首个 delta 后迁回第 5 节点面板
const thinkInReport = computed(() => streamActive.value && !!streamThink.value && !bodyStarted.value)
// 草稿就绪：generate_report 步骤已完成（含评审进行中）→ 报告区从打字机切换为渲染好的草稿
const draftReady = computed(() =>
  (taskResult.value?.steps || []).some(s => s && s.step === 'generate_report' && s.status === 'completed'))

// ====== 步骤状态映射（key → status，驱动流水线 skipped/failed 展示） ======
const stepStatusMap = computed(() => {
  const m = {}
  for (const st of (taskResult.value?.steps || [])) {
    if (st && st.step) m[st.step] = st.status || 'completed'
  }
  return m
})

// ====== 审批闸口轮询的触发/停止（须在 stepStatusMap 定义之后：watch 注册时同步执行
// 一次 getter，提前引用会 TDZ ReferenceError 导致 setup 崩溃、整页白屏） ======
// 评审完成 + 任务运行中 + 卡片未显示 → 启动；卡片出现或任务落定 → 停止
watch(() => [
  stepStatusMap.value.review_report,
  taskResult.value?.status,
  showApproval.value,
], ([rev, st, shown]) => {
  if (shown) { stopGatePoll(); return }
  if (rev === 'completed' && (st === 'running' || st === 'pending')) startGatePoll()
  if (st === 'completed' || st === 'failed' || st === 'cancelled' || st === 'awaiting_approval') stopGatePoll()
})
watch(running, (r) => { if (!r) stopGatePoll() })

// ====== 任务运行期详情轮询兜底（SSE 丢事件/断连时从 DB 恢复步骤与状态） ======
// running 期间每 4s 轻量拉详情：步骤指纹变化才替换（避免无效重渲染）；
// 终态 → 以 DB 为准收尾（停 SSE/轮询、入历史）；awaiting → 出审批卡。
// SSE 正常时指纹一致自然跳过，双通道幂等。
let runningPollTimer = null
const RUNNING_POLL_MS = 4000
const stopRunningPoll = () => {
  if (runningPollTimer) { clearInterval(runningPollTimer); runningPollTimer = null }
}
const stepsFingerprint = (steps, status) => {
  const list = steps || []
  const last = list[list.length - 1] || {}
  return `${status}:${list.length}:${last.step || ''}:${last.status || ''}`
}
const startRunningPoll = () => {
  if (runningPollTimer || !currentTaskId.value) return
  runningPollTimer = setInterval(async () => {
    const tid = currentTaskId.value
    if (!tid || !running.value) { stopRunningPoll(); return }
    try {
      const d = await fetchTaskDetail(tid)
      if (d.code !== 200 || !d.data || currentTaskId.value !== tid) return
      const data = d.data
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        // 终态：DB 唯一事实源，收尾（finishRun 关 SSE 防重复终态事件）
        stopRunningPoll()
        taskResult.value = toTaskResult(data)
        mergePersistedThinking(data.steps)
        streamActive.value = false
        running.value = false
        finishRun()
        if (data.report) pushHistoryItem({ ...data, id: tid }, query.value.trim())
        return
      }
      if (data.status === 'awaiting_approval') {
        // 闸口已触发而 SSE approval 未送达：出审批卡（showApproval 三来源判定生效）
        taskResult.value = toTaskResult(data)
        mergePersistedThinking(data.steps)
        if (!approvalEditContent.value) approvalEditContent.value = draftReport.value
        running.value = false
        stopRunningPoll()
        finishRun()
        return
      }
      // 运行中：步骤指纹变化才替换，并按 DB 步骤推流水线游标
      const cur = taskResult.value
      if (!cur || stepsFingerprint(cur.steps, cur.status) !== stepsFingerprint(data.steps, data.status)) {
        taskResult.value = toTaskResult(data)
        mergePersistedThinking(data.steps)
        activeStep.value = Math.max(activeStep.value, deriveActiveStep(data.steps))
      }
    } catch { /* 静默：下一轮重试 */ }
  }, RUNNING_POLL_MS)
}
watch(running, (r) => { if (r) startRunningPoll(); else stopRunningPoll() })

// ====== 任务进程抽屉（页头入口常驻，运行中显示活跃数徽标） ======
const taskPanelOpen = ref(false)
const taskDrawerRef = ref(null)

// ====== 任务历史 ======
const taskHistory = ref([])

// 任务历史持久化（localStorage，按用户隔离，避免多账号同浏览器串数据）
const HISTORY_KEY = () => `agent_task_history_${(auth.user && auth.user.username) || 'guest'}`
// 同一问题只保留最新一条：重跑/驳回重写不堆积历史（后端仍保留全部任务，报告中心按次各成新报告）
const dedupeHistory = (list) => {
  const seen = new Set()
  return (list || []).filter(t => {
    const key = ((t && t.query) || '').trim()
    if (!key) return true
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
const loadHistory = () => {
  try {
    taskHistory.value = dedupeHistory(JSON.parse(localStorage.getItem(HISTORY_KEY()) || '[]'))
  } catch {
    taskHistory.value = []
  }
}
const saveHistory = () => {
  try {
    localStorage.setItem(HISTORY_KEY(), JSON.stringify(taskHistory.value.slice(0, 50)))
  } catch {
    /* 忽略 */
  }
}
loadHistory()

// ====== 当前任务持久化（localStorage，按用户隔离）======
// 切页/刷新回到 Agent 中心时优先恢复"上次看的那个任务"，而不是清空重来
const CURRENT_TASK_KEY = () => `agent_current_task_${(auth.user && auth.user.username) || 'guest'}`
const readCurrentTask = () => {
  try {
    return JSON.parse(localStorage.getItem(CURRENT_TASK_KEY()) || 'null')
  } catch {
    return null
  }
}
const saveCurrentTask = (id, q) => {
  if (!id) return
  try {
    localStorage.setItem(CURRENT_TASK_KEY(), JSON.stringify({ id, query: q || '' }))
  } catch {
    /* 忽略 */
  }
}
const clearCurrentTask = () => {
  try {
    localStorage.removeItem(CURRENT_TASK_KEY())
  } catch {
    /* 忽略 */
  }
}

// ====== 7 步流水线定义（P1：+质量评审 + 人工审核；skipped/failed 由后端步骤状态驱动） ======
// 第 7 步为 HITL 审批闸口（approval 步骤行）：等待审批时显示「待审核」，定稿后显示已完成
const pipelineSteps = [
  { key: 'parse_task', label: '拆解任务', agent: 'Orchestrator', icon: '→' },
  { key: 'query_data', label: '查询数据', agent: 'DataAgent', icon: '→' },
  { key: 'analyze_gis', label: '分析 GIS', agent: 'GisAgent', icon: '→' },
  { key: 'retrieve_knowledge', label: '检索知识', agent: 'RagAgent', icon: '→' },
  { key: 'generate_report', label: '生成报告', agent: 'ReportAgent', icon: '→' },
  { key: 'review_report', label: '质量评审', agent: 'Reviewer', icon: '→' },
  { key: 'approval', label: '人工审核通过', agent: 'HITL', icon: '→' },
]

// 是否展示第 7 步审批节点：有 approval 步骤行，或任务仍在进行（新任务 HITL 口径）时展示；
// 无审批行且已结束的旧任务（HITL 上线前/未开启审批）隐藏，保持 6 步观感
const showApprovalStep = computed(() => {
  const steps = taskResult.value?.steps || []
  if (steps.some(s => s && s.step === 'approval')) return true
  const st = taskResult.value?.status
  return st === 'running' || st === 'pending' || st === 'awaiting_approval'
})
const pipelineStepsView = computed(() =>
  showApprovalStep.value ? pipelineSteps : pipelineSteps.slice(0, 6))

// ====== 示例任务 ======
const exampleTasks = [
  '分析2026年4月云南高风险区域，给出重点巡防建议并输出报告',
  '查询普洱市2025年历史火点情况',
  '2026年春季哪些州市风险最高？',
  '近3年高置信度火点最多的5个州市是哪些？',
]

// ====== 获取步骤状态（pending→running→completed 三态；skipped/failed 由后端步骤真实状态驱动） ======
// parse_task 计划是否包含知识检索：计划不含时该节点根本不会执行，必须显示"已跳过"，
// 否则运行中前端会按线性 6 步把它误显示成"检索知识执行中"（实际是报告在生成）
const planHasRetrieve = computed(() => {
  const parse = (taskResult.value?.steps || []).find(s => s.step === 'parse_task')
  const plan = parse?.output?.plan
  if (!Array.isArray(plan) || !plan.length) return null // 计划未知 → 不做 skipped 推断
  return plan.some(p => p && p.task_type === 'retrieve_knowledge')
})

const getStepStatus = (index) => {
  const key = pipelineSteps[index] && pipelineSteps[index].key
  const st = stepStatusMap.value[key]
  if (st) {
    if (st === 'skipped') return 'skipped'
    if (st === 'failed') return 'failed'
    if (st === 'running' || st === 'awaiting') return 'running'
    return 'completed'
  }
  if (key === 'retrieve_knowledge' && planHasRetrieve.value === false) return 'skipped'
  if (running.value) {
    if (index < activeStep.value) return 'completed'
    if (index === activeStep.value) return 'running'
  }
  return 'pending'
}

// 交给 AgentPipeline 的一次性预计算结果（等价于原模板逐项调用 getStepStatus）
// 注意与 pipelineStepsView 对齐：旧任务隐藏第 7 步时状态数组同长，不错位
const stepStatuses = computed(() => pipelineStepsView.value.map((_, i) => getStepStatus(i)))

// ====== 任务元信息「步骤 x/y」口径 ======
// 分母：有审批步骤行或任务仍在进行 → 7（含人工审核）；已结束的旧任务按实际行数/6 口径
const stepTotal = computed(() => {
  const steps = taskResult.value?.steps || []
  if (steps.some(s => s && s.step === 'approval')) return 7
  const st = taskResult.value?.status
  if (st === 'running' || st === 'pending' || st === 'awaiting_approval') return 7
  return Math.max(steps.length, 6)
})
// 分子：已完成/失败/跳过的行数；running 预写行与 awaiting 审批行不计入
const stepDone = computed(() =>
  (taskResult.value?.steps || []).filter(s => {
    const st = s?.status || 'completed'
    return st !== 'running' && st !== 'awaiting'
  }).length)

// 从后端步骤行推算流水线游标（刷新/重新进入页面时恢复"走到哪"）
const deriveActiveStep = (steps) => {
  let cur = -1
  for (const st of (steps || [])) {
    const idx = pipelineSteps.findIndex(p => p.key === st.step)
    if (idx < 0) continue
    const status = st.status || 'completed'
    cur = Math.max(cur, (status === 'running' || status === 'awaiting') ? idx : idx + 1)
  }
  return cur
}

// ====== 获取 Agent 状态 ======
const fetchAgentStatus = async () => {
  try {
    const json = await fetchStatus()
    if (json.code === 200) {
      agentStatus.value = json.data
    }
  } catch {
    // 静默
  }
}

// ====== 执行任务（SSE 真实进度） ======
// 历史入列（SSE report 事件与断线兜底共用；流式增量不写入历史）
const pushHistoryItem = (d, q) => {
  const itemId = d.id || Date.now()
  const key = (q || '').trim()
  taskHistory.value = [
    {
      id: itemId,
      reportId: d.report_id || null,
      query: q,
      status: d.status,
      llm_used: !!d.llm_used,
      llm_provider: d.llm_provider || null,
      llm_model: d.llm_model || null,
      time: d.created_at || new Date().toLocaleString(),
      result: {
        status: d.status,
        steps: d.steps || [],
        report: d.report || '',
        llm_used: !!d.llm_used,
        llm_provider: d.llm_provider || null,
        llm_model: d.llm_model || null,
        // 元信息（已用时/Token）随缓存落盘：历史回看不等接口即可展示
        llm_tokens: d.llm_tokens ?? null,
        total_tokens: typeof d.total_tokens === 'number' ? d.total_tokens : null,
        elapsed_seconds: typeof d.elapsed_seconds === 'number' ? d.elapsed_seconds : null,
        started_at: d.started_at || null,
        finished_at: d.finished_at || null,
      },
    },
    // 同一任务（驳回重写后再次落定）或同一问题只保留最新一条，避免历史堆积
    ...taskHistory.value.filter(t => t.id !== itemId && (t.query || '').trim() !== key),
  ]
  saveHistory()
}

const handleExecute = async () => {
  const q = query.value.trim()
  if (!q) {
    ElMessage.warning('请输入分析任务')
    return
  }

  pendingStartedAt.value = 0 // 新执行从当前时刻计时，不继承上次恢复的开始时间
  running.value = true
  taskResult.value = null
  activeStep.value = -1
  approvalMode.value = 'approve'
  approvalComment.value = ''
  streamReport.value = ''
  resetThinkState() // 新任务：清空本任务全部思考轮次
  approvalHandled.value = false // 新任务：重置审批锁/事件去重标记
  streamRun.value = 0
  streamActive.value = false

  try {
    // 1) 创建任务：后端立即返回 task_id，LangGraph 工作流在后台执行
    const json = await createTask(q)
    if (json.code !== 200 || !json.data || !json.data.task_id) {
      ElMessage.error('创建任务失败: ' + (json.message || '未知错误'))
      finishRun()
      return
    }
    const taskId = json.data.task_id
    currentTaskId.value = taskId
    saveCurrentTask(taskId, q) // 记住当前任务：切页/刷新后回来仍是这个任务，而不是"重新开始"
    fetchAgentStatus()

    // 2) SSE 订阅真实节点进度（fetch + Authorization 头，token 不进 URL）
    subscribeSse(taskId, q)
  } catch (e) {
    ElMessage.error('网络错误: ' + e.message)
    finishRun()
  }
}

// ====== HITL 审批提交（approve / edit / reject） ======
// 一次点击直接提交，无二次确认弹窗。幂等与防假成功设计：
// - 闸口未触发（gateReady=false）直接拦截，不发请求；
// - 后端 409 + detail.code（approval_not_ready / already_resumed / approval_busy /
//   task_finished）时按语义提示，不弹成功 toast；
// - approving 锁不在接口返回时释放，而覆盖到终态确认（或 SSE 终态/异常事件），
//   期间重复点击被吞掉，不产生第二次 resume / 第二条 toast；
// - approve/edit 成功后立即回读详情：已定稿则直接切报告视图，未跑完则订阅 SSE 兜底；
//   迟到/重放的 approval 事件由 approvalHandled 标记吞掉（见 useTaskStream）。
const handleResume = async (action) => {
  if (!currentTaskId.value || approving.value) return // 幂等锁：提交中/已提交忽略重复点击
  if (!gateReady.value) {
    ElMessage.warning('审批闸口尚未就绪，请等待「人工审核」节点进入待审核状态')
    return
  }
  if (action === 'edit' && !approvalEditContent.value.trim()) {
    ElMessage.warning('请输入修改后的报告内容')
    return
  }
  if (action === 'reject' && !approvalComment.value.trim()) {
    ElMessage.warning('请填写驳回意见')
    return
  }
  approving.value = true
  const taskId = currentTaskId.value
  const release = () => { approving.value = false }
  try {
    const json = await resumeTask(taskId, action, {
      content: approvalEditContent.value,
      comment: approvalComment.value,
    })
    if (json.code !== 200) {
      // FastAPI HTTPException(409, detail={code,message}) → json.detail 为对象
      const detail = json.detail
      const errCode = (detail && typeof detail === 'object') ? detail.code : ''
      const errMsg = (detail && typeof detail === 'object' ? detail.message : detail) || json.message || '提交审批失败'
      if (json.code === 409 || errCode) ElMessage.warning(errMsg)
      else ElMessage.error(errMsg)
      release()
      return
    }
    ElMessage.success(action === 'reject' ? '已驳回，报告将按意见重写'
      : (action === 'edit' ? '已以编辑稿定稿' : '已通过并定稿'))
    approvalComment.value = ''
    // 继续沿用原开始时间：审批等待不计入"重开"，已用时从任务首次执行起算
    pendingStartedAt.value = startedAt.value || Date.now()
    running.value = true
    streamActive.value = false  // 续订后由新轮次的 report_delta 重新点亮

    if (action === 'reject') {
      // 驳回进入新一轮重写：审批锁释放（下一次闸口触发还要再审），
      // approvalHandled 复位以接收新一轮 approval 事件；思考不清空，新轮追加（需求 3）
      approvalHandled.value = false
      activeStep.value = pipelineSteps.length - 1
      subscribeSse(taskId, query.value.trim())
      release()
      return
    }

    // approve / edit：标记决策已提交（迟到/重放的 approval 事件不再切回界面）。
    // 回读轮询确认后端真正推进：resume 200 只代表受理，必须等到任务 completed
    // （或明确回到 awaiting=未生效）才算定稿，防止"假成功"（第三次反馈根因的兜底面）
    approvalHandled.value = true
    activeStep.value = pipelineSteps.length
    for (let attempt = 0; attempt < 9; attempt++) {
      if (attempt) await new Promise(r => setTimeout(r, 2000))
      let data = null
      try {
        const d = await fetchTaskDetail(taskId)
        data = d.code === 200 ? d.data : null
      } catch { continue }
      if (!data) continue
      // 统一装配（含 elapsed_seconds / total_tokens 元信息），报告缺失时先用草稿兜底展示
      taskResult.value = { ...toTaskResult(data), report: data.report || draftReport.value }
      mergePersistedThinking(data.steps) // 审批轮思考并入第 5 节点面板
      if (data.status === 'completed' || data.status === 'failed') {
        // 后端已真正定稿：直接展示报告，不再订阅 SSE（避免终态事件重复提示）
        running.value = false
        if (data.report) pushHistoryItem({ ...data, id: taskId }, query.value.trim())
        release()
        return
      }
      if (data.status === 'awaiting_approval') {
        // 审批未生效：图没有被真正恢复（后端拒绝/异常），明确报错并允许重试
        approvalHandled.value = false
        running.value = false
        ElMessage.error('审批未生效：任务仍处于待审批状态，请重试；若持续出现请联系管理员检查 checkpoint 配置')
        release()
        return
      }
      // running/pending：收尾中（长任务报告落库较慢）→ 继续轮询
    }
    // 16s 内未到终态（仍在收尾）→ 订阅 SSE 兜底收终态；
    // 终态事件只会用 DB 完整报告覆盖展示，不会清空或切回流程视图
    subscribeSse(taskId, query.value.trim())
    // 注意：此处不释放 approving —— 锁保持到 SSE 终态/异常事件确认（useTaskStream 内释放）
  } catch (e) {
    ElMessage.error('网络错误: ' + e.message)
    release()
  }
}

// ====== 加载历史任务（运行中任务会重新接上 SSE，刷新页面后自动恢复进度） ======
const loadHistoryTask = async (item) => {
  finishRun() // 切到另一个任务前先断开旧 SSE，避免旧任务增量覆盖新视图
  // 缓冲归属判定：同一任务（切页/刷新后回来）保留已上屏的正文与思考，由服务端
  // 首帧 report_snapshot 补齐离开期间的增量；真的换任务才清空（bindStreamTask 内部清）
  bindStreamTask(item.id)
  approvalHandled.value = false // 切换任务：审批锁/事件去重标记随任务重置
  query.value = item.query
  currentTaskId.value = item.id
  saveCurrentTask(item.id, item.query)
  approvalMode.value = 'approve'
  approvalComment.value = ''
  pendingStartedAt.value = 0
  if (item.result) {
    activeStep.value = pipelineSteps.length
    taskResult.value = item.result
    // 本分支只处理已落定的缓存结果：关掉流式卡，否则会残留一枚半截的「流式生成中」
    streamActive.value = false
    // 缓存内时间戳定格总用时（新缓存含 started_at/finished_at；旧缓存缺失时由下方回填兜底）
    const cStart = parseTs(item.result.started_at)
    const cEnd = parseTs(item.result.finished_at)
    if (cStart) {
      startedAt.value = cStart
      finalElapsed.value = cEnd ? Math.max(0, cEnd - cStart) : 0
    }
    if (item.result.status === 'awaiting_approval') {
      approvalEditContent.value = draftReport.value
    }
    // 旧缓存缺 elapsed_seconds/total_tokens → 后台拉详情补齐元信息（不阻塞首屏，不覆盖新任务）
    if (typeof item.result.elapsed_seconds !== 'number') {
      const tid = item.id
      fetchTaskDetail(tid).then(json => {
        if (json.code !== 200 || !json.data) return
        if (currentTaskId.value !== tid) return // 已切到别的任务，丢弃迟到响应
        const d = json.data
        taskResult.value = {
          ...taskResult.value,
          steps: (d.steps && d.steps.length) ? d.steps : taskResult.value.steps,
          report: taskResult.value.report || d.report || '',
          elapsed_seconds: d.elapsed_seconds,
          total_tokens: d.total_tokens ?? null,
          llm_tokens: d.llm_tokens ?? taskResult.value.llm_tokens ?? null,
          started_at: d.started_at || taskResult.value.started_at || null,
          finished_at: d.finished_at || taskResult.value.finished_at || null,
        }
        mergePersistedThinking(d.steps)
      }).catch(() => { /* 静默：回填失败保留缓存视图 */ })
    }
    return true
  }
  // 本地无缓存结果 → 从后端拉取任务详情（执行步骤持久化于 agent_task_steps 表）
  try {
    const json = await fetchTaskDetail(item.id)
    if (json.code === 200 && json.data) {
      const d = json.data
      if ((d.steps && d.steps.length) || d.report || d.status === 'running' || d.status === 'pending') {
        taskResult.value = toTaskResult(d) // 统一装配：含 elapsed_seconds / total_tokens 元信息
        if (d.status === 'running' || d.status === 'pending') {
          // 任务仍在后台执行：先注入真实开始时间，watch(running) 才不会把计时清零
          pendingStartedAt.value = parseTs(d.started_at || d.created_at) || Date.now()
          running.value = true
          activeStep.value = Math.max(0, deriveActiveStep(d.steps))
          streamActive.value = false
          subscribeSse(item.id, item.query)
          ElMessage.info('任务仍在执行，已重新接入实时进度')
          return true
        }
        // 已落定任务：用后端的开始/结束时间定格总用时
        const startTs = parseTs(d.started_at || d.created_at)
        const endTs = parseTs(d.finished_at)
        startedAt.value = startTs
        finalElapsed.value = endTs && startTs ? Math.max(0, endTs - startTs) : 0
        activeStep.value = pipelineSteps.length
        streamActive.value = false // 已落定：终态报告接管展示，流式卡退出（缓冲保留供对照）
        if (d.status === 'awaiting_approval') {
          approvalEditContent.value = draftReport.value
          ElMessage.warning('该任务报告待审批，可在右侧完成审批')
        }
        return true
      }
    }
  } catch {
    /* 静默，走报告兜底 */
  }
  // 兜底：从报告中心拉取该任务生成的报告
  if (item.reportId) {
    try {
      const json = await fetchReportDetail(item.reportId)
      if (json.code === 200) {
        activeStep.value = pipelineSteps.length
        taskResult.value = {
          status: item.status,
          steps: [],
          report: json.data.content || '',
          llm_used: (json.data.tags || []).includes('LLM'),
        }
        return true
      }
    } catch {
      /* 静默 */
    }
  }
  taskResult.value = null
  return false
}

// ====== 取消任务（运行中 / 待审批） ======
const handleCancel = async (item) => {
  const id = item ? item.id : currentTaskId.value
  if (!id || cancelling.value) return
  const ok = await ElMessageBox.confirm(
    `确定终止任务 #${id}？终止后不可恢复。`,
    '终止任务',
    { type: 'warning', confirmButtonText: '终止', cancelButtonText: '取消' },
  ).then(() => true).catch(() => false)
  if (!ok) return
  cancelling.value = true
  // 先关闭本任务的 SSE：否则后端终态推送会在取消响应前后重复弹「任务已取消」
  if (currentTaskId.value === id) {
    finishRun()
    streamActive.value = false
  }
  try {
    const json = await cancelTask(id)
    if (json.code !== 200) {
      ElMessage.error(json.detail || json.message || '取消失败')
      return
    }
    ElMessage.info('任务已取消')
    if (currentTaskId.value === id) {
      running.value = false
      taskResult.value = taskResult.value
        ? { ...taskResult.value, status: 'cancelled' }
        : { status: 'cancelled', steps: [], report: '', llm_used: false }
      streamActive.value = false
      // 需求 B3：取消后回读任务详情，把运行中已落库的思考内容补进第 5 节点
      // （本地缓存的步骤行是取消前的，不含后端运行中持续写入的 thinking）
      try {
        const d = await fetchTaskDetail(id)
        if (d.code === 200 && d.data && Array.isArray(d.data.steps) && d.data.steps.length) {
          // 统一装配并强制 cancelled 态：elapsed_seconds / total_tokens 随详情补齐
          taskResult.value = { ...toTaskResult(d.data), status: 'cancelled' }
        }
      } catch {
        /* 静默：保留本地已有步骤 */
      }
    }
    syncHistoryFromApi()
    fetchAgentStatus()
    taskDrawerRef.value?.refresh()
  } catch (e) {
    ElMessage.error('取消任务失败: ' + e.message)
  } finally {
    cancelling.value = false
  }
}

// ====== 重试任务：以相同问题新建任务并立即订阅进度 ======
const handleRetry = async (item) => {
  try {
    const json = await retryTask(item.id)
    if (json.code !== 200 || !json.data || !json.data.task_id) {
      ElMessage.error(json.detail || json.message || '重试失败')
      return
    }
    const newId = json.data.task_id
    ElMessage.success('已重新发起任务')
    query.value = item.query
    currentTaskId.value = newId
    saveCurrentTask(newId, item.query) // 重试产生新任务：持久化指向新 id
    taskResult.value = null
    streamReport.value = ''
    resetThinkState()
    approvalHandled.value = false
    streamRun.value = 0
    streamActive.value = false
    activeStep.value = 0
    pendingStartedAt.value = 0
    running.value = true
    subscribeSse(newId, item.query)
    syncHistoryFromApi()
    fetchAgentStatus()
    taskPanelOpen.value = false
  } catch (e) {
    ElMessage.error('重试失败: ' + e.message)
  }
}

// ====== 任务进程里点「查看」：定位到主视图并关闭抽屉 ======
const handleSelectTask = (item) => {
  taskPanelOpen.value = false
  loadHistoryTask(item)
}

// ====== 任务进程空态「新建任务」：关闭抽屉并清空当前视图 ======
const handleNewTaskFromDrawer = () => {
  taskPanelOpen.value = false
  handleNewTask()
}

// ====== 删除历史任务（后端数据库 + 本地缓存） ======
const deleteHistoryItem = async (item) => {
  try {
    const json = await deleteTask(item.id)
    if (json.code !== 200) {
      ElMessage.error(json.detail || json.message || '删除失败')
      return
    }
  } catch (e) {
    // 旧本地记录在后端已不存在（404）→ 仅清理本地；执行中的任务由后端 400 拒绝
    if (!/不存在|404/.test(String(e.message || ''))) {
      ElMessage.error('删除失败: ' + e.message)
      return
    }
  }
  taskHistory.value = taskHistory.value.filter(t => t.id !== item.id)
  saveHistory()
  if (currentTaskId.value === item.id) {
    // 删除的正是当前查看的任务：清空视图与持久化指针（否则返回本页还会尝试恢复它）
    finishRun()
    clearCurrentTask()
    currentTaskId.value = null
    taskResult.value = null
    activeStep.value = -1
    streamReport.value = ''
    resetThinkState()
    approvalHandled.value = false
    streamActive.value = false
  }
}

// ====== 从后端数据库同步任务历史（按用户隔离） ======
const syncHistoryFromApi = async () => {
  try {
    const json = await fetchTasks()
    if (json.code === 200 && Array.isArray(json.data)) {
      const local = taskHistory.value
      // /tasks 已按时间倒序返回；每问题只保留最新一条（去重后仍是"最新在前"）
      taskHistory.value = dedupeHistory(json.data.map(t => {
        // 同一查询且同一天执行的本地记录保留完整结果（含步骤）
        const match = local.find(l => l.query === t.query && t.created_at && l.time && l.time.startsWith(t.created_at.slice(0, 10)))
        return {
          id: t.id,
          query: t.query,
          status: t.status,
          llm_used: match ? match.llm_used : !!t.llm_provider,
          llm_provider: t.llm_provider || (match ? match.llm_provider : null),
          llm_model: t.llm_model || (match ? match.llm_model : null),
          time: t.created_at || '',
          result: match ? match.result : null,
          reportId: t.report_id || null,
          progress: t.progress || null,
          current_agent: t.current_agent || '',
        }
      }))
    }
  } catch {
    /* 静默 */
  }
}

// ====== 刷新/首次进入页面：优先恢复上次查看的任务（localStorage），其次最近活跃任务 ======
const restorePersistedTask = async () => {
  if (running.value || currentTaskId.value) return false
  const cur = readCurrentTask()
  if (!cur || !cur.id) return false
  const item = taskHistory.value.find(t => t.id === cur.id) || {}
  const ok = await loadHistoryTask({
    id: cur.id,
    query: cur.query || item.query || '',
    status: item.status || 'running',
    result: item.result || null,
    reportId: item.reportId || null,
    time: item.time || '',
  })
  if (!ok) clearCurrentTask() // 任务已被删除/不可访问 → 丢弃过期指针
  return ok
}

// ====== 刷新/首次进入页面：自动恢复最近一个活跃任务（解决"刷新后显示空闲"） ======
const restoreActiveTask = async () => {
  if (running.value || currentTaskId.value) return
  try {
    const json = await fetchTasks()
    if (json.code !== 200 || !Array.isArray(json.data)) return
    const active = json.data.find(t => ['running', 'pending', 'awaiting_approval'].includes(t.status))
    if (!active) return
    await loadHistoryTask({
      id: active.id,
      query: active.query,
      status: active.status,
      result: null,
      reportId: active.report_id || null,
      time: active.created_at || '',
    })
  } catch {
    /* 静默：恢复失败不影响手动操作 */
  }
}

// ====== SSE 订阅：状态与回调经 ctx 注入 composable（逻辑见 composables/useTaskStream.js） ======
const { finishRun, subscribeSse } = useTaskStream({
  auth,
  pipelineSteps,
  activeStep,
  running,
  currentTaskId,
  taskResult,
  streamReport,
  streamRun,
  streamActive,
  streamThink,
  approvalMode,
  approvalEditContent,
  approving,
  approvalHandled,
  draftReport,
  pushHistoryItem,
  syncHistoryFromApi,
})

// ====== 快捷键 ======
const handleKeydown = (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    handleExecute()
  }
}

// ====== 刷新（Agent 状态 + 历史双源同步 + 活跃任务接管） ======
const handleRefresh = () => {
  fetchAgentStatus()
  syncHistoryFromApi().then(async () => {
    const ok = await restorePersistedTask()
    if (!ok) restoreActiveTask()
  })
}

// ====== 页头徽标派生 ======
// 就绪数排除忙碌 Agent，避免运行中仍显示「6 就绪」的静态假象；总数用于 5/6 就绪展示
const agentReadyCount = computed(() => (agentStatus.value?.agents || []).filter(a => a.status !== 'busy').length)
const agentBusyCount = computed(() => (agentStatus.value?.agents || []).filter(a => a.status === 'busy').length)
const activeTaskCount = computed(() => agentStatus.value?.active_tasks || 0)
const runningTaskCount = computed(() => agentStatus.value?.running_tasks || 0)
const pendingTaskCount = computed(() => agentStatus.value?.pending_tasks || 0)
const awaitingTaskCount = computed(() => agentStatus.value?.awaiting_tasks || 0)
const staleAwaitingCount = computed(() => agentStatus.value?.stale_awaiting_tasks || 0)
const staleAwaitingHours = computed(() => agentStatus.value?.awaiting_stale_hours || 24)
const agentTotal = computed(() => (agentStatus.value?.agents || []).length)

// 待审批任务是否已滞留（与后端阈值同源，避免前后端判定不一致）
const parseTs = (s) => {
  if (!s) return 0
  const t = new Date(String(s).replace(' ', 'T')).getTime()
  return Number.isFinite(t) ? t : 0
}
const isStaleAwaiting = (t) => {
  if (!t || t.status !== 'awaiting_approval') return false
  const start = parseTs(t.started_at || t.created_at)
  return start > 0 && Date.now() - start > staleAwaitingHours.value * 3600 * 1000
}
const currentAwaitingFresh = computed(
  () => taskResult.value?.status === 'awaiting_approval' && !isStaleAwaiting(taskResult.value),
)
// 入口徽标取「后端活跃任务数 / 本页运行中 / 新鲜待审批」三者最大值，
// 滞留待审批不计入（否则没有任何进程时仍会亮着 5）
const taskEntryCount = computed(() => Math.max(
  activeTaskCount.value,
  running.value ? 1 : 0,
  currentAwaitingFresh.value ? 1 : 0,
))
// 页头状态：按「执行中 > 待审批 > 排队中 > 空闲」优先级收敛为一个结论，
// 用语义色区分（执行中=accent / 待审批=warning / 排队=中性 / 空闲=success）
const runState = computed(() => {
  if (running.value) return { text: '任务执行中', tone: 'run' }
  if (runningTaskCount.value) return { text: `${runningTaskCount.value} 个任务执行中`, tone: 'run' }
  if (pendingTaskCount.value) return { text: `${pendingTaskCount.value} 个任务排队中`, tone: 'wait' }
  if (awaitingTaskCount.value || currentAwaitingFresh.value) {
    return { text: `${awaitingTaskCount.value || 1} 个任务待审批`, tone: 'appr' }
  }
  return { text: taskResult.value ? '已就绪' : '空闲', tone: 'idle' }
})
const runStateText = computed(() => runState.value.text)
const runStateTone = computed(() => runState.value.tone)
// 徽标配色与页头状态同源，避免「有任务」却显示绿色这种语义冲突
const taskEntryTone = computed(() => {
  if (running.value || runningTaskCount.value) return 'run'
  if (pendingTaskCount.value) return 'wait'
  if (awaitingTaskCount.value || currentAwaitingFresh.value) return 'appr'
  return ''
})
const taskEntryHint = computed(() => {
  const parts = []
  if (runningTaskCount.value || running.value) parts.push(`${Math.max(runningTaskCount.value, 1)} 个执行中`)
  if (pendingTaskCount.value) parts.push(`${pendingTaskCount.value} 个排队中`)
  if (awaitingTaskCount.value) parts.push(`${awaitingTaskCount.value} 个待审批`)
  if (staleAwaitingCount.value) parts.push(`${staleAwaitingCount.value} 条滞留待审批`)
  return parts.length ? `${parts.join(' · ')}，点击查看任务进程` : '查看任务进程'
})

// ====== 任务元信息（右列 meta-list） ======
const metaStatusText = (s) => (
  { completed: '已完成', awaiting_approval: '待审批', running: '执行中', failed: '失败', cancelled: '已取消' }[s] || s || '—'
)
const metaModel = computed(() => {
  const r = taskResult.value
  if (!r) return '—'
  return r.llm_model || (r.llm_provider ? r.llm_provider : (r.llm_used ? 'LLM' : '模板'))
})

// ====== 已用时（v0 元信息「已用时 00:42」：执行中每秒走表，落定后定格） ======
const nowTick = ref(Date.now())
let tickTimer = null
let statusTimer = null
const startedAt = ref(0)        // 本次执行开始时间戳（ms）
const finalElapsed = ref(0)     // 落定后的总用时（ms）
// 跨页恢复 running 任务时的真实开始时间：watch(running) 用它续算，避免计时从 0 重新开始
const pendingStartedAt = ref(0)
watch(running, (r) => {
  if (r) {
    startedAt.value = pendingStartedAt.value || Date.now()
    pendingStartedAt.value = 0
    finalElapsed.value = 0
  } else if (startedAt.value) {
    finalElapsed.value = Date.now() - startedAt.value
  }
})
const fmtElapsed = (ms) => {
  const s = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
const elapsedText = computed(() => {
  // 进行中：本地每秒走表（后端 elapsed_seconds 是拉取时快照，会过期）
  if (running.value && startedAt.value) return fmtElapsed(nowTick.value - startedAt.value)
  // 终态/回看：优先后端统一口径 elapsed_seconds（含审批等待；审批后回填路径必备）
  const backendSecs = taskResult.value?.elapsed_seconds
  if (typeof backendSecs === 'number' && isFinite(backendSecs) && backendSecs >= 0) {
    return fmtElapsed(backendSecs * 1000)
  }
  // 本地兜底：本会话计时 → 步骤耗时求和（旧缓存无 elapsed_seconds 时）
  if (finalElapsed.value) return fmtElapsed(finalElapsed.value)
  const stepSecs = (taskResult.value?.steps || [])
    .reduce((acc, s) => acc + (typeof s?.duration === 'number' && isFinite(s.duration) ? s.duration : 0), 0)
  return stepSecs > 0 ? fmtElapsed(stepSecs * 1000) : '—'
})

// ====== Token 汇总（步骤级优先 → 后端聚合 → 报告级 usage 兜底；都没有显示 —） ======
const totalTokens = computed(() => {
  let sum = 0
  for (const st of (taskResult.value?.steps || [])) {
    const t = st?.output?.tokens?.total_tokens
    if (typeof t === 'number' && isFinite(t)) sum += t
  }
  if (sum > 0) return sum
  const backend = taskResult.value?.total_tokens
  if (typeof backend === 'number' && isFinite(backend) && backend > 0) return backend
  // 报告级 usage 兜底（llm_tokens 兼容 dict / 数字）
  const rep = taskResult.value?.llm_tokens
  if (typeof rep === 'number' && isFinite(rep) && rep > 0) return rep
  if (rep && typeof rep === 'object') {
    const v = rep.total_tokens
    if (typeof v === 'number' && isFinite(v) && v > 0) return v
  }
  return 0
})
const tokenText = computed(() => (totalTokens.value > 0 ? totalTokens.value.toLocaleString() : '—'))

// ====== 检索来源（RAG 步骤 output.sources/documents/chunks，v0 右列 Top3 + 相关度） ======
const retrievalSources = computed(() => {
  const st = (taskResult.value?.steps || []).find(s => s.step === 'retrieve_knowledge')
  const o = st?.output
  const raw = o && (Array.isArray(o.sources) ? o.sources : (Array.isArray(o.documents) ? o.documents : (Array.isArray(o.chunks) ? o.chunks : null)))
  if (!raw) return []
  return raw.slice(0, 3).map((s) => {
    if (typeof s === 'string') return { name: s, score: null }
    const name = s.source || s.doc || s.title || s.document || s.name || '未知来源'
    const sc = s.score ?? s.relevance ?? s.similarity
    return { name, score: typeof sc === 'number' && isFinite(sc) ? sc : null }
  })
})

// ====== 新建任务（v0 页头主按钮：清空当前视图并聚焦输入框） ======
const formRef = ref(null)
const handleNewTask = () => {
  if (running.value) {
    ElMessage.warning('当前任务执行中，完成后再新建')
    return
  }
  query.value = ''
  taskResult.value = null
  currentTaskId.value = null
  clearCurrentTask() // 显式新建任务：不再恢复旧任务
  activeStep.value = -1
  streamReport.value = ''
  resetThinkState()
  approvalHandled.value = false
  streamRun.value = 0
  streamActive.value = false
  pendingStartedAt.value = 0
  startedAt.value = 0
  finalElapsed.value = 0
  formRef.value?.focus()
}

// ====== 初始化 ======
onMounted(() => {
  fetchAgentStatus()
  // 先同步历史（拿到本地缓存结果），再恢复上次查看的任务；没有再回退到"最近活跃任务"
  syncHistoryFromApi().then(async () => {
    const ok = await restorePersistedTask()
    if (!ok) restoreActiveTask()
  })
  tickTimer = setInterval(() => { nowTick.value = Date.now() }, 1000) // 已用时走表
  // 页头任务入口的活跃数由后端状态驱动，定时刷新避免长期停留在旧值
  statusTimer = setInterval(fetchAgentStatus, 10000)
})
onUnmounted(() => {
  clearInterval(tickTimer)
  clearInterval(statusTimer)
  stopGatePoll() // 停止审批闸口详情轮询
  stopRunningPoll() // 停止运行期详情轮询
  finishRun() // 关闭 SSE 连接
  cleanupSpeech() // 停止语音播报/录音
})
</script>

<template>
  <div class="ag-page">
    <!-- ===== 页头（v0 page-head 同构：64px 单行） ===== -->
    <header class="ag-head">
      <div class="ag-head__t">
        <h1 class="ag-head__h1">Agent 协作中心</h1>
        <p class="ag-head__sub">多智能体编排 · 火险研判报告生成 · 人工审批闸口</p>
      </div>
      <BackHomeButton />
      <span class="ag-head__sp"></span>
      <span class="ag-head__badge mono" :title="agentTotal ? `${agentReadyCount}/${agentTotal} 个 Agent 就绪` : 'Agent 状态未知'">Agent {{ agentTotal ? `${agentReadyCount}/${agentTotal}` : '—' }} 就绪<template v-if="agentBusyCount"> · {{ agentBusyCount }} 运行</template></span>
      <span class="ag-head__live" :class="`is-${runStateTone}`" role="status" aria-live="polite">
        <i class="ag-head__dot" aria-hidden="true"></i>{{ runStateText }}
      </span>
      <button
        class="ag-head__btn"
        :class="{ recording: recordState.recording }"
        :title="recordState.recording ? '停止录音并识别' : '语音输入任务'"
        @click="handleMicClick"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="7.5" y="3" width="5" height="9" rx="2.5"/><path d="M5 10a5 5 0 0 0 10 0"/><path d="M10 15v2.5"/></svg>
        {{ recordState.recording ? '停止' : '语音' }}
      </button>
      <button class="ag-head__btn" title="刷新 Agent 状态与任务历史" @click="handleRefresh">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16.4 8.4A6.6 6.6 0 1 0 10 16.6a6.6 6.6 0 0 0 4.6-1.9"/><path d="M16.6 3.6v5h-5"/></svg>
        刷新
      </button>
      <button
        class="ag-head__btn ag-head__btn--tasks"
        :class="[taskEntryTone ? `is-${taskEntryTone}` : '', { 'is-active': taskEntryCount > 0 }]"
        :title="taskEntryHint"
        :aria-label="taskEntryHint"
        :aria-expanded="taskPanelOpen"
        aria-haspopup="dialog"
        @click="taskPanelOpen = true"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 5.5h9M7 10h9M7 14.5h9"/><circle cx="4" cy="5.5" r="1"/><circle cx="4" cy="10" r="1"/><circle cx="4" cy="14.5" r="1"/></svg>
        任务进程
        <span v-if="taskEntryCount" class="ag-head__count" :aria-label="`${taskEntryCount} 个进行中任务`">{{ taskEntryCount }}</span>
      </button>
      <button class="ag-head__btn ag-head__btn--primary" title="清空当前视图，开始新任务" @click="handleNewTask">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 4.5v11"/><path d="M4.5 10h11"/></svg>
        新建任务
      </button>
    </header>

    <!-- ===== 主体三列（v0 agent-body：左输入+历史 / 中流水线+报告 / 右元信息+审批+能力） ===== -->
    <div class="ag-body">
      <!-- 左列 -->
      <aside class="ag-col ag-col--l">
        <div class="ag-col__scroll">
          <TaskFormCard
            ref="formRef"
            :query="query"
            :running="running"
            :example-tasks="exampleTasks"
            @update:query="query = $event"
            @keydown="handleKeydown"
            @execute="handleExecute"
          />
          <TaskHistoryList
            :task-history="taskHistory"
            :active-id="currentTaskId"
            @load="loadHistoryTask"
            @delete="deleteHistoryItem"
            @cancel="handleCancel"
            @retry="handleRetry"
          />
        </div>
      </aside>

      <!-- 中列 -->
      <div class="ag-col ag-col--c">
        <div class="ag-col__scroll">
          <!-- 执行流水线（后端步骤审计 summary + chips 已并入各节点） -->
          <AgentPipeline
            :pipeline-steps="pipelineStepsView"
            :step-statuses="stepStatuses"
            :trace-steps="taskResult?.steps || []"
            :report-thinking="reportThinking"
            :live-think="streamThink"
            :live-think-rounds="streamThinkRounds"
            :report-started="!!streamReport"
            :think-in-report="thinkInReport"
          />

          <!-- 报告正文（实时生成中）：SSE report_delta 打字机 + report_think 深度思考面板；
               生成完成（评审进行中）自动切换为渲染好的草稿预览 -->
          <AgentStreamView
            v-if="showStreamReport"
            :stream-report="streamReport"
            :stream-think="streamThink"
            :body-started="bodyStarted"
            :draft-ready="draftReady"
          />

          <!-- 待审批：草稿全文直接放在「分析报告」区域（全宽可读）；编辑模式原位展开大编辑器；
               草稿尚未落库时显示占位（闸口已触发但报告全文未写入），不留空白；
               已定稿的审批卡只占右列结果态，中列仍由终态 AgentReportView 展示正式报告 -->
          <template v-if="showApproval && taskResult?.status === 'awaiting_approval'">
            <div v-if="approvalMode === 'edit'" class="ag-draft-edit">
              <div class="ag-draft-edit__hd">
                <span class="ag-draft-edit__t">修订报告草稿</span>
                <span class="ag-draft-edit__h">直接修改全文，完成后在右侧「草稿审阅」提交</span>
              </div>
              <el-input
                :model-value="approvalEditContent"
                type="textarea"
                :autosize="{ minRows: 18, maxRows: 34 }"
                placeholder="编辑报告全文…"
                @update:model-value="approvalEditContent = $event"
              />
            </div>
            <div v-else-if="!draftReport" class="ag-draft-wait">
              <span class="ag-draft-wait__dots"><i></i><i></i><i></i></span>
              草稿生成中：审批闸口已触发，报告全文即将就绪…
            </div>
            <AgentReportView v-else :task-result="approvalPreviewResult" />
          </template>

          <!-- 报告展示（终态：审批通过/编辑定稿/完成/失败后直接在此显示）；
               流式生成中不渲染（由上方流式卡承载，避免出现第二个空「分析报告」方块） -->
          <AgentReportView
            v-else-if="taskResult && taskResult.status !== 'awaiting_approval' && !showStreamReport"
            :task-result="taskResult"
          />

          <!-- 空态（v0 empty：虚线发丝框） -->
          <div v-if="!taskResult && !showStreamReport" class="ag-empty">
            <svg class="ag-empty__ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="10" cy="10" r="2.2"/><path d="M10 3.2v2.2M10 14.6v2.2M3.2 10h2.2M14.6 10h2.2M5.2 5.2l1.6 1.6M13.2 13.2l1.6 1.6M14.8 5.2l-1.6 1.6M6.8 13.2l-1.6 1.6"/>
            </svg>
            输入分析任务，系统将自动执行
            <span class="ag-empty__hint">编排 Agent 拆解任务 → 数据 Agent 查询 → GIS Agent 分析 → RAG Agent 检索 → 报告 Agent 生成</span>
          </div>
        </div>
      </div>

      <!-- 右列：任务元信息 + 审批 + 系统能力 -->
      <aside class="ag-col ag-col--r">
        <div class="ag-col__scroll">
          <!-- 任务元信息（v0 meta-list） -->
          <section v-if="currentTaskId || taskResult" class="ag-meta">
            <div class="ag-sec">
              <span class="ag-sec__t">任务元信息</span>
              <span class="ag-sec__sp"></span>
            </div>
            <div class="meta-list">
              <div class="meta-list__r"><span class="meta-list__k">任务 ID</span><span class="meta-list__v mono">{{ currentTaskId || '—' }}</span></div>
              <div class="meta-list__r"><span class="meta-list__k">状态</span><span class="meta-list__v">{{ metaStatusText(taskResult?.status) }}</span></div>
              <div class="meta-list__r"><span class="meta-list__k">模型</span><span class="meta-list__v mono">{{ metaModel }}</span></div>
              <div class="meta-list__r"><span class="meta-list__k">步骤</span><span class="meta-list__v mono">{{ stepDone }} / {{ stepTotal }}</span></div>
              <div class="meta-list__r"><span class="meta-list__k">已用时</span><span class="meta-list__v mono">{{ elapsedText }}</span></div>
              <div class="meta-list__r"><span class="meta-list__k">Token</span><span class="meta-list__v mono">{{ tokenText }}</span></div>
            </div>
          </section>

          <ApprovalPanel
            v-if="showApproval"
            :approval-step="approvalStep"
            :approval-review="approvalReview"
            :approving="approving"
            :mode="approvalMode"
            :comment="approvalComment"
            @update:mode="approvalMode = $event"
            @update:edit-content="approvalEditContent = $event"
            @update:comment="approvalComment = $event"
            @submit="handleResume"
          />

          <!-- 检索来源（RAG 召回 Top3，v0 右列同构） -->
          <section v-if="retrievalSources.length" class="ag-meta">
            <div class="ag-sec">
              <span class="ag-sec__t">检索来源</span>
              <span class="ag-sec__sp"></span>
            </div>
            <div class="ag-sources">
              <div v-for="(s, i) in retrievalSources" :key="i" class="ag-source" :title="s.name">
                <span class="ag-source__t">{{ s.name }}</span>
                <span class="ag-source__m mono">相关度 {{ s.score != null ? s.score.toFixed(2) : '—' }}</span>
              </div>
            </div>
          </section>

          <!-- 系统能力面板（P0/P1/P2 能力一览，自包含组件，默认展开） -->
          <SystemCapabilities />
        </div>
      </aside>
    </div>

    <!-- 任务进程抽屉：页头入口打开，可定位/终止/重试 -->
    <TaskProcessDrawer
      ref="taskDrawerRef"
      v-model="taskPanelOpen"
      :current-task-id="currentTaskId"
      :stale-hours="staleAwaitingHours"
      @select="handleSelectTask"
      @cancel="handleCancel"
      @retry="handleRetry"
      @new-task="handleNewTaskFromDrawer"
    />
  </div>
</template>

<style scoped>
.ag-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fs-bg-canvas);
  /* 指挥台网格底纹（qt 工具类：hairline 级网格，随亮暗主题取色） */
  background-image:
    linear-gradient(rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px);
  background-size: 48px 48px;
  color: var(--fs-ink-900);
  overflow: hidden;
}

/* ===== 页头（v0 page-head） ===== */
.ag-head {
  flex-shrink: 0;
  height: var(--fs-topbar-h, 64px);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--fs-bg-surface);
  border-bottom: 1px solid var(--fs-hairline);
}
.ag-head__t { min-width: 0; flex: 0 1 auto; }
.ag-head__h1 {
  margin: 0;
  font-size: var(--fs-t-h1, 28px);
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.2;
  color: var(--fs-ink-900);
  /* 窄屏禁止逐字竖排：宁可截断，也不让标题把页头撑成一列 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ag-head__sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--fs-ink-500);
}
.ag-head__sp { flex: 1; }
/* v0 badge--muted mono 同构：就绪计数盒 */
.ag-head__badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 11px;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
  white-space: nowrap;
}
.ag-head__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  font-size: 11px;
  color: var(--fs-ink-700);
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.ag-head__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--fs-ink-400);
}
.ag-head__live.is-idle .ag-head__dot { background: var(--fs-success); }
.ag-head__live.is-run { color: var(--fs-accent); }
.ag-head__live.is-run .ag-head__dot {
  background: var(--fs-accent);
  animation: ag-pulse 1.2s ease-in-out infinite;
}
.ag-head__live.is-appr { color: var(--fs-warning); }
.ag-head__live.is-appr .ag-head__dot { background: var(--fs-warning); }
.ag-head__live.is-wait { color: var(--fs-ink-500); }
.ag-head__live.is-wait .ag-head__dot { background: var(--fs-ink-400); }
/* 运行 / 待审批：徽标外壳同步着色，状态一眼可读（不只点点子变色） */
.ag-head__live.is-run { box-shadow: inset 0 0 0 1px var(--fs-accent); }
.ag-head__live.is-appr { box-shadow: inset 0 0 0 1px var(--fs-warning); }
@keyframes ag-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .ag-head__live.is-run .ag-head__dot,
  html:not([data-motion="on"]) .ag-head__btn.recording,
  html:not([data-motion="on"]) .ag-draft-wait__dots i,
  html:not([data-motion="on"]) .ag-col { animation: none; }
}
html[data-motion-allowed="false"] .ag-head__live.is-run .ag-head__dot,
html[data-motion-allowed="false"] .ag-head__btn.recording,
html[data-motion-allowed="false"] .ag-draft-wait__dots i,
html[data-motion-allowed="false"] .ag-col { animation: none; }
/* 窄屏优先保留操作入口：收起副标题、压缩间距 */
@media (max-width: 1180px) {
  .ag-head { gap: 8px; padding: 0 16px; }
  .ag-head__sub { display: none; }
  .ag-head__h1 { font-size: 22px; }
  /* 状态徽标/运行态文字让位给操作按钮（同样信息在流水线与任务进程里仍在） */
  .ag-head__badge,
  .ag-head__live { display: none; }
  /* 按钮退化为纯图标：文字用 font-size:0 收掉，计数徽标单独还原字号 */
  .ag-head__btn { padding: 0 7px; gap: 0; font-size: 0; }
  .ag-head__count { font-size: 10px; }
}
.ag-head__btn {
  height: 28px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline); /* v0 .btn 同构：发丝环 */
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.ag-head__btn svg {
  width: 13px;
  height: 13px;
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
.ag-head__btn:hover { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.ag-head__btn:active { transform: translateY(0.5px); }
/* 图标语义微交互：刷新转一圈、麦克风轻放大（仅悬停一次性，不改布局） */
.ag-head__btn[title^="刷新"] svg { transition: transform 0.5s var(--fs-ease-out, ease-out); }
.ag-head__btn[title^="刷新"]:hover svg { transform: rotate(-180deg); }
.ag-head__btn[title^="语音"]:hover:not(.recording) svg { transform: scale(1.12); }
.ag-head__btn.recording {
  color: var(--fs-danger);
  box-shadow: inset 0 0 0 1px var(--fs-danger);
  animation: ag-pulse 1.2s ease-in-out infinite;
}

/* ===== 主体三列（v0 agent-body：通栏 + 发丝分隔） ===== */
.ag-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.ag-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  animation: ag-col-in 0.4s var(--fs-ease-out) both;
}
/* 三列错峰落位（左→中→右），首屏像「指挥台就位」而不是一次糊上来 */
.ag-col--l { animation-delay: 0s; }
.ag-col--c { animation-delay: 0.07s; }
.ag-col--r { animation-delay: 0.14s; }
@keyframes ag-col-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.ag-col--l {
  flex: none;
  width: 340px;
  background: var(--fs-bg-surface);
  border-right: 1px solid var(--fs-hairline);
}
.ag-col--c {
  flex: 1;
  background: var(--fs-bg-canvas);
}
.ag-col--r {
  flex: none;
  width: 380px;
  background: var(--fs-bg-surface);
  border-left: 1px solid var(--fs-hairline);
}
.ag-col__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden; /* 内容横向溢出时不出现底部横向滚动条（此前被误认为分页器） */
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
@media (max-width: 1440px) {
  .ag-col--l { width: 300px; }
  .ag-col--r { width: 340px; }
}
/* 左列：顶部 24px 与页头留出呼吸（知识库/智能查询左列同款），卡间距收窄保证整列一屏装下 */
.ag-col--l .ag-col__scroll {
  padding: 24px 16px 14px;
  gap: 14px;
}
@media (max-width: 1100px) {
  .ag-body { flex-direction: column; overflow-y: auto; }
  .ag-col--l, .ag-col--r { width: 100%; border: none; }
  .ag-col__scroll { overflow: visible; }
}

/* sec-t 同构（右列小节标题） */
.ag-sec {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ag-sec::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--fs-hairline);
}
.ag-sec__t {
  position: relative;
  padding-left: 9px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
.ag-sec__t::before {
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

/* 任务元信息（v0 meta-list 同构：行高 32px / 键 76px / 值 ink-700） */
.meta-list { display: flex; flex-direction: column; }
.meta-list__r {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 32px;
  padding: 0 6px;
  margin: 0 -6px;
  font-size: 12px;
  border-bottom: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-xs, 3px);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.meta-list__r:hover { background: color-mix(in srgb, var(--fs-ink-900) 3%, transparent); }
.meta-list__r:last-child { border-bottom: none; }
.meta-list__k { width: 76px; flex: none; color: var(--fs-ink-500); }
.meta-list__v {
  color: var(--fs-ink-700);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-list__v.mono {
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-weight: 400;
}

/* 检索来源（v0 hist-item 两行同构：标题 13px + meta mono 相关度） */
.ag-sources { display: flex; flex-direction: column; gap: 8px; }
.ag-source {
  position: relative;
  padding: 10px 12px;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  transition: background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
/* 来源左沿导轨：悬停浮现，读作「可点开的引文」 */
.ag-source::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--fs-accent);
  transform: scaleX(0);
  transform-origin: center top;
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
.ag-source:hover {
  background: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  transform: translateX(2px);
}
.ag-source:hover::before { transform: scaleX(1); }
.ag-source__t {
  font-size: 13px;
  line-height: 1.5;
  color: var(--fs-ink-700);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}
.ag-source__m {
  font-family: var(--fs-font-mono);
  font-size: 11px;
  color: var(--fs-ink-400);
}

/* 页头主按钮（v0 btn--primary 同构：新建任务） */
.ag-head__btn--primary {
  position: relative;
  overflow: hidden;
  height: 30px;
  padding: 0 12px;
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-weight: 600;
  letter-spacing: 0.02em;
  box-shadow: inset 0 0 0 1px var(--fs-accent), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.ag-head__btn--primary::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.22) 50%, transparent 62%);
  transform: translateX(-130%);
}
.ag-head__btn--primary:hover {
  color: var(--fs-on-accent);
  background: var(--fs-accent-hover);
  box-shadow: inset 0 0 0 1px var(--fs-accent-hover), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.ag-head__btn--primary:hover::after { animation: ag-sheen 0.62s var(--fs-ease-out, ease-out); }
.ag-head__btn--primary:hover svg { transform: rotate(90deg); }
@keyframes ag-sheen {
  to { transform: translateX(130%); }
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .ag-head__btn--primary::after { animation: none; }
}
html[data-motion-allowed="false"] .ag-head__btn--primary::after { animation: none; }

/* 任务进程入口：有活跃任务时点亮，配色随最高优先级状态变化
   执行中=accent / 待审批=warning / 排队=中性；不使用固定 accent 抢占主按钮视觉 */
.ag-head__btn--tasks.is-active { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
.ag-head__btn--tasks.is-run {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
}
.ag-head__btn--tasks.is-run:hover { color: var(--fs-accent); box-shadow: inset 0 0 0 1px var(--fs-accent); }
.ag-head__btn--tasks.is-appr {
  color: var(--fs-warning);
  background: color-mix(in srgb, var(--fs-warning) 8%, var(--fs-bg-surface));
  box-shadow: inset 0 0 0 1px var(--fs-warning);
}
.ag-head__btn--tasks.is-appr:hover { color: var(--fs-warning); box-shadow: inset 0 0 0 1px var(--fs-warning); }
.ag-head__btn--tasks.is-wait { color: var(--fs-ink-700); box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
.ag-head__count {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
}
.ag-head__btn--tasks.is-appr .ag-head__count { background: var(--fs-warning); }
.ag-head__btn--tasks.is-wait .ag-head__count { background: var(--fs-ink-500); }
.ag-head__btn:focus-visible { outline: 2px solid var(--fs-accent); outline-offset: 1px; }

/* 空态（v0 empty：虚线发丝框） */
.ag-empty {
  flex: 1;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  background: var(--fs-bg-surface);
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-md, 10px);
  color: var(--fs-ink-500);
  font-size: 13px;
  text-align: center;
}
/* 空态底部的指挥台刻度装饰（宽度收窄居中，弱化不抢提示文案） */
.ag-empty::after {
  content: '';
  width: 120px;
  height: 5px;
  margin-top: 10px;
  background: repeating-linear-gradient(90deg, var(--fs-hairline) 0 1px, transparent 1px 8px);
}
.ag-empty__ic {
  width: 22px;
  height: 22px;
  color: var(--fs-ink-400);
}
.ag-empty__hint {
  font-size: 11px;
  color: var(--fs-ink-400);
  max-width: 420px;
  line-height: 1.7;
}

/* 待审批 · 编辑态：草稿编辑器与报告卡同构（surface 卡 + 发丝环），占满中列 */
.ag-draft-edit {
  flex: 1 1 auto;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.ag-draft-edit__hd {
  min-height: 48px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--fs-hairline);
  flex-shrink: 0;
}
.ag-draft-edit__t {
  position: relative;
  padding-left: 9px;
  font-size: 14px;
  font-weight: 600;
  color: var(--fs-ink-900);
}
.ag-draft-edit__t::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 2px;
  height: 13px;
  margin-top: -6.5px;
  border-radius: 1px;
  background: var(--fs-accent);
}
/* 草稿生成中占位（审批闸口已触发、报告全文未落库）：虚线发丝框，与空态同语言 */
.ag-draft-wait {
  flex-shrink: 0;
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 20px;
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-md, 10px);
  color: var(--fs-ink-400);
  font-size: 13px;
}
.ag-draft-wait__dots { display: inline-flex; gap: 4px; }
.ag-draft-wait__dots i {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: var(--fs-accent);
  animation: ag-wait-hop 1.2s ease-in-out infinite;
}
.ag-draft-wait__dots i:nth-child(2) { animation-delay: 0.15s; }
.ag-draft-wait__dots i:nth-child(3) { animation-delay: 0.3s; }
@keyframes ag-wait-hop {
  0%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
.ag-draft-edit__h { font-size: 11px; color: var(--fs-ink-400); }
.ag-draft-edit :deep(.el-textarea__inner) {
  flex: 1;
  min-height: 320px;
  padding: 14px 18px;
  border-radius: 0;
  box-shadow: none;
  background: var(--fs-bg-canvas);
  font-size: 13px;
  line-height: 1.8;
  resize: vertical;
}

/* ===== 中列内容卡入场（v-if 挂载即播一次，切换审批/编辑/终态时有明确的「换页」感） ===== */
.ag-empty,
.ag-draft-edit,
.ag-draft-wait { animation: ag-card-in 0.4s var(--fs-ease-out) both; }
@keyframes ag-card-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
/* 计数徽标出现时一次轻弹（任务入列的确定性反馈） */
.ag-head__count { animation: ag-count-in 0.28s var(--fs-ease-out) both; }
@keyframes ag-count-in {
  0% { opacity: 0; transform: scale(0.7); }
  60% { opacity: 1; transform: scale(1.08); }
  100% { opacity: 1; transform: scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .ag-empty,
  html:not([data-motion="on"]) .ag-draft-edit,
  html:not([data-motion="on"]) .ag-draft-wait,
  html:not([data-motion="on"]) .ag-head__count { animation: none; }
}
html[data-motion-allowed="false"] .ag-empty,
html[data-motion-allowed="false"] .ag-draft-edit,
html[data-motion-allowed="false"] .ag-draft-wait,
html[data-motion-allowed="false"] .ag-head__count { animation: none; }
/* 位移类悬停反馈在关闭动效时取消（导轨 ::before 保持隐藏，靠背景/发丝边表达可点） */
html[data-motion-allowed="false"] .ag-source:hover { transform: none; }
html[data-motion-allowed="false"] .ag-source:hover::before { transform: scaleX(0); }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .ag-source:hover { transform: none; }
  html:not([data-motion="on"]) .ag-source:hover::before { transform: scaleX(0); }
}
</style>
