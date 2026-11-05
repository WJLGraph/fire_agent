<script setup>
/**
 * AppSectionTitle — 分区标题行
 *
 * 用于「不用卡片包裹」的分区：一个小标题 + 可选说明 + 右侧操作 + 底部 1px 分隔线。
 * 与 AppPanel 的区别：本组件只提供标题与分隔，不提供表面/边框，鼓励用间距与发丝线分组。
 */
defineProps({
  title: { type: String, required: true },
  /** 标题右侧说明（数量、更新时间等） */
  meta: { type: String, default: '' },
  /** 底部是否渲染 1px 分隔线 */
  divided: { type: Boolean, default: true },
})
</script>

<template>
  <div class="app-section-title" :class="{ 'is-divided': divided }">
    <div class="app-section-title-main">
      <h4 class="app-section-title-text">{{ title }}</h4>
      <span v-if="meta" class="app-section-title-meta">{{ meta }}</span>
      <slot />
    </div>
    <div v-if="$slots.actions" class="app-section-title-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.app-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
}

.app-section-title.is-divided {
  border-bottom: 1px solid var(--fs-hairline);
}

.app-section-title-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.app-section-title-text {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}

.app-section-title-meta {
  font-size: 12px;
  color: var(--fs-ink-500);
}

.app-section-title-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
</style>
