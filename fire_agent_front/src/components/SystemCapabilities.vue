<script setup>
/**
 * 系统能力面板 — 后端 P0/P1/P2 能力一览
 *
 * 数据源: GET /api/v1/agent/capabilities（需登录，{code,message,data}）
 * 自包含：自带 loading / 失败降级提示（不抛错、不白屏）/ 可折叠（默认展开）
 *
 * 视觉 V7：chips 云 → 「行清单」语言——每能力组为 k/v 发丝行（值截断 + title 全文），
 * 仅真正枚举型短项（供应商链 / 拓扑流 / 评估指标）保留 chips；根除长枚举值
 * （检索策略 / 降级矩阵）nowrap 胶囊撑出横向滚动的问题。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchCapabilities } from '@/api/agent'

const loading = ref(true)
const loadError = ref('')
const caps = ref(null)
const collapsed = ref(false)
const snapshotAt = ref('') // 快照时间（HH:MM）
let refreshTimer = null

// LLM 供应商友好名（阶段 5：提取到 utils/llmProviders.js，全站共用一份）
import { providerName as pname } from '@/utils/llmProviders'

const fetchCaps = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const json = await fetchCapabilities()
    if (json.code === 200 && json.data) {
      caps.value = json.data
      const d = new Date()
      snapshotAt.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    } else {
      loadError.value = json.message || '接口返回异常'
    }
  } catch (e) {
    loadError.value = e.message || '网络错误'
  } finally {
    loading.value = false
  }
}

// 10s 轮询刷新（与 Agent 中心输入卡模型通道同源同频）：
// 后端热切换模型/重启后，两处"当前模型"显示实时一致，不再停留在旧快照
onMounted(() => {
  fetchCaps()
  refreshTimer = setInterval(fetchCaps, 10000)
})
onUnmounted(() => clearInterval(refreshTimer))

// ====== 派生视图 ======
// 折叠态摘要：一眼确认"能力已具备"
const summaryLine = computed(() => {
  const c = caps.value
  if (!c) return ''
  const parts = []
  if (c.llm) parts.push(`LLM ${pname(c.llm.active_provider)}${c.llm.available === false ? '（不可用）' : '可用'}`)
  if (c.checkpointer) parts.push(c.checkpointer.backend === 'postgres' ? 'Postgres 检查点' : '内存检查点')
  if (c.data?.dual_source) parts.push('双数据源')
  if (c.rag) parts.push(`RAG ${c.rag.retrieval || ''}`.trim())
  if (c.orchestration?.hitl?.required) parts.push('HITL')
  return parts.filter(Boolean).join(' · ')
})

// 熔断器条目：{ name, open, consecutive_failures, threshold, cooldown, remaining }
const breakerEntries = computed(() => {
  const b = caps.value?.llm?.breakers
  if (!b || typeof b !== 'object') return []
  return Object.entries(b).map(([k, v]) => ({ name: pname(k), ...(v || {}) }))
})

// ====== 健康摘要（v0 cap-sum：「全部正常」+ 快照时间 + 熔断 N/M） ======
const openBreakers = computed(() => breakerEntries.value.filter(b => b.open).length)
const healthy = computed(() => {
  const c = caps.value
  if (!c) return false
  if (c.llm && c.llm.available === false) return false
  return openBreakers.value === 0
})

// 编排拓扑：拆分 '∥' 并行段为 { text, sep } 流
const topoFlow = computed(() => {
  const t = caps.value?.orchestration?.topology
  if (!Array.isArray(t)) return []
  const out = []
  t.forEach((item, i) => {
    String(item).split('∥').forEach((seg, j) => {
      out.push({ text: seg.trim(), sep: j === 0 ? (i === 0 ? '' : '→') : '∥' })
    })
  })
  return out.filter(x => x.text)
})

// 降级矩阵条目
const DEGRADE_LABELS = { llm: 'LLM', checkpointer: '检查点', rerank: 'Rerank', mcp: 'MCP', preferences: '偏好记忆' }
const degradationList = computed(() => {
  const d = caps.value?.degradation
  if (!d || typeof d !== 'object') return []
  return Object.entries(d).map(([k, v]) => ({ key: DEGRADE_LABELS[k] || k, value: String(v ?? '—') }))
})

// 数据源行
const dataSources = computed(() => (Array.isArray(caps.value?.data?.sources) ? caps.value.data.sources : []))

// ====== 行清单（k/v 行，替代 chips 云） ======
// LLM 组
const llmRows = computed(() => {
  const l = caps.value?.llm
  if (!l) return []
  const rows = []
  rows.push({ k: '当前模型', v: [pname(l.active_provider), l.active_model].filter(Boolean).join(' · '), mono: true })
  rows.push({
    k: '可用性',
    v: l.available === false ? '不可用' : `可用 · 流式${l.stream_enabled ? '开' : '关'}`,
    ok: l.available !== false,
  })
  if (l.retry && l.retry.delays) {
    rows.push({ k: '重试策略', v: `指数退避 ${l.retry.delays.join('/')}s × ${num(l.retry.max_attempts)}`, mono: true })
  }
  return rows
})

// RAG 组
const ragRows = computed(() => {
  const r = caps.value?.rag
  if (!r) return []
  const rows = []
  if (r.embedding_model) rows.push({ k: '向量模型', v: r.embedding_model, mono: true })
  if (r.retrieval) rows.push({ k: '检索策略', v: r.retrieval, tip: r.retrieval })
  if (r.rerank) {
    rows.push({
      k: '重排',
      v: r.rerank.enabled ? `${r.rerank.model || 'rerank'}${r.rerank.fallback ? ' · 可兜底' : ''}` : '未启用',
      ok: r.rerank.enabled,
      mono: true,
    })
  }
  const params = []
  if (r.top_k != null) params.push(`Top ${r.top_k}`)
  if (r.documents != null) params.push(`文档 ${r.documents} 篇`)
  if (params.length) rows.push({ k: '检索参数', v: params.join(' · '), mono: true })
  const feats = []
  if (r.citation) feats.push('引用标注')
  if (r.stream) feats.push('流式输出')
  if (feats.length) rows.push({ k: '输出能力', v: feats.join(' · ') })
  return rows
})

// 记忆 · 工具 · 观测组
const memoRows = computed(() => {
  const c = caps.value
  if (!c) return []
  const rows = []
  if (c.memory) {
    rows.push({ k: '偏好记忆', v: c.memory.preferences_enabled ? '开启' : '关闭', ok: c.memory.preferences_enabled })
    if (c.memory.store) rows.push({ k: '存储后端', v: c.memory.store, mono: true, tip: c.memory.inject ? `注入 ${c.memory.inject}` : '' })
  }
  if (c.mcp) {
    const servers = (c.mcp.servers || []).map(s => (typeof s === 'string' ? s : (s.name || ''))).filter(Boolean)
    rows.push({
      k: 'MCP 工具',
      v: c.mcp.enabled ? (servers.join(' · ') || '已启用') : '未启用',
      ok: c.mcp.enabled,
      mono: true,
      tip: servers.join(' · ') || '',
    })
    if (c.mcp.fallback) rows.push({ k: 'MCP 兜底', v: c.mcp.fallback, tip: c.mcp.fallback })
  }
  if (c.observability) {
    rows.push({
      k: '链路观测',
      v: c.observability.langfuse_enabled ? 'Langfuse 已接入' : 'Langfuse 未接入',
      ok: c.observability.langfuse_enabled,
      tip: c.observability.fallback ? `兜底：${c.observability.fallback}` : '',
    })
  }
  return rows
})

// 编排组（拓扑流之外的规则行）
const orchRows = computed(() => {
  const o = caps.value?.orchestration
  if (!o) return []
  const rows = []
  if (o.framework) rows.push({ k: '框架', v: o.framework, mono: true })
  const modes = []
  if (o.plan_driven_routing) modes.push('计划驱动路由')
  if (o.parallel_fanout) modes.push('并行 Fan-out')
  if (modes.length) rows.push({ k: '编排模式', v: modes.join(' · ') })
  if (o.reflection_retry) rows.push({ k: '反思重试', v: `≤ ${num(o.reflection_retry.max_rounds)} 轮`, mono: true })
  if (o.review_loop) rows.push({ k: '评审循环', v: `≤ ${num(o.review_loop.max_revisions)} 轮 · 底线 ${num(o.review_loop.hard_guardrail_min_chars)} 字`, mono: true })
  if (o.hitl && o.hitl.required) rows.push({ k: '人工闸口', v: `HITL · ${(o.hitl.actions || []).join('/') || '审批'}`, warn: true })
  if (o.node_progress_sse) rows.push({ k: '进度推送', v: '节点级 SSE', ok: true })
  return rows
})

const yn = (v) => (v ? '✓' : '—')
const num = (v) => (v == null ? '—' : v)

onMounted(fetchCaps)
</script>

<template>
  <section class="cap-card">
    <!-- 标题条（折叠时显示摘要行，仍能一眼确认能力已具备） -->
    <div class="cap-head" @click="collapsed = !collapsed" title="点击展开/收起">
      <span class="cap-title">系统能力</span>
      <span class="cap-en mono">Capabilities</span>
      <span class="cap-sp"></span>
      <span v-if="collapsed && summaryLine" class="cap-summary">{{ summaryLine }}</span>
      <span class="cap-toggle">{{ collapsed ? '展开 ▾' : '收起 ▴' }}</span>
    </div>

    <div v-if="!collapsed" class="cap-body">
      <div v-if="loading" class="cap-hint">能力清单加载中…</div>

      <div v-else-if="loadError" class="cap-error">
        <span>能力加载失败：{{ loadError }}</span>
        <button class="cap-retry" @click="fetchCaps">重试</button>
      </div>

      <template v-else-if="caps">
        <!-- 健康摘要行（v0 cap-sum：全部正常 / 快照 / 熔断计数） -->
        <div class="cap-sum">
          <span class="cap-health" :class="{ bad: !healthy }">
            <i></i>{{ healthy ? '全部正常' : '存在异常' }}
          </span>
          <span class="cap-sum__sp"></span>
          <span class="cap-sum__m mono">快照 {{ snapshotAt || '—' }}<template v-if="breakerEntries.length"> · 熔断 {{ openBreakers.length }}/{{ breakerEntries.length }}</template></span>
        </div>

        <!-- 大模型 -->
        <div v-if="caps.llm" class="cap-group">
          <div class="cap-gt">大模型</div>
          <div class="cap-rows">
            <div v-for="(r, i) in llmRows" :key="i" class="cap-row" :title="r.tip || ''">
              <span class="cap-rk">{{ r.k }}</span>
              <span class="cap-rv" :class="{ mono: r.mono }">
                <i v-if="r.ok === true" class="cap-dot ok"></i>
                <i v-else-if="r.ok === false" class="cap-dot err"></i>
                {{ r.v }}
              </span>
            </div>
          </div>
          <!-- 供应商降级链（枚举短项，保留 chips） -->
          <div v-if="caps.llm.provider_chain && caps.llm.provider_chain.length" class="cap-chips">
            <span class="cap-chip-label">降级链</span>
            <span v-for="p in caps.llm.provider_chain" :key="p" class="cap-chip">{{ pname(p) }}</span>
          </div>
          <!-- 熔断器状态：状态点 + 失败计数 / 恢复倒计时 -->
          <div v-if="breakerEntries.length" class="cap-breakers">
            <div v-for="b in breakerEntries" :key="b.name" class="cap-breaker">
              <span class="cap-dot mo-loop" :class="b.open ? 'open' : 'closed'"></span>
              <span class="cap-bname">{{ b.name }}</span>
              <span class="cap-bval">{{ b.open ? `熔断中 · 恢复 ${num(b.remaining)}s` : `失败 ${num(b.consecutive_failures)}/${num(b.threshold)}` }}</span>
            </div>
          </div>
        </div>

        <!-- 检查点 -->
        <div v-if="caps.checkpointer" class="cap-group">
          <div class="cap-gt">检查点</div>
          <div class="cap-rows">
            <div class="cap-row" :title="caps.checkpointer.note || ''">
              <span class="cap-rk">持久化</span>
              <span class="cap-rv mono">
                <i class="cap-dot" :class="caps.checkpointer.persistent ? 'ok' : 'err'"></i>
                {{ caps.checkpointer.backend === 'postgres' ? 'Postgres' : 'Memory' }} · {{ caps.checkpointer.persistent ? '持久化' : '非持久化' }}
              </span>
            </div>
          </div>
        </div>

        <!-- 编排 -->
        <div v-if="caps.orchestration" class="cap-group">
          <div class="cap-gt">编排</div>
          <div v-if="topoFlow.length" class="cap-topo">
            <template v-for="(t, i) in topoFlow" :key="i">
              <span v-if="t.sep" class="cap-topo-sep" :class="{ par: t.sep === '∥' }">{{ t.sep }}</span>
              <span class="cap-topo-chip">{{ t.text }}</span>
            </template>
          </div>
          <div class="cap-rows">
            <div v-for="(r, i) in orchRows" :key="i" class="cap-row" :title="r.tip || ''">
              <span class="cap-rk">{{ r.k }}</span>
              <span class="cap-rv" :class="{ mono: r.mono }">
                <i v-if="r.ok === true" class="cap-dot ok"></i>
                <i v-else-if="r.warn" class="cap-dot warn"></i>
                {{ r.v }}
              </span>
            </div>
          </div>
        </div>

        <!-- 数据源 -->
        <div v-if="caps.data" class="cap-group">
          <div class="cap-gt">数据源</div>
          <div class="cap-rows">
            <div v-if="caps.data.gis" class="cap-row">
              <span class="cap-rk">GIS 图层</span>
              <span class="cap-rv mono">
                <i class="cap-dot" :class="caps.data.dual_source ? 'ok' : 'err'"></i>
                历史 {{ yn(caps.data.gis.historical) }} · 预测 {{ yn(caps.data.gis.predicted) }}
              </span>
            </div>
            <div v-for="(s, i) in dataSources" :key="i" class="cap-row" :title="`${s.label || s.table} · ${s.range || ''}`">
              <span class="cap-rk">{{ s.label || s.table }}</span>
              <span class="cap-rv mono">{{ s.range || '—' }}</span>
            </div>
          </div>
        </div>

        <!-- 知识检索 RAG -->
        <div v-if="caps.rag" class="cap-group">
          <div class="cap-gt">知识检索 RAG</div>
          <div class="cap-rows">
            <div v-for="(r, i) in ragRows" :key="i" class="cap-row" :title="r.tip || ''">
              <span class="cap-rk">{{ r.k }}</span>
              <span class="cap-rv" :class="{ mono: r.mono }">
                <i v-if="r.ok === true" class="cap-dot ok"></i>
                <i v-else-if="r.ok === false" class="cap-dot err"></i>
                {{ r.v }}
              </span>
            </div>
          </div>
        </div>

        <!-- 偏好记忆 / MCP / 观测 -->
        <div v-if="memoRows.length" class="cap-group">
          <div class="cap-gt">记忆 · 工具 · 观测</div>
          <div class="cap-rows">
            <div v-for="(r, i) in memoRows" :key="i" class="cap-row" :title="r.tip || ''">
              <span class="cap-rk">{{ r.k }}</span>
              <span class="cap-rv" :class="{ mono: r.mono }">
                <i v-if="r.ok === true" class="cap-dot ok"></i>
                <i v-else-if="r.ok === false" class="cap-dot err"></i>
                {{ r.v }}
              </span>
            </div>
          </div>
        </div>

        <!-- 评估回归（指标为短枚举，保留 chips） -->
        <div v-if="caps.evaluation" class="cap-group">
          <div class="cap-gt">评估回归</div>
          <div class="cap-rows">
            <div v-if="caps.evaluation.golden_cases != null" class="cap-row">
              <span class="cap-rk">金标用例</span>
              <span class="cap-rv mono">{{ caps.evaluation.golden_cases }} 例</span>
            </div>
          </div>
          <div v-if="(caps.evaluation.metrics || []).length || (caps.evaluation.modes || []).length" class="cap-chips">
            <span v-for="(m, i) in caps.evaluation.metrics || []" :key="'m' + i" class="cap-chip">{{ m }}</span>
            <span v-for="(m, i) in caps.evaluation.modes || []" :key="'md' + i" class="cap-chip dim">{{ m }}</span>
          </div>
        </div>

        <!-- 降级矩阵（长枚举值，改行清单） -->
        <div v-if="degradationList.length" class="cap-group">
          <div class="cap-gt">降级矩阵</div>
          <div class="cap-rows">
            <div v-for="d in degradationList" :key="d.key" class="cap-row" :title="`${d.key} → ${d.value}`">
              <span class="cap-rk">{{ d.key }}</span>
              <span class="cap-rv mono">{{ d.value }}</span>
            </div>
          </div>
        </div>

        <!-- 刷新能力快照（v0 cap 底部 ghost 钮） -->
        <button class="cap-refresh" :disabled="loading" @click="fetchCaps">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16.4 8.4A6.6 6.6 0 1 0 10 16.6a6.6 6.6 0 0 0 4.6-1.9"/><path d="M16.6 3.6v5h-5"/></svg>
          刷新能力快照
        </button>
      </template>
    </div>
  </section>
</template>

<style scoped>
/* v0 卡片：表面卡 + 发丝环 */
.cap-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}

.cap-head {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border-bottom: 1px solid var(--fs-hairline);
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
}

.cap-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--fs-ink-900);
  flex: none; /* 防止被折叠摘要挤压成一字一行竖排 */
  white-space: nowrap;
}

.cap-en {
  font-family: var(--fs-font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--fs-ink-400);
  flex: none;
}

.cap-sp { flex: 1; }

.cap-summary {
  min-width: 0;
  font-size: 10px;
  color: var(--fs-ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cap-toggle {
  font-size: 10px;
  color: var(--fs-ink-400);
  flex-shrink: 0;
}

.cap-head:not(:hover) .cap-toggle {
  opacity: 0.6;
}

.cap-body {
  padding: 12px 14px;
  overflow-y: auto;
  overflow-x: hidden; /* 长枚举值截断展示，绝不横向撑破 */
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

.cap-hint {
  font-size: 11px;
  color: var(--fs-ink-500);
  padding: 8px 0;
}

/* 健康摘要行（v0 cap-sum 同构） */
.cap-sum {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: var(--fs-bg-canvas);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
}
.cap-health {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--fs-success);
  flex-shrink: 0;
}
.cap-health i {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
}
.cap-health.bad { color: var(--fs-danger); }
.cap-sum__sp { flex: 1; }
.cap-sum__m {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-500);
  white-space: nowrap;
}

/* 刷新能力快照（v0 btn--ghost 同构） */
.cap-refresh {
  height: 26px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  align-self: flex-start;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  color: var(--fs-ink-500);
  background: transparent;
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.cap-refresh svg { width: 12px; height: 12px; }
.cap-refresh:hover:not(:disabled) {
  color: var(--fs-accent);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
}
.cap-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

.cap-error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--fs-danger);
  padding: 6px 0;
}

.cap-retry {
  flex-shrink: 0;
  font-size: 10px;
  padding: 2px 9px;
  color: var(--fs-ink-700);
  background: transparent;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.cap-retry:hover {
  color: var(--fs-accent);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
}

/* ===== 能力组：组标题 + 行清单 ===== */
.cap-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cap-gt {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--fs-ink-500);
}

/* k/v 发丝行（任务元信息 meta-list 同构） */
.cap-rows { display: flex; flex-direction: column; }
.cap-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-height: 26px;
  padding: 3px 0;
  font-size: 11px;
  line-height: 1.6;
  border-bottom: 1px solid var(--fs-hairline);
  min-width: 0;
}
.cap-row:last-child { border-bottom: none; }
.cap-rk {
  flex: none;
  width: 64px;
  color: var(--fs-ink-500);
}
.cap-rv {
  flex: 1;
  min-width: 0;
  color: var(--fs-ink-900);
  font-weight: 500;
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cap-rv.mono {
  font-family: var(--fs-font-mono);
  font-weight: 400;
}

/* 状态点（行内 ok / warn / err 三态） */
.cap-dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  align-self: center;
}
.cap-dot.ok { background: var(--fs-success); }
.cap-dot.warn { background: var(--fs-warning); }
.cap-dot.err { background: var(--fs-danger); }
.cap-dot.open {
  background: var(--fs-danger);
  animation: cap-blink 1.2s ease-in-out infinite;
}
@keyframes cap-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

/* 枚举短项 chips（仅供应商链 / 评估指标 / 拓扑流使用） */
.cap-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.cap-chip-label {
  font-size: 10px;
  color: var(--fs-ink-400);
  flex-shrink: 0;
}
.cap-chip {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  line-height: 1.7;
  padding: 0 8px;
  border-radius: 999px;
  white-space: nowrap;
  color: var(--fs-ink-500);
  background: var(--fs-bg-canvas);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  border: none;
}
.cap-chip.dim {
  font-family: inherit;
  color: var(--fs-ink-400);
  box-shadow: none;
  background: transparent;
}

/* 编排拓扑流 */
.cap-topo {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.cap-topo-chip {
  font-family: var(--fs-font-mono);
  font-size: 9px;
  padding: 0 7px;
  border-radius: 999px;
  color: var(--fs-ink-700);
  background: var(--fs-bg-canvas);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
}
.cap-topo-sep {
  font-size: 9px;
  color: var(--fs-ink-400);
}
.cap-topo-sep.par {
  color: var(--fs-accent);
  font-weight: 700;
}

/* 熔断器（canvas 底 + 发丝环容器） */
.cap-breakers {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 7px 10px;
  background: var(--fs-bg-canvas);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
}
.cap-breaker {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  line-height: 1.7;
}
.cap-bname {
  color: var(--fs-ink-900);
  font-weight: 500;
  flex-shrink: 0;
}
.cap-bval {
  margin-left: auto;
  color: var(--fs-ink-500);
  font-family: var(--fs-font-mono);
}
</style>
