<script setup>
/**
 * 报告中心 · 左侧报告列表（v0 rep-list 同构：发丝行列表，去浮卡）
 *
 * 受控组件：列表数据、分页、loading 由父组件持有，选中与删除由事件上抛。
 * 视觉：sec-t 头 + badge 计数；rep-item 行（title 13px 2 行截断 + meta 徽标行）；
 *       选中态 accent-soft 底 + 左缘 2px accent 条；删除钮悬停显现；el-pagination 同款翻页。
 */
import { providerShort, isAgentGenerated } from '@/utils/reportMeta'

defineProps({
  reports: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  pageSize: { type: Number, default: 6 },
  page: { type: Number, default: 1 },
  currentId: { type: [Number, String], default: null },
})
const emit = defineEmits(['select', 'delete', 'page-change'])
</script>

<template>
  <aside class="rl">
    <!-- 头：sec-t + 计数徽标 -->
    <div class="rl__hd">
      <span class="rl__t">报告列表</span>
      <span class="rl__sp"></span>
      <span class="rl__badge">{{ total }}</span>
    </div>

    <!-- 列表：rep-item 发丝行 -->
    <div v-loading="loading" class="rl__bd">
      <div v-if="reports.length === 0 && !loading" class="rl__empty">
        <svg class="rl__empty-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 3.5h7.5L16 7v9.5H5z"/><path d="M12.5 3.5V7H16"/><path d="M7.5 10.5h5M7.5 13h5"/>
        </svg>
        暂无报告
        <span class="rl__empty-hint">在 Agent 协作中心执行任务后，报告会自动保存到这里</span>
      </div>

      <div
        v-for="item in reports"
        :key="item.id"
        class="rl-item"
        :class="{ 'is-on': currentId === item.id }"
        @click="emit('select', item)"
      >
        <button
          class="rl-item__del"
          title="删除该报告"
          @click.stop="emit('delete', item)"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5.5h13"/><path d="M8 2.8h4"/><path d="M5.2 5.5 5.9 17h8.2l.7-11.5"/><path d="M8.4 8.4v5.4M11.6 8.4v5.4"/></svg>
        </button>
        <span class="rl-item__t" :title="item.title">{{ item.title }}</span>
        <span class="rl-item__m">
          <span
            v-if="isAgentGenerated(item)"
            class="rl-badge rl-badge--accent"
            title="由 Agent 协作中心自动生成"
          >Agent</span>
          <span v-else class="rl-badge" title="人工上传或模板生成">人工</span>
          <span
            v-if="item.llm_model || item.llm_provider"
            class="rl-badge"
            :title="`模型来源：${item.llm_model || providerShort(item.llm_provider)}`"
          >{{ item.llm_model || providerShort(item.llm_provider) }}</span>
          <!-- 重生成走 upsert：created_at 不变、updated_at 刷新，优先展示更新时间避免"新报告像旧的" -->
          <span class="rl-item__time">{{ item.updated_at && item.updated_at !== item.created_at ? '更新于 ' + item.updated_at : item.created_at }}</span>
        </span>
      </div>

      <!-- 翻页器（与 Agent 中心历史同款） -->
      <div v-if="reports.length > 0" class="rl__pager">
        <el-pagination
          size="small"
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="emit('page-change', $event)"
        />
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* v0 rep-list：surface 列 + 右缘发丝线（通栏，无浮卡圆角） */
.rl {
  flex: none;
  width: 340px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: var(--fs-bg-surface);
  border-right: 1px solid var(--fs-hairline);
}
@media (max-width: 1440px) {
  .rl { width: 300px; }
}

/* 头（sec-t 同构 + badge 计数） */
.rl__hd {
  flex: none;
  padding: 16px;
  border-bottom: 1px solid var(--fs-hairline);
  display: flex;
  align-items: center;
  gap: 8px;
}
.rl__t {
  position: relative;
  padding-left: 10px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
/* 标题前置 2px 刻度条（与大屏图表卡同语言） */
.rl__t::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 2px;
  height: 11px;
  transform: translateY(-50%);
  border-radius: 2px;
  background: var(--fs-hairline-strong);
}
.rl__sp { flex: 1; }
.rl__badge {
  height: 20px;
  padding: 0 7px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-size: 11px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* 列表体 */
.rl__bd {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

/* v0 rep-item：发丝行（无边框浮卡） */
.rl-item {
  position: relative;
  box-sizing: border-box;
  height: 87px; /* 固定行高：padding 24 + 标题 39（2 行）+ gap 5 + meta 18 + 发丝线 1 */
  padding: 12px 16px;
  border-bottom: 1px solid var(--fs-hairline);
  display: flex;
  flex-direction: column;
  gap: 5px;
  cursor: pointer;
  transition: background-color var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
/* 左沿 2px 强调竖轨：与智能查询/知识库/Agent 中心历史条目同一语言 */
.rl-item::before {
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
.rl-item:hover {
  background-color: var(--fs-bg-sunken);
  transform: translateX(2px);
}
.rl-item:hover::before { transform: scaleY(1); }
.rl-item:active { transform: translateX(2px) scale(0.995); }
.rl-item.is-on {
  background: var(--fs-accent-soft);
}
.rl-item.is-on::before { transform: scaleY(1); }
.rl-item__t {
  height: 39px; /* 固定 2 行（13px × 1.5 × 2）：单行/双行条目等高，翻页不跳动 */
  font-size: 13px;
  font-weight: 500;
  color: var(--fs-ink-900);
  line-height: 1.5;
  padding-right: 22px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}
.rl-item__m {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--fs-ink-400);
  min-width: 0;
}
.rl-item__time {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 徽标（v0 badge 同构） */
.rl-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-size: 10px;
  font-weight: 500;
  max-width: 96px;
  overflow: hidden;
  white-space: nowrap;
}
.rl-badge--accent {
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
}
/* 删除（悬停显现，v0 ghost danger 同构） */
.rl-item__del {
  position: absolute;
  right: 8px;
  top: 10px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  color: var(--fs-ink-500);
  background: var(--fs-bg-sunken);
  opacity: 0;
  cursor: pointer;
  z-index: 1;
  transition: opacity var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.rl-item:hover .rl-item__del { opacity: 1; }
.rl-item__del svg { width: 11px; height: 11px; }
.rl-item__del:hover {
  color: var(--fs-danger);
  background: color-mix(in srgb, var(--fs-danger) 10%, transparent);
}
.rl-item__del:active { transform: scale(0.9); }

/* 空态（v0 empty：虚线发丝框） */
.rl__empty {
  margin: 16px;
  padding: 40px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-md, 10px);
  color: var(--fs-ink-500);
  font-size: 13px;
  text-align: center;
}
.rl__empty-ic { width: 22px; height: 22px; color: var(--fs-ink-400); }
.rl__empty-hint {
  font-size: 11px;
  color: var(--fs-ink-400);
  line-height: 1.7;
  max-width: 220px;
}

/* 翻页器：margin-top:auto 沉底——末页条数不足时仍钉在栏底，不跟着上跳 */
.rl__pager {
  flex-shrink: 0;
  margin-top: auto;
  padding: 10px 0 12px;
  display: flex;
  justify-content: center;
}

/* 行 hover 位移、竖轨展开与按下回弹受动效双闸门管控 */
html[data-motion-allowed="false"] .rl-item:hover,
html[data-motion-allowed="false"] .rl-item:active,
html[data-motion-allowed="false"] .rl-item__del:active { transform: none; }
html[data-motion-allowed="false"] .rl-item:hover::before { transform: scaleY(0); }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .rl-item:hover,
  html:not([data-motion="on"]) .rl-item:active,
  html:not([data-motion="on"]) .rl-item__del:active { transform: none; }
  html:not([data-motion="on"]) .rl-item:hover::before { transform: scaleY(0); }
}
</style>
