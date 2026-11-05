<script setup>
/**
 * 公开子页统一壳：滚动容器 + 页头/页脚 + 首屏头区（eyebrow/标题/导语）
 * 动效由 usePubMotion 统一装配；正文经默认插槽传入（用 .rv / data-stagger 参与显现）。
 */
import { ref, computed } from 'vue'
import PubHeader from '@/components/welcome/PubHeader.vue'
import PubFooter from '@/components/welcome/PubFooter.vue'
import PubPager from '@/components/welcome/PubPager.vue'
import QtCursor from '@/components/welcome/QtCursor.vue'
import { usePubMotion } from '@/composables/usePubMotion'

const props = defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  lead: { type: String, default: '' },
  /** 当前页在公开页组中的序号（翻页带用）：1 能力 / 2 工作流 / 3 技术 / 4 关于 */
  pageIndex: { type: Number, default: 1 },
})

const rootRef = ref(null)
const { scrollPct: pct } = usePubMotion(rootRef)
/** index rail：页码 0N / 05 + 页名（eyebrow 前半） + 滚动百分比 */
const railNo = computed(() => `${String(props.pageIndex + 1).padStart(2, '0')} / 05`)
const railName = computed(() => (props.eyebrow.split('·')[0] || '').trim())
const pctText = computed(() => `${String(Math.round(pct.value * 100)).padStart(3, '0')}%`)
</script>

<template>
  <div ref="rootRef" class="wl">
    <div class="grain" aria-hidden="true"></div>
    <div class="wl-content">
      <div class="wl-progress" aria-hidden="true"><i data-progress class="wl-progress__bar"></i></div>

      <PubHeader :show-back="true" />
      <QtCursor />

      <main>
        <section class="phead" data-head>
          <div class="phead__inner">
            <p data-h="eyebrow" class="qt-eyebrow phead__eyebrow">{{ eyebrow }}</p>
            <h1 data-h="title" class="phead__title">{{ title }}</h1>
            <p v-if="lead" data-h="lead" class="phead__lead">{{ lead }}</p>
            <div data-h="acts" class="phead__acts"><slot name="head-acts" /></div>

            <!-- index rail：页头右侧坐标注记（页码 / 页名 / 竖向进度线 / 滚动百分比） -->
            <div class="phead__rail" aria-hidden="true">
              <span class="rail__no qt-num">{{ railNo }}</span>
              <span class="rail__name qt-eyebrow">{{ railName }}</span>
              <i class="rail__track"><i class="rail__bar" :style="{ transform: `scaleY(${pct})` }"></i></i>
              <span class="rail__pct qt-num">{{ pctText }}</span>
            </div>
          </div>
          <div class="phead__ticks qt-ticks--tall qt-ticks" aria-hidden="true"></div>
        </section>

        <div class="pbody">
          <slot />
        </div>
      </main>

      <PubPager :index="props.pageIndex" />
      <PubFooter />
    </div>
  </div>
</template>
<style scoped>
.wl {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--fs-bg-canvas);
  color: var(--fs-ink-900);
}
.wl-content { position: relative; }

.wl-progress {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 2px;
  z-index: 60;
  pointer-events: none;
}
.wl-progress__bar {
  display: block;
  width: 100%; height: 100%;
  transform: scaleX(0);
  transform-origin: left center;
  will-change: transform;
  background: linear-gradient(90deg, var(--fs-accent), var(--fs-risk-mid));
}

.phead {
  border-bottom: 1px solid var(--fs-hairline);
}
.phead__inner {
  position: relative;
  width: min(1120px, 100% - 48px);
  margin: 0 auto;
  padding: var(--fs-s12) 0 var(--fs-s8);
}

/* index rail：填充页头右半边的坐标注记 */
.phead__rail {
  position: absolute;
  right: 0;
  bottom: var(--fs-s8);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  text-align: right;
}
.rail__no {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--fs-ink-900);
  font-variant-numeric: tabular-nums;
}
.rail__name { letter-spacing: 0.18em; }
.rail__track {
  position: relative;
  width: 1px;
  height: 56px;
  background: var(--fs-hairline);
  overflow: hidden;
}
.rail__bar {
  position: absolute;
  inset: 0;
  background: var(--fs-accent);
  transform: scaleY(0);
  transform-origin: top center;
  will-change: transform;
}
.rail__pct {
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 900px) {
  .phead__rail { display: none; }
}
.phead__eyebrow {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
/* eyebrow 前短横线：由 --hd-line（GSAP scrub）驱动展开；静态默认满格 */
.phead__eyebrow::before {
  content: '';
  width: 22px;
  height: 1px;
  background: var(--fs-accent);
  transform: scaleX(var(--hd-line, 1));
  transform-origin: left center;
}
.phead__title {
  margin: 14px 0 0;
  font-size: clamp(28px, 3.6vw, 42px);
  font-weight: 600;
  letter-spacing: 0.01em;
  line-height: 1.3;
  color: var(--fs-ink-900);
}
/* 标题下发丝线：同上 scrub 驱动 */
.phead__title::after {
  content: '';
  display: block;
  width: 56px;
  height: 1px;
  margin-top: 12px;
  background: var(--fs-hairline-strong);
  transform: scaleX(var(--hd-line, 1));
  transform-origin: left center;
}
.phead__lead {
  margin: 16px 0 0;
  max-width: 620px;
  font-size: 14px;
  line-height: 2;
  color: var(--fs-ink-500);
  text-wrap: pretty;
}
.phead__acts { margin-top: 24px; display: flex; flex-wrap: wrap; gap: 12px; }
.phead__ticks { width: min(1120px, 100% - 48px); margin: 0 auto; opacity: 0.7; }

.pbody { /* 不设 min-height：正文结束后立即收束，杜绝大片区空白 */ }

@media (max-width: 640px) {
  .phead__inner { width: min(1120px, 100% - 32px); }
  .phead__ticks { width: min(1120px, 100% - 32px); }
}
</style>
