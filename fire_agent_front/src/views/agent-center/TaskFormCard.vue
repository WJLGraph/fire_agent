<script setup>
/**
 * Agent 协作中心 · 任务输入卡（v0 §agent 任务输入同构）
 *
 * sec-t 标题 + v0 textarea + 示例任务胶囊 + 操作行（语音 ghost / Ctrl+↵ / 执行 primary）。
 * query 由父组件持有（SSE 流程与历史回填都要读写它），这里以 v-model 形式受控。
 */
import { ref } from 'vue'

defineProps({
  /** 任务输入内容（受控，由父组件持有） */
  query: { type: String, default: '' },
  exampleTasks: { type: Array, default: () => [] },
  /** 任务执行中（执行钮禁用） */
  running: { type: Boolean, default: false },
})

const emit = defineEmits(['update:query', 'keydown', 'execute'])

// 供父组件「新建任务」聚焦输入框
const taRef = ref(null)
defineExpose({ focus: () => taRef.value?.focus() })
</script>

<template>
  <section class="tf">
    <div class="tf__sec">
      <span class="tf__t">任务输入</span>
      <span class="tf__sp"></span>
      <span class="tf__hint">Ctrl + ↵</span>
    </div>

    <textarea
      ref="taRef"
      :value="query"
      class="tf__ta"
      rows="4"
      placeholder="描述研判需求，例如：分析楚雄州近 30 天火险趋势并生成值班简报"
      @input="emit('update:query', $event.target.value)"
      @keydown="emit('keydown', $event)"
    ></textarea>

    <!-- 示例任务胶囊（v0 sq-chip 同构） -->
    <div class="tf__chips">
      <button
        v-for="(ex, i) in exampleTasks"
        :key="i"
        class="tf__chip"
        :title="ex"
        @click="emit('update:query', ex)"
      >{{ ex }}</button>
    </div>

    <!-- 操作行（v0 同构：执行 primary 右对齐） -->
    <div class="tf__ops">
      <span class="tf__hint">Ctrl + Enter 快速执行</span>
      <button class="tf__run" :disabled="running" @click="emit('execute')">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10h12"/><path d="m10.5 5 5 5-5 5"/></svg>
        {{ running ? '执行中…' : '执行' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.tf {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* sec-t 同构：标题 + 延伸发丝线 */
.tf__sec {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tf__sec::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--fs-hairline);
}
.tf__t {
  position: relative;
  padding-left: 9px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
.tf__t::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 2px;
  height: 11px;
  margin-top: -5.5px;
  border-radius: 1px;
  background: var(--fs-accent);
}
.tf__sp { flex: 1; }

/* textarea（v0 .textarea 同构） */
.tf__ta {
  width: 100%;
  padding: 10px;
  background: var(--fs-bg-surface); /* v0 .textarea 同构：与列同底色，仅发丝环界定 */
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  border: none;
  outline: none;
  resize: vertical;
  min-height: 88px;
  font: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: var(--fs-ink-900);
  caret-color: var(--fs-accent);
  transition: box-shadow var(--fs-dur-fast, 0.16s) var(--fs-ease);
}
.tf__ta::placeholder { color: var(--fs-ink-400); }
.tf__ta:hover { box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
/* 聚焦：1px 强调描边 + 3px 柔光（与全局输入控件同一档） */
.tf__ta:focus { box-shadow: inset 0 0 0 1px var(--fs-accent), 0 0 0 3px var(--fs-accent-soft); }

/* 示例任务胶囊（v0 badge--muted 同构：20px 方角 sunken 底，hover 点亮 accent） */
.tf__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tf__chip {
  height: 20px;
  padding: 0 7px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  font-weight: 500;
  color: var(--fs-ink-500);
  background: var(--fs-bg-sunken);
  border: none;
  cursor: pointer;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  box-shadow: inset 0 0 0 1px transparent;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.tf__chip:hover {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
}
.tf__chip:active { transform: translateY(0.5px); }

/* 操作行（v0：hint + 执行，两端对齐） */
.tf__ops {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.tf__hint {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
}

/* 执行（v0 btn--primary 同构） */
.tf__run {
  flex: none;
  position: relative;
  overflow: hidden;
  height: 32px;
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
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
  transition: background var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.tf__run::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.22) 50%, transparent 62%);
  transform: translateX(-130%);
}
.tf__run svg {
  width: 13px;
  height: 13px;
  position: relative;
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
.tf__run:hover:not(:disabled) { background: var(--fs-accent-hover); }
.tf__run:hover:not(:disabled) svg { transform: translateX(2px); }
.tf__run:hover:not(:disabled)::after { animation: tf-sheen 0.62s var(--fs-ease-out, ease-out); }
@keyframes tf-sheen {
  to { transform: translateX(130%); }
}
.tf__run:active:not(:disabled) { transform: translateY(0.5px); }
.tf__run:disabled {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-400);
  box-shadow: none;
  cursor: not-allowed;
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .tf__run:hover:not(:disabled)::after { animation: none; }
}
html[data-motion-allowed="false"] .tf__run::after { animation: none; }
</style>
