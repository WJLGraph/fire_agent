<script setup>
/**
 * 知识库 · RAG 回答卡（v0 kb-ans 同构）
 *
 * 头部：标题 + 真实模型徽标（后端 result.llm_model，降级时附「已降级」标记）+ 播报；
 * 正文：流式打字机（纯文本）/ 终态 Markdown 渲染（[来源N] 高亮可点击联动引用列表）；
 *       思考过程折叠面板（默认收起，DeepSeek 风格）：<think> 双层拆分
 *       （后端 _ThinkFilter/_split_think + 前端 splitThink 兜底旧数据）。
 * 受控组件：回答结果、流式缓冲文本、asking 由父组件持有；引用展开项在本组件内闭环。
 */
import { ref, computed, watch, nextTick } from 'vue'
import { speakState, speakText } from '@/utils/speech'
import { renderMarkdown, splitThink } from '@/utils/markdown'
import KbRetrievalPanel from './KbRetrievalPanel.vue'
import KbReferenceList from './KbReferenceList.vue'

const props = defineProps({
  result: { type: Object, default: null },
  streamText: { type: String, default: '' },
  asking: { type: Boolean, default: false },
  streamMeta: { type: Object, default: null },   // 流式期间的检索元信息（meta 事件先行到达）
  streamThink: { type: String, default: '' },    // 思考过程增量（qwen3 / DeepSeek 系 <think> 段）
})

// 当前展开的引用来源（点击切换）
const activeIndex = ref(null)

// 思考过程拆分（新记录：后端 reasoning 字段；旧记录：从 answer 文本中剥离兜底）
const parts = computed(() => splitThink(props.result?.answer || ''))
const cleanAnswer = computed(() => parts.value.answer)
const streamClean = computed(() => splitThink(props.streamText).answer)
const reasoning = computed(() => (props.result?.reasoning || '').trim() || parts.value.reasoning)
const thinkOpen = ref(false)
// 思考过程 Markdown 渲染（思考文本含 **加粗**/列表/小节等 md 语法；renderMarkdown 已全量转义）
// 注意：streamThink 是 prop 字符串（非 ref），reasoning 是 computed ref，取值方式不同
const thinkHtml = computed(() => renderMarkdown(reasoning.value))

// ====== 流式"深度思考中"面板（DeepSeek 同款：思考阶段展开，首段回答到达自动收起） ======
const thinkLiveOpen = ref(true)
let thinkFolded = false
// 流式思考渲染：180ms 节流（每 chunk 全量渲染是 O(n²)，长思考会越到后面越卡——实测修复），
// 渲染与自动滚动同节奏合并；面板收起时跳过渲染
const streamThinkHtml = ref('')
const liveThinkBody = ref(null)
let thinkRenderTimer = null
watch(() => [props.streamThink, thinkLiveOpen.value], ([, open]) => {
  if (thinkRenderTimer) return
  thinkRenderTimer = setTimeout(() => {
    thinkRenderTimer = null
    if (!open) return // 收起时不渲染，重新展开时由下方 watch 立即补渲
    streamThinkHtml.value = renderMarkdown(props.streamThink || '')
    nextTick(() => {
      const el = liveThinkBody.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }, 180)
}, { immediate: true })
watch(thinkLiveOpen, (open) => {
  if (open && !thinkRenderTimer) {
    streamThinkHtml.value = renderMarkdown(props.streamThink || '')
  }
})
watch(() => props.streamClean, (v, o) => {
  if (!o && v && !thinkFolded) { thinkLiveOpen.value = false; thinkFolded = true }
})
watch(() => props.streamThink, (v) => {
  if (v && !thinkFolded) thinkLiveOpen.value = true
})
const thinkPhase = computed(() => (streamClean.value ? '已深度思考' : '深度思考中'))
// 展示模型名：优先真实模型；旧记录无字段时回退 LLM
const modelLabel = computed(() => props.result?.llm_model || (props.result?.llm_used ? 'LLM' : ''))

// 终态 Markdown 渲染 + [来源N] 上标角标（renderMarkdown 已全量 HTML 转义，此处只追加固定安全标签）
// 容错：兼容 "[来源1]" / "[来源 1]" 两种写法；角标点击 → 展开并滚动到引用列表对应条目；
// 连续角标间的空格折叠（"[来源1] [来源2]" → 紧凑上标组）
const answerHtml = computed(() =>
  renderMarkdown(cleanAnswer.value)
    .replace(/\[来源\s*(\d+)\]/g, '<sup class="kb-cite-num" data-cite="$1" title="跳转到来源 $1">$1</sup>')
    .replace(/(<\/sup>)\s+(<sup)/g, '$1$2'),
)

// 点击正文中的来源角标 → 展开下方引用列表对应项并平滑滚动过去
const refListRef = ref(null)
const onBodyClick = (e) => {
  const sup = e.target.closest('.kb-cite-num')
  if (!sup) return
  const i = Number(sup.dataset.cite) - 1
  const refs = props.result?.references || []
  if (i >= 0 && i < refs.length) {
    activeIndex.value = i
    refListRef.value?.scrollTo(i)
  }
}
</script>

<template>
  <div class="ka">
    <!-- 检索过程（v0 顺序：检索 → 回答 → 引用；流式期间 meta 先行渲染） -->
    <KbRetrievalPanel :retrieval="(result && result.retrieval) || streamMeta" />

    <!-- P2#18：回答流式生成中（打字机增量；来源引用在流结束后随 done 附上） -->
    <div v-if="asking && (streamClean || streamThink)" class="kb-ans">
      <div class="kb-ans__hd">
        <span class="kb-ans__t">RAG 回答</span>
        <span class="kb-ans__live"><i></i>{{ streamClean ? '生成中' : '思考中' }}</span>
        <span class="kb-ans__sp"></span>
      </div>

      <!-- 流式思考过程（DeepSeek 同款：思考中展开实时滚动，首段回答到达自动收起） -->
      <div v-if="streamThink" class="kb-think kb-think--live" :class="{ open: thinkLiveOpen }">
        <button class="kb-think__hd" @click="thinkLiveOpen = !thinkLiveOpen">
          <svg class="kb-think__chev" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m7.5 5 5 5-5 5"/></svg>
          <span>{{ thinkPhase }}</span>
          <span class="kb-think__len">{{ streamThink.length }} 字</span>
        </button>
        <div v-show="thinkLiveOpen" ref="liveThinkBody" class="kb-think__bd kb-think__bd--md"><span class="kb-md" v-html="streamThinkHtml"></span><span v-if="!streamClean" class="ka-cursor">▌</span></div>
      </div>

      <div v-if="streamClean" class="kb-ans__bd kb-ans__bd--raw">{{ streamClean }}<span class="ka-cursor">▌</span></div>
    </div>

    <!-- 终态结果 -->
    <template v-if="result">
      <div class="kb-ans">
        <div class="kb-ans__hd">
          <span class="kb-ans__t">RAG 回答</span>
          <span v-if="result.llm_used" class="kb-ans__model" :title="`回答模型 ${modelLabel}`">{{ modelLabel }}</span>
          <span v-if="result.llm_used && result.llm_degraded" class="kb-ans__degraded" title="主提供商不可用，本次回答由降级通道生成">已降级</span>
          <span v-if="!result.llm_used" class="kb-ans__fallback">关键词·向量检索</span>
          <span class="kb-ans__sp"></span>
          <button
            class="kb-ans__btn"
            :class="{ speaking: speakState.speaking || speakState.loading }"
            :title="speakState.speaking || speakState.loading ? '停止播报' : '语音播报回答'"
            @click="speakText(cleanAnswer)"
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8v4h2.6l3.4 3V5L6.6 8z"/><path d="M13.2 7.6a3.6 3.6 0 0 1 0 4.8"/></svg>
            {{ speakState.speaking || speakState.loading ? '停止' : '播报' }}
          </button>
        </div>
        <!-- 思考过程折叠面板（默认收起；新记录来自后端 reasoning 字段，旧记录从 answer 剥离） -->
        <div v-if="reasoning" class="kb-think" :class="{ open: thinkOpen }">
          <button class="kb-think__hd" @click="thinkOpen = !thinkOpen">
            <svg class="kb-think__chev" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m7.5 5 5 5-5 5"/></svg>
            <span>思考过程</span>
            <span class="kb-think__len">{{ reasoning.length }} 字</span>
          </button>
          <div v-show="thinkOpen" class="kb-think__bd kb-think__bd--md"><span class="kb-md" v-html="thinkHtml"></span></div>
        </div>
        <!-- 终态 Markdown 渲染；[来源N] 角标点击联动引用列表 -->
        <div class="kb-ans__bd markdown-body" @click.capture="onBodyClick" v-html="answerHtml"></div>
      </div>

      <!-- 引用溯源（v0 kb-cite 列表；角标点击跳转到对应条目） -->
      <KbReferenceList
        v-if="result.references && result.references.length > 0"
        ref="refListRef"
        v-model:active-index="activeIndex"
        :references="result.references"
      />

      <!-- 检索为空提示 -->
      <div v-else class="ka-nomatch">
        RagAgent 在知识库中未找到相关片段，请先上传与问题相关的文档。
      </div>
    </template>
  </div>
</template>

<style scoped>
.ka {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 回答卡（v0 kb-ans：表面卡 + 发丝环；悬停加亮、挂载升起） */
.kb-ans {
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
  transition: box-shadow var(--up-dur-fast, 120ms) var(--fs-ease);
  animation: ka-in 0.4s var(--fs-ease-out) both;
}
.kb-ans:hover { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
@keyframes ka-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.kb-ans__hd {
  min-height: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
/* 标题 2px 刻度条：静息发丝、悬停转强调 */
.kb-ans__t { display: inline-flex; align-items: center; font-size: 13px; font-weight: 500; color: var(--fs-ink-900); }
.kb-ans__t::before {
  content: '';
  width: 2px;
  height: 11px;
  margin-right: 7px;
  border-radius: 1px;
  background: var(--fs-hairline-strong);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, ease);
}
.kb-ans:hover .kb-ans__t::before { background: var(--fs-accent); }
.kb-ans__sp { flex: 1; }
.kb-ans__model {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  font-size: 11px;
  letter-spacing: 0.02em;
}
.kb-ans__fallback {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-size: 11px;
}
.kb-ans__degraded {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-warn-soft, rgba(217, 119, 6, 0.12));
  color: var(--fs-warn, #b45309);
  font-size: 11px;
}
/* 正文来源角标（[来源N] → accent 上标数字，点击跳转到引用列表对应条目） */
.kb-ans__bd :deep(.kb-cite-num) {
  color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  padding: 0 1px;
  margin: 0 0.5px;
  cursor: pointer;
  vertical-align: super;
  user-select: none;
  border-radius: 2px;
  transition: background var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.kb-ans__bd :deep(.kb-cite-num:hover) {
  background: var(--fs-accent-soft);
  text-decoration: underline;
}
.kb-ans__btn {
  height: 26px;
  padding: 0 9px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.kb-ans__btn svg { width: 12px; height: 12px; }
.kb-ans__btn:hover { color: var(--fs-ink-900); background: var(--fs-bg-sunken); }
.kb-ans__btn.speaking { color: var(--fs-danger); }

/* 思考过程折叠面板（DeepSeek 风格：默认收起、沉底灰调） */
.kb-think {
  border-bottom: 1px solid var(--fs-hairline);
  background: var(--fs-bg-sunken);
}
/* 流式思考态：标题呼吸（"深度思考中…"进行感） */
.kb-think--live .kb-think__hd > span:first-of-type {
  animation: ka-pulse 1.2s ease-in-out infinite;
}
.kb-think__hd {
  width: 100%;
  height: 36px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  font-size: 12px;
  color: var(--fs-ink-500);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.kb-think__hd:hover { color: var(--fs-ink-900); background: rgba(var(--fs-ink-900-rgb), 0.03); }
.kb-think__chev {
  width: 12px;
  height: 12px;
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
.kb-think.open .kb-think__chev { transform: rotate(90deg); }
.kb-think__len {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
}
.kb-think__bd {
  max-height: 260px;
  overflow-y: auto;
  padding: 10px 16px 14px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--fs-ink-500);
  white-space: pre-wrap;
  word-break: break-word;
  border-top: 1px dashed var(--fs-hairline);
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
/* 思考过程 Markdown 渲染态：块级排版由 .kb-md 接管，关闭纯文本 pre-wrap */
.kb-think__bd--md { white-space: normal; }
.kb-md {
  display: block;
  font-size: 12.5px;
  line-height: 1.8;
}
.kb-md :deep(p) { margin: 0 0 8px; }
.kb-md :deep(p:last-child) { margin-bottom: 0; }
.kb-md :deep(h1), .kb-md :deep(h2), .kb-md :deep(h3), .kb-md :deep(h4) {
  margin: 10px 0 5px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--fs-ink-900);
}
.kb-md :deep(ul), .kb-md :deep(ol) { margin: 0 0 8px; padding-left: 18px; }
.kb-md :deep(li) { margin: 3px 0; }
.kb-md :deep(strong) { color: var(--fs-ink-900); font-weight: 600; }
.kb-md :deep(code) {
  padding: 0 4px;
  border-radius: 3px;
  background: var(--fs-bg-sunken);
  font-family: var(--fs-font-mono);
  font-size: 11px;
}
.kb-md :deep(blockquote) {
  margin: 4px 0;
  padding: 2px 10px;
  border-left: 2px solid var(--fs-hairline-strong);
  color: var(--fs-ink-400);
}
.kb-md :deep(table) { margin: 6px 0; border-collapse: collapse; }
.kb-md :deep(th), .kb-md :deep(td) {
  padding: 3px 8px;
  border: 1px solid var(--fs-hairline);
  font-size: 11px;
}
.kb-md :deep(hr) { margin: 8px 0; border: none; border-top: 1px dashed var(--fs-hairline); }

.kb-ans__bd {
  padding: 16px 18px;
  font-size: 13.5px;
  line-height: 1.9;
  color: var(--fs-ink-700);
  word-break: break-word;
}
/* ===== 回答 Markdown 排版（呼吸感行距：段落 12px、块间距统一 4px 倍数阶梯） ===== */
.kb-ans__bd :deep(p) { margin: 0 0 12px; }
.kb-ans__bd :deep(p:last-child) { margin-bottom: 0; }
.kb-ans__bd :deep(h1), .kb-ans__bd :deep(h2), .kb-ans__bd :deep(h3), .kb-ans__bd :deep(h4) {
  margin: 16px 0 8px;
  font-size: 14.5px;
  font-weight: 600;
  color: var(--fs-ink-900);
  letter-spacing: -0.005em;
}
.kb-ans__bd :deep(h1:first-child), .kb-ans__bd :deep(h2:first-child), .kb-ans__bd :deep(h3:first-child) { margin-top: 0; }
.kb-ans__bd :deep(ul), .kb-ans__bd :deep(ol) { margin: 0 0 12px; padding-left: 20px; }
.kb-ans__bd :deep(li) { margin: 5px 0; }
.kb-ans__bd :deep(li::marker) { color: var(--fs-ink-400); }
.kb-ans__bd :deep(strong) { color: var(--fs-ink-900); font-weight: 600; }
.kb-ans__bd :deep(code) {
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--fs-bg-sunken);
  font-family: var(--fs-font-mono);
  font-size: 12px;
}
.kb-ans__bd :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 14px;
  border-left: 2px solid var(--fs-accent);
  background: var(--fs-accent-soft);
  border-radius: 0 var(--fs-r-xs, 3px) var(--fs-r-xs, 3px) 0;
  color: var(--fs-ink-500);
}
.kb-ans__bd :deep(blockquote p:last-child) { margin-bottom: 0; }
.kb-ans__bd :deep(table) { margin: 12px 0; border-collapse: collapse; width: 100%; }
.kb-ans__bd :deep(th), .kb-ans__bd :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--fs-hairline);
  font-size: 12.5px;
  text-align: left;
  font-variant-numeric: tabular-nums;
}
.kb-ans__bd :deep(th) { background: var(--fs-bg-sunken); font-weight: 600; color: var(--fs-ink-900); }
.kb-ans__bd :deep(hr) { margin: 12px 0; border: none; border-top: 1px dashed var(--fs-hairline); }
/* 流式打字机为纯文本：保留换行；终态走 markdown-body 排版 */
.kb-ans__bd--raw { white-space: pre-wrap; }

/* 流式生成中徽标 + 光标 */
.kb-ans__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-size: 11px;
  animation: ka-pulse 1.2s ease-in-out infinite;
}
.kb-ans__live i {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
}
.ka-cursor {
  display: inline-block;
  color: var(--fs-accent);
  animation: ka-blink 1s step-start infinite;
}
@keyframes ka-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
@keyframes ka-blink {
  50% { opacity: 0; }
}

/* 未命中提示（v0 empty 同构） */
.ka-nomatch {
  padding: 24px;
  font-size: 12px;
  line-height: 1.7;
  text-align: center;
  color: var(--fs-ink-500);
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-md, 10px);
  animation: ka-in 0.4s var(--fs-ease-out) both;
}

/* ===== 动效闸门：关闭时循环停、入场落终态 ===== */
html[data-motion-allowed="false"] .kb-ans,
html[data-motion-allowed="false"] .ka-nomatch,
html[data-motion-allowed="false"] .kb-ans__live,
html[data-motion-allowed="false"] .kb-think--live .kb-think__hd > span:first-of-type,
html[data-motion-allowed="false"] .ka-cursor { animation: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .kb-ans,
  html:not([data-motion="on"]) .ka-nomatch,
  html:not([data-motion="on"]) .kb-ans__live,
  html:not([data-motion="on"]) .kb-think--live .kb-think__hd > span:first-of-type,
  html:not([data-motion="on"]) .ka-cursor { animation: none; }
}
</style>
