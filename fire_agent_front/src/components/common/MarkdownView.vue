<script setup>
/**
 * MarkdownView — Markdown 渲染容器
 *
 * 统一替代各页手写的 `<div class="markdown-body" v-html="renderMarkdown(...)">`：
 *   - 渲染逻辑仍走 utils/markdown.js（渲染结果一字不变）
 *   - 统一容器类名 .markdown-body，供 style/markdown.css 全局样式命中
 *
 * 注意：本组件的 v-html 内容来自本地渲染器，不含外部输入直出；
 * 若未来接入不可信来源，需先在上层做白名单清洗。
 */
import { computed } from 'vue'
import renderMarkdown from '@/utils/markdown'

const props = defineProps({
  /** Markdown 原文 */
  content: { type: String, default: '' },
  /** 是否加最小高度占位（流式渲染前避免高度抖动） */
  minHeight: { type: String, default: '' },
})

const html = computed(() => renderMarkdown(props.content || ''))
</script>

<template>
  <div class="markdown-view" :style="minHeight ? { minHeight } : null">
    <div v-if="!content" class="markdown-view-empty">
      <slot name="empty">暂无内容</slot>
    </div>
    <div v-else class="markdown-body" v-html="html" />
  </div>
</template>

<style scoped>
.markdown-view {
  width: 100%;
  min-width: 0;
  color: var(--fs-ink-900);
  font-size: 14px;
  line-height: 1.75;
}

.markdown-view-empty {
  color: var(--fs-ink-500);
  font-size: 13px;
}
</style>
