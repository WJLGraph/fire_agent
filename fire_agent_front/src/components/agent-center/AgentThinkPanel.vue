<script setup>
/**
 * Agent 协作中心 · 思考过程面板（共用组件）
 *
 * 两个宿主共用同一实现，避免两套样式/两套渲染跑偏：
 *   - AgentStreamView「分析报告」流式卡：本轮思考进行中（正文未产出）时宿主于此；
 *   - AgentPipeline 第 5 节点「生成报告 ReportAgent」：正文首个 delta 后迁回于此常驻。
 *
 * 统一交互与外观：
 *   - 标题行：折叠箭头 + 「深度思考/思考过程」+ 字数徽标 + 状态标签（复读中断/已折叠等）；
 *   - 默认收起，首个思考增量自动展开并贴底跟随；用户手动折叠后保持折叠
 *     （展开态存在 useAgentStreamState 模块级共享，两处宿主迁移时延续）；
 *   - 主体 Markdown 渲染（renderMarkdown 全量 HTML 转义），固定最大高度内部滚动，
 *     流式增量 150ms 节流重渲。
 */
import { ref, computed, watch, nextTick } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { dedupeThinkText, thinkLenText, streamNoteText } from '@/utils/thinkText'
import { useAgentStreamState, toggleThinkPanel, autoOpenThinkPanel } from '@/composables/useAgentStreamState'

const props = defineProps({
  /** 思考全文（全部轮次，已含「第 N 轮思考」小标题；原始文本，组件内部做展示清洗） */
  text: { type: String, default: '' },
  /** 本轮思考进行中：标题显示「深度思考」并带脉动状态点 */
  active: { type: Boolean, default: false },
  /** 流式中断标记（think_loop/think_limit/content_loop/cancelled），空串不显示 */
  note: { type: String, default: '' },
})

// 展开态模块级共享：报告区 → 第 5 节点迁移时，用户手动折叠的选择延续（不自动重新展开）
const { thinkPanelOpen } = useAgentStreamState()

// 展示清洗（极端复读行折叠 + 超长保留尾部）。
// 性能关键：view 只在面板展开且节流到期时才被 render() 读取（computed 惰性求值）；
// 折叠状态下 watch getter 不读 props.text，增量不触发任何清洗/渲染计算
const view = computed(() => dedupeThinkText(props.text))

// 首个思考增量到达自动展开（含宿主迁移后挂载时补判定；touched 后不干预）
watch(() => props.text, (v) => {
  if (v) autoOpenThinkPanel()
}, { immediate: true })

// Markdown 渲染：150ms 节流（合并 burst 内多个 chunk，长文本避免 O(n²) 卡顿）。
// watch getter 依赖 thinkPanelOpen 短路：折叠时返回 null，不追踪 props.text（零计算）；
// 展开瞬间由下方 watch 立即补渲一次
const html = ref('')
let timer = null
const render = () => {
  html.value = renderMarkdown(view.value.body)
}
watch(() => (thinkPanelOpen.value ? props.text : null), () => {
  if (!thinkPanelOpen.value) return
  if (timer) return
  timer = setTimeout(() => {
    timer = null
    if (thinkPanelOpen.value) render()
  }, 150)
}, { immediate: true })
watch(thinkPanelOpen, (open) => {
  if (open) render()
})

// 实时增量贴底跟随（getter 同样折叠短路；收起时跳过）
const bodyRef = ref(null)
watch(() => (thinkPanelOpen.value ? props.text : ''), () => {
  if (!thinkPanelOpen.value) return
  nextTick(() => {
    const el = bodyRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
})
</script>

<template>
  <div class="tk">
    <button class="tk__hd" @click="toggleThinkPanel">
      <svg class="tk__chev" :class="{ 'is-open': thinkPanelOpen }" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m7.5 5 5 5-5 5"/></svg>
      <span>{{ active ? '深度思考' : '思考过程' }}</span>
      <span v-if="active" class="tk__live"><i></i>思考中</span>
      <span class="tk__len mono">{{ thinkLenText(text.length) }}</span>
      <span v-if="note" class="tk__note">{{ streamNoteText(note) }}</span>
    </button>
    <div v-show="thinkPanelOpen" ref="bodyRef" class="tk__bd">
      <span class="amd-md" v-html="html"></span>
    </div>
  </div>
</template>

<style scoped>
/* sunken 底折叠面板（与第 5 节点原思考面板同一套 token/边框/字号） */
.tk {
  border-radius: var(--fs-r-sm, 6px);
  background: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.tk__hd {
  width: 100%;
  height: 28px;
  padding: 0 9px;
  display: flex;
  align-items: center;
  gap: 5px;
  border: none;
  background: transparent;
  color: var(--fs-ink-500);
  font-size: 11px;
  cursor: pointer;
  text-align: left;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.tk__hd:hover { color: var(--fs-ink-900); background: color-mix(in srgb, var(--fs-ink-900) 4%, transparent); }
.tk__chev {
  width: 11px;
  height: 11px;
  flex: none;
  color: var(--fs-ink-400);
  transition: transform var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.tk__chev.is-open { transform: rotate(90deg); }
.tk__hd:hover .tk__chev { color: inherit; }
/* 思考中状态点（accent 脉动，与报告卡 live 徽标同语言） */
.tk__live {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 16px;
  padding: 0 6px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-size: 10px;
  animation: tk-pulse 1.6s ease-in-out infinite;
}
.tk__live i {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: currentColor;
}
@keyframes tk-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
/* 动效三态降级：脉动静止，「思考中」语义由徽标文案与配色承担 */
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .tk__live { animation: none; }
}
html[data-motion-allowed="false"] .tk__live { animation: none; }
.tk__len {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
}
.tk__note {
  margin-left: auto;
  font-size: 10px;
  color: var(--fs-warning);
  white-space: nowrap;
}
.tk__note + .tk__note { margin-left: 6px; }
.tk__bd {
  max-height: 240px;
  min-height: 40px;
  overflow-y: auto;
  padding: 6px 10px 10px;
  border-top: 1px dashed var(--fs-hairline);
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--fs-ink-500);
  word-break: break-word;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

/* 思考 Markdown 渲染排版（标题/列表/加粗/表格；固定最大高度，长文本滚动稳定） */
.amd-md {
  display: block;
  font-size: 12px;
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
.amd-md :deep(em) { color: var(--fs-ink-700); }
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
.amd-md :deep(.md-table-wrap) { max-width: 100%; overflow-x: auto; }
.amd-md :deep(table) { margin: 6px 0; border-collapse: collapse; }
.amd-md :deep(th), .amd-md :deep(td) {
  padding: 3px 8px;
  border: 1px solid var(--fs-hairline);
  font-size: 11px;
}
.amd-md :deep(hr) { margin: 8px 0; border: none; border-top: 1px dashed var(--fs-hairline); }
</style>
