<script setup>
/**
 * Agent 协作中心 · 分析报告展示（待审批时隐藏，避免与审批卡草稿混淆）
 *
 * v0 卡片同构：头部（标题 + 通道徽标 + 状态徽标 + 播报 ghost 钮）+ markdown 正文。
 * speakState / speakText 来自 utils/speech 的全局单例，可直接在本组件内使用。
 */
import renderMarkdown from '@/utils/markdown'
import { speakState, speakText } from '@/utils/speech'

defineProps({
  /** { status, report, llm_used } */
  taskResult: { type: Object, required: true },
})

// ====== 报告状态展示辅助 ======
const reportStatusClass = (s) => (s === 'completed' ? 'ok' : (s === 'awaiting_approval' ? 'wait' : (s === 'running' ? 'run' : 'fail')))
const reportStatusText = (s) => (s === 'completed' ? '完成' : (s === 'awaiting_approval' ? '待审批' : (s === 'running' ? '执行中' : '失败')))
</script>

<template>
  <section class="rp">
    <div class="rp__hd">
      <span class="rp__t">分析报告</span>
      <span v-if="taskResult.llm_used" class="rp__model" title="LLM 生成">LLM</span>
      <span v-else class="rp__fallback" title="模板生成">模板</span>
      <span class="rp__sp"></span>
      <span class="rp__st" :class="reportStatusClass(taskResult.status)">
        <i></i>{{ reportStatusText(taskResult.status) }}
      </span>
      <button
        class="rp__btn"
        :class="{ speaking: speakState.speaking || speakState.loading }"
        :title="speakState.speaking || speakState.loading ? '停止播报' : '语音播报分析报告'"
        @click="speakText(taskResult.report)"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8v4h2.6l3.4 3V5L6.6 8z"/><path d="M13.2 7.6a3.6 3.6 0 0 1 0 4.8"/></svg>
        {{ speakState.speaking || speakState.loading ? '停止' : '播报' }}
      </button>
    </div>
    <div class="rp__bd markdown-body" v-html="renderMarkdown(taskResult.report)" />
  </section>
</template>

<style scoped>
/* v0 卡片：表面卡 + 发丝环 */
.rp {
  flex: 1 1 auto;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.rp__hd {
  min-height: 48px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
  flex-shrink: 0;
}
.rp__t {
  position: relative;
  padding-left: 9px;
  font-size: 14px;
  font-weight: 600;
  color: var(--fs-ink-900);
}
.rp__t::before {
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
.rp__sp { flex: 1; }
.rp__model {
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
.rp__fallback {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-size: 11px;
}
.rp__st {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--fs-ink-400);
  white-space: nowrap;
}
.rp__st i {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
}
.rp__st.ok { color: var(--fs-success); }
.rp__st.wait { color: var(--fs-warning); }
.rp__st.run { color: var(--fs-accent); }
.rp__st.fail { color: var(--fs-danger); }
.rp__btn {
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
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.rp__btn svg { width: 12px; height: 12px; }
.rp__btn:hover { color: var(--fs-ink-900); background-color: var(--fs-bg-sunken); }
.rp__btn:active { transform: scale(0.97); }
.rp__btn.speaking { color: var(--fs-danger); }

.rp__bd {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  font-size: 13px;
  line-height: 1.9;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
/* ===== 报告排版精修（覆盖全局 markdown-body 的泛用样式） ===== */
.rp__bd :deep(.markdown-body) { font-size: 13.5px; line-height: 1.85; color: var(--fs-ink-700); }
/* 文档主标题：accent 竖条 + 收敛字号（全局 h1 过大，与面板头「分析报告」层级冲突） */
.rp__bd :deep(.markdown-body > h1:first-child) {
  margin: 4px 0 14px;
  padding-left: 10px;
  font-size: 19px;
  line-height: 1.4;
  border-left: 3px solid var(--fs-accent);
}
.rp__bd :deep(.markdown-body h2) {
  margin: 22px 0 10px;
  padding-bottom: 6px;
  font-size: 15px;
  border-bottom: 1px solid var(--fs-hairline);
}
.rp__bd :deep(.markdown-body h3) { font-size: 14px; }
/* 元信息引用块：sunken 底条而非大引号块 */
.rp__bd :deep(.markdown-body blockquote) {
  margin: 0 0 14px;
  padding: 8px 12px;
  color: var(--fs-ink-500);
  font-size: 12px;
  background: var(--fs-bg-sunken);
  border-left: 3px solid var(--fs-hairline-strong);
  border-radius: var(--fs-r-sm, 6px);
}
.rp__bd :deep(.markdown-body blockquote p) { margin: 0; }
/* 表格：发丝环 + 表头 sunken，替代无边框裸表 */
.rp__bd :deep(.markdown-body table) {
  width: 100%;
  margin: 10px 0 16px;
  border-collapse: collapse;
  font-size: 12.5px;
}
.rp__bd :deep(.markdown-body th),
.rp__bd :deep(.markdown-body td) {
  padding: 7px 12px;
  border: 1px solid var(--fs-hairline);
  text-align: left;
}
.rp__bd :deep(.markdown-body th) {
  font-weight: 600;
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
  white-space: nowrap;
}
/* 表格行悬停提亮：长报告横向读数不串行 */
.rp__bd :deep(.markdown-body tbody tr) { transition: background-color var(--fs-dur-micro) var(--fs-ease); }
.rp__bd :deep(.markdown-body tbody tr:hover) { background-color: color-mix(in srgb, var(--fs-ink-900) 3%, transparent); }
.rp__bd :deep(.markdown-body td) { font-variant-numeric: tabular-nums; }
/* 列表与段落间距收敛，避免大段落松散 */
.rp__bd :deep(.markdown-body p) { margin: 0 0 10px; }
.rp__bd :deep(.markdown-body ul),
.rp__bd :deep(.markdown-body ol) { margin: 0 0 10px; padding-left: 20px; }
.rp__bd :deep(.markdown-body li) { margin: 3px 0; }
.rp__bd :deep(.markdown-body hr) { margin: 16px 0; border: none; border-top: 1px solid var(--fs-hairline); }

/* ===== 状态点呼吸 + 卡片入场（终态回填时也有「出结果」的一次性反馈） ===== */
.rp__st.run i,
.rp__st.wait i { animation: rp-pulse 1.6s ease-in-out infinite; }
@keyframes rp-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}
.rp { animation: rp-in 0.4s var(--fs-ease-out) both; }
@keyframes rp-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .rp { animation: none; }
  html:not([data-motion="on"]) .rp__st.run i,
  html:not([data-motion="on"]) .rp__st.wait i { animation: none; }
}
html[data-motion-allowed="false"] .rp,
html[data-motion-allowed="false"] .rp__st.run i,
html[data-motion-allowed="false"] .rp__st.wait i { animation: none; }
</style>
