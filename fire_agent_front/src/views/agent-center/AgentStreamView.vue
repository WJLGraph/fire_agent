<script setup>
/**
 * Agent 协作中心 · 报告正文（SSE 实时流式区，v0 report-stream 同构）
 *
 * 头部：报告标题 + 状态徽标 + 字数 mono 徽标；正文分两态：
 *   - 打字机态（生成中）：等宽打字机逐字上屏；
 *   - 草稿态（generate_report 步骤完成、评审进行中）：整篇 Markdown 渲染展示，
 *     评审/审批流程继续在后台走（draftReady 由父组件按步骤行注入）。
 * 思考过程两段式（问题 B，同一数据源 streamThink，两处宿主互斥不同时显示）：
 *   - 本轮思考进行中（正文未产出）：在本卡内渲染共用的 AgentThinkPanel
 *     （可折叠/标题/字数/状态标签/贴底跟随，与第 5 节点面板完全一致）；
 *   - 正文首个 delta 到达：思考迁回第 5 节点「生成报告」卡片面板，本卡只留正文；
 *   - 无正文流的终态回填不经过本卡（streamActive=false 时本卡不渲染）。
 */
import { ref, computed, watch, nextTick } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import AgentThinkPanel from '@/components/agent-center/AgentThinkPanel.vue'

const props = defineProps({
  /** 流式累积的报告内容（本轮正文增量；思考期显示为下方草稿区） */
  streamReport: { type: String, default: '' },
  /** 思考过程累积全文（全部轮次）：思考期内为本卡宿主内容，正文开始后迁回第 5 节点 */
  streamThink: { type: String, default: '' },
  /** 本轮正文是否已开始产出：false → 思考宿主 + 草稿区同显；true → 正文打字机 */
  bodyStarted: { type: Boolean, default: false },
  /** 生成步骤已完成（评审进行中）→ 正文切换为渲染好的草稿预览 */
  draftReady: { type: Boolean, default: false },
})

const streamBodyRef = ref(null)

// 头部徽标：思考中 → 生成中 → 草稿预览（评审中）→ 等待输出
const liveText = computed(() => {
  if (props.draftReady) return '草稿预览 · 评审中'
  return props.streamReport ? '流式生成中' : (props.streamThink ? '深度思考中' : '等待输出')
})

// 字数紧凑显示
const fmtLen = computed(() => {
  const n = props.streamReport.length
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k 字` : `${n} 字`
})

// 草稿态：整篇 Markdown 渲染（评审进行中持续重渲；评审退回重写时缓冲清空回到打字机态）
const draftHtml = computed(() => renderMarkdown(props.streamReport || ''))

// 思考期宿主：渲染/节流/贴底跟随全部收口在 AgentThinkPanel（与第 5 节点面板同一实现）

// 打字机态正文自动滚动：仅在用户本就贴近底部时跟随（每 flush 一次，不逐增量读布局；
// 用户向上回看时不强行拽回底部）
watch(() => props.streamReport, () => {
  if (props.draftReady) return
  nextTick(() => {
    const el = streamBodyRef.value
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    if (nearBottom) el.scrollTop = el.scrollHeight
  })
})
// 打字机 → 草稿切换时回到顶部阅读
watch(() => props.draftReady, (v) => {
  if (v) nextTick(() => {
    const el = streamBodyRef.value
    if (el) el.scrollTop = 0
  })
})
</script>

<template>
  <section class="rs">
    <div class="rs__hd">
      <span class="rs__t">分析报告</span>
      <span class="rs__live" :class="{ 'is-draft': draftReady }"><i></i>{{ liveText }}</span>
      <span class="rs__sp"></span>
      <span class="rs__n mono">{{ streamReport ? fmtLen : '等待输出' }}</span>
    </div>

    <!-- 五态优先级：思考宿主+草稿区同显（本轮正文未开始，草稿=实时增量/占位）>
         草稿（评审中）> 正文打字机 > 等待占位；
         思考面板在上、草稿在下，互不重复；正文首个 delta 后思考迁回第 5 节点 -->
    <div v-if="streamThink && !bodyStarted" class="rs__bd rs__bd--think">
      <AgentThinkPanel :text="streamThink" />
      <div v-if="streamReport" class="rs__draftblk">
        <span class="rs__draftblk__hd">草稿预览（正文生成中，完成后替换本区）</span>
        <span class="amd-md rs__draftblk__bd" v-html="draftHtml"></span>
      </div>
      <div v-else class="rs__wait rs__wait--below"><span class="rs__dots"><i></i><i></i><i></i></span>草稿生成中：思考完成后正文将逐字上屏…</div>
    </div>
    <div v-else-if="draftReady" class="rs__bd rs__bd--md"><span class="amd-md" v-html="draftHtml"></span></div>
    <pre v-else-if="streamReport" ref="streamBodyRef" class="rs__bd">{{ streamReport }}<span class="rs__cursor"></span></pre>
    <pre v-else ref="streamBodyRef" class="rs__bd"><span class="rs__wait"><span class="rs__dots"><i></i><i></i><i></i></span>ReportAgent 正在撰写报告，输出将逐字上屏…<span class="rs__cursor"></span></span></pre>
  </section>
</template>

<style scoped>
/* v0 report-stream：表面卡 + 发丝环 */
.rs {
  /* 中列是定高 flex 容器：报告卡吃掉流水线收起后腾出的高度，
     正文自身滚动（此前 flex-shrink:0 + max-height:420px 会留一大片空白） */
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
  animation: rs-in 0.4s var(--fs-ease-out) both;
}
.rs__hd {
  flex-shrink: 0;
  min-height: 48px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.rs__t {
  position: relative;
  padding-left: 9px;
  font-size: 14px;
  font-weight: 600;
  color: var(--fs-ink-900);
}
/* 报告卡标题刻度（与小节标题同一语言） */
.rs__t::before {
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
.rs__sp { flex: 1; }
/* v0 badge--accent 同构：状态徽标 */
.rs__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-size: 11px;
  font-weight: 500;
  animation: rs-pulse 1.6s ease-in-out infinite;
}
.rs__live.is-draft { background: var(--fs-bg-sunken); color: var(--fs-ink-700); animation: none; }
.rs__live i {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
}
/* v0 badge--muted mono 同构：字数 */
.rs__n {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
}
/* 正文：文档感（15px/1.9 正常字体，v0 stream-body 同构；非终端等宽） */
.rs__bd {
  flex: 1;
  /* 铺满剩余高度，但不塌成一条：流水线展开时至少保留一屏可读正文，超出由本框滚动 */
  min-height: 220px;
  margin: 0;
  overflow-y: auto;
  padding: 20px;
  font-size: 15px;
  line-height: 1.9;
  color: var(--fs-ink-700);
  white-space: pre-wrap;
  word-break: break-word;
  text-wrap: pretty;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
/* 草稿态：Markdown 块级排版（关闭 pre-wrap，复用紧凑 md 样式） */
.rs__bd--md { white-space: normal; font-size: 14px; line-height: 1.85; }
/* 首个 delta 到达前的等待态：三点跳动 + 提示文案（进入生成节点即刻可见） */
.rs__wait {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--fs-ink-400);
  font-size: 13px;
}
.rs__dots {
  display: inline-flex;
  gap: 4px;
}
.rs__dots i {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: var(--fs-accent);
  animation: rs-hop 1.2s ease-in-out infinite;
}
.rs__dots i:nth-child(2) { animation-delay: 0.15s; }
.rs__dots i:nth-child(3) { animation-delay: 0.3s; }
@keyframes rs-hop {
  0%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
/* v0 caret：1px 细线光标（accent，闪烁） */
.rs__cursor {
  display: inline-block;
  width: 1px;
  height: 1em;
  background: var(--fs-accent);
  vertical-align: text-bottom;
  margin-left: 1px;
  animation: rs-blink 1.1s steps(2) infinite;
}
@keyframes rs-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
@keyframes rs-blink {
  50% { opacity: 0; }
}
@keyframes rs-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
/* 动效三态降级：入场/呼吸/光标闪烁全静止，状态语义由颜色与文案承担 */
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .rs { animation: none; }
  html:not([data-motion="on"]) .rs__live,
  html:not([data-motion="on"]) .rs__dots i,
  html:not([data-motion="on"]) .rs__cursor { animation: none; }
}
html[data-motion-allowed="false"] .rs,
html[data-motion-allowed="false"] .rs__live,
html[data-motion-allowed="false"] .rs__dots i,
html[data-motion-allowed="false"] .rs__cursor { animation: none; }
/* 关闭动效时光标不留下半截空白观感 */
html[data-motion-allowed="false"] .rs__cursor { opacity: 0.7; }

/* ===== 思考期宿主：整宽内嵌 AgentThinkPanel（与第 5 节点面板同一组件同一视觉），
   「等待写报告」提示排在其下方（flex column + gap，不贴边、不悬浮、不挤压面板） ===== */
.rs__bd--think {
  display: flex;
  flex-direction: column;
  gap: 10px;
  white-space: normal;
  font-size: 14px;
  line-height: 1.85;
}
.rs__wait--below { display: flex; } /* 块级占行：面板展开/折叠时始终在下方 */
/* 思考期草稿区（思考+草稿同显）：Markdown 渲染、可滚动、样式与正文一致 */
.rs__draftblk {
  min-height: 60px;
  max-height: 200px;
  overflow-y: auto;
  padding: 8px 10px;
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
  background: var(--fs-bg-surface);
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
.rs__draftblk__hd {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--fs-ink-400);
}
.rs__draftblk__bd {
  color: var(--fs-ink-600, var(--fs-ink-700));
}

/* ===== 草稿 Markdown 渲染 ===== */
.amd-md {
  display: block;
  font-size: 12.5px;
  line-height: 1.75;
}
.amd-md :deep(p) { margin: 0 0 8px; }
.amd-md :deep(p:last-child) { margin-bottom: 0; }
.amd-md :deep(h1), .amd-md :deep(h2), .amd-md :deep(h3), .amd-md :deep(h4) {
  margin: 10px 0 5px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--fs-ink-900);
}
.amd-md :deep(ul), .amd-md :deep(ol) { margin: 0 0 8px; padding-left: 18px; }
.amd-md :deep(li) { margin: 3px 0; }
.amd-md :deep(strong) { color: var(--fs-ink-900); font-weight: 600; }
.amd-md :deep(code) {
  padding: 0 4px;
  border-radius: 3px;
  background: var(--fs-bg-surface);
  font-family: var(--fs-font-mono);
  font-size: 11px;
}
.amd-md :deep(blockquote) {
  margin: 4px 0;
  padding: 2px 10px;
  border-left: 2px solid var(--fs-hairline-strong);
  color: var(--fs-ink-400);
}
.amd-md :deep(table) { margin: 6px 0; border-collapse: collapse; }
.amd-md :deep(th), .amd-md :deep(td) {
  padding: 3px 8px;
  border: 1px solid var(--fs-hairline);
  font-size: 11px;
}
.amd-md :deep(hr) { margin: 8px 0; border: none; border-top: 1px dashed var(--fs-hairline); }
</style>
