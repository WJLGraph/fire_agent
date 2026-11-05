<script setup>
/**
 * 系统管理 · 数据源 Tab — v0 kb-ans 面板 + 发丝行同构
 */
import { ref } from 'vue'
import { testDatabase as testDatabaseApi } from '@/api/admin'

defineProps({
  config: { type: Object, default: null },
})

const emit = defineEmits(['refresh-status'])

// ====== 测试结果 ======
const testDb = ref(null) // { ok, detail } | null
const testing = ref(false)

const testDatabase = async () => {
  testing.value = true
  testDb.value = null
  try {
    const res = await testDatabaseApi()
    const json = await res.json()
    testDb.value = json.data
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="ds">
    <div v-if="config" class="kb-ans">
      <div class="kb-ans__hd">
        <span class="kb-ans__t">数据源配置</span>
        <span class="sq-panel__sp"></span>
        <button class="vbtn vbtn--ghost" @click="emit('refresh-status')">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 10a6.5 6.5 0 1 1-1.9-4.6"/><path d="M16.5 3.5v3h-3"/></svg>
          刷新状态
        </button>
      </div>
      <div class="kb-ans__bd ds__rows">
        <!-- v0 sq-parse 发丝行：key 固定宽 + value -->
        <div class="ds__row">
          <span class="ds__k">数据库地址</span>
          <span class="ds__v mono">{{ config.datasource?.database_url }}</span>
        </div>
        <div class="ds__row">
          <span class="ds__k">高德地图 Key</span>
          <span class="ds__v mono">{{ config.datasource?.amap_key || '未配置' }}</span>
        </div>
      </div>
    </div>

    <!-- 连接测试 -->
    <div class="kb-ans">
      <div class="kb-ans__hd"><span class="kb-ans__t">连接测试</span></div>
      <div class="kb-ans__bd">
        <div class="ds__test-row">
          <button class="vbtn vbtn--primary" :disabled="testing" @click="testDatabase">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5a5.5 5.5 0 0 0-5.5 5.5c0 2.2 1.3 3.6 2.4 4.9.6.7 1.1 1.4 1.1 2.1h4c0-.7.5-1.4 1.1-2.1 1.1-1.3 2.4-2.7 2.4-4.9A5.5 5.5 0 0 0 10 2.5z"/><path d="M8 18h4"/></svg>
            {{ testing ? '测试中…' : '测试数据库连接' }}
          </button>
          <span v-if="testDb" class="ds__result" :class="testDb.ok ? 'ok' : 'fail'">
            <i></i>{{ testDb.detail }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ds {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex-shrink: 0; /* 禁止纵向压缩（原 min-height:100% 会导致卡片被压矮、内容被裁） */
}

/* ===== kb-ans 面板（v0 同构） ===== */
.kb-ans {
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.kb-ans__hd {
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
.kb-ans__bd {
  padding: 6px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sq-panel__sp { flex: 1; }
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; font-variant-numeric: tabular-nums; }

/* v0 btn 同构 */
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
.vbtn--primary {
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-weight: 600;
  height: 28px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.vbtn--primary:hover:not(:disabled) {
  background: var(--fs-accent-hover);
  color: var(--fs-on-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
}
.vbtn:disabled { color: var(--fs-ink-400); cursor: not-allowed; }
/* 主按钮禁用态：卸下 accent 底，避免"看着能点其实点不动" */
.vbtn--primary:disabled { background: var(--fs-bg-sunken); box-shadow: none; }

/* 发丝行（v0 sq-parse__r 同构） */
.ds__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 2px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.ds__row:hover { background: rgba(var(--fs-ink-900-rgb), 0.02); }
.ds__row:last-child { border-bottom: none; }
.ds__k {
  flex: none;
  width: 96px;
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
}
.ds__v {
  font-size: 12px;
  color: var(--fs-ink-900);
  word-break: break-all;
  user-select: all; /* 连接串与 Key 整段选中，一次复制不必手动圈选 */
}

/* 测试结果 */
.ds__test-row { display: flex; align-items: center; gap: 12px; padding: 6px 2px; flex-wrap: wrap; }
.ds__result {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  letter-spacing: 0.01em;
  padding: 6px 12px;
  border-radius: var(--fs-r-sm, 6px);
  animation: ds-in 0.4s var(--fs-ease-out) both;
}
@keyframes ds-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
html[data-motion-allowed="false"] .ds__result { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .ds__result { animation: none; }
}
.ds__result i { width: 6px; height: 6px; border-radius: 50%; flex: none; }
.ds__result.ok { color: var(--fs-success); background: color-mix(in srgb, var(--fs-success) 10%, transparent); }
.ds__result.ok i { background: var(--fs-success); }
.ds__result.fail { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 10%, transparent); }
.ds__result.fail i { background: var(--fs-danger); }
</style>
