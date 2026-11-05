<script setup>
/**
 * 智能查询 · QueryAgent 解析卡（v0 sq-parse 同构）
 *
 * 头部（标题 + 解析方式徽标）+ 发丝行网格（意图 / 参数 / 说明）。
 * 受控组件：parsedInfo 由父组件传入，标签映射与参数格式化原样保留。
 */
import { computed } from 'vue'

const props = defineProps({
  parsedInfo: { type: Object, default: null },
})

// ====== QueryAgent 解析过程展示辅助 ======
const INTENT_LABELS = {
  history: '历史火点查询',
  predict: '预测火险查询',
  summary: '数据汇总统计',
}
const PARAM_LABELS = {
  city: '城市', year: '年份', month: '月份', months: '季节月份',
  confidence: '置信度', top_k: 'TopN', sort: '排序',
}
const intentLabel = (i) => INTENT_LABELS[i] || i || '未知'
const formatParamValue = (k, v) => {
  if (Array.isArray(v)) return `${v.join(',')}月`
  if (k === 'sort') return v === 'desc' ? '降序' : '升序'
  if (k === 'confidence') return ({ high: '高', nominal: '中', low: '低' })[v] || v
  return v
}
const parsedParams = computed(() => {
  const p = (props.parsedInfo && props.parsedInfo.params) || {}
  return Object.entries(p).map(([k, v]) => ({
    key: PARAM_LABELS[k] || k,
    value: formatParamValue(k, v),
  }))
})
</script>

<template>
  <section class="qp">
    <!-- 头部：标题 + 解析方式徽标 -->
    <div class="qp__hd">
      <span class="qp__t">QueryAgent 解析</span>
      <span class="qp__sp"></span>
      <span class="qp__badge" :class="parsedInfo.method">
        {{ parsedInfo.method === 'llm' ? 'LLM 解析' : '关键词解析' }}
      </span>
    </div>

    <!-- 发丝行网格：意图 / 参数 / 说明 -->
    <div class="qp__grid">
      <div class="qp__r">
        <span class="qp__k">查询意图</span>
        <span class="qp__v qp__v--accent">{{ intentLabel(parsedInfo.intent) }}</span>
      </div>
      <div v-for="(param, i) in parsedParams" :key="i" class="qp__r">
        <span class="qp__k">{{ param.key }}</span>
        <span class="qp__v">{{ param.value }}</span>
      </div>
      <div v-if="parsedInfo.explanation" class="qp__r">
        <span class="qp__k">说明</span>
        <span class="qp__v qp__v--note">{{ parsedInfo.explanation }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* v0 sq-parse：表面卡 + inset 发丝环 */
.qp {
  flex-shrink: 0;
  padding: 16px;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease);
  animation: qp-in 0.4s var(--fs-ease-out) both;
}
.qp:hover { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
@keyframes qp-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.qp__hd {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qp__t {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
  color: var(--fs-ink-900);
}
.qp__t::before {
  content: '';
  width: 2px;
  height: 12px;
  border-radius: 1px;
  background-color: var(--fs-hairline-strong);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.qp:hover .qp__t::before { background-color: var(--fs-accent); }
.qp__sp { flex: 1; }
.qp__badge {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.qp__badge.llm {
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
}
.qp__badge.keyword {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
}

/* 发丝行网格（v0 sq-parse__r / meta-list 同构） */
.qp__grid { display: flex; flex-direction: column; }
.qp__r {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-height: 30px;
  border-bottom: 1px solid var(--fs-hairline);
  font-size: 12px;
}
.qp__r:last-child { border-bottom: none; }
.qp__k {
  width: 72px;
  flex-shrink: 0;
  color: var(--fs-ink-500);
}
.qp__v {
  color: var(--fs-ink-900);
  font-weight: 500;
  line-height: 1.6;
  word-break: break-all;
  font-variant-numeric: tabular-nums;
}
.qp__v--accent { color: var(--fs-accent); }
.qp__v--note {
  font-weight: 400;
  color: var(--fs-ink-500);
}
html[data-motion-allowed="false"] .qp { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .qp { animation: none; }
}
</style>
