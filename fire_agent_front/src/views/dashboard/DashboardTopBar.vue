<script setup>
/**
 * 作战大屏 · 顶栏（单行 64px：字标 / KPI / 天气 / 时钟，visual-v0 dash-top 同构）
 *
 * v0 对齐（三轮）：
 *   - 天气改为纯文本单行「昆明 · 晴 18°C · 湿度 31% · 西南风 3 级」，去卡片按钮与弹层
 *   - 删除「DataAgent · 后端数据」徽标（数据源状态由地图左上 MapOverlays 承担）
 *
 * 筛选控制（数据模式 / 日期 / 行政区）在右栏 RailFilterPanel。
 * 本组件为受控组件：KPI 由父组件算好传入。
 */
import { ref, onMounted } from 'vue'
import BackHomeButton from '@/components/base/BackHomeButton.vue'
import Clock from '@/components/clock.vue'                          // 实时时钟
import { fethLocation } from '@/utils/timeWeather'
import AnimNumber from './AnimNumber.vue'

defineProps({
  /** 顶栏 KPI：[{ key, label, value, unit, hot }]，由父组件按当前数据算出 */
  kpis: { type: Array, default: () => [] },
})

// ====== 天气（纯文本，v0 dash-top__weather 同构） ======
const amapKey     = import.meta.env.VITE_AMAP_KEY || 'b09f93666c56d12e71ac488e70cdf2d3'
const weatherInfo = ref(null)

onMounted(() => {
  // 异步加载天气
  fethLocation(amapKey, weatherInfo)
})
</script>

<template>
  <header class="gis-topbar">
    <!-- 单行 64px：字标 · KPI / 天气 / 时钟 -->
    <div class="gis-banner">
      <div class="gis-banner-side left">
        <div class="brand-block">
          <span class="brand-cn">焰哨 · 作战大屏</span>
          <span class="brand-en">FLAME SENTRY · SITUATION ROOM</span>
          <i class="brand-rule" aria-hidden="true"></i>
        </div>
        <BackHomeButton />
      </div>

      <div class="gis-banner-side right">
        <!-- 3 个 KPI（等宽数字，读数对齐） -->
        <div class="kpi-row">
          <div
            v-for="(k, i) in kpis"
            :key="k.key"
            class="kpi"
            :class="{ 'is-hot': k.hot, 'is-toned': !!k.color }"
            :style="[{ '--i': i }, k.color ? { '--kpi-c': k.color } : null]"
          >
            <span class="kpi__lb">{{ k.label }}</span>
            <span class="kpi__v"><AnimNumber :value="k.value" /><span v-if="k.unit" class="kpi__u">{{ k.unit }}</span></span>
          </div>
        </div>
        <!-- 天气：纯文本单行（v0 dash-top__weather 同构） -->
        <span
          v-if="weatherInfo && weatherInfo.city"
          class="header-weather"
          :title="`${weatherInfo.city} · ${weatherInfo.weather} ${weatherInfo.temperature}°C · 湿度 ${weatherInfo.humidity}% · ${weatherInfo.winddirection}风`"
        >{{ weatherInfo.city }} · {{ weatherInfo.weather }} {{ weatherInfo.temperature }}°C · 湿度 {{ weatherInfo.humidity }}% · {{ weatherInfo.winddirection }}风</span>
        <span v-else class="header-weather is-pending">定位天气…</span>
        <div class="header-time"><Clock /></div>
      </div>
    </div>
  </header>
</template>

<style lang="scss" scoped>
.gis-topbar {
  position: relative;
  z-index: 20;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid var(--fs-hairline);
  background: var(--fs-bg-surface);
  overflow: visible;
}
.gis-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  height: var(--fs-topbar-h, 64px);
  padding: 0 20px;
}
.gis-banner-side {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}
/* 左：字标可压缩（极窄时省略号），右：读数条按内容宽度优先保完整 */
.gis-banner-side.left { flex: 1 1 auto; }
.gis-banner-side.right {
  flex: 0 1 auto;
  justify-content: flex-end;
  gap: 14px;
}

/* 字标：无发光、无渐变 */
.brand-block {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  animation: tb-in 0.5s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) both;
}
.brand-cn {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--fs-ink-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: letter-spacing var(--fs-dur-panel, 280ms) var(--fs-ease);
}
.brand-block:hover .brand-cn { letter-spacing: 0.13em; }
.brand-en {
  font-family: var(--fs-font-mono);
  font-size: 8px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
  white-space: nowrap;
}
/* 字标强调线：挂载即从左向右绘出（基线为终态，动效关闭时静态可见） */
.brand-rule {
  height: 1px;
  margin-top: 4px;
  background: var(--fs-accent);
  transform: scaleX(1);
  transform-origin: left center;
  animation: tb-rule-in 0.62s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) 0.1s both;
}

/* KPI：等宽数字，读数对齐 */
.kpi-row {
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
}
.kpi {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1px;
  padding: 0 16px;
  border-left: 1px solid var(--fs-hairline);
  transition: background-color 0.16s var(--fs-ease);
  animation: tb-in 0.45s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) both;
  animation-delay: calc(var(--i, 0) * 70ms + 60ms);
}
.kpi:hover { background: rgba(var(--fs-ink-900-rgb), 0.03); }
.kpi:first-child { border-left: none; }
/* 悬停读数条：2px 色带由中心展开；带等级的 KPI 常显（色带即预警色） */
.kpi::after {
  content: '';
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 0;
  height: 2px;
  background: var(--kpi-c, var(--fs-accent));
  transform: scaleX(0);
  transition: transform var(--fs-dur-panel, 280ms) var(--fs-ease);
}
.kpi:hover::after,
.kpi.is-toned::after { transform: scaleX(1); }
.kpi__lb {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--fs-ink-500);
  white-space: nowrap;
  transition: color 0.16s var(--fs-ease);
}
.kpi:hover .kpi__lb { color: var(--fs-ink-700); }
.kpi__v {
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
  color: var(--fs-ink-900);
  white-space: nowrap;
}
.kpi__u {
  margin-left: 3px;
  font-size: 11px;
  font-weight: 400;
  color: var(--fs-ink-400);
}
.kpi.is-hot .kpi__v { color: var(--fs-accent); }
/* 预警等级读数：直接采用预警口径的等级色（与右栏预警条、地图图例同一色彩事实源） */
.kpi.is-toned .kpi__v { color: var(--kpi-c); }
.kpi.is-toned .kpi__lb {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.kpi.is-toned .kpi__lb::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: var(--kpi-c);
}

/* 天气：纯文本单行（v0 dash-top__weather），详情悬停 title 查看 */
.header-weather {
  flex-shrink: 0;
  font-size: 11px;
  letter-spacing: 0.01em;
  color: var(--fs-ink-500);
  white-space: nowrap;
  animation: tb-in 0.45s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) 0.16s both;
}
.header-weather.is-pending { color: var(--fs-ink-400); }
.header-time {
  display: flex;
  align-items: center;
  animation: tb-in 0.45s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) 0.22s both;
}

/* ==================== 入场关键帧（终态即基线，动效关闭时无残留） ==================== */
@keyframes tb-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: none; }
}
@keyframes tb-rule-in {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}

/* 动效三态闸门：off / 系统 reduce 时静态呈现终态 */
html[data-motion-allowed="false"] .brand-block,
html[data-motion-allowed="false"] .brand-rule,
html[data-motion-allowed="false"] .kpi,
html[data-motion-allowed="false"] .header-weather,
html[data-motion-allowed="false"] .header-time {
  animation: none;
}
html[data-motion-allowed="false"] .brand-cn,
html[data-motion-allowed="false"] .kpi::after {
  transition: none;
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .brand-block,
  html:not([data-motion="on"]) .brand-rule,
  html:not([data-motion="on"]) .kpi,
  html:not([data-motion="on"]) .header-weather,
  html:not([data-motion="on"]) .header-time {
    animation: none;
  }
  html:not([data-motion="on"]) .brand-cn,
  html:not([data-motion="on"]) .kpi::after {
    transition: none;
  }
}

/* ==================== 窄视口收口 ====================
   顶栏是单行读数条，不换行：按信息重要性依次让位（天气/英文字标先退），
   KPI 与时钟始终完整可见，避免相互压叠成「文字叠字」。 */
@media (max-width: 1400px) {
  .header-weather { display: none; }
}
@media (max-width: 1180px) {
  .brand-en { display: none; }
  .kpi { padding: 0 12px; }
  .kpi__v { font-size: 19px; }
  .kpi::after { left: 12px; right: 12px; }
}
@media (max-width: 900px) {
  .gis-banner { padding: 0 12px; gap: 8px; }
  .gis-banner-side { gap: 10px; }
  .brand-cn { font-size: 14px; }
}
/* 字标与读数条实在放不下时，字标退场（侧栏字标仍在，不丢品牌） */
@media (max-width: 760px) {
  .brand-block { display: none; }
}
</style>
