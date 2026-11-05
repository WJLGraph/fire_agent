<script setup>
/**
 * 智能查询 · 提问区（v0 smartquery 左栏同构）
 *
 * sec-t「提问」标题 + textarea + 语音/执行按钮行 + Ctrl+Enter 提示 + 示例问题胶囊。
 * 受控组件：查询文本、loading、录音状态由父组件持有，本组件只做展示与事件上抛。
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  recording: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'query', 'mic', 'example'])

const text = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const exampleQueries = [
  '2025年1月普洱市预测火险',
  '2025年春季哪些州市风险最高',
  '高置信度火点最多的5个州市',
  '2025年火险数据汇总',
]

// Ctrl/Cmd + Enter 快速查询
const handleKeydown = (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    emit('query')
  }
}
</script>

<template>
  <section class="qi">
    <!-- 提问 -->
    <div class="qi__sec"><span class="qi__t">提问</span></div>
    <textarea
      v-model="text"
      class="qi__ta"
      rows="3"
      placeholder="输入自然语言查询，例如：2025年1月普洱市预测火险"
      @keydown="handleKeydown"
    ></textarea>

    <!-- 操作行：语音 + 快捷键提示 + 执行 -->
    <div class="qi__ops">
      <button
        class="qi__mic"
        :class="{ recording }"
        :title="recording ? '停止录音并识别' : '语音输入'"
        @click="emit('mic')"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="8" y="2.8" width="4" height="9" rx="2"/>
          <path d="M5.2 9.6a4.8 4.8 0 0 0 9.6 0"/>
          <path d="M10 14.4v2.6"/>
        </svg>
        {{ recording ? '停止录音' : '语音输入' }}
      </button>
      <span class="qi__sp"></span>
      <span class="qi__hint">Ctrl + ↵</span>
      <button class="qi__run" :disabled="loading" @click="emit('query')">
        {{ loading ? '查询中…' : '执行查询' }}
        <svg v-if="!loading" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 10h12"/><path d="m11.4 5.4 4.6 4.6-4.6 4.6"/>
        </svg>
      </button>
    </div>

    <!-- 示例问题 -->
    <div class="qi__sec"><span class="qi__t">示例问题</span></div>
    <div class="qi__chips">
      <button
        v-for="(ex, i) in exampleQueries"
        :key="i"
        class="qi__chip"
        @click="emit('example', ex)"
      >{{ ex }}</button>
    </div>
  </section>
</template>

<style scoped>
.qi {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* sec-t 同构：标题 + 延伸发丝线 */
.qi__sec {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qi__sec::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--fs-hairline);
}
.qi__t {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
.qi__t::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 1px;
  background-color: var(--fs-hairline-strong);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.qi__sec:hover .qi__t::before { background-color: var(--fs-accent); }

/* textarea（v0 .textarea 同构） */
.qi__ta {
  width: 100%;
  padding: 10px;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  border: none;
  outline: none;
  resize: vertical;
  min-height: 72px;
  font: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: var(--fs-ink-900);
  caret-color: var(--fs-accent);
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.qi__ta::placeholder { color: var(--fs-ink-400); }
.qi__ta:hover:not(:focus) { box-shadow: inset 0 0 0 1px rgba(var(--fs-ink-900-rgb), 0.26); }
.qi__ta:focus { box-shadow: inset 0 0 0 1px var(--fs-accent); }

/* 操作行 */
.qi__ops {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qi__sp { flex: 1; }
.qi__hint {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
}
.qi__mic {
  height: 28px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.qi__mic svg { width: 13px; height: 13px; }
.qi__mic:hover { color: var(--fs-ink-900); background: var(--fs-bg-sunken); }
.qi__mic.recording {
  color: var(--fs-danger);
  animation: qi-blink 1.2s ease-in-out infinite;
}
@keyframes qi-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 执行查询（v0 btn--primary 同构） */
.qi__run {
  position: relative;
  overflow: hidden;
  height: 30px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--fs-r-sm, 6px);
  background-color: var(--fs-accent);
  color: var(--fs-on-accent);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
  transition: background-color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.qi__run svg { width: 13px; height: 13px; }
.qi__run::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.22) 50%, transparent 62%);
  transform: translateX(-130%);
}
.qi__run:hover:not(:disabled) {
  background-color: var(--fs-accent-hover);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
  transform: translateY(-1px);
}
.qi__run:hover:not(:disabled)::after { animation: qi-sheen 0.62s var(--up-ease, cubic-bezier(0.32, 0.72, 0, 1)); }
.qi__run:active:not(:disabled) {
  transform: translateY(0.5px) scale(0.99);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.qi__run:disabled {
  box-shadow: none;
  background-color: var(--fs-bg-sunken);
  color: var(--fs-ink-400);
  cursor: not-allowed;
}
@keyframes qi-sheen {
  to { transform: translateX(130%); }
}

/* 示例问题胶囊（v0 sq-chip 同构） */
.qi__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.qi__chip {
  height: 26px;
  padding: 0 11px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.qi__chip:hover {
  color: var(--fs-accent);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
}

/* 动效三态闸门：录音脉冲为循环动画，位移/扫光为悬停动效，一并受控 */
html[data-motion-allowed="false"] .qi__mic.recording,
html[data-motion-allowed="false"] .qi__run:hover:not(:disabled)::after { animation: none; }
html[data-motion-allowed="false"] .qi__run:hover:not(:disabled),
html[data-motion-allowed="false"] .qi__run:active:not(:disabled) { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .qi__mic.recording,
  html:not([data-motion="on"]) .qi__run:hover:not(:disabled)::after { animation: none; }
  html:not([data-motion="on"]) .qi__run:hover:not(:disabled),
  html:not([data-motion="on"]) .qi__run:active:not(:disabled) { transform: none; }
}
</style>
