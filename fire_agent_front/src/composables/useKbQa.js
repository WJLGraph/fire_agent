/**
 * 知识库问答状态（模块级单例）
 *
 * 与 Agent 中心同理：问答有时耗时较久，切页/返回不能丢进度。
 * 状态放在模块作用域而非组件内 —— 组件卸载只断视图，fetch 流在模块里继续跑，
 * 回到知识库页面时同一段响应式状态重新挂载：流式进行中继续打字，已完成的直接回显。
 *
 * 任务进程管理（参考 Agent 中心「任务进程」）：
 * 每次提问登记为一条任务（kbTasks），实时推进阶段（检索中 → 深度思考中 → 生成回答中），
 * 进行中的任务可终止（AbortController 断开流式连接）；终态结果由后端 rag_history 落库，
 * 「已结束」列表以服务端历史为准（本地仅保留失败/终止/已转后台的会话内记录）。
 */
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { ask, askStream } from '@/api/rag'

// ====== 模块级单例状态（跨页面存活） ======
const question = ref('')
const asking = ref(false)
const answerResult = ref(null)
// 流式增量缓冲（半截内容不落库，done 后以完整结果为准）
const streamAnswer = ref('')
const streamMeta = ref(null)
// 思考过程缓冲（qwen3 / DeepSeek 系模型 <think> 段，流式"深度思考中"展示）
const streamThink = ref('')

// ====== 任务进程（会话内登记，实时阶段推进；终态以服务端历史为准） ======
// task: { key, question, startedAt, status: running|done|failed|cancelled|archived,
//         phase: 检索中|推理中|深度思考中|生成回答中, model, matched, _cancel() }
const kbTasks = ref([])

// 当前活跃流的取消句柄（仅最新提问可终止；旧流已让出 UI，由服务端跑完入档）
let abortCtl = null

// 僵尸任务看门狗：运行超 10 分钟的任务强制判超时（正常链路：流式 240s 上限 + 非流式
// 兜底 120s×Provider 链，远小于此）；防服务端极端挂死导致"进行中"永久滞留
let watchdogTimer = null
const WATCHDOG_MS = 10 * 60 * 1000
if (!watchdogTimer) {
  watchdogTimer = setInterval(() => {
    const now = Date.now()
    for (const t of kbTasks.value) {
      if (t.status === 'running' && now - t.startedAt > WATCHDOG_MS) {
        t.status = 'failed'
        t.phase = '超时'
        if (t.key === qaSeq) {
          abortCtl?.abort()
          asking.value = false
          ElMessage.error('问答任务超时（超过 10 分钟无响应），已自动终止')
        }
      }
    }
  }, 5000)
}

// 问答序号：允许重复/连续提问（不拦截）。旧流未结束又发新问时，
// 旧流让出状态所有权（停写 UI、服务端照常跑完并入档），展示层始终跟随最新提问。
let qaSeq = 0

/** 终止问答任务：仅进行中且仍是当前流的任务可终止 */
export function cancelKbTask(key) {
  const t = kbTasks.value.find(x => x.key === key)
  if (t && t.status === 'running') t._cancel?.()
}

export function useKbQa({ onFinished } = {}) {
  const askQuestion = async () => {
    const q = question.value.trim()
    if (!q) {
      ElMessage.warning('请输入问题')
      return
    }

    // 旧running任务转「已转后台」：服务端继续执行并存档，前端不再观测
    for (const t of kbTasks.value) {
      if (t.status === 'running') t.status = 'archived'
    }

    const mySeq = ++qaSeq
    asking.value = true
    answerResult.value = null
    streamAnswer.value = ''
    streamMeta.value = null
    streamThink.value = ''

    // reactive 包装：后续 task.status/phase 的原地修改才能触发依赖它的
    // computed（抽屉"进行中"列表、页头徽标）重算——裸对象改属性不触发响应式，
    // 会出现"回答已完成、任务进程仍显示生成中"的假状态（用户反馈修复）
    const task = reactive({ key: mySeq, question: q, startedAt: Date.now(), status: 'running', phase: '检索中', model: '', matched: null })
    kbTasks.value = [task, ...kbTasks.value].slice(0, 30)

    let cancelled = false
    task._cancel = () => { cancelled = true; abortCtl?.abort() }

    const stale = () => mySeq !== qaSeq // 已有更新提问接管状态

    try {
      // 流式接口（SSE；EventSource 不支持 POST，用 fetch reader 解析）
      abortCtl = new AbortController()
      const res = await askStream(q, 5, { signal: abortCtl.signal })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done || stale()) break
        buf += decoder.decode(value, { stream: true })
        const frames = buf.split('\n\n')
        buf = frames.pop() || ''
        for (const frame of frames) {
          const line = frame.split('\n').find(l => l.startsWith('data: '))
          if (!line) continue
          let ev
          try { ev = JSON.parse(line.slice(6)) } catch { continue }
          if (ev.type === 'meta') {
            streamMeta.value = ev.retrieval || null   // 检索元信息先行渲染
            task.phase = '推理中'
          } else if (ev.type === 'think') {
            streamThink.value += ev.text || ''        // 思考过程增量（折叠面板实时展示）
            task.phase = '深度思考中'
          } else if (ev.type === 'delta') {
            streamAnswer.value += ev.text || ''       // 回答增量打字机
            task.phase = '生成回答中'
          } else if (ev.type === 'done') {
            answerResult.value = ev.result            // 终态完整结果（与 /ask 契约一致）
          } else if (ev.type === 'error') {
            throw new Error(ev.message || '流式回答失败')
          }
          if (stale()) break
        }
      }
      if (stale()) { task.status = 'archived'; return } // 旧流静默退出：服务端仍会存档，历史列表可见
      if (cancelled) { task.status = 'cancelled'; return }
      if (!answerResult.value) throw new Error('流式回答未返回结果')
      task.status = 'done'
      task.model = answerResult.value.llm_model || ''
      task.matched = answerResult.value.references?.length ?? answerResult.value.retrieval?.matched ?? null
      onFinished && onFinished('ok')
    } catch (e) {
      if (stale()) { task.status = 'archived'; return }
      if (cancelled || e?.name === 'AbortError') { task.status = 'cancelled'; return }
      task.phase = '生成回答中'
      // 流式失败/不支持 → 回退非流式接口，保证总能拿到回答
      try {
        const json = await ask(q, 5)
        if (stale()) { task.status = 'archived'; return }
        if (cancelled) { task.status = 'cancelled'; return }
        if (json.code === 200) {
          answerResult.value = json.data
          task.status = 'done'
          task.model = json.data.llm_model || ''
          task.matched = json.data.references?.length ?? json.data.retrieval?.matched ?? null
          onFinished && onFinished('ok')
        } else {
          task.status = 'failed'
          ElMessage.error('查询失败: ' + (json.detail || json.message))
          onFinished && onFinished('error')
        }
      } catch (e2) {
        if (stale()) { task.status = 'archived'; return }
        if (cancelled) { task.status = 'cancelled'; return }
        task.status = 'failed'
        ElMessage.error('网络错误: ' + (e2.message || e.message || e2))
        onFinished && onFinished('error')
      }
    } finally {
      if (task._cancel) delete task._cancel
      if (!stale()) {
        asking.value = false
        if (task.status === 'done') {
          streamAnswer.value = ''
          streamMeta.value = null
          // streamThink 保留：完成后折叠面板"已深度思考"仍可回看
        } else {
          // 失败/终止：流式缓冲一并清掉，避免残留半截内容
          streamAnswer.value = ''
          streamMeta.value = null
          streamThink.value = ''
        }
      }
    }
  }

  return { question, asking, answerResult, streamAnswer, streamMeta, streamThink, kbTasks, askQuestion }
}
