<script setup>
/**
 * 系统管理 · 系统总览 Tab
 *
 * 一屏布局：顶部 5 栏 KPI + 下方双栏（左 Agent 运行状态 / 右 模型状态）。
 * 模型状态已从独立 Tab 并入此处：每类模型当前提供商/模型/状态 + 四提供商熔断状态。
 * 页面本身不滚动（父级在总览 Tab 下关闭 overflow），所有区块按视口高度自适应。
 */
import { ref, computed, onMounted } from 'vue'
import { fetchModelStatus } from '@/api/admin'

defineProps({
  status: { type: Object, default: null },
  loadingStatus: { type: Boolean, default: false },
})

const modelData = ref(null)
const loadingModels = ref(false)

const loadModels = async () => {
  loadingModels.value = true
  try {
    const json = await fetchModelStatus()
    if (json.code === 200) modelData.value = json.data
  } catch {
    modelData.value = null
  } finally {
    loadingModels.value = false
  }
}

onMounted(loadModels)

const models = computed(() => modelData.value?.models || [])
const providers = computed(() => modelData.value?.providers || [])
const enabledCount = computed(() => models.value.filter(m => m.enabled).length)

const stateText = (m) => {
  if (m.enabled) return '已配置'
  if (!m.configured) return '未配置'
  return '已关闭'
}
const stateCls = (m) => (m.enabled ? 'ok' : (!m.configured ? 'off' : 'warn'))

const breaker = (key) => modelData.value?.breakers?.[key]
const breakerText = (key) => {
  const b = breaker(key)
  if (b?.open) return `熔断 ${Math.round(b.remaining || 0)}s`
  const p = providers.value.find(x => x.key === key)
  return p?.configured ? '正常' : '未配置'
}
const breakerCls = (key) => {
  const b = breaker(key)
  if (b?.open) return 'fail'
  const p = providers.value.find(x => x.key === key)
  return p?.configured ? 'ok' : 'off'
}

const agentStatusText = (a) => {
  const s = String(a.status || '').toLowerCase()
  return s === 'busy' ? '运行中' : (s === 'ready' ? '就绪' : a.status || '—')
}
</script>

<template>
  <div v-loading="loadingStatus || loadingModels" class="ov">
    <template v-if="status">
      <!-- 顶部 KPI：数据库 / 当前底座 / 主对话模型 / 模型类别 / 注册 Agent -->
      <div class="sq-kpis anim" style="--d:80ms">
        <div class="sq-kpi">
          <span class="sq-kpi__v">{{ status.database === 'connected' ? '正常' : '断开' }}</span>
          <span class="sq-kpi__k">数据库</span>
        </div>
        <div class="sq-kpi">
          <span class="sq-kpi__v sq-kpi__v--sm">{{ modelData?.active_provider_label || '—' }}</span>
          <span class="sq-kpi__k">当前模型底座</span>
        </div>
        <div class="sq-kpi">
          <span class="sq-kpi__v sq-kpi__v--sm" :title="modelData?.active_model || ''">{{ modelData?.active_model || status.llm_model || '未配置' }}</span>
          <span class="sq-kpi__k">主对话模型</span>
        </div>
        <div class="sq-kpi">
          <span class="sq-kpi__v">
            {{ modelData ? enabledCount : '—' }}<span v-if="modelData" class="sq-kpi__u">/{{ models.length }}</span>
          </span>
          <span class="sq-kpi__k">已配置模型类别</span>
        </div>
        <div class="sq-kpi">
          <span class="sq-kpi__v">{{ (status.agents || []).length }}</span>
          <span class="sq-kpi__k">注册 Agent</span>
        </div>
      </div>

      <div class="ov-grid">
        <!-- 左栏：Agent 运行状态 -->
        <section class="kb-ans ov-panel">
          <header class="kb-ans__hd">
            <span class="kb-ans__t">Agent 运行状态</span>
            <span class="sq-panel__sp"></span>
            <span class="badge badge--muted mono">{{ (status.agents || []).length }} agents</span>
          </header>
          <div class="kb-ans__bd ov__agents">
            <div v-for="a in (status.agents || [])" :key="a.name" class="ov__agent">
              <span class="ov__agent-name">{{ a.name }}</span>
              <span class="ov__agent-fw mono">{{ a.framework }}</span>
              <span class="sq-panel__sp"></span>
              <span class="ov__agent-status" :class="{ ok: String(a.status).toLowerCase() === 'ready', busy: String(a.status).toLowerCase() === 'busy' }">
                <i aria-hidden="true"></i>{{ agentStatusText(a) }}
              </span>
            </div>
            <div v-if="!(status.agents || []).length" class="ov__empty">暂无注册 Agent</div>
            <div class="ov__agents-ft">
              <span class="badge badge--muted mono">v{{ status.version }}</span>
              <span class="sq-panel__sp"></span>
              <span class="ov__llm" :class="{ off: !status.llm_available }">
                <i aria-hidden="true"></i>模型服务{{ status.llm_available ? '正常' : '异常' }}
              </span>
            </div>
          </div>
        </section>

        <!-- 右栏：模型状态（每类模型 + 提供商熔断） -->
        <section class="kb-ans ov-panel">
          <header class="kb-ans__hd">
            <span class="kb-ans__t">模型状态</span>
            <span class="sq-panel__sp"></span>
            <span class="badge badge--muted mono" title="按密钥与开关判断配置状态；实际调用可能受账号额度/欠费影响">{{ models.length }} 类 · 已配置 {{ enabledCount }}</span>
          </header>
          <div class="ov__models">
            <div v-for="m in models" :key="m.key" class="ov__model">
              <div class="ov__model-main">
                <span class="ov__model-label">{{ m.label }}</span>
                <span class="ov__model-desc" :title="`${m.description}${m.chain ? ' · ' + m.chain : ''}`">{{ m.description }}</span>
              </div>
              <span class="ov__model-name mono" :title="m.model">{{ m.model || '—' }}</span>
              <span class="ov__model-prov">{{ m.provider_label }}</span>
              <span class="ov__model-st" :class="stateCls(m)"><i aria-hidden="true"></i>{{ stateText(m) }}</span>
            </div>
            <div v-if="!modelData && !loadingModels" class="ov__empty">
              模型状态获取失败
              <button class="ov__retry" @click="loadModels">重新加载</button>
            </div>
          </div>
          <div class="ov__provs">
            <div v-for="p in providers" :key="p.key" class="ov__prov" :class="{ 'is-active': p.active, 'is-off': !p.configured }">
              <span class="ov__prov-name">{{ p.label }}</span>
              <span class="ov__prov-m mono" :title="p.model">{{ p.model || '—' }}</span>
              <span class="ov__prov-st" :class="breakerCls(p.key)"><i aria-hidden="true"></i>{{ breakerText(p.key) }}</span>
            </div>
          </div>
        </section>
      </div>
    </template>
    <div v-else-if="!loadingStatus" class="ov__empty">暂无系统状态数据</div>
  </div>
</template>

<style scoped>
.ov {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.anim {
  animation: rise 0.4s var(--fs-ease-out) both;
  animation-delay: var(--d, 0ms);
}
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* ===== 顶部 KPI：五联通栏 ===== */
.sq-kpis {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.sq-kpi {
  padding: 11px 16px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  border-left: 1px solid var(--fs-hairline);
  min-width: 0;
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.sq-kpi:hover { background: rgba(var(--fs-ink-900-rgb), 0.02); }
.sq-kpi:first-child { border-left: none; }
.sq-kpi__v {
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.2;
  color: var(--fs-ink-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sq-kpi__v--sm { font-size: 13.5px; line-height: 23px; }
.sq-kpi__u { font-size: 11px; color: var(--fs-ink-400); font-weight: 500; }
.sq-kpi__k {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--fs-ink-500);
  white-space: nowrap;
}

/* ===== 双栏：左 Agent / 右 模型 ===== */
.ov-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
}
.ov-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 面板（与既有 kb-ans 同构） */
.kb-ans {
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.kb-ans__hd {
  flex-shrink: 0;
  height: 38px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.kb-ans__t {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--fs-ink-900);
}
.kb-ans__t::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 2px;
  background: var(--fs-accent);
  opacity: 0.7;
}
.sq-panel__sp { flex: 1; }
.badge {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 10px;
  font-weight: 500;
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
  white-space: nowrap;
}
.badge--muted { color: var(--fs-ink-500); }
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; font-variant-numeric: tabular-nums; }

/* Agent 清单 */
.kb-ans__bd { padding: 4px 14px 10px; }
.ov__agents {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.ov__agent {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8.5px 0;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.ov__agent:hover { background: rgba(var(--fs-ink-900-rgb), 0.02); }
.ov__agent-name { font-size: 12.5px; font-weight: 500; color: var(--fs-ink-900); }
.ov__agent-fw {
  font-size: 9.5px;
  color: var(--fs-ink-400);
  padding: 2px 6px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  max-width: 118px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ov__agent-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10.5px;
  color: var(--fs-ink-500);
  white-space: nowrap;
}
.ov__agent-status i { width: 5px; height: 5px; border-radius: 50%; background: var(--fs-ink-400); }
.ov__agent-status.ok { color: var(--fs-success); }
.ov__agent-status.ok i { background: var(--fs-success); }
.ov__agent-status.busy { color: var(--fs-accent); }
.ov__agent-status.busy i { background: var(--fs-accent); }
.ov__agents-ft {
  margin-top: auto;
  padding-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ov__llm { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; color: var(--fs-success); white-space: nowrap; }
.ov__llm i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.ov__llm.off { color: var(--fs-danger); }

/* 模型清单：类别+描述 / 模型 / 提供商 / 状态 */
.ov__models {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ov__model {
  min-height: 0;
  padding: 6.5px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.ov__model:hover { background: rgba(var(--fs-ink-900-rgb), 0.02); }
.ov__model-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.ov__model-label { font-size: 12px; font-weight: 600; color: var(--fs-ink-900); white-space: nowrap; }
.ov__model-desc {
  font-size: 9.5px;
  color: var(--fs-ink-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ov__model-name {
  flex-shrink: 0;
  width: 152px;
  font-size: 10.5px;
  color: var(--fs-ink-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ov__model-prov {
  flex-shrink: 0;
  width: 78px;
  font-size: 10.5px;
  color: var(--fs-ink-500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ov__model-st {
  flex-shrink: 0;
  width: 56px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--fs-ink-400);
  white-space: nowrap;
}
.ov__model-st i { width: 5px; height: 5px; border-radius: 999px; background: currentColor; }
.ov__model-st.ok { color: var(--fs-success); }
.ov__model-st.warn { color: var(--fs-warning); }
.ov__model-st.off { color: var(--fs-ink-400); }

/* 提供商条：4 列 */
.ov__provs {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--fs-hairline);
  background: var(--fs-bg-sunken);
}
.ov__prov {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  border-left: 1px solid var(--fs-hairline);
  min-width: 0;
  transition:
    background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    opacity var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.ov__prov:first-child { border-left: none; }
.ov__prov:hover:not(.is-active) { background: rgba(var(--fs-ink-900-rgb), 0.03); }
.ov__prov.is-active { background: var(--fs-accent-soft); }
.ov__prov.is-off { opacity: 0.55; }
.ov__prov-name { font-size: 10.5px; font-weight: 600; color: var(--fs-ink-900); white-space: nowrap; }
.ov__prov-m {
  font-size: 9.5px;
  color: var(--fs-ink-500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ov__prov-st { display: inline-flex; align-items: center; gap: 4px; font-size: 9.5px; color: var(--fs-ink-400); white-space: nowrap; }
.ov__prov-st i { width: 4px; height: 4px; border-radius: 50%; background: currentColor; }
.ov__prov-st.ok { color: var(--fs-success); }
.ov__prov-st.fail { color: var(--fs-danger); }

.ov__empty { padding: 18px 2px; font-size: 12px; color: var(--fs-ink-400); text-align: center; }
.ov__retry {
  margin-left: 6px;
  border: none;
  background: transparent;
  color: var(--fs-accent);
  font-size: 12px;
  letter-spacing: 0.01em;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
  transition: color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.ov__retry:hover { color: var(--fs-accent-hover); }
.ov__retry:focus-visible { outline: 2px solid var(--fs-accent); outline-offset: 2px; }

/* 低高度屏幕进一步压缩行高，保证一屏无滚动 */
@media (max-height: 760px) {
  .sq-kpi { padding: 8px 14px; }
  .ov__agent { padding: 6.5px 0; }
  .ov__model { padding: 4.5px 14px; }
  .ov__prov { padding: 6px 10px; }
  .ov-grid { gap: 12px; }
}
@media (max-width: 1200px) {
  .ov-grid { grid-template-columns: 288px minmax(0, 1fr); }
  .ov__model-name { width: 128px; }
}

html[data-motion-allowed="false"] .anim { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .anim { animation: none; }
}
</style>
