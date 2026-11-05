<script setup>
/**
 * Agent 协作中心 · 任务进程抽屉
 *
 * 现代任务中心的常见形态：页头一个常驻入口（带活跃数徽标），点开右侧抽屉，
 * 分「进行中 / 已结束」查看全部任务，支持定位、终止、重试。
 * 本组件只负责展示与轮询；终止/重试动作交给父组件复用既有 API 逻辑。
 */
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { fetchTasks } from '@/api/agent'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  currentTaskId: { type: [Number, String], default: null },
  // 待审批超过该小时数视为滞留（由后端 /agent/status 下发，前后端同源）
  staleHours: { type: Number, default: 24 },
})
const emit = defineEmits(['update:modelValue', 'select', 'cancel', 'retry', 'new-task'])

const tasks = ref([])
const loading = ref(false)
const tab = ref('active')
const now = ref(Date.now())
const panelRef = ref(null)
let prevFocus = null
let pollTimer = null
let tickTimer = null

const ACTIVE_STATUS = ['running', 'pending', 'awaiting_approval']
const isActive = (s) => ACTIVE_STATUS.includes(s)

const activeTasks = computed(() => tasks.value.filter(t => isActive(t.status)))
const doneTasks = computed(() => tasks.value.filter(t => !isActive(t.status)).slice(0, 30))
const runningCount = computed(() => tasks.value.filter(t => t.status === 'running').length)
const pendingCount = computed(() => tasks.value.filter(t => t.status === 'pending').length)

// 待审批分两种：新鲜（真正等人处理）与滞留（超时未处理，多为测试遗留）。
// 抽屉把滞留单独成页，避免和"正在运行"的进程混在一起，页头也不会被滞留数点亮。
const isStaleAwaiting = (t) => {
  if (t.status !== 'awaiting_approval') return false
  const start = parseTime(t.started_at || t.created_at)
  return start > 0 && (now.value - start) > props.staleHours * 3600 * 1000
}
const liveTasks = computed(() => activeTasks.value.filter(t => !isStaleAwaiting(t)))
const staleTasks = computed(() => activeTasks.value.filter(isStaleAwaiting))
const awaitingCount = computed(() => liveTasks.value.filter(t => t.status === 'awaiting_approval').length)
const staleCount = computed(() => staleTasks.value.length)

// 清空滞留后自动回到「进行中」，避免停留在空页
watch(staleCount, (n) => {
  if (!n && tab.value === 'stale') tab.value = 'active'
})

const statusText = (s) => ({
  running: '执行中',
  pending: '排队中',
  awaiting_approval: '待审批',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}[s] || s || '未知')

const statusCls = (s) => ({
  running: 'run',
  pending: 'wait',
  awaiting_approval: 'appr',
  completed: 'ok',
  failed: 'fail',
  cancelled: 'cancel',
}[s] || 'wait')

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
  if (n < 86400) return `${Math.floor(n / 3600)}h${Math.floor((n % 3600) / 60)}m`
  return `${Math.floor(n / 86400)}天`
}

const elapsedSec = (t) => {
  const start = parseTime(t.started_at || t.created_at)
  return start ? (now.value - start) / 1000 : null
}

// 不同状态看不同的时间：执行中看已运行、排队看已等待、待审批看等待审批、
// 滞留看已滞留多久、终态看总耗时
const timing = (t) => {
  if (t.status === 'awaiting_approval') {
    return { label: isStaleAwaiting(t) ? '滞留' : '等待审批', value: formatSec(elapsedSec(t)) }
  }
  if (t.status === 'pending') return { label: '排队', value: formatSec(elapsedSec(t)) }
  if (isActive(t.status)) return { label: '已运行', value: formatSec(elapsedSec(t)) }
  return { label: '耗时', value: formatSec(typeof t.duration === 'number' ? t.duration : elapsedSec(t)) }
}

const progress = (t) => t.progress || { done: 0, total: 7, percent: 0 }
const progressPercent = (t) => {
  const p = progress(t)
  if (typeof p.percent === 'number') return Math.min(100, Math.max(0, p.percent))
  return Math.min(100, Math.round((p.done / (p.total || 7)) * 100))
}

const refresh = async () => {
  if (!props.modelValue) return
  loading.value = !tasks.value.length
  try {
    const json = await fetchTasks()
    if (json.code === 200 && Array.isArray(json.data)) tasks.value = json.data
  } catch {
    /* 静默：抽屉轮询失败不打扰主流程 */
  } finally {
    loading.value = false
  }
}

const stopTimers = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (tickTimer) { clearInterval(tickTimer); tickTimer = null }
}

// ===== 无障碍：Esc 关闭 + 焦点留在抽屉内 + 关闭后焦点回到入口按钮 =====
const focusables = () => {
  if (!panelRef.value) return []
  return Array.from(panelRef.value.querySelectorAll(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  ))
}
const onKeydown = (e) => {
  if (e.key === 'Escape') {
    e.stopPropagation()
    close()
    return
  }
  if (e.key !== 'Tab') return
  const items = focusables()
  if (!items.length) return
  const first = items[0]
  const last = items[items.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

const startTimers = () => {
  stopTimers()
  now.value = Date.now()
  refresh()
  pollTimer = setInterval(refresh, 3000)
  tickTimer = setInterval(() => { now.value = Date.now() }, 1000)
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
const select = (t) => emit('select', t)
const cancel = (t) => emit('cancel', t)
const retry = (t) => emit('retry', t)
const newTask = () => emit('new-task')

defineExpose({ refresh })
</script>

<template>
  <Teleport to="body">
    <Transition name="tp">
      <div v-if="modelValue" class="tp-mask" @click.self="close">
        <aside ref="panelRef" class="tp" role="dialog" aria-modal="true" aria-labelledby="tp-title" aria-describedby="tp-sub" tabindex="-1">
          <header class="tp__hd">
            <div class="tp__hd-t">
              <h3 id="tp-title" class="tp__title">任务进程</h3>
              <p id="tp-sub" class="tp__sub" aria-live="polite">
                {{ liveTasks.length }} 个进行中<template v-if="runningCount"> · {{ runningCount }} 执行中</template><template v-if="pendingCount"> · {{ pendingCount }} 排队中</template><template v-if="awaitingCount"> · {{ awaitingCount }} 待审批</template><template v-if="staleCount"> · {{ staleCount }} 条滞留</template>
              </p>
            </div>
            <button class="tp__close" aria-label="关闭任务进程" title="关闭" @click="close">
              <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M6 6l8 8M14 6l-8 8"/></svg>
            </button>
          </header>

          <div class="tp__tabs">
            <button class="tp__tab" :class="{ 'is-on': tab === 'active' }" :aria-pressed="tab === 'active'" @click="tab = 'active'">
              进行中<span v-if="liveTasks.length" class="tp__tab-n">{{ liveTasks.length }}</span>
            </button>
            <button v-if="staleCount" class="tp__tab" :class="{ 'is-on': tab === 'stale' }" :aria-pressed="tab === 'stale'" @click="tab = 'stale'">
              滞留<span class="tp__tab-n tp__tab-n--warn">{{ staleCount }}</span>
            </button>
            <button class="tp__tab" :class="{ 'is-on': tab === 'done' }" :aria-pressed="tab === 'done'" @click="tab = 'done'">已结束</button>
            <span class="tp__sp"></span>
            <button class="tp__refresh" :disabled="loading" aria-label="立即刷新任务列表" title="立即刷新" @click="refresh">
              <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M16.4 8.4A6.6 6.6 0 1 0 10 16.6a6.6 6.6 0 0 0 4.6-1.9"/><path d="M16.6 3.6v5h-5"/></svg>
              刷新
            </button>
          </div>

          <div v-loading="loading" class="tp__bd">
            <!-- 进行中 -->
            <template v-if="tab === 'active'">
              <div v-for="t in liveTasks" :key="t.id" class="tp-task" :class="{ 'is-cur': String(t.id) === String(currentTaskId) }">
                <div class="tp-task__top">
                  <span class="tp-st" :class="statusCls(t.status)"><i aria-hidden="true"></i>{{ statusText(t.status) }}</span>
                  <span class="tp-task__id mono">#{{ t.id }}</span>
                  <span class="tp__sp"></span>
                  <span class="tp-task__time mono">{{ timing(t).label }} {{ timing(t).value }}</span>
                </div>
                <p class="tp-task__q" :title="t.query">{{ t.query }}</p>
                <div class="tp-task__prog">
                  <div class="tp-bar" role="progressbar" :aria-valuenow="progressPercent(t)" aria-valuemin="0" aria-valuemax="100" :aria-label="`任务 #${t.id} 进度`"><i :style="{ transform: `scaleX(${progressPercent(t) / 100})` }"></i></div>
                  <span class="tp-task__meta mono">{{ t.current_agent || '等待调度' }} · {{ progress(t).done }}/{{ progress(t).total }}</span>
                </div>
                <div class="tp-task__ops">
                  <button class="tp-btn" :aria-label="`${t.status === 'awaiting_approval' ? '去审批' : '查看'}任务 #${t.id}`" @click="select(t)">{{ t.status === 'awaiting_approval' ? '去审批' : '查看' }}</button>
                  <button class="tp-btn tp-btn--danger" :aria-label="`终止任务 #${t.id}`" @click="cancel(t)">终止</button>
                </div>
              </div>
              <div v-if="!loading && !liveTasks.length" class="tp-empty">
                <span class="tp-empty__t">暂无进行中的任务</span>
                <span class="tp-empty__h">{{ staleCount ? `有 ${staleCount} 条待审批已滞留，可在「滞留」中处理` : '提交任务后，这里会实时显示执行进度' }}</span>
                <button v-if="staleCount" class="tp-btn tp-empty__cta" @click="tab = 'stale'">查看滞留任务</button>
                <button v-else class="tp-btn tp-empty__cta" @click="newTask">新建任务</button>
              </div>
            </template>

            <!-- 滞留待审批（超过阈值未处理，不计入页头实时状态） -->
            <template v-else-if="tab === 'stale'">
              <p class="tp-note">超过 {{ staleHours }} 小时未审批，已标记为滞留；可继续审批或终止。</p>
              <div v-for="t in staleTasks" :key="t.id" class="tp-task tp-task--stale" :class="{ 'is-cur': String(t.id) === String(currentTaskId) }">
                <div class="tp-task__top">
                  <span class="tp-st" :class="statusCls(t.status)"><i aria-hidden="true"></i>{{ statusText(t.status) }}</span>
                  <span class="tp-task__id mono">#{{ t.id }}</span>
                  <span class="tp__sp"></span>
                  <span class="tp-task__time mono">{{ timing(t).label }} {{ timing(t).value }}</span>
                </div>
                <p class="tp-task__q" :title="t.query">{{ t.query }}</p>
                <div class="tp-task__ops">
                  <button class="tp-btn" :aria-label="`去审批任务 #${t.id}`" @click="select(t)">去审批</button>
                  <button class="tp-btn tp-btn--danger" :aria-label="`终止任务 #${t.id}`" @click="cancel(t)">终止</button>
                </div>
              </div>
            </template>

            <!-- 已结束 -->
            <template v-else>
              <div v-for="t in doneTasks" :key="t.id" class="tp-task tp-task--done" :class="{ 'is-cur': String(t.id) === String(currentTaskId) }">
                <div class="tp-task__top">
                  <span class="tp-st" :class="statusCls(t.status)"><i aria-hidden="true"></i>{{ statusText(t.status) }}</span>
                  <span class="tp-task__id mono">#{{ t.id }}</span>
                  <span class="tp__sp"></span>
                  <span class="tp-task__time mono">{{ timing(t).label }} {{ timing(t).value }}</span>
                </div>
                <p class="tp-task__q" :title="t.query">{{ t.query }}</p>
                <div class="tp-task__ops">
                  <button class="tp-btn" :aria-label="`查看任务 #${t.id}`" @click="select(t)">查看</button>
                  <button class="tp-btn" :aria-label="`重试任务 #${t.id}`" @click="retry(t)">重试</button>
                </div>
              </div>
              <div v-if="!loading && !doneTasks.length" class="tp-empty">
                <span class="tp-empty__t">暂无已结束的任务</span>
              </div>
            </template>
          </div>

          <footer class="tp__ft">任务在后台持续执行，关闭面板不会中断运行</footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.tp-mask {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(12, 16, 20, 0.34);
  display: flex;
  justify-content: flex-end;
}
.tp {
  width: 420px;
  max-width: 92vw;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-left: 1px solid var(--fs-hairline);
  box-shadow: -18px 0 48px rgba(0, 0, 0, 0.18);
}

/* 抽屉进出场：只动 opacity / transform（合成层），交互反馈 ≤200ms */
.tp-enter-active, .tp-leave-active { transition: opacity 160ms var(--fs-ease-out, ease); }
.tp-enter-active .tp, .tp-leave-active .tp { transition: transform 200ms var(--fs-ease-out, ease); }
.tp-enter-from, .tp-leave-to { opacity: 0; }
.tp-enter-from .tp, .tp-leave-to .tp { transform: translateX(100%); }

.tp__hd {
  flex-shrink: 0;
  padding: 18px 18px 14px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border-bottom: 1px solid var(--fs-hairline);
}
.tp__hd-t { min-width: 0; }
.tp__title { margin: 0; font-size: 16px; font-weight: 600; color: var(--fs-ink-900); }
.tp__sub { margin: 3px 0 0; font-size: 11px; color: var(--fs-ink-500); }
.tp__close {
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
  transition: background-color var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.tp__close:hover { background: var(--fs-bg-sunken); color: var(--fs-ink-900); }
.tp__close:active { transform: scale(0.96); }
.tp__close svg { width: 16px; height: 16px; transition: transform var(--fs-dur-micro) var(--fs-ease); }
.tp__close:hover svg { transform: rotate(90deg); }

.tp__tabs {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 10px 14px 0;
}
.tp__tab {
  position: relative;
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  background: transparent;
  color: var(--fs-ink-500);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.tp__tab:hover { color: var(--fs-ink-900); background: color-mix(in srgb, var(--fs-ink-900) 4%, transparent); }
.tp__tab.is-on { background: var(--fs-bg-sunken); color: var(--fs-ink-900); }
/* 选中页签底部 2px 强调导轨（与主框架页签同一语言） */
.tp__tab.is-on::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 2px;
  border-radius: 1px;
  background: var(--fs-accent);
  transform: scaleX(1);
  animation: tp-tab-in 0.24s var(--fs-ease-out, ease-out) both;
}
@keyframes tp-tab-in {
  from { transform: scaleX(0.3); opacity: 0; }
  to { transform: scaleX(1); opacity: 1; }
}
.tp__tab-n {
  margin-left: 5px;
  padding: 0 5px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-size: 10px;
}
.tp__tab-n--warn { background: var(--fs-warning); color: var(--fs-on-accent); }
.tp__sp { flex: 1; }
.tp__refresh {
  height: 26px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  background: transparent;
  color: var(--fs-ink-400);
  font-size: 11px;
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.tp__refresh:hover { color: var(--fs-ink-700); background: var(--fs-bg-sunken); }
.tp__refresh:disabled { opacity: 0.5; cursor: default; }
.tp__refresh svg {
  width: 13px;
  height: 13px;
  transition: transform 0.5s var(--fs-ease-out, ease-out);
}
.tp__refresh:not(:disabled):hover svg { transform: rotate(-180deg); }

.tp__bd {
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

.tp-task {
  position: relative;
  padding: 12px 13px;
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  background: var(--fs-bg-surface);
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.tp-task:hover { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
.tp-task.is-cur {
  box-shadow: inset 0 0 0 1px var(--fs-accent), inset 3px 0 0 var(--fs-accent);
  background: var(--fs-accent-soft);
}
.tp-task__top { display: flex; align-items: center; gap: 8px; }
.tp-task__id { font-size: 10px; color: var(--fs-ink-400); }
.tp-task__time { font-size: 11px; color: var(--fs-ink-500); }
.tp-task__q {
  margin: 8px 0 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--fs-ink-900);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
/* 滞留任务：降低视觉权重，明确是"历史欠账"而非正在运行 */
.tp-task--stale { background: var(--fs-bg-surface); box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
.tp-note { margin: 0 2px 2px; font-size: 11px; line-height: 1.5; color: var(--fs-ink-500); }
.tp-task__prog { margin-top: 10px; display: flex; align-items: center; gap: 8px; }
.tp-bar {
  flex: 1;
  height: 4px;
  border-radius: 999px;
  background: var(--fs-bg-sunken);
  overflow: hidden;
}
.tp-bar i {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 999px;
  background: var(--fs-accent);
  transform-origin: left center;
  transition: transform 200ms var(--fs-ease-out, ease);
}
.tp-task__meta { flex-shrink: 0; font-size: 10px; color: var(--fs-ink-500); }
.tp-task__ops { margin-top: 10px; display: flex; align-items: center; gap: 8px; }
.tp-task--done .tp-task__ops { margin-top: 8px; }
.tp-btn {
  height: 24px;
  padding: 0 10px;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
  font-size: 11px;
  cursor: pointer;
  transition: background-color var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.tp-btn:hover { background: var(--fs-hairline); color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
.tp-btn:active { transform: scale(0.97); }
.tp-btn--danger { margin-left: auto; color: var(--fs-danger); }
.tp-btn--danger:hover { background: var(--fs-danger-soft, #fdecec); color: var(--fs-danger); box-shadow: inset 0 0 0 1px var(--fs-danger); }

/* 状态点 */
.tp-st { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; white-space: nowrap; color: var(--fs-ink-500); }
.tp-st i { width: 5px; height: 5px; border-radius: 999px; background: currentColor; }
.tp-st.run { color: var(--fs-accent); }
.tp-st.run i { animation: tp-pulse 1.4s ease-in-out infinite; }
.tp-st.appr { color: var(--fs-warning); }
.tp-st.appr i { animation: tp-pulse 1.8s ease-in-out infinite; }
.tp-st.ok { color: var(--fs-success); }
.tp-st.fail { color: var(--fs-danger); }
.tp-st.cancel, .tp-st.wait { color: var(--fs-ink-400); }
@keyframes tp-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.tp-empty {
  flex: 1;
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--fs-ink-400);
}
.tp-empty__t { font-size: 13px; color: var(--fs-ink-500); }
.tp-empty__h { font-size: 11px; }

.tp__ft {
  flex-shrink: 0;
  padding: 10px 18px;
  border-top: 1px solid var(--fs-hairline);
  font-size: 10px;
  color: var(--fs-ink-400);
}

/* 数字统一等宽，倒计时/进度跳动不抖动 */
.tp-task__time, .tp-task__meta, .tp-task__id, .tp__tab-n, .tp__sub {
  font-variant-numeric: tabular-nums;
}

/* 键盘可见焦点 */
.tp__close:focus-visible, .tp__tab:focus-visible, .tp__refresh:focus-visible,
.tp-btn:focus-visible, .tp-empty__cta:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: 1px;
}
.tp:focus-visible { outline: none; }

/* 空态给一个明确的下一步动作 */
.tp-empty__cta { margin-top: 8px; background: var(--fs-accent); color: var(--fs-on-accent); }
.tp-empty__cta:hover { background: var(--fs-accent-hover); color: var(--fs-on-accent); }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .tp-enter-active,
  html:not([data-motion="on"]) .tp-leave-active,
  html:not([data-motion="on"]) .tp-enter-active .tp,
  html:not([data-motion="on"]) .tp-leave-active .tp { transition: none; }
  html:not([data-motion="on"]) .tp-bar i { transition: none; }
  html:not([data-motion="on"]) .tp-st.run i,
  html:not([data-motion="on"]) .tp-st.appr i,
  html:not([data-motion="on"]) .tp__tab.is-on::after { animation: none; }
}
/* 手动关闭动效：进出场、进度条补间、呼吸点与页签导轨一次全部静止 */
html[data-motion-allowed="false"] .tp-enter-active,
html[data-motion-allowed="false"] .tp-leave-active,
html[data-motion-allowed="false"] .tp-enter-active .tp,
html[data-motion-allowed="false"] .tp-leave-active .tp { transition: none; }
html[data-motion-allowed="false"] .tp-bar i { transition: none; }
html[data-motion-allowed="false"] .tp-st.run i,
html[data-motion-allowed="false"] .tp-st.appr i,
html[data-motion-allowed="false"] .tp__tab.is-on::after { animation: none; }
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; }
</style>
