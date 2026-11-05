<script setup>
/**
 * AppSegmentedControl — 分段选择器
 *
 * 替代 el-radio-group / el-tabs 在工具栏场景的用法（图层切换、视图模式、Tab 组内的小切换）。
 * 语义使用原生 button + aria-pressed，支持键盘 Tab 与回车。
 *
 * 注意：本组件只负责「切换外观」，不承担内容面板切换逻辑（由调用方根据 modelValue 渲染）。
 */
defineProps({
  /** 当前选中值 */
  modelValue: { type: [String, Number], default: '' },
  /** 选项数组：[{ value, label, disabled?, count? }] */
  options: {
    type: Array,
    default: () => [],
    validator: (list) => list.every((o) => o && 'value' in o && 'label' in o),
  },
  /** 尺寸：sm=26px 高 / md=32px 高 */
  size: {
    type: String,
    default: 'sm',
    validator: (v) => ['sm', 'md'].includes(v),
  },
  /** 是否撑满容器宽度（等分） */
  block: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'change'])

const select = (option) => {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
}
</script>

<template>
  <div class="app-segmented" :class="[`is-${size}`, { 'is-block': block }]" role="group">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      class="app-segmented-item"
      :class="{ 'is-active': option.value === modelValue }"
      :aria-pressed="option.value === modelValue"
      :disabled="option.disabled"
      :title="option.label"
      @click="select(option)"
    >
      {{ option.label }}
      <span v-if="option.count !== undefined && option.count !== null" class="app-segmented-count">
        {{ option.count }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.app-segmented {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-sm);
}

.app-segmented.is-block {
  display: flex;
  width: 100%;
}

.app-segmented-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0 10px;
  font-size: 12px;
  color: var(--fs-ink-500);
  background: transparent;
  border: none;
  border-radius: var(--fs-r-xs);
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s, background 0.15s;
}

.is-block .app-segmented-item {
  flex: 1;
}

.app-segmented.is-sm .app-segmented-item { height: 24px; }
.app-segmented.is-md .app-segmented-item { height: 28px; font-size: 13px; }

.app-segmented-item:hover:not(:disabled):not(.is-active) {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
}

.app-segmented-item:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: -1px;
}

.app-segmented-item.is-active {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  font-weight: 500;
}

.app-segmented-item:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.app-segmented-count {
  font-size: 11px;
  opacity: 0.75;
  font-variant-numeric: tabular-nums;
}
</style>
