<script setup>
/**
 * 知识库 · 问答任务进程抽屉（对齐 Agent 中心 TaskProcessDrawer 交互）
 *
 * 页头常驻入口（带活跃数徽标）→ 右侧抽屉，分「进行中 / 已结束」管理问答任务：
 * - 进行中：本地任务实时阶段（检索中 → 深度思考中 → 生成回答中）+ 已用时 + 终止；
 * - 已结束：服务端历史（已完成，可查看/删除）+ 会话内失败/终止/已转后台记录；
 *   时间统一「年月日 + 时间」。数据请求与状态变更由事件上抛，本组件只负责展示与计时。
 */
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 会话内任务（useKbQa kbTasks）：running / failed / cancelled / archived
  tasks: { type: Array, default: () => [] },
  // 服务端历史（rag_history）：{ id, text, time, llm_model, llm_used, matched }
  history: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'cancel', 'view', 'delete', 'clear'])

const tab = ref('active')
const now = ref(Date.now())
const panelRef = ref(null)
let prevFocus = null
let tickTimer = null

const runningTasks = computed(() => props.tasks.filter(t => t.status === 'running'))
// 已结束：本地（失败/终止/已转后台，且服务端历史中尚无同问题记录）+ 服务端历史，时间倒序
const endedList = computed(() => {
  const histTexts = new Set(props.history.map(h => h.text))
  const local = props.tasks
    .filter(t => t.status !== 'running' && t.status !== 'done' && !histTexts.has(t.question))
    .map(t => ({ kind: 'live', ...t, time: fmtTs(t.startedAt), text: t.question }))
  const hist = props.history.map(h => ({ kind: 'hist', ...h }))
  return [...local, ...hist]
    .sort((a, b) => parseTime(b.time) - parseTime(a.time))
    .slice(0, 60)
})

// ===== 状态徽标 =====
const liveCls = 'run'
const liveLabel = (t) => ({
  '检索中': '检索中',
  '推理中': '推理中',
  '深度思考中': '深度思考中',
  '生成回答中': '生成回答中',
}[t.phase] || '执行中')

const statusText = (t) => ({
  failed: '失败',
  cancelled: '已终止',
  archived: '已转后台',
}[t.status] || (t.kind === 'hist' ? '已完成' : '已结束'))
const statusCls = (t) => ({
  failed: 'fail',
  cancelled: 'cancel',
  archived: 'back',
}[t.status] || 'ok')

const histModel = (t) => t.llm_model || (t.llm_used ? 'LLM' : '检索')

// ===== 时间 =====
const p2 = (n) => String(n).padStart(2, '0')
// 年月日 + 时间（完整），与历史存档展示一致
const fmtTs = (ms) => {
  const d = new Date(ms)
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`
}
// "2026-11-02 10:00:00" → 本地时间戳（避免部分浏览器把空格格式当 UTC 解析）
const parseTime = (s) => {
  if (!s) return 0
  const t = new Date(String(s).replace(' ', 'T')).getTime()
  return Number.isFinite(t) ? t : 0
}
const formatSec = (sec) => {
  if (sec === null || sec === undefined) return '—'
  const n = Math.max(0, Math.round(sec))
  if (n < 60) return `${n}s`
  if (n < 3600) return `${Math.floor(n / 60)}m${n % 60 ? `${n % 60}s` : ''}`
  return `${Math.floor(n / 3600)}h${Math.floor((n % 3600) / 60)}m`
}
const elapsedSec = (t) => Math.max(0, (now.value - t.startedAt) / 1000)

// 已转后台任务：服务端执行完后入档，此处提供「查看」时尝试定位最新同问题历史
const viewEnded = (t) => {
  if (t.kind === 'hist') { emit('view', t); return }
  const match = [...props.history].reverse().find(h => h.text === t.question)
  if (match) emit('view', match)
}

const stopTimers = () => {
  if (tickTimer) { clearInterval(tickTimer); tickTimer = null }
}
const startTimers = () => {
  stopTimers()
  now.value = Date.now()
  tickTimer = setInterval(() => { now.value = Date.now() }, 1000)
}

// ===== 无障碍：Esc 关闭 + 焦点留抽屉 + 关闭后焦点回到入口 =====
const onKeydown = (e) => {
  if (e.key === 'Escape') {
    e.stopPropagation()
    close()
  }
}
watch(() => props.modelValue, (open) => {
  if (open) {
    prevFocus = document.activeElement
    startTimers()
    document.addEventListener('keydown', onKeydown, true)
    nextTick(() => panelRef.value?.focus())
  } else {
    stopTimers()
    document.removeEventListener('keydown', onKeydown, true)
    prevFocus?.focus?.()
  }
}, { immediate: true })
onUnmounted(() => {
  stopTimers()
  document.removeEventListener('keydown', onKeydown, true)
})

const close = () => emit('update:modelValue', false)
</script>

<template>
  <Teleport to="body">
    <Transition name="kt">
      <div v-if="modelValue" class="kt-mask" @click.self="close">
        <aside ref="panelRef" class="kt" role="dialog" aria-modal="true" aria-labelledby="kt-title" tabindex="-1">
          <header class="kt__hd">
            <div class="kt__hd-t">
              <h3 id="kt-title" class="kt__title">问答任务 · 任务进程</h3>
              <p class="kt__sub" aria-live="polite">
                {{ runningTasks.length }} 个进行中 · 共 {{ history.length }} 条存档
              </p>
            </div>
            <button class="kt__close" aria-label="关闭任务进程" title="关闭" @click="close">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M6 6l8 8M14 6l-8 8"/></svg>
            </button>
          </header>

          <div class="kt__tabs">
            <button class="kt__tab" :class="{ 'is-on': tab === 'active' }" @click="tab = 'active'">
              进行中<span v-if="runningTasks.length" class="kt__tab-n">{{ runningTasks.length }}</span>
            </button>
            <button class="kt__tab" :class="{ 'is-on': tab === 'done' }" @click="tab = 'done'">
              已结束<span v-if="endedList.length" class="kt__tab-n kt__tab-n--muted">{{ endedList.length }}</span>
            </button>
          </div>

          <div class="kt__bd">
            <!-- 进行中：实时阶段 + 已用时 + 终止 -->
            <template v-if="tab === 'active'">
              <div v-for="t in runningTasks" :key="t.key" class="kt-task">
                <div class="kt-task__top">
                  <span class="kt-st" :class="liveCls"><i></i>{{ liveLabel(t) }}</span>
                  <span class="kt__sp"></span>
                  <span class="kt-task__time mono">已用时 {{ formatSec(elapsedSec(t)) }}</span>
                </div>
                <p class="kt-task__q" :title="t.question">{{ t.question }}</p>
                <div class="kt-task__ops">
                  <span class="kt-task__note">切换页面不会中断回答，完成后自动入档</span>
                  <button class="kt-btn kt-btn--danger" @click="emit('cancel', t)">终止</button>
                </div>
              </div>
              <div v-if="!runningTasks.length" class="kt-empty">
                <span class="kt-empty__t">暂无进行中的问答任务</span>
                <span class="kt-empty__h">提交提问后，这里会实时显示检索 / 思考 / 生成进度</span>
              </div>
            </template>

            <!-- 已结束：服务端存档 + 会话内失败/终止/已转后台 -->
            <template v-else>
              <div v-for="(t, i) in endedList" :key="(t.id ?? `live-${t.key}`) + '-' + i" class="kt-task" :class="{ 'is-dim': t.kind === 'live' }">
                <div class="kt-task__top">
                  <span class="kt-st" :class="statusCls(t)"><i></i>{{ statusText(t) }}</span>
                  <span v-if="t.kind === 'hist' && t.llm_used" class="kt-task__model" :title="`回答模型 ${histModel(t)}`">{{ histModel(t) }}</span>
                  <span class="kt__sp"></span>
                  <span class="kt-task__time mono">{{ t.time }}</span>
                </div>
                <p class="kt-task__q" :title="t.text">{{ t.text }}</p>
                <div class="kt-task__ops">
                  <span
                    v-if="t.kind === 'hist'"
                    class="kt-task__hit"
                    :class="{ ok: t.matched > 0 }"
                  >{{ t.matched > 0 ? `命中 ${t.matched} 片段` : '未命中' }}</span>
                  <span v-else class="kt-task__note">{{ t.status === 'archived' ? '服务端执行完毕后自动入档' : '未产生存档结果' }}</span>
                  <span class="kt__sp"></span>
                  <button
                    v-if="t.kind === 'hist' || t.status === 'archived'"
                    class="kt-btn"
                    @click="viewEnded(t)"
                  >查看</button>
                  <button v-if="t.kind === 'hist'" class="kt-btn kt-btn--danger" @click="emit('delete', t)">删除</button>
                </div>
              </div>
              <div v-if="!endedList.length" class="kt-empty">
                <span class="kt-empty__t">暂无已结束的任务</span>
              </div>
              <div v-if="history.length" class="kt__ft">
                <button class="kt-btn kt-btn--clear" @click="emit('clear')">清空全部存档</button>
              </div>
            </template>
          </div>

          <footer class="kt__ftbar">回答由服务端持久化存档，关闭面板不会中断进行中的任务</footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.kt-mask {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(12, 16, 20, 0.34);
  display: flex;
  justify-content: flex-end;
}
.kt {
  width: 440px;
  max-width: 92vw;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-left: 1px solid var(--fs-hairline);
  box-shadow: -18px 0 48px rgba(0, 0, 0, 0.18);
}
.kt-enter-active, .kt-leave-active { transition: opacity 160ms var(--fs-ease-out, ease); }
.kt-enter-active .kt, .kt-leave-active .kt { transition: transform 200ms var(--fs-ease-out, ease); }
.kt-enter-from, .kt-leave-to { opacity: 0; }
.kt-enter-from .kt, .kt-leave-to .kt { transform: translateX(100%); }

.kt__hd {
  flex-shrink: 0;
  padding: 18px 18px 14px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border-bottom: 1px solid var(--fs-hairline);
}
.kt__hd-t { min-width: 0; }
/* 标题 2px 刻度条：静息发丝、悬停转强调 */
.kt__title {
  margin: 0;
  display: inline-flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  color: var(--fs-ink-900);
}
.kt__title::before {
  content: '';
  width: 2px;
  height: 12px;
  margin-right: 8px;
  border-radius: 1px;
  background: var(--fs-hairline-strong);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, ease);
}
.kt__hd:hover .kt__title::before { background: var(--fs-accent); }
.kt__sub { margin: 3px 0 0; font-size: 11px; color: var(--fs-ink-500); font-variant-numeric: tabular-nums; }
.kt__close {
  margin-left: auto;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  background: transparent;
  color: var(--fs-ink-500);
  cursor: pointer;
  transition:
    background-color var(--up-dur-fast, 120ms) var(--fs-ease),
    color var(--up-dur-fast, 120ms) var(--fs-ease);
}
.kt__close:hover { background: var(--fs-bg-sunken); color: var(--fs-ink-900); }
.kt__close svg { width: 16px; height: 16px; }

.kt__tabs {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 10px 14px 0;
}
.kt__tab {
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  background: transparent;
  color: var(--fs-ink-500);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color var(--up-dur-fast, 120ms) var(--fs-ease),
    color var(--up-dur-fast, 120ms) var(--fs-ease),
    box-shadow var(--up-dur-fast, 120ms) var(--fs-ease);
}
.kt__tab:hover { color: var(--fs-ink-900); }
.kt__tab.is-on { background: var(--fs-bg-sunken); color: var(--fs-ink-900); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14); }
.kt__tab-n {
  margin-left: 5px;
  padding: 0 5px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}
.kt__tab-n--muted { background: var(--fs-bg-sunken); color: var(--fs-ink-500); }
.kt__sp { flex: 1; }

.kt__bd {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

.kt-task {
  padding: 12px 13px;
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  background: var(--fs-bg-surface);
  animation: kt-in 0.36s var(--fs-ease-out) both;
  transition: box-shadow var(--up-dur-fast, 120ms) var(--fs-ease);
}
.kt-task:hover { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong), var(--fs-e1); }
/* 只位移不透明度：避免 fill 覆盖 is-dim 的弱化透明度 */
@keyframes kt-in {
  from { transform: translateY(6px); }
  to { transform: none; }
}
.kt-task.is-dim { opacity: 0.82; }
.kt-task__top { display: flex; align-items: center; gap: 8px; min-width: 0; }
.kt-task__model {
  height: 16px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  font-size: 10px;
  max-width: 110px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.kt-task__time { font-size: 10.5px; color: var(--fs-ink-500); white-space: nowrap; font-variant-numeric: tabular-nums; }
.kt-task__q {
  margin: 8px 0 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--fs-ink-900);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.kt-task__ops { margin-top: 10px; display: flex; align-items: center; gap: 8px; }
.kt-task__note { flex: 1; min-width: 0; font-size: 10px; color: var(--fs-ink-400); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kt-task__hit { font-size: 10.5px; color: var(--fs-ink-400); white-space: nowrap; }
.kt-task__hit.ok { color: var(--fs-success); }
.kt__ft { display: flex; justify-content: center; padding-top: 2px; }

.kt-btn {
  height: 24px;
  padding: 0 10px;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background-color var(--up-dur-fast, 120ms) var(--fs-ease),
    color var(--up-dur-fast, 120ms) var(--fs-ease),
    box-shadow var(--up-dur-fast, 120ms) var(--fs-ease);
}
.kt-btn:hover { background: var(--fs-hairline); color: var(--fs-ink-900); box-shadow: var(--fs-e1); }
.kt-btn--danger { color: var(--fs-danger); }
.kt-btn--danger:hover { background: var(--fs-danger-soft, #fdecec); color: var(--fs-danger); box-shadow: var(--fs-e1); }
.kt-btn--clear { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); background: transparent; color: var(--fs-ink-500); }
.kt-btn--clear:hover { color: var(--fs-danger); box-shadow: inset 0 0 0 1px var(--fs-danger); background: transparent; }

/* 状态点 */
.kt-st { display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; white-space: nowrap; color: var(--fs-ink-500); }
.kt-st i { width: 5px; height: 5px; border-radius: 999px; background: currentColor; }
.kt-st.run { color: var(--fs-accent); }
.kt-st.run i { animation: kt-pulse 1.4s ease-in-out infinite; }
.kt-st.ok { color: var(--fs-success); }
.kt-st.fail { color: var(--fs-danger); }
.kt-st.cancel, .kt-st.back { color: var(--fs-ink-400); }
@keyframes kt-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.kt-empty {
  flex: 1;
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--fs-ink-400);
}
.kt-empty__t { font-size: 13px; color: var(--fs-ink-500); }
.kt-empty__h { font-size: 11px; }

.kt__ftbar {
  flex-shrink: 0;
  padding: 10px 18px;
  border-top: 1px solid var(--fs-hairline);
  font-size: 10px;
  color: var(--fs-ink-400);
}
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; }
.kt:focus-visible { outline: none; }

/* ===== 动效闸门：关闭时循环状态点停呼吸、卡片入场落终态 ===== */
html[data-motion-allowed="false"] .kt-st.run i,
html[data-motion-allowed="false"] .kt-task { animation: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .kt-st.run i,
  html:not([data-motion="on"]) .kt-task { animation: none; }
}
</style>
