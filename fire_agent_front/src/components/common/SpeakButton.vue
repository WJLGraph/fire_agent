<script setup>
/**
 * SpeakButton — 语音播报按钮（TTS）
 *
 * 统一四处重复的"朗读报告/回答"实现（dashboard / agent-center / knowledge-base / report-center）：
 *   - 单例播放状态与 TTS 逻辑仍走 utils/speech.js（speakText / stopSpeak / speakState）
 *   - Markdown → 纯文本的转换由 utils/speech 的 mdToPlain 负责（各页行为保持一致）
 *
 * 交互：未播报 → 点击开始；播报中 → 再次点击停止（与 speakText 内部语义一致）
 */
import AppIcon from '@/components/base/AppIcon.vue'
import { speakState, speakText, stopSpeak } from '@/utils/speech'

const props = defineProps({
  /** 待播报内容（可为 Markdown） */
  text: { type: String, default: '' },
  /** 按钮标题 */
  title: { type: String, default: '语音播报' },
  /** 尺寸：sm=32 / md=36 */
  size: {
    type: String,
    default: 'sm',
    validator: (v) => ['sm', 'md'].includes(v),
  },
  disabled: { type: Boolean, default: false },
})

const handleClick = () => {
  // 无内容时若正在播报则停止，否则提示（与原实现保持一致：由 speakText 内部提示）
  speakText(props.text || '')
}

const stop = () => stopSpeak()
</script>

<template>
  <button
    type="button"
    class="speak-btn"
    :class="[`is-${size}`, { 'is-speaking': speakState.speaking, 'is-loading': speakState.loading }]"
    :title="speakState.speaking ? '停止播报' : title"
    :aria-label="speakState.speaking ? '停止播报' : title"
    :disabled="disabled || speakState.loading"
    @click="speakState.speaking ? stop() : handleClick()"
  >
    <AppIcon :name="speakState.speaking ? 'stop' : 'speaker'" :size="size === 'md' ? 18 : 16" />
  </button>
</template>

<style scoped>
.speak-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--fs-ink-500);
  background: transparent;
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm);
  cursor: pointer;
  transition: color 0.15s, background 0.15s, border-color 0.15s;
}

.speak-btn.is-sm { width: 32px; height: 32px; }
.speak-btn.is-md { width: 36px; height: 36px; }

.speak-btn:hover:not(:disabled) {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
  border-color: var(--fs-accent);
}

.speak-btn:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: 1px;
}

.speak-btn.is-speaking {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  border-color: var(--fs-accent);
}

.speak-btn.is-loading {
  opacity: 0.6;
  cursor: progress;
}

.speak-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
