<script setup>
/**
 * 报告中心 · 右侧报告详情（v0 rep-bar + rep-paper 同构）
 *
 * 结构：56px 操作条（标题 + 播报/导出/打印/删除）→ 弹性滚动区 →
 *       760px 居中纸张（30px 大标题 + 发丝分隔 + meta 行 + 摘要注记 + 15px/1.9 正文 + 三线表）。
 * 受控组件：当前报告、错误文案、loading 由父组件持有，导出/打印/删除/播报由事件上抛。
 * Markdown 清洗（悬空表格行防死循环）与 Token 统计逻辑零改动。
 */
import { computed } from 'vue'
import renderMarkdown from '@/utils/markdown'
import { speakState } from '@/utils/speech'
import { providerLabel, isAgentGenerated } from '@/utils/reportMeta'

const props = defineProps({
  report: { type: Object, default: null },
  detailError: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['speak', 'export', 'print', 'delete'])

// ====== Markdown 渲染（支持表格/加粗/代码块） ======
// 名字刻意不叫 sanitize：这里做的事是「把不是合法表格的悬空 | 行转义成字面文本」，
// 属于排版修正；安全性由 renderMarkdown 自己的 HTML 转义 + 链接协议白名单负责。
// （渲染器现已保证不会因这类行空转，见 utils/markdown.js 的进度保证；本函数保留是
//  为了让这类行显示成原文而不是被吞进一个假表格。）
const isTableSep = (s) =>
  typeof s === 'string' && s.includes('-') && /^\s*\|?[\s:|-]+\|?\s*$/.test(s)

const escapeStrayTablePipes = (md) => {
  const lines = String(md).replace(/\r\n/g, '\n').split('\n')
  const isPipe = (l) => typeof l === 'string' && l.trim().startsWith('|')
  const out = lines.slice()
  let i = 0
  while (i < lines.length) {
    if (!isPipe(lines[i])) {
      i++
      continue
    }
    let j = i
    while (j < lines.length && isPipe(lines[j])) j++ // 连续以 | 开头的行块
    // 仅当该块是合法表格（首行紧跟分隔行）时才原样保留，否则整块转义
    const validTable = j - i >= 2 && isTableSep(lines[i + 1])
    if (!validTable) {
      for (let k = i; k < j; k++) out[k] = lines[k].replace(/^(\s*)\|/, '$1\\|')
    }
    i = j
  }
  return out.join('\n')
}

const renderHtml = computed(() => {
  const raw =
    props.report && typeof props.report.content === 'string'
      ? props.report.content
      : ''
  if (!raw.trim()) return ''
  try {
    return renderMarkdown(escapeStrayTablePipes(raw))
  } catch {
    return '' // 渲染异常交由模板显示空态，避免整页空白
  }
})

// 正文是否有可渲染内容
const hasContent = computed(
  () =>
    !!(props.report &&
      typeof props.report.content === 'string' &&
      props.report.content.trim()),
)

// ====== rep-meta 行（v0：生成时间 · 来源 · 正文字数 · Token） ======
const charCount = computed(() => {
  const c = props.report && props.report.content
  return typeof c === 'string' && c.trim() ? c.replace(/\s/g, '').length.toLocaleString() : null
})

const sourceText = computed(() => {
  const r = props.report
  if (!r) return ''
  if (isAgentGenerated(r)) {
    return `Agent 生成 · ${r.llm_model || providerLabel(r.llm_provider)}`
  }
  return providerLabel(r.llm_provider) // 模板生成 / 人工上传
})

// Token 总量（优先 total_tokens，否则用 prompt+completion 求和），无则 null
const tokenTotal = computed(() => {
  const t = props.report && props.report.llm_tokens
  if (!t) return null
  if (t.total_tokens != null) return t.total_tokens
  const sum = (t.prompt_tokens || 0) + (t.completion_tokens || 0)
  return sum > 0 ? sum : null
})

// Token 明细（tooltip）
const tokenDetail = computed(() => {
  const t = props.report && props.report.llm_tokens
  if (!t) return ''
  return `输入 ${t.prompt_tokens ?? '—'} / 输出 ${t.completion_tokens ?? '—'}`
})
</script>

<template>
  <main class="rd" v-loading="loading">
    <!-- ===== 操作条（v0 rep-bar：56px surface + 发丝下缘） ===== -->
    <div class="rd-bar">
      <span class="rd-bar__t" :title="report ? report.title : ''">{{ report ? report.title : '报告详情' }}</span>
      <span class="rd-bar__sp"></span>
      <template v-if="report">
        <button
          class="rd-btn rd-btn--ghost mo-loop"
          :class="{ speaking: speakState.speaking || speakState.loading }"
          title="语音播报报告（摘要 + 正文）"
          @click="emit('speak')"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8v4h2.6l3.4 3V5L6.6 8z"/><path d="M13.2 7.6a3.6 3.6 0 0 1 0 4.8"/></svg>
          {{ speakState.speaking || speakState.loading ? '停止' : '播报' }}
        </button>
        <button class="rd-btn" title="导出 Markdown 文件" @click="emit('export', report, 'md')">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3.5v9"/><path d="m6.4 9 3.6 3.5L13.6 9"/><path d="M4 15.5h12"/></svg>
          导出
        </button>
        <button class="rd-btn" title="在浏览器中打开打印预览（另存为 PDF）" @click="emit('print', report)">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 7V3.5h8V7"/><rect x="3.5" y="7" width="13" height="6" rx="1"/><path d="M6 11h8v5.5H6z"/></svg>
          打印
        </button>
        <button class="rd-btn rd-btn--ghost rd-btn--danger" title="删除该报告" @click="emit('delete', report)">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5.5h13"/><path d="M8 2.8h4"/><path d="M5.2 5.5 5.9 17h8.2l.7-11.5"/><path d="M8.4 8.4v5.4M11.6 8.4v5.4"/></svg>
        </button>
      </template>
    </div>

    <!-- ===== 滚动区 ===== -->
    <div class="rd-scroll">
      <!-- 错误态（v0 empty） -->
      <div v-if="detailError" class="rd-empty">
        <svg class="rd-empty__ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3.2 17 15.8H3z"/><path d="M10 8.4v3.4"/><circle cx="10" cy="13.9" r="0.4" fill="currentColor"/></svg>
        {{ detailError }}
        <span class="rd-empty__hint">该报告可能已被删除，或您没有查看权限</span>
      </div>

      <!-- 空态（v0 empty） -->
      <div v-else-if="!report" class="rd-empty">
        <svg class="rd-empty__ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3.5h7.5L16 7v9.5H5z"/><path d="M12.5 3.5V7H16"/><path d="M7.5 10.5h5M7.5 13h5"/></svg>
        请从左侧选择一份报告
        <span class="rd-empty__hint">报告由 Agent 协作中心自动生成，或经人工上传归档</span>
      </div>

      <!-- ===== 纸张（v0 rep-paper：760px 居中） ===== -->
      <article v-else class="rd-paper">
        <h1 class="rd-title">{{ report.title }}</h1>
        <div class="rd-meta">
          <span>生成时间 {{ report.created_at || '—' }}</span>
          <span v-if="report.updated_at && report.updated_at !== report.created_at">更新于 {{ report.updated_at }}</span>
          <span :title="`模型来源：${report.llm_model || providerLabel(report.llm_provider)}`">{{ sourceText }}</span>
          <span v-if="report.llm_degraded" class="rd-meta__warn" title="本次生成发生降级（模板兜底或换用备用 Provider）">降级产出</span>
          <span v-if="charCount">正文 {{ charCount }} 字</span>
          <el-tooltip v-if="tokenTotal != null" :content="tokenDetail || '无明细'" placement="top">
            <span>Token {{ tokenTotal.toLocaleString() }}</span>
          </el-tooltip>
        </div>

        <!-- 摘要（v0 blockquote：accent 左缘注记） -->
        <div v-if="report.summary" class="rd-summary">
          <strong>摘要</strong>{{ report.summary }}
        </div>

        <!-- 正文（v0 .paper：15px/1.9 + 三线表） -->
        <div v-if="hasContent" class="rd-body markdown-body" v-html="renderHtml" />
        <div v-else class="rd-body-empty">报告内容为空</div>
      </article>
    </div>
  </main>
</template>

<style scoped>
/* v0 rep-detail：canvas 底通栏 */
.rd {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-canvas);
}

/* ===== 操作条（v0 rep-bar） ===== */
.rd-bar {
  flex: none;
  height: 56px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--fs-bg-surface);
  border-bottom: 1px solid var(--fs-hairline);
}
.rd-bar__t {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.005em;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--fs-ink-900);
}
.rd-bar__sp { flex: 1; }
/* v0 .btn / .btn--ghost 同构 */
.rd-btn {
  height: 28px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.rd-btn svg { width: 13px; height: 13px; }
.rd-btn:hover { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); transform: translateY(-1px); }
.rd-btn:active { transform: translateY(0.5px); }
.rd-btn--ghost { background: transparent; box-shadow: none; }
.rd-btn--ghost:hover { background: var(--fs-bg-sunken); box-shadow: none; }
.rd-btn--danger { color: var(--fs-danger); }
.rd-btn--danger:hover { color: var(--fs-danger); box-shadow: inset 0 0 0 1px var(--fs-danger); background: transparent; }
.rd-btn.speaking {
  color: var(--fs-danger);
  animation: rd-pulse 1.2s ease-in-out infinite;
}
@keyframes rd-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

/* ===== 滚动区 ===== */
.rd-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

/* 空态/错误态（v0 empty） */
.rd-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--fs-ink-500);
  font-size: 13px;
  text-align: center;
}
.rd-empty__ic { width: 22px; height: 22px; color: var(--fs-ink-400); }
.rd-empty__hint { font-size: 11px; color: var(--fs-ink-400); }

/* ===== 纸张（v0 rep-paper：760px 居中 + 大留白） ===== */
.rd-paper {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 32px 96px;
}
.rd-title {
  margin: 0;
  font-size: 30px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.35;
  color: var(--fs-ink-900);
  padding-bottom: 16px;
  border-bottom: 1px solid var(--fs-hairline-strong);
}
.rd-meta {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  font-size: 11px;
  letter-spacing: 0.01em;
  font-variant-numeric: tabular-nums;
  color: var(--fs-ink-400);
}
.rd-meta__warn {
  color: var(--fs-warning);
  background: color-mix(in srgb, var(--fs-warning) 10%, transparent);
  padding: 0 6px;
  border-radius: var(--fs-r-xs, 3px);
}

/* 摘要（v0 blockquote 同构：accent 左缘注记） */
.rd-summary {
  margin-top: 20px;
  padding-left: 16px;
  border-left: 1px solid var(--fs-accent);
  color: var(--fs-ink-500);
  font-size: 14px;
  line-height: 1.8;
}
.rd-summary strong {
  font-weight: 600;
  color: var(--fs-ink-900);
  margin-right: 8px;
}

/* ===== 正文（v0 .paper 同构：15px/1.9 文档排版 + 三线表） ===== */
.rd-body {
  margin-top: 32px;
  font-size: 15px;
  line-height: 1.9;
  color: var(--fs-ink-700);
  text-wrap: pretty;
  word-break: break-word;
}
.rd-body :deep(p) { margin: 0 0 1em; }
.rd-body :deep(h1),
.rd-body :deep(h2) {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--fs-ink-900);
  margin: 1.8em 0 0.7em;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--fs-hairline);
}
.rd-body :deep(h3),
.rd-body :deep(h4) {
  font-size: 15px;
  font-weight: 600;
  color: var(--fs-ink-900);
  margin: 1.4em 0 0.5em;
}
.rd-body :deep(strong) { font-weight: 600; color: var(--fs-ink-900); }
.rd-body :deep(ul),
.rd-body :deep(ol) { margin: 0 0 1em; padding-left: 1.2em; }
.rd-body :deep(li) { margin-bottom: 0.35em; }
.rd-body :deep(blockquote) {
  margin: 1.2em 0;
  padding-left: 16px;
  border-left: 1px solid var(--fs-accent);
  color: var(--fs-ink-500);
  font-size: 14px;
}
.rd-body :deep(code) {
  font-family: var(--fs-font-mono);
  font-size: 13px;
  background: var(--fs-bg-sunken);
  padding: 1px 5px;
  border-radius: var(--fs-r-xs, 3px);
}
.rd-body :deep(pre) {
  background: var(--fs-bg-sunken);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
  padding: 12px 14px;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
.rd-body :deep(pre code) { background: transparent; padding: 0; }
/* 顶刊三线表：表头下 1px + 表底 1px，无竖线无斑马纹 */
.rd-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1.2em 0 1.6em;
  font-size: 13px;
}
.rd-body :deep(th) {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
  text-align: left;
  padding: 6px 10px 6px 0;
  border-bottom: 1px solid var(--fs-hairline-strong);
}
.rd-body :deep(td) {
  padding: 7px 10px 7px 0;
  border-bottom: 1px solid var(--fs-hairline);
  color: var(--fs-ink-700);
  font-variant-numeric: tabular-nums;
}
.rd-body :deep(tr:last-child td) { border-bottom: 1px solid var(--fs-hairline-strong); }
.rd-body :deep(th[align='right']),
.rd-body :deep(td[align='right']) {
  text-align: right;
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
}

.rd-body-empty {
  margin-top: 32px;
  padding: 32px;
  text-align: center;
  font-size: 13px;
  color: var(--fs-ink-500);
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-md, 10px);
}

@media (max-width: 900px) {
  .rd-paper { padding: 24px 20px 48px; }
  .rd-title { font-size: 24px; }
}

/* 按钮 hover/按下位移受双闸门管控；播报脉冲已挂 mo-loop，由全局循环闸门接管 */
html[data-motion-allowed="false"] .rd-btn:hover,
html[data-motion-allowed="false"] .rd-btn:active { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .rd-btn:hover,
  html:not([data-motion="on"]) .rd-btn:active { transform: none; }
}
</style>
