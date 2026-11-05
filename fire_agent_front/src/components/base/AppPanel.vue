<script setup>
/**
 * AppPanel — 通用面板容器
 *
 * 统一替代各页自造的卡片外壳（agent-card / kb-panel / report-card / admin-card 等）：
 * 表面色 + 1px 发丝边 + 统一圆角，顶部可选「标题 + 副标题 + 操作区」，底部可选 footer。
 *
 * 约束：
 *   - 不使用渐变、不使用发光、不使用左侧装饰色条（避免一千种卡片长相）
 *   - 所有取值来自 --gis-* 令牌，组件内无颜色字面量
 */
defineProps({
  /** 面板标题，为空则不渲染标题行 */
  title: { type: String, default: '' },
  /** 标题右侧次要说明（计数、时间范围等） */
  subtitle: { type: String, default: '' },
  /** 标题字号层级：md=16 / sm=14 / xs=12 */
  titleSize: {
    type: String,
    default: 'sm',
    validator: (v) => ['md', 'sm', 'xs'].includes(v),
  },
  /** 紧凑模式：内边距 16 → 12 */
  dense: { type: Boolean, default: false },
  /** 是否渲染 1px 边框（浮于地图之上的面板可关闭） */
  bordered: { type: Boolean, default: true },
  /** 面板最小高度（空态列表等需要占位时使用） */
  minHeight: { type: String, default: '' },
})
</script>

<template>
  <section class="app-panel" :class="[`is-${titleSize}`, { 'is-dense': dense, 'is-plain': !bordered }]">
    <header v-if="title || $slots.actions" class="app-panel-head">
      <div class="app-panel-titles">
        <h3 v-if="title" class="app-panel-title">{{ title }}</h3>
        <span v-if="subtitle" class="app-panel-sub">{{ subtitle }}</span>
        <slot name="title-extra" />
      </div>
      <div v-if="$slots.actions" class="app-panel-actions">
        <slot name="actions" />
      </div>
    </header>

    <div class="app-panel-body" :style="minHeight ? { minHeight } : null">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="app-panel-foot">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.app-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  color: var(--fs-ink-900);
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md);
  overflow: hidden;
}

.app-panel.is-plain {
  background: transparent;
  border-color: transparent;
}

.app-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--fs-hairline);
}

.is-dense .app-panel-head {
  padding: 8px 12px;
}

.app-panel-titles {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.app-panel-title {
  margin: 0;
  font-weight: 500;
  color: var(--fs-ink-900);
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.is-md .app-panel-title { font-size: 16px; }
.is-sm .app-panel-title { font-size: 14px; }
/* xs = 分区标题层级：12px / 500 / 字距 .04em，与 AppSectionTitle 对齐 */
.is-xs .app-panel-title {
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}

.app-panel-sub {
  font-size: 12px;
  color: var(--fs-ink-500);
  white-space: nowrap;
}

.app-panel-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.app-panel-body {
  flex: 1;
  min-height: 0;
  padding: 16px;
}

.is-dense .app-panel-body {
  padding: 12px;
}

.app-panel-foot {
  padding: 10px 16px;
  border-top: 1px solid var(--fs-hairline);
}
</style>
