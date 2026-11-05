<script setup>
/**
 * 知识库 · 引用溯源列表（v0 kb-cite 同构：序号方徽 + 文档名 · 分数 + 原文预览）
 *
 * 受控组件：引用列表与当前展开项由父组件持有（activeIndex 用 v-model 双向），
 * 点击条目展开/收起全文。正文角标点击 → 父组件调 scrollTo(i) 平滑滚动到对应条目。
 */
import { nextTick } from 'vue'

defineProps({
  references: { type: Array, default: () => [] },
  activeIndex: { type: Number, default: null },
})
const emit = defineEmits(['update:activeIndex'])

const fmtScore = (v) => {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : v
}

// 条目 DOM 引用（函数 ref 收集，供角标跳转定位）
const itemEls = []
const setItemRef = (el, i) => { if (el) itemEls[i] = el }

// 平滑滚动到第 i 条来源并展开（由父组件在角标点击时调用）
const scrollTo = async (i) => {
  emit('update:activeIndex', i)
  await nextTick()
  itemEls[i]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
defineExpose({ scrollTo })
</script>

<template>
  <div v-if="references && references.length > 0" class="kref">
    <div class="kref__hd">
      <span class="kref__t">引用溯源</span>
      <span class="kref__n">{{ references.length }}</span>
      <span class="kref__sp"></span>
      <span class="kref__tip">点击条目展开原文</span>
    </div>

    <div class="kref__list">
      <div
        v-for="(ref, i) in references"
        :key="i"
        :ref="(el) => setItemRef(el, i)"
        class="kb-cite"
        :class="{ 'is-on': activeIndex === i }"
        @click="emit('update:activeIndex', activeIndex === i ? null : i)"
      >
        <span class="kb-cite__i">{{ i + 1 }}</span>
        <div class="kb-cite__b">
          <span class="kb-cite__t">
            {{ ref.document_title || '未知文档' }}
            <span class="mono">· 相关性 {{ fmtScore(ref.score) }}<template v-if="ref.vector_score !== undefined"> · 向量 {{ fmtScore(ref.vector_score) }}</template><template v-if="ref.keyword_score !== undefined"> · 关键词 {{ fmtScore(ref.keyword_score) }}</template></span>
          </span>
          <p class="kb-cite__p">{{ ref.content }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kref {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kref__hd {
  display: flex;
  align-items: center;
  gap: 6px;
}
/* 引用溯源：与检索卡同语言的 2px 刻度条标题 */
.kref__t {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
.kref__t::before {
  content: '';
  width: 2px;
  height: 11px;
  margin-right: 6px;
  border-radius: 1px;
  background: var(--fs-hairline-strong);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, ease);
}
.kref:hover .kref__t::before { background: var(--fs-accent); }
.kref__n {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
}
.kref__sp { flex: 1; height: 1px; background: var(--fs-hairline); }
.kref__tip {
  font-size: 10px;
  color: var(--fs-ink-400);
}

.kref__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 引用条目（v0 kb-cite 同构）：悬停发丝加亮+中性抬升，序号方徽点亮 */
.kb-cite {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  animation: kref-in 0.4s var(--fs-ease-out) both;
  transition:
    background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.kb-cite:nth-child(2) { animation-delay: 55ms; }
.kb-cite:nth-child(3) { animation-delay: 110ms; }
.kb-cite:nth-child(4) { animation-delay: 165ms; }
.kb-cite:nth-child(5) { animation-delay: 220ms; }
.kb-cite:nth-child(6) { animation-delay: 275ms; }
.kb-cite:nth-child(n + 7) { animation-delay: 330ms; }
@keyframes kref-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.kb-cite:hover {
  background: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong), var(--fs-e1);
}
.kb-cite.is-on { box-shadow: inset 0 0 0 1px var(--fs-accent), var(--fs-e1); }

/* 序号方徽 */
.kb-cite__i {
  flex: none;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  transition: background-color var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.kb-cite:hover .kb-cite__i,
.kb-cite.is-on .kb-cite__i { background: var(--fs-accent); color: var(--fs-on-accent); }
.kb-cite__b {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kb-cite__t {
  font-size: 12px;
  color: var(--fs-ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-cite__t .mono {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
}
.kb-cite__p {
  margin: 0;
  font-size: 11px;
  line-height: 1.7;
  color: var(--fs-ink-500);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
}
.kb-cite.is-on .kb-cite__p {
  -webkit-line-clamp: unset;
  line-clamp: unset;
}

/* ===== 动效闸门：关闭时错峰入场落终态 ===== */
html[data-motion-allowed="false"] .kb-cite { animation: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .kb-cite { animation: none; }
}
</style>
