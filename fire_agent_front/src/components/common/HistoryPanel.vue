<script setup>
/**
 * HistoryPanel — 历史记录面板（列表 + 单条删除 + 清空）
 *
 * 目标：统一 smart-query / knowledge-base / agent-center 三处各自手写的历史列表，
 * 消除三份实现之间的行为差异（删除提示、空态文案、时间格式）。
 *
 * ★ 纯新增组件，接入阶段需逐页对照原有行为；数据源仍由各页自身的 API 决定。
 *
 * 用法：
 *   <HistoryPanel
 *     :items="history"
 *     label-key="text"
 *     :active-id="currentId"
 *     @select="onClickItem"
 *     @delete="onDeleteItem"
 *     @clear="onClearAll"
 *   >
 *     <template #meta="{ item }">{{ item.time }}</template>
 *   </HistoryPanel>
 */
import AppEmpty from '@/components/base/AppEmpty.vue'
import AppIconButton from '@/components/base/AppIconButton.vue'

const props = defineProps({
  /** 历史条目数组 */
  items: { type: Array, default: () => [] },
  /** 主文本字段名（三处分别为 text / text / query） */
  labelKey: { type: String, default: 'text' },
  /** 当前选中项的 id（用于高亮） */
  activeId: { type: [String, Number], default: null },
  /** 加载态 */
  loading: { type: Boolean, default: false },
  /** 是否显示"清空"按钮 */
  clearable: { type: Boolean, default: true },
  /** 空态文案 */
  emptyText: { type: String, default: '暂无历史记录' },
  /** 面板最小高度 */
  minHeight: { type: String, default: '' },
})

const emit = defineEmits(['select', 'delete', 'clear'])

const labelOf = (item) => (item && item[props.labelKey] != null ? String(item[props.labelKey]) : '')
</script>

<template>
  <div class="history-panel" :style="minHeight ? { minHeight } : null">
    <header v-if="$slots.header || clearable" class="history-panel-head">
      <slot name="header">
        <span class="history-panel-count" v-if="items.length">{{ items.length }} 条</span>
      </slot>
      <AppIconButton
        v-if="clearable && items.length"
        icon="trash"
        title="清空历史"
        danger
        @click="emit('clear')"
      />
    </header>

    <AppEmpty v-if="!items.length" :description="emptyText" icon="layers" min-height="96px" />

    <ul v-else class="history-panel-list">
      <li
        v-for="item in items"
        :key="item.id"
        class="history-panel-item"
        :class="{ 'is-active': activeId !== null && item.id === activeId }"
      >
        <button type="button" class="history-panel-main" :title="labelOf(item)" @click="emit('select', item)">
          <span class="history-panel-label">{{ labelOf(item) }}</span>
          <span v-if="$slots.meta" class="history-panel-meta">
            <slot name="meta" :item="item" />
          </span>
        </button>
        <AppIconButton
          class="history-panel-del"
          icon="close"
          :title="`删除：${labelOf(item)}`"
          size="sm"
          danger
          @click="emit('delete', item)"
        />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.history-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  min-height: 24px;
}

.history-panel-count {
  font-size: 12px;
  color: var(--fs-ink-500);
}

.history-panel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  min-height: 0;
}

.history-panel-item {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background 0.15s;
}

.history-panel-item:last-child {
  border-bottom: none;
}

.history-panel-item:hover {
  background: var(--fs-bg-sunken);
}

.history-panel-item.is-active {
  background: var(--fs-accent-soft);
}

.history-panel-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 4px 8px 8px;
  text-align: left;
  background: transparent;
  border: none;
  cursor: pointer;
  color: inherit;
}

.history-panel-main:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: -2px;
}

.history-panel-label {
  width: 100%;
  font-size: 13px;
  color: var(--fs-ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-panel-meta {
  font-size: 11px;
  color: var(--fs-ink-500);
  font-variant-numeric: tabular-nums;
}

/* 默认隐藏删除按钮，hover / focus 时显现，降低列表噪音 */
.history-panel-del {
  opacity: 0;
  transition: opacity 0.15s;
}

.history-panel-item:hover .history-panel-del,
.history-panel-del:focus-visible {
  opacity: 1;
}
</style>
