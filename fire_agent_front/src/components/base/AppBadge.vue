<script setup>
/**
 * AppBadge — 语义徽标 / 状态标签
 *
 * 用途：风险等级、任务状态、角色、来源标记等。
 * 视觉：语义色 10% 底 + 同色文字（不用高饱和纯色块），可选前置圆点。
 *
 * 语义色统一来自 --gis-* 令牌（含 success/warning/danger/info 语义），
 * 组件内不出现颜色字面量。
 */
defineProps({
  /** 语义类型；neutral 为中性灰 */
  type: {
    type: String,
    default: 'neutral',
    validator: (v) => ['success', 'warning', 'danger', 'info', 'accent', 'neutral'].includes(v),
  },
  /** 是否显示 6px 前置状态点 */
  dot: { type: Boolean, default: false },
  /** 紧凑模式：更小内边距与字号，用于表格行内 */
  small: { type: Boolean, default: false },
})
</script>

<template>
  <span class="app-badge" :class="[`is-${type}`, { 'is-small': small }]" :title="$slots.default ? undefined : ''">
    <i v-if="dot" class="app-badge-dot" aria-hidden="true" />
    <slot />
  </span>
</template>

<style scoped>
.app-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  font-size: 12px;
  line-height: 18px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-sunken);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-xs);
  white-space: nowrap;
}

.app-badge.is-small {
  padding: 0 6px;
  font-size: 11px;
  line-height: 16px;
}

.app-badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

/* 语义色取自现有 Element Plus 语义令牌（gis-theme.css 已定义），避免组件内写字面色值 */

/* success */
.app-badge.is-success {
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
  border-color: var(--el-color-success-light-8);
}

/* warning */
.app-badge.is-warning {
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
  border-color: var(--el-color-warning-light-8);
}

/* danger */
.app-badge.is-danger {
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-8);
}

/* info */
.app-badge.is-info {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  border-color: var(--fs-accent);
}

/* accent */
.app-badge.is-accent {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  border-color: var(--fs-accent);
}
</style>
