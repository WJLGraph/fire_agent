<script setup>
/**
 * 知识库 · 提问卡（v0 kb-q 同构：textarea + 示例胶囊 + 语音提问 / 提问）
 *
 * 受控组件：问题文本、asking、录音状态由父组件持有，本组件只做展示与事件上抛。
 * 交互逻辑（Ctrl+Enter 快捷提问、语音识别自动提交）零改动。
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  asking: { type: Boolean, default: false },
  recording: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'ask', 'mic', 'example'])

const text = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const exampleQuestions = [
  '森林火险等级如何划分？',
  '4级火险应该采取什么措施？',
  '林区封山的条件是什么？',
]

const handleKeydown = (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    emit('ask')
  }
}
</script>

<template>
  <div class="kq">
    <textarea
      v-model="text"
      class="kq__ta"
      rows="2"
      placeholder="输入关于森林防火的问题…"
      @keydown="handleKeydown"
    ></textarea>

    <!-- 示例问题胶囊（v0 sq-chip 同构） -->
    <div class="kq__chips">
      <button
        v-for="(ex, i) in exampleQuestions"
        :key="i"
        class="kq__chip"
        @click="emit('example', ex)"
      >{{ ex }}</button>
    </div>

    <!-- 操作行：语音提问（左）/ Ctrl+↵ + 提问（右） -->
    <div class="kq__ops">
      <button
        class="kq__mic"
        :class="{ recording }"
        :title="recording ? '停止录音并识别' : '语音提问'"
        @click="emit('mic')"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="7.5" y="3" width="5" height="9" rx="2.5"/><path d="M5 10a5 5 0 0 0 10 0"/><path d="M10 15v2.5"/></svg>
        {{ recording ? '停止录音' : '语音提问' }}
      </button>
      <span class="kq__sp"></span>
      <span class="kq__hint">Ctrl + ↵</span>
      <button class="kq__run" :disabled="asking" @click="emit('ask')">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3v8.6"/><path d="m6.4 8.2 3.6 3.6 3.6-3.6"/><path d="M3.5 15.4v1.1h13v-1.1"/></svg>
        {{ asking ? '提问中…' : '提问' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
/* v0 kb-q：表面卡 + inset 发丝环（提问聚焦时边缘加亮一档） */
.kq {
  flex-shrink: 0;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  transition: box-shadow var(--up-dur-fast, 120ms) var(--fs-ease);
}
.kq:focus-within { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }

/* textarea（v0 .textarea 同构；聚焦=1px 强调描边+3px 光环，与全局输入语言一致） */
.kq__ta {
  width: 100%;
  padding: 10px;
  background: var(--fs-bg-canvas);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  border: none;
  outline: none;
  resize: vertical;
  min-height: 64px;
  font: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: var(--fs-ink-900);
  caret-color: var(--fs-accent);
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.kq__ta::placeholder { color: var(--fs-ink-400); }
.kq__ta:focus { box-shadow: inset 0 0 0 1px var(--fs-accent), 0 0 0 3px var(--fs-accent-soft); }

/* 示例胶囊（v0 sq-chip 同构） */
.kq__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.kq__chip {
  height: 26px;
  padding: 0 11px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-canvas);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  cursor: pointer;
  white-space: nowrap;
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.kq__chip:hover {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
  transform: translateY(-1px);
}

/* 操作行 */
.kq__ops {
  display: flex;
  align-items: center;
  gap: 8px;
}
.kq__sp { flex: 1; }
.kq__hint {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
}
.kq__mic {
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
.kq__mic svg { width: 13px; height: 13px; }
.kq__mic:hover { color: var(--fs-ink-900); background: var(--fs-bg-sunken); }
.kq__mic.recording {
  color: var(--fs-danger);
  background: rgba(var(--fs-ink-900-rgb), 0.04);
  animation: kq-blink 1.2s ease-in-out infinite;
}
@keyframes kq-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 提问（v0 btn--primary 同构：镜面高光+中性投影+hover 扫光，与全局主按钮同语言） */
.kq__run {
  position: relative;
  overflow: hidden;
  height: 30px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--fs-r-sm, 6px);
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
  transition:
    background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.kq__run::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.22) 50%, transparent 62%);
  transform: translateX(-130%);
}
.kq__run svg { width: 13px; height: 13px; }
.kq__run:hover:not(:disabled) {
  background: var(--fs-accent-hover);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e2);
  transform: translateY(-1px);
}
.kq__run:hover:not(:disabled)::after { animation: kq-sheen 0.62s var(--fs-ease-out); }
@keyframes kq-sheen {
  to { transform: translateX(130%); }
}
.kq__run:active:not(:disabled) {
  transform: translateY(0.5px) scale(0.99);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.kq__run:disabled {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-400);
  cursor: not-allowed;
  box-shadow: none;
}

/* ===== 动效闸门：关闭时循环停、扫光撤、悬停位移归零 ===== */
html[data-motion-allowed="false"] .kq__mic.recording,
html[data-motion-allowed="false"] .kq__run:hover:not(:disabled)::after { animation: none; }
html[data-motion-allowed="false"] .kq__run::after { transform: translateX(-130%); }
html[data-motion-allowed="false"] .kq__chip:hover,
html[data-motion-allowed="false"] .kq__run:hover:not(:disabled) { transform: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .kq__mic.recording,
  html:not([data-motion="on"]) .kq__run:hover:not(:disabled)::after { animation: none; }
  html:not([data-motion="on"]) .kq__run::after { transform: translateX(-130%); }
  html:not([data-motion="on"]) .kq__chip:hover,
  html:not([data-motion="on"]) .kq__run:hover:not(:disabled) { transform: none; }
}
</style>
