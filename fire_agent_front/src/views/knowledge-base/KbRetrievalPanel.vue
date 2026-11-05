<script setup>
/**
 * 知识库 · 检索过程卡（v0 sq-parse 同构：标题行 + 发丝行网格 + 关键词胶囊）
 *
 * 受控组件：retrieval 元信息由父组件传入（total_chunks / matched_chunks /
 * method / vector_enabled / keywords），展示逻辑零改动。
 */
import { computed } from 'vue'

const props = defineProps({
  retrieval: { type: Object, default: null },
})

// 检索方式中文标签（覆盖后端全部枚举，含 rerank 组合；未知值原样回退）
const METHOD_MAP = {
  hybrid: '向量 + 关键词混合',
  vector: '向量语义',
  keyword: '关键词匹配',
  none: '未命中',
  'keyword+rerank': '关键词 + 重排',
  'vector+rerank': '向量 + 重排',
  'hybrid+rerank': '混合检索 + 重排',
  rerank: '重排',
}
const retrievalMethodLabel = (m) => METHOD_MAP[m] || m

// 关键词碎片过多时截断（后端分词可能产生大量 n-gram 碎片，全量展示会溢出）
const MAX_KW = 8
const shownKeywords = computed(() => (props.retrieval?.keywords || []).slice(0, MAX_KW))
const extraKeywordCount = computed(() => Math.max(0, (props.retrieval?.keywords?.length || 0) - MAX_KW))
</script>

<template>
  <div v-if="retrieval" class="kr">
    <div class="kr__hd">
      <span class="kr__t">检索过程</span>
      <span class="kr__sp"></span>
      <span class="kr__badge" :class="retrieval.matched_chunks > 0 ? 'ok' : ''">
        <i></i>{{ retrieval.matched_chunks > 0 ? `命中 ${retrieval.matched_chunks} 片段` : '未命中' }}
      </span>
    </div>

    <!-- 发丝行网格（v0 sq-parse__r 同构） -->
    <div class="kr__grid">
      <div class="kr__r">
        <span class="kr__k">检索分片</span>
        <span class="kr__v mono">{{ retrieval.total_chunks }} chunks</span>
      </div>
      <div class="kr__r">
        <span class="kr__k">检索方式</span>
        <span class="kr__v kr__v--accent">{{ retrievalMethodLabel(retrieval.method) }}</span>
      </div>
      <div class="kr__r">
        <span class="kr__k">向量状态</span>
        <span class="kr__v" :class="retrieval.vector_enabled ? '' : 'kr__v--note'">
          {{ retrieval.vector_enabled ? '已启用 · 语义召回' : '不可用 · 仅关键词' }}
        </span>
      </div>
      <div v-if="retrieval.keywords && retrieval.keywords.length" class="kr__r">
        <span class="kr__k">提取关键词</span>
        <span class="kr__v">
          <span v-for="(kw, i) in shownKeywords" :key="i" class="kr__kw">{{ kw }}</span>
          <span v-if="extraKeywordCount > 0" class="kr__kw kr__kw--more">+{{ extraKeywordCount }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* v0 sq-parse：表面卡 + inset 发丝环（悬停边缘加亮，与大屏图表卡同语言） */
.kr {
  flex-shrink: 0;
  padding: 16px;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: box-shadow var(--up-dur-fast, 120ms) var(--fs-ease);
  animation: kr-in 0.4s var(--fs-ease-out) both;
}
.kr:hover { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
@keyframes kr-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.kr__hd {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 标题 2px 刻度条：静息发丝、悬停转强调 */
.kr__t {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  font-weight: 500;
  color: var(--fs-ink-900);
}
.kr__t::before {
  content: '';
  width: 2px;
  height: 11px;
  margin-right: 7px;
  border-radius: 1px;
  background: var(--fs-hairline-strong);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, ease);
}
.kr:hover .kr__t::before { background: var(--fs-accent); }
.kr__sp { flex: 1; }
.kr__badge {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  white-space: nowrap;
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
}
.kr__badge i {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--fs-ink-400);
}
.kr__badge.ok { background: color-mix(in srgb, var(--fs-success) 10%, transparent); color: var(--fs-success); }
.kr__badge.ok i { background: currentColor; }

/* 发丝行网格：行悬停淡底，扫读时定位当前行 */
.kr__grid { display: flex; flex-direction: column; }
.kr__r {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-height: 30px;
  padding: 0 6px;
  margin: 0 -6px;
  border-bottom: 1px solid var(--fs-hairline);
  font-size: 12px;
  border-radius: var(--fs-r-xs, 3px);
  transition: background-color var(--up-dur-fast, 120ms) var(--fs-ease);
}
.kr__r:hover { background: rgba(var(--fs-ink-900-rgb), 0.02); }
.kr__r:last-child { border-bottom: none; }
.kr__k {
  width: 72px;
  flex-shrink: 0;
  color: var(--fs-ink-500);
}
.kr__v {
  color: var(--fs-ink-900);
  font-weight: 500;
  line-height: 1.6;
  word-break: break-all;
  font-variant-numeric: tabular-nums;
}
.kr__v--accent { color: var(--fs-accent); }
.kr__v--note { font-weight: 400; color: var(--fs-ink-500); }
.kr__v.mono { font-family: var(--fs-font-mono); }

/* 关键词胶囊（v0 sq-chip 迷你同构，行内换行不溢出） */
.kr__kw {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  margin: 2px 4px 2px 0;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 400;
  color: var(--fs-ink-500);
  background: var(--fs-bg-canvas);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  white-space: nowrap;
}
.kr__kw--more {
  background: transparent;
  color: var(--fs-ink-400);
  box-shadow: none;
  font-family: var(--fs-font-mono);
}

/* ===== 动效闸门：关闭时入场停于终态 ===== */
html[data-motion-allowed="false"] .kr { animation: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .kr { animation: none; }
}
</style>
