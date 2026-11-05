<script setup>
/**
 * 智能查询 · 查询历史（与知识库「问答任务」hist-item 同款，常驻列表）
 *
 * 标题行（sec-t 同构 + 计数 + 清除）+ 历史卡片（单行截断文本 + mono 时间 + 解析方式徽标 + 悬停删除）。
 * 每页 4 条固定，行高与间距按 4 条刚好铺满历史区来定（列表 overflow: hidden，不出现滚动条）。
 * 条目视觉（左侧 2px 强调竖轨 + 悬停位移 + 选中 accent 环）与知识库问答历史保持同一套语言。
 * 受控组件：历史数据由父组件持有，本组件只负责渲染与上抛事件。
 */
import { ref, computed, watch } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  activeId: { type: [String, Number], default: null },
})
const emit = defineEmits(['select', 'remove', 'clear'])

// LLM 通道模型名（与页头徽标一致；后端配置变更时同步改这里）
const LLM_MODEL = 'qwen-plus'

// ====== 本地分页（每页 4 条） ======
const PAGE_SIZE = 4
const currentPage = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(props.items.length / PAGE_SIZE)))
const pagedItems = computed(() =>
  props.items.slice((currentPage.value - 1) * PAGE_SIZE, currentPage.value * PAGE_SIZE),
)
// 历史被删除/清除后页码越界时回退
watch(() => props.items.length, () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})
const goPage = (p) => { currentPage.value = p }

// 选中态与知识库问答历史同款判定（当前回显的那条高亮）
const isOn = (item) => props.activeId !== null && String(item.id) === String(props.activeId)
</script>

<template>
  <section class="qh">
    <!-- 标题行 -->
    <div class="qh__hd">
      <span class="qh__t">查询历史</span>
      <span class="qh__n">{{ items.length }}</span>
      <span class="qh__sp"></span>
      <button v-if="items.length" class="qh__clear" title="清除全部历史" @click="emit('clear')">清除</button>
    </div>

    <!-- 空态 -->
    <div v-if="!items.length" class="qh__empty">暂无查询记录，执行一次查询后自动归档</div>

    <!-- 历史卡片 -->
    <div v-else class="qh__list">
      <div
        v-for="(item, i) in pagedItems"
        :key="item.id ?? i"
        class="qh__item"
        :class="{ 'is-on': isOn(item) }"
        @click="emit('select', item)"
      >
        <div class="qh__text" :title="item.text">{{ item.text }}</div>
        <div class="qh__meta">
          <span class="qh__time">{{ item.time }}</span>
          <span
            class="qh__method"
            :class="item.method"
            :title="item.method === 'llm' ? 'LLM 解析' : '关键词解析'"
          >{{ item.method === 'llm' ? LLM_MODEL : '关键词' }}</span>
          <span class="qh__sp"></span>
          <button class="qh__del" title="删除该记录" @click.stop="emit('remove', item)">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5.5h13"/><path d="M8 2.8h4"/><path d="M5.2 5.5 5.9 17h8.2l.7-11.5"/><path d="M8.4 8.4v5.4M11.6 8.4v5.4"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 翻页器（常显：与 Agent 中心历史/报告中心左栏同款 el-pagination small） -->
    <div v-if="items.length" class="qh__pager">
      <el-pagination
        size="small"
        layout="prev, pager, next"
        :total="items.length"
        :page-size="PAGE_SIZE"
        :current-page="currentPage"
        @current-change="goPage"
      />
    </div>
  </section>
</template>

<style scoped>
.qh {
  flex: 1; /* 占满左列剩余高度：输入区定高，历史区弹性 */
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 标题行（sec-t 同构：标题 + 计数 + 延伸发丝线 + 清除） */
.qh__hd {
  display: flex;
  align-items: center;
  gap: 6px;
}
.qh__t {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
.qh__t::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 1px;
  background-color: var(--fs-hairline-strong);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.qh__hd:hover .qh__t::before { background-color: var(--fs-accent); }
.qh__n {
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 10px;
  color: var(--fs-ink-400);
}
.qh__sp { flex: 1; height: 1px; background: var(--fs-hairline); }
.qh__clear {
  height: 20px;
  padding: 0 7px;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.qh__clear:hover { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 8%, transparent); }

/* 空态 */
.qh__empty {
  padding: 14px 10px;
  text-align: center;
  font-size: 11px;
  line-height: 1.6;
  color: var(--fs-ink-400);
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
}

/* 历史卡片（v0 hist-item 同构） */
.qh__list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  /* 每页 4 条按行高实测铺满历史区，两个方向的滚动条都不该出现；
     padding-right 给悬停 2px 位移留出余量，避免位移把横向滚动条顶出来 */
  overflow: hidden;
  padding-right: 2px;
}
.qh__item {
  box-sizing: border-box;
  position: relative;
  flex-shrink: 0; /* 行高固定：条数按高度实测，装不下宁可分页也不压扁 */
  height: 57px; /* 固定行高：padding 16 + 文本 18（1 行）+ meta 上边距 5 + meta 18；紧凑等高，翻页不跳动 */
  padding: 8px 12px;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  transition: background-color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
/* 左侧 2px 强调竖轨：与知识库问答历史 hist-item 同款（悬停/选中展开，静息收起） */
.qh__item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--fs-accent);
  transform: scaleY(0);
  transform-origin: center;
  transition: transform 0.32s var(--fs-ease);
}
.qh__item:hover {
  background-color: var(--fs-bg-sunken);
  transform: translateX(2px);
}
.qh__item:hover::before { transform: scaleY(1); }
.qh__item:active { transform: translateX(2px) scale(0.995); }
/* 选中条目：accent 环 + 竖轨常驻（与知识库 is-on 一致） */
.qh__item.is-on { box-shadow: inset 0 0 0 1px var(--fs-accent); }
.qh__item.is-on::before { transform: scaleY(1); }
.qh__text {
  height: 18px; /* 固定 1 行（12px × 1.5）：单行省略，条目更紧凑 */
  font-size: 12px;
  color: var(--fs-ink-700);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.qh__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 5px;
}
.qh__time {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums; /* 与问答历史一致：时间跳动不抖 */
  white-space: nowrap;
}
.qh__method {
  height: 16px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 10px;
  font-weight: 500;
}
.qh__method.llm {
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  letter-spacing: 0.02em;
}
.qh__method.keyword {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
}
.qh__del {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  color: var(--fs-ink-500);
  background: var(--fs-bg-sunken); /* 常显底色：暗色下不再是一坨深方块，图标清晰可辨 */
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.qh__del svg { width: 11px; height: 11px; }
/* 行悬停时把删除键从 sunken 行底「托」起，避免与悬停底色糊在一起 */
.qh__item:hover .qh__del { background: var(--fs-bg-surface); }
.qh__del:hover,
.qh__item:hover .qh__del:hover {
  color: var(--fs-danger);
  background: color-mix(in srgb, var(--fs-danger) 12%, transparent);
}
.qh__del:active { transform: scale(0.9); }

/* ===== 翻页器（el-pagination small，常显沉底） ===== */
.qh__pager {
  flex-shrink: 0;
  padding: 2px 0 0;
  display: flex;
  justify-content: center;
}
.qh__pager :deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--fs-ink-500);
  --el-pagination-button-color: var(--fs-ink-500);
  --el-pagination-button-disabled-color: var(--fs-ink-400);
  --el-pagination-hover-color: var(--fs-accent);
  --el-pagination-font-size: 12px;
  font-family: var(--fs-font-mono);
}
.qh__pager :deep(.el-pager li) {
  min-width: 24px;
  height: 24px;
  border-radius: var(--fs-r-xs, 3px);
  background: transparent;
}
.qh__pager :deep(.el-pager li.is-active) {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
}
.qh__pager :deep(.el-pagination .btn-prev),
.qh__pager :deep(.el-pagination .btn-next) {
  background: transparent;
}

/* 动效三态闸门：悬停/按压位移与竖轨展开受控（选中态 is-on 的竖轨属状态，不受闸门影响） */
html[data-motion-allowed="false"] .qh__item:hover,
html[data-motion-allowed="false"] .qh__item:active,
html[data-motion-allowed="false"] .qh__del:active { transform: none; }
html[data-motion-allowed="false"] .qh__item:hover::before { transform: scaleY(0); }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .qh__item:hover,
  html:not([data-motion="on"]) .qh__item:active,
  html:not([data-motion="on"]) .qh__del:active { transform: none; }
  html:not([data-motion="on"]) .qh__item:hover::before { transform: scaleY(0); }
}
</style>
