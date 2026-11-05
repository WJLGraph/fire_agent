<script setup>
/**
 * 作战大屏 · 火险预警信息条（整体摘要 + 各州市详情）
 *
 * v0 视觉规范：
 *  - 摘要条为单行 mono 读数，无脉冲发光动画；
 *  - 详情为「栏内」紧凑列表（随右栏文档流展开，不再 absolute 浮于地图之上），
 *    单行一条州市记录，等高色条表意等级，超长描述省略号 + title 悬浮全文。
 *
 * 受控组件：fireWarning 由父级 computed 提供，展开状态以 v-model:showDetail 双向绑定。
 */
defineProps({
  fireWarning: { type: Object, required: true },
  showDetail: { type: Boolean, default: false },
})

const emit = defineEmits(['update:showDetail'])
</script>

<template>
  <div class="fire-warning">
    <!-- 摘要条：单行读数，点击展开/收起详情 -->
    <button
      type="button"
      class="fw-summary"
      :style="{ '--fw-c': fireWarning.summary.color }"
      @click="emit('update:showDetail', !showDetail)"
    >
      <span class="fw-dot" aria-hidden="true"></span>
      <span class="fw-date">{{ fireWarning.year }}-{{ String(fireWarning.month).padStart(2, '0') }}{{ fireWarning.day ? ('-' + String(fireWarning.day).padStart(2, '0')) : '' }}</span>
      <span class="fw-level">{{ fireWarning.summary.label }}</span>
      <span class="fw-sp"></span>
      <span class="fw-meta">高风险<b>{{ fireWarning.highRiskCount }}</b> · 中风险<b>{{ fireWarning.warningCount - fireWarning.highRiskCount }}</b></span>
      <span class="fw-toggle">{{ showDetail ? '收起' : '详情' }}</span>
    </button>

    <!-- 详情：栏内紧凑列表（各州市一行，等级色条 + 描述省略） -->
    <div v-if="showDetail" class="fw-detail">
      <div
        v-for="(region, idx) in fireWarning.regionList"
        :key="region.city"
        class="fw-row"
        :style="{ '--fw-c': region.color, '--i': idx }"
        :title="`${region.desc} ${region.measure}`"
      >
        <div class="fw-row__hd">
          <span class="fw-row__city">{{ region.city }}</span>
          <span class="fw-row__tag" :style="{ background: region.color }">{{ region.label }}</span>
        </div>
        <div class="fw-row__desc">{{ region.desc }}</div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.fire-warning {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* 摘要条：与 v0 field 徽标同语（mono 读数 + 发丝线） */
.fw-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 10px;
  font-family: var(--fs-font-mono);
  font-size: 11px;
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
  border: 1px solid var(--fs-hairline);
  border-left: 2px solid var(--fw-c, var(--fs-accent));
  border-radius: var(--fs-r-sm, 6px);
  cursor: pointer;
  text-align: left;
  transition:
    border-color var(--fs-dur-micro, 160ms) var(--fs-ease),
    background var(--fs-dur-micro, 160ms) var(--fs-ease),
    transform var(--fs-dur-micro, 160ms) var(--fs-ease);

  &:hover {
    background: var(--fs-bg-surface);
    border-color: var(--fs-hairline-strong);
    transform: translateX(1px);
  }
  &:active { transform: translateX(1px) scale(0.995); }
}
.fw-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--fw-c, var(--fs-accent));
  flex-shrink: 0;
  transition: transform var(--fs-dur-micro, 160ms) var(--fs-ease);
}
.fw-summary:hover .fw-dot { transform: scale(1.2); }
.fw-date {
  color: var(--fs-ink-500);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.fw-level {
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--fw-c, var(--fs-accent));
  white-space: nowrap;
}
.fw-sp { flex: 1; }
.fw-meta {
  color: var(--fs-ink-500);
  white-space: nowrap;
  b { color: var(--fs-ink-900); font-weight: 700; font-variant-numeric: tabular-nums; }
}
.fw-toggle {
  color: var(--fs-accent);
  white-space: nowrap;
  /* 悬停时补出下划线，提示摘要条本身可点击展开 */
  box-shadow: inset 0 -1px 0 transparent;
  transition: box-shadow var(--fs-dur-micro, 160ms) var(--fs-ease);
}
.fw-summary:hover .fw-toggle { box-shadow: inset 0 -1px 0 currentColor; }

/* 详情：栏内文档流，单列紧凑行 */
.fw-detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 6px;
  /* 高度受限于视口比例：详情过长时本区自滚动，不挤压下方图表 */
  max-height: min(216px, 28vh);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
  animation: fwIn 0.18s var(--fs-ease, ease-out);
}
@keyframes fwIn {
  from { opacity: 0; transform: translateY(-3px); }
  to   { opacity: 1; transform: none; }
}
.fw-row {
  padding: 6px 9px;
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-left: 2px solid var(--fw-c, var(--fs-accent));
  border-radius: var(--fs-r-sm, 6px);
  min-width: 0;
  transition:
    border-color var(--fs-dur-micro, 160ms) var(--fs-ease),
    box-shadow var(--fs-dur-micro, 160ms) var(--fs-ease),
    transform var(--fs-dur-micro, 160ms) var(--fs-ease);
  /* 展开时逐行错峰入场（32ms/行），基线为终态 */
  animation: fw-row-in 0.28s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) both;
  animation-delay: calc(var(--i, 0) * 32ms);
}
.fw-row:hover {
  border-color: var(--fs-hairline-strong);
  border-left-color: var(--fw-c, var(--fs-accent));
  box-shadow: var(--fs-e1);
  transform: translateX(1px);
}
.fw-row__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.fw-row__city {
  font-size: 12px;
  font-weight: 600;
  color: var(--fs-ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fw-row__tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 999px;
  color: var(--fs-bg-canvas);
  white-space: nowrap;
  flex-shrink: 0;
  font-family: var(--fs-font-mono);
}
/* 描述两行截断（原单行省略号在 320px 栏宽下几乎读不到内容）；全文仍在 title 中 */
.fw-row__desc {
  margin-top: 3px;
  font-size: 11px;
  line-height: 1.55;
  color: var(--fs-ink-500);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
}

@keyframes fw-row-in {
  from { opacity: 0; transform: translateX(-4px); }
  to   { opacity: 1; transform: none; }
}

/* 动效三态闸门：入场与位移反馈在 off / 系统 reduce 下关闭（基线可见） */
html[data-motion-allowed="false"] .fw-detail,
html[data-motion-allowed="false"] .fw-row { animation: none; }
html[data-motion-allowed="false"] .fw-summary:hover,
html[data-motion-allowed="false"] .fw-summary:active,
html[data-motion-allowed="false"] .fw-row:hover { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .fw-detail,
  html:not([data-motion="on"]) .fw-row { animation: none; }
  html:not([data-motion="on"]) .fw-summary:hover,
  html:not([data-motion="on"]) .fw-summary:active,
  html:not([data-motion="on"]) .fw-row:hover { transform: none; }
}
</style>
