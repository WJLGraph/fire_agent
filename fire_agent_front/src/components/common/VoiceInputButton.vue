<script setup>
/**
 * VoiceInputButton — 语音输入按钮（录音 → ASR 识别 → 回调文本）
 *
 * 统一三处重复的麦克风按钮实现（agent-center / knowledge-base）：
 *   - 单例状态与录音逻辑仍走 utils/speech.js（startRecord / stopRecord / recordState）
 *   - 识别结果通过 emit('result', text) 交给调用方，回调行为由调用方决定
 *
 * 状态：default / 录音中 / 识别中 / disabled
 */
import AppIcon from '@/components/base/AppIcon.vue'
import { recordState, startRecord } from '@/utils/speech'

defineProps({
  /** 按钮标题（悬浮与无障碍名称） */
  title: { type: String, default: '语音输入' },
  /** 尺寸：sm=32 / md=36 */
  size: {
    type: String,
    default: 'sm',
    validator: (v) => ['sm', 'md'].includes(v),
  },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['result'])

const handleClick = () => {
  // 录音中再次调用 = 停止并识别（utils/speech 内部语义）
  startRecord((text) => emit('result', text))
}
</script>

<template>
  <button
    type="button"
    class="voice-btn mo-loop"
    :class="[`is-${size}`, { 'is-recording': recordState.recording, 'is-loading': recordState.loading }]"
    :title="recordState.recording ? '结束录音并识别' : (recordState.loading ? '识别中…' : title)"
    :aria-label="title"
    :disabled="disabled || recordState.loading"
    @click="handleClick"
  >
    <AppIcon :name="recordState.recording ? 'mic-off' : 'mic'" :size="size === 'md' ? 18 : 16" />
  </button>
</template>

<style scoped>
.voice-btn {
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

.voice-btn.is-sm { width: 32px; height: 32px; }
.voice-btn.is-md { width: 36px; height: 36px; }

.voice-btn:hover:not(:disabled) {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
  border-color: var(--fs-accent);
}

.voice-btn:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: 1px;
}

.voice-btn.is-recording {
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-8);
  animation: voice-pulse 1.2s ease-in-out infinite;
}

.voice-btn.is-loading {
  opacity: 0.6;
  cursor: progress;
}

.voice-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

@keyframes voice-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

@media (prefers-reduced-motion: reduce) {
  .voice-btn.is-recording { animation: none; }
}
</style>
