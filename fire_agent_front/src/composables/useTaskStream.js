/**
 * Agent 协作中心 · SSE 任务进度订阅（composable）
 *
 * 阶段 4h：从 views/agent-center/index.vue 中整段搬运（subscribeSse / loadTaskDetailFallback / finishRun），
 * 逻辑一字未改，仅把「需要读写的外部状态与回调」改为由调用方通过 ctx 注入，
 * 从而让父组件从 854 行降到 800 行以内（G2）。
 *
 * @param {Object} ctx 宿主状态与回调集合（全部为 ref / computed / 函数）
 *   auth                  — 鉴权 store（取 token 构造 SSE URL）
 *   pipelineSteps         — 流水线定义数组（普通数组即可）
 *   activeStep, running, currentTaskId, taskResult
 *   streamReport, streamRun, streamActive, streamThink
 *   approvalMode, approvalEditContent
 *   approving             — 审批提交锁：approve/edit 后由终态/异常事件释放
 *   approvalHandled       — 审批决策已提交标记：迟到/重放的 approval 事件直接吞掉
 *   draftReport           — computed：审批草稿全文
 *   pushHistoryItem(d, q) — 终态/兜底入列历史
 *   syncHistoryFromApi()  — 从后端同步任务历史
 */
import { ElMessage } from 'element-plus'
import { fetchTaskDetail, openTaskStream } from '@/api/agent'
import {
  appendThinkChunk,
  bindStreamTask,
  markBodyStarted,
  mergePersistedRounds,
  mergePersistedThinking,
  resetBodyStarted,
  truncateLiveThink,
} from '@/composables/useAgentStreamState'

/**
 * 任务详情/终态事件 → taskResult 统一装配（含元信息字段）
 * 已用时 elapsed_seconds / Token total_tokens / llm_tokens / 起止时间由后端统一下发，
 * 各回填路径（SSE 终态、审批后详情、断线兜底、历史回看）都必须带上，否则元信息丢失
 */
export function toTaskResult(d) {
  return {
    status: d.status,
    steps: d.steps || [],
    report: d.report || '',
    llm_used: !!d.llm_used,
    llm_provider: d.llm_provider || null,
    llm_model: d.llm_model || null,
    llm_tokens: d.llm_tokens ?? null,
    total_tokens: typeof d.total_tokens === 'number' ? d.total_tokens : null,
    elapsed_seconds: typeof d.elapsed_seconds === 'number' ? d.elapsed_seconds : null,
    started_at: d.started_at || null,
    finished_at: d.finished_at || null,
  }
}

export function useTaskStream(ctx) {
  let streamCtl = null // 当前 SSE 订阅的 AbortController（fetch 流，见 subscribeSse）
  // ====== SSE 增量缓冲（性能关键）======
  // report_delta / report_think 每秒可达数十帧，逐帧写响应式大字符串会触发
  // computed 链（mergeThinkRounds/composeThinkRounds/步骤重算）逐帧 O(n) 重算，
  // 长任务下形成 O(n²) 主线程长任务（整页冻结）。改为：增量先进非响应式队列，
  // 180ms 定时批量 flush 一次响应式写入；终态/断线/切任务时丢弃残余半截增量。
  const FLUSH_MS = 180
  let deltaBuf = null // { run, text }
  let thinkBuf = null // { run, text }
  let freshRun = false // run 切换后正文未刷新：首个 delta flush 时清旧缓冲（保留旧草稿到新正文开始）
  let flushTimer = null
  const discardBuffers = () => {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null }
    deltaBuf = null
    thinkBuf = null
    freshRun = false
  }
  const flushBuffers = () => {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null }
    const d = deltaBuf
    const t = thinkBuf
    deltaBuf = null
    thinkBuf = null
    const run = (d || t || {}).run
    if (run == null) return
    // 轮次切换：只切 streamRun，不清正文——旧草稿保留展示（思考+草稿同显），
    // 待本轮首个 report_delta 到达时一次性替换（见下方 freshRun）
    if (run !== ctx.streamRun.value) {
      ctx.streamRun.value = run
      freshRun = d != null // 有正文才需要刷新；纯思考切换时旧草稿继续展示
    }
    if (t && t.text) {
      ctx.streamActive.value = true
      appendThinkChunk(run, t.text)
    }
    if (d && d.text) {
      if (freshRun) {
        ctx.streamReport.value = '' // 新一轮正文开始：替换旧草稿
        freshRun = false
        markBodyStarted()
      }
      ctx.streamReport.value += d.text
      ctx.streamActive.value = true
    }
  }
  const scheduleFlush = () => {
    if (!flushTimer) flushTimer = setTimeout(flushBuffers, FLUSH_MS)
  }
  const pushDelta = (run, text) => {
    if (!text) return
    // 任一缓冲存在异 run 残留 → 立即同步 flush（run 切换不被 180ms 定时延迟/吞掉）
    if ((deltaBuf && deltaBuf.run !== run) || (thinkBuf && thinkBuf.run !== run)) flushBuffers()
    if (deltaBuf && deltaBuf.run === run) deltaBuf.text += text
    else deltaBuf = { run, text }
    scheduleFlush()
  }
  const pushThink = (run, text) => {
    if (!text) return
    if ((deltaBuf && deltaBuf.run !== run) || (thinkBuf && thinkBuf.run !== run)) flushBuffers()
    if (thinkBuf && thinkBuf.run === run) thinkBuf.text += text
    else thinkBuf = { run, text }
    scheduleFlush()
  }

  // 终态提示去重：EventSource 被服务端正常关闭后浏览器会自动重连并重放终态事件，
  // 不去重时会反复弹「任务已取消 / 任务执行完成」，同时造成 /stream 与详情接口被轮询轰炸
  const notifiedTerminal = new Set()
  const notifyTerminal = (taskId, d) => {
    const key = `${taskId}:${d.status}`
    if (notifiedTerminal.has(key)) return
    notifiedTerminal.add(key)
    if (d.status === 'cancelled') return // 用户主动终止，父组件已提示，避免重复弹窗
    if (d.status === 'failed') ElMessage.error('任务执行失败')
    // 审批通过/定稿提交时已弹「已通过并定稿」，终态不再重复弹完成提示（避免看起来像两次操作）
    else if (!ctx.approvalHandled?.value) ElMessage.success('任务执行完成')
  }

  // 释放审批提交锁（approve/edit 后锁覆盖到终态/异常确认，期间重复点击被吞掉）
  const releaseApproving = () => {
    if (ctx.approving) ctx.approving.value = false
  }

  const finishRun = () => {
    ctx.running.value = false
    discardBuffers() // 丢弃未 flush 的半截增量（切任务/断开时不残留）
    if (streamCtl) {
      streamCtl.abort()
      streamCtl = null
    }
  }

  // SSE 断开后的兜底：直接查任务详情（任务可能仍在后台执行/待审批/已完成）
  const loadTaskDetailFallback = async (taskId, q) => {
    discardBuffers() // 详情以 DB 为准，丢弃流式残余
    try {
      const json = await fetchTaskDetail(taskId)
      if (json.code === 200 && json.data) {
        const d = json.data
        if (d.status === 'running') {
          ElMessage.info('连接中断，任务仍在后台执行，可稍后在历史记录中查看结果')
          return
        }
        ctx.activeStep.value = ctx.pipelineSteps.length
        ctx.currentTaskId.value = taskId
        ctx.taskResult.value = toTaskResult(d)
        mergePersistedThinking(d.steps) // 断线兜底：落库思考并入同一面板，不覆盖实时已展示内容
        if (d.status === 'awaiting_approval') {
          // 审批决策已提交后的迟到/重放 awaiting 状态：不切回"等待审批"、不弹提示
          if (ctx.approvalHandled?.value) return
          ctx.approvalEditContent.value = ctx.draftReport.value
          ctx.approvalMode.value = 'approve'
          ElMessage.warning('报告已生成，等待人工审批')
          return
        }
        ctx.pushHistoryItem(d, q)
        notifyTerminal(taskId, d)
        releaseApproving()
      }
    } catch {
      /* 静默 */
    }
  }

  // 步骤行合并进 taskResult.steps：任务一开始就把每个阶段的结果（summary/chips）展示出来，
  // 不再等终态报告。后端按 step 名唯一定位行（running 预写 → 完成后覆盖），前端同键 upsert。
  const mergeStep = (st) => {
    if (!st || !st.step) return
    const cur = ctx.taskResult.value
    const base = cur && typeof cur === 'object'
      ? { ...cur, steps: [...(cur.steps || [])] }
      : { status: 'running', steps: [], report: '', llm_used: false }
    const i = base.steps.findIndex(s => s && s.step === st.step)
    if (i >= 0) base.steps[i] = { ...base.steps[i], ...st }
    else base.steps.push({ ...st })
    ctx.taskResult.value = base
  }

  // SSE 订阅（创建任务与审批恢复共用）：真实节点进度 + 审批事件 + 终态报告
  const subscribeSse = (taskId, q) => {
    // 先关掉旧连接：重复订阅同一/别的任务时残留连接会各自重连、重复处理事件
    if (streamCtl) {
      streamCtl.abort()
      streamCtl = null
    }
    // 同一任务重连（切页回来 / 审批续跑）不清缓冲：已上屏内容继续显示，
    // 离开期间产出的增量由服务端首帧 report_snapshot 补齐；换任务才清
    bindStreamTask(taskId)
    discardBuffers() // 丢弃旧任务/旧轮次的未 flush 增量
    const ctl = new AbortController()
    streamCtl = ctl
    let closed = false
    // 只关"本连接"：不能用 finishRun 的全局变量（它可能已被新订阅覆盖，
    // 关错对象会让当前连接在服务端收尾后继续推送，形成 /stream 请求风暴）
    const shut = () => {
      if (closed) return
      closed = true
      ctl.abort()
      if (streamCtl === ctl) streamCtl = null
    }

    const handleEvent = (payload) => {
      if (closed) return

      if (payload.type === 'step') {
        // 三态：running=节点真正开始（转圈）；终态完成 → 推进到下一步
        const st = payload.step || {}
        mergeStep(st)
        const idx = ctx.pipelineSteps.findIndex(s => s.key === st.step)
        if (idx >= 0) {
          const status = st.status || 'completed'
          if (status === 'running' || status === 'awaiting') {
            ctx.activeStep.value = Math.max(ctx.activeStep.value, idx)
          } else if (status !== 'failed') {
            ctx.activeStep.value = Math.max(ctx.activeStep.value, idx + 1)
          }
        }
        // 进入报告生成即刻亮出流式打字壳（不等首个 delta；首轮 run 预置 1 防清缓冲）
        if (st.step === 'generate_report' && (st.status || 'completed') === 'running') {
          if (!ctx.streamRun.value) ctx.streamRun.value = 1
          ctx.streamActive.value = true
        }
      } else if (payload.type === 'think_reset') {
        // 复读截断（后端已把该轮思考截断到重复前的句子边界并以 note 落库）：
        // 丢弃缓冲中的未 flush 残余，用服务端截断版替换该轮实时思考（丢重复尾巴）；
        // 随后 run+1 的 report_think 会开新轮展示（「第 N 轮思考」分隔）
        discardBuffers()
        resetBodyStarted()
        truncateLiveThink(Number(payload.run) || 0, String(payload.text || ''))
      } else if (payload.type === 'report_snapshot') {
        // 通道补齐帧（订阅首帧）：本次连接建立前本轮已产出的正文/思考。
        // 没有它，「流式中切到别的页再回来」只会看到回来之后新增的尾巴（用户反馈）。
        discardBuffers()
        const run = Number(payload.run) || 0
        const rep = String(payload.report || '')
        const th = String(payload.think || '')
        const curRun = Number(ctx.streamRun.value) || 0
        if (run) ctx.streamRun.value = run
        // 同一轮：只在快照比本地更全时覆盖（本地已收到实时帧可能更多，不动它）；
        // 换了轮（离开期间被评审退回/驳回重写）：必须以快照为准，否则新轮增量会接在旧轮草稿尾巴上
        if (run !== curRun || rep.length > (ctx.streamReport.value || '').length) {
          ctx.streamReport.value = rep
          if (rep) markBodyStarted()
        }
        if (th) mergePersistedRounds([{ round: run || 1, text: th }])
        if (rep || th) ctx.streamActive.value = true
      } else if (payload.type === 'report_delta') {
        // 报告增量打字机：先入非响应式缓冲，180ms 批量 flush（性能：避免逐帧 O(n) 响应式重算）
        pushDelta(payload.run, payload.text || '')
      } else if (payload.type === 'report_think') {
        // 思考过程增量（qwen3 / DeepSeek 系模型 <think> 段）：本轮思考先在
        // 「分析报告」流式卡展示（两段式），正文首个 delta 后迁回第 5 节点面板
        // 同样入缓冲批量 flush；思考紧接上一轮末尾追加，不清空、不覆盖
        pushThink(payload.run, payload.text || '')
      } else if (payload.type === 'approval') {
        discardBuffers() // 审批草稿来自 DB 详情，丢弃流式残余增量
        // 审批决策已提交（approve/edit）后迟到/重放的审批事件：吞掉——
        // 不把界面切回"等待审批"，不再弹提示；仅关闭本连接
        if (ctx.approvalHandled?.value) {
          shut()
          ctx.running.value = false
          releaseApproving()
          return
        }
        // HITL：任务在审批闸口暂停（草稿在 approval 步骤的 draft_report 中，未落报告中心）
        const d = payload.data || {}
        ctx.activeStep.value = ctx.pipelineSteps.length
        ctx.currentTaskId.value = d.id || taskId
        ctx.taskResult.value = { ...toTaskResult(d), status: d.status || 'awaiting_approval' }
        ctx.streamReport.value = ctx.draftReport.value  // 用审批草稿替换流式缓冲
        mergePersistedThinking(d.steps)                  // 思考保留并合并落库内容
        ctx.streamActive.value = false
        ctx.approvalMode.value = 'approve'
        ctx.approvalEditContent.value = ctx.draftReport.value
        ElMessage.warning('报告已生成，等待人工审批')
        shut()
        ctx.running.value = false
      } else if (payload.type === 'report') {
        // 终态（completed/failed）：完整报告以 DB 内容为准，替换流式缓冲
        discardBuffers() // 终态全量覆盖，丢弃流式残余
        const d = payload.data || {}
        ctx.streamReport.value = d.report || ''
        mergePersistedThinking(d.steps) // 终态思考回填：与实时内容按轮次合并，不清空
        ctx.streamActive.value = false
        ctx.activeStep.value = ctx.pipelineSteps.length
        ctx.taskResult.value = toTaskResult(d)
        ctx.pushHistoryItem(d, q)
        notifyTerminal(taskId, d)
        shut()
        ctx.running.value = false
        releaseApproving() // 审批锁覆盖到终态确认（approve/edit 提交后的兜底释放）
      } else if (payload.type === 'error') {
        discardBuffers()
        ElMessage.error(payload.message || '进度推送异常')
        ctx.streamActive.value = false
        shut()
        ctx.running.value = false
        releaseApproving()
        ctx.syncHistoryFromApi()
      }
    }

    // 读取 SSE 帧：fetch 流没有 EventSource 的自动重连，断线一律走详情兜底
    // （与改造前行为一致：改造前 onerror 里也是 shut() + loadTaskDetailFallback）
    const onBrokenStream = () => {
      if (closed) return
      discardBuffers() // 断线：丢弃未 flush 的半截增量，终态以详情接口为准
      ctx.streamActive.value = false
      shut()
      ctx.running.value = false
      loadTaskDetailFallback(taskId, q)
    }

    ;(async () => {
      try {
        const res = await openTaskStream(taskId, { signal: ctl.signal })
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''
        for (;;) {
          const { value, done } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const frames = buf.split('\n\n')
          buf = frames.pop() || ''
          for (const frame of frames) {
            const line = frame.split('\n').find(l => l.startsWith('data: '))
            if (!line) continue // ': ping' 心跳注释帧
            let payload
            try { payload = JSON.parse(line.slice(6)) } catch { continue }
            handleEvent(payload)
            if (closed) return // 终态/审批已收尾：本连接不再读
          }
        }
        onBrokenStream() // 流被服务端/代理关闭且未见终态 → 兜底查详情
      } catch (e) {
        if (closed || e?.name === 'AbortError') return // shut() 主动断开，属正常收尾
        onBrokenStream()
      }
    })()
  }

  return { finishRun, subscribeSse }
}
