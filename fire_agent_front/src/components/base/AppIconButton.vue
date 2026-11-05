<script setup>
/**
 * AppIconButton — 纯图标按钮
 *
 * 替换现存「字符当按钮」的写法（☀ / ☾ / ⏻ / ✕ …），统一：
 *   - 32px（sm）/ 36px（md）方形、发丝边、hover 微亮、按下轻微下沉
 *   - 必须传 title（无障碍与悬浮提示），禁止无提示的纯图标按钮
 *   - 覆盖 default / hover / focus-visible / active / disabled 五态
 */
import AppIcon from '@/components/base/AppIcon.vue'

defineProps({
  /** 图标名（见 AppIcon） */
  icon: { type: String, required: true },
  /** 悬浮提示与无障碍名称，必填 */
  title: { type: String, required: true },
  /** 尺寸：sm=32px / md=36px */
  size: {
    type: String,
    default: 'sm',
    validator: (v) => ['sm', 'md'].includes(v),
  },
  /** 激活态（工具栏选中、导航高亮） */
  active: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  /** 危险语义（删除/停止），hover 与文字转语义红 */
  danger: { type: Boolean, default: false },
  /** 圆形外观（头像、播放键等） */
  round: { type: Boolean, default: false },
})

const emit = defineEmits(['click'])

const onClick = (e) => emit('click', e)
</script>

<template>
  <button
    type="button"
    class="app-icon-btn"
    :class="[`is-${size}`, { 'is-active': active, 'is-danger': danger, 'is-round': round }]"
    :title="title"
    :aria-label="title"
    :disabled="disabled"
    @click="onClick"
  >
    <AppIcon :name="icon" :size="size === 'md' ? 18 : 16" />
  </button>
</template>

<style scoped>
.app-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--fs-ink-500);
  background: transparent;
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm);
  cursor: pointer;
  transition: color 0.15s, background 0.15s, border-color 0.15s, transform 0.12s;
}

.app-icon-btn.is-sm { width: 32px; height: 32px; }
.app-icon-btn.is-md { width: 36px; height: 36px; }

.app-icon-btn.is-round { border-radius: 50%; }

.app-icon-btn:hover:not(:disabled) {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
  border-color: var(--fs-accent);
}

.app-icon-btn:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: 1px;
}

.app-icon-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.app-icon-btn.is-active {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  border-color: var(--fs-accent);
}

.app-icon-btn.is-danger:hover:not(:disabled) {
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-8);
}

.app-icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
