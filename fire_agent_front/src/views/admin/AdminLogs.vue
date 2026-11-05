<script setup>
/**
 * 系统管理 · 运行日志 Tab — v0 adm-log 终端同构
 *
 * 日志数据由父组件持有并每 30 秒轮询（原先即为此行为），这里只负责渲染。
 */
defineProps({
  logs: { type: Array, default: () => [] },
  loadingLogs: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh'])

// ====== 日志等级样式 ======
const levelClass = (lv) => {
  if (lv === 'ERROR') return 'err'
  if (lv === 'WARN') return 'warn'
  return 'ok'
}
</script>

<template>
  <div class="al">
    <!-- v0 kb-ans 面板：标题行 + adm-log 终端 -->
    <div class="kb-ans anim" style="--d:80ms">
      <div class="kb-ans__hd">
        <span class="kb-ans__t">运行日志</span>
        <span class="badge badge--muted mono">30s 自动刷新</span>
        <span class="sq-panel__sp"></span>
        <span class="badge badge--muted mono">{{ logs.length }} entries</span>
        <button class="vbtn vbtn--ghost" :disabled="loadingLogs" @click="emit('refresh')">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 10a6.5 6.5 0 1 1-1.9-4.6"/><path d="M16.5 3.5v3h-3"/></svg>
          刷新
        </button>
      </div>
      <div class="adm-log mono" v-loading="loadingLogs">
        <div v-if="logs.length === 0" class="al__empty">暂无日志</div>
        <div v-for="(log, i) in logs" :key="i">
          <span class="t">{{ log.time }}</span>
          <span class="lv" :class="levelClass(log.level)">{{ log.level }}</span>
          <span class="al__src">{{ log.source }}</span>
          <span class="al__msg">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.al {
  display: flex;
  flex-direction: column;
  gap: 16px;
  /* 运行日志 Tab 为 col-scroll--fit 一屏模式：铺满剩余高度，底部不留白、外层无滚动；
     内部高度约束逐层下传（卡片 flex:1 → 日志列表 flex:1 内部滚动），min-height:0 允许收缩 */
  flex: 1 1 0;
  min-height: 0;
}

.anim {
  animation: rise 0.4s var(--fs-ease-out) both;
  animation-delay: var(--d, 0ms);
}
@keyframes rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
/* ===== kb-ans 面板（v0 同构）：卡片撑满 .al，头部固定、日志区内部滚动 ===== */
.kb-ans {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.kb-ans__hd {
  flex-shrink: 0;
  min-height: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.kb-ans__t {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--fs-ink-900);
}
.kb-ans__t::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 2px;
  background: var(--fs-accent);
  opacity: 0.7;
}
.sq-panel__sp { flex: 1; }
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  font-weight: 500;
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
  white-space: nowrap;
}
.badge--muted { color: var(--fs-ink-500); }
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; font-variant-numeric: tabular-nums; }

/* v0 btn（ghost）同构 */
.vbtn {
  height: 26px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  letter-spacing: 0.01em;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.vbtn svg { width: 12px; height: 12px; }
.vbtn:hover:not(:disabled) { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.vbtn--ghost { background: transparent; box-shadow: none; }
.vbtn--ghost:hover:not(:disabled) { background: var(--fs-bg-sunken); box-shadow: none; }
.vbtn:disabled { color: var(--fs-ink-400); cursor: not-allowed; }

/* ===== v0 adm-log 终端：flex:1 铺满卡片剩余高度，min-height:0 + 内部滚动（不再用 100vh 魔法数） ===== */
.adm-log {
  flex: 1;
  min-height: 0;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 11px;
  line-height: 1.6;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
.adm-log > div {
  display: flex;
  align-items: baseline;
  gap: 10px;
  color: var(--fs-ink-700);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.adm-log > div:not(.al__empty):hover { background: rgba(var(--fs-ink-900-rgb), 0.03); }
.adm-log .t { color: var(--fs-ink-400); flex: none; }
.adm-log .lv {
  flex: none;
  width: 44px;
  padding: 1px 0;
  text-align: center;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 9px;
  letter-spacing: 0.08em;
}
.adm-log .lv.ok { color: var(--fs-success); }
.adm-log .lv.warn { color: var(--fs-warning); background: color-mix(in srgb, var(--fs-warning) 10%, transparent); }
.adm-log .lv.err { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 10%, transparent); }
.al__src { flex: none; color: var(--fs-ink-500); }
.al__msg { flex: 1; min-width: 0; word-break: break-word; }
.al__empty { padding: 40px 0; text-align: center; color: var(--fs-ink-400); }

html[data-motion-allowed="false"] .anim { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .anim { animation: none; }
}
</style>
