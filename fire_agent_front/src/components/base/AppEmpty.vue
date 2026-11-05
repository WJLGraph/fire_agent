<script setup>
/**
 * AppEmpty — 空态占位
 *
 * 统一替代各页自造的空态文案（"暂无数据" / "暂无历史记录" …）。
 * 视觉：细线占位框 + 一句说明 + 可选操作（不放大插画、不使用 Emoji）。
 */
import AppIcon from '@/components/base/AppIcon.vue'

defineProps({
  /** 说明文案 */
  description: { type: String, default: '暂无数据' },
  /** 次要提示（操作指引、筛选条件说明） */
  hint: { type: String, default: '' },
  /** 图标名，传空字符串则不显示图标 */
  icon: { type: String, default: 'layers' },
  /** 占位区最小高度 */
  minHeight: { type: String, default: '120px' },
})
</script>

<template>
  <div class="app-empty" :style="{ minHeight }">
    <AppIcon v-if="icon" :name="icon" :size="22" class="app-empty-icon" />
    <p class="app-empty-desc">{{ description }}</p>
    <p v-if="hint" class="app-empty-hint">{{ hint }}</p>
    <div v-if="$slots.default" class="app-empty-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.app-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px;
  text-align: center;
  color: var(--fs-ink-500);
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-md);
}

.app-empty-icon {
  opacity: 0.7;
  margin-bottom: 2px;
}

.app-empty-desc {
  margin: 0;
  font-size: 13px;
  color: var(--fs-ink-500);
}

.app-empty-hint {
  margin: 0;
  font-size: 12px;
  opacity: 0.8;
}

.app-empty-actions {
  margin-top: 6px;
}
</style>
