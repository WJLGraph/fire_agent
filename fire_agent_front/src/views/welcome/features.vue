<script setup>
/**
 * /welcome/features — 能力详解（公开）
 *
 * 编辑式栅格：2 大能力（GIS 作战大屏 / 多智能体协同，配 SVG 可视化）+
 * 4 小能力紧凑条目；下接「场景」区（3 个真实使用场景，tab 手动切换，160–220ms 过渡）。
 * 全部内容来自系统真实功能，口径与系统内一致。
 */
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import AppIcon from '@/components/base/AppIcon.vue'
import PubPage from '@/components/welcome/PubPage.vue'

/* 大能力 ×2（配可视化） */
const majors = [
  {
    no: 'C1',
    icon: 'map',
    title: 'GIS 作战大屏',
    desc: '二三维一体化地图承载全部态势：火点聚合、风险分级、趋势联动，一屏总览。',
    points: ['火点聚合与分级着色', '历史 / 预测双模式切换', '州市维度统计联动', 'EPSG:4326 空间基线'],
    visual: 'map',
  },
  {
    no: 'C2',
    icon: 'nodes',
    title: '多智能体协同',
    desc: '编排 Agent 拆解任务，数据 / GIS / 检索 / 报告 / 评审并行协作，过程全程可视。',
    points: ['七环节流水线编排（查询 ∥ 检索并行）', 'SSE 流式过程可视', '思考过程按轮次留存', '评审三态 + 人工闸口'],
    visual: 'mesh',
  },
]

/* 小能力 ×4（紧凑条目） */
const minors = [
  { icon: 'layers', title: '多源数据融合', desc: '卫星火点、气象与州市边界统一到 EPSG:4326 空间基准，历史序列与预测火险同屏可比。' },
  { icon: 'crosshair', title: '智能查询', desc: '自然语言问数：解析意图、查询数据、成图成表一步完成。' },
  { icon: 'layers', title: '知识库 RAG', desc: '防火制度文档向量检索问答，答案附引用溯源。' },
  { icon: 'file', title: '报告评审闭环', desc: '报告生成、质量评审、人工审批、归档发布，全程可追溯。' },
]

/* 场景（3 个真实使用场景，手动切换） */
const scenes = [
  {
    key: 'assess',
    label: '火险研判',
    title: '早班会前的全域火险研判',
    desc: '值班员输入一句自然语言任务，编排 Agent 拆解后联动数据与 GIS 智能体，几分钟内得到带地图结论的研判结果。',
    steps: ['下达研判任务', '数据与 GIS 并行分析', '风险分区结论上图'],
  },
  {
    key: 'brief',
    label: '值班简报',
    title: '每日值班简报自动成稿',
    desc: '报告 Agent 汇总当日火点与火险态势成文，评审 Agent 逐项核查，通过后经人工审批归档进入报告中心。',
    steps: ['自动汇总成文', '质量评审核查', '人工审批归档'],
  },
  {
    key: 'qa',
    label: '知识问答',
    title: '防火制度随问随答',
    desc: '对上传的防火预案与制度文档做向量检索，答案附引用来源，新到岗值班员也能快速上手。',
    steps: ['上传防火文档', '自然语言提问', '带引用的回答'],
  },
]
const activeScene = ref('assess')
/* 当前场景对象（单 pane 渲染 + :key 切换重播 scene-in，规避 v-for+v-show 同元素的更新异常） */
const curScene = computed(() => scenes.find((s) => s.key === activeScene.value) || scenes[0])
/* 滑动指示条：跟随当前 tab（JS 量位，200ms 过渡由 CSS 承担） */
const tabsRef = ref(null)
const ink = ref({ left: 0, width: 0 })
const syncInk = async () => {
  await nextTick()
  const cur = tabsRef.value?.querySelector('.scene__tab.is-active')
  if (cur) ink.value = { left: cur.offsetLeft, width: cur.offsetWidth }
}
const switchScene = (k) => {
  activeScene.value = k
  // URL hash 可分享（replaceState 不破坏历史栈）
  history.replaceState(null, '', `#scene=${k}`)
  syncInk()
}
onMounted(() => {
  const m = /#scene=(assess|brief|qa)/.exec(location.hash)
  if (m) activeScene.value = m[1]
  syncInk()
  window.addEventListener('resize', syncInk, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('resize', syncInk))

/* GIS 可视化：等高线 + 火点（确定性生成） */
const mapRing = (i) => {
  const n = 36
  let d = ''
  for (let k = 0; k < n; k++) {
    const a = (k / n) * Math.PI * 2
    const wob = 1 + 0.14 * Math.sin(a * 3 + i * 0.4) + 0.08 * Math.sin(a * 5 - i)
    const x = 180 + Math.cos(a) * i * 20 * wob
    const y = 80 + Math.sin(a) * i * 12.5 * wob
    d += `${k ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
  }
  return d + 'Z'
}
</script>

<template>
  <PubPage
    eyebrow="CAPABILITIES · 能力详解"
    title="从数据到报告，四层能力各司其职"
    lead="每一层能力都对应作战大屏与业务模块里的真实功能；本页按「2 大 + 4 小」拆到能力点粒度，口径与系统内一致。"
    :page-index="1"
  >
    <!-- 2 大能力 -->
    <section class="pg-sec">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">01</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">CORE · 主能力</p>
            <h2 class="pg-head__title pg-h2">两个主能力</h2>
            <p class="pg-head__lead pg-body">空间态势与智能体编排，是整条链路的两个支点。</p>
          </div>
          <span class="pg-head__meta">2 / 6</span>
        </div>
        <div class="majors" data-stagger>
          <article v-for="c in majors" :key="c.no" class="pg-card qt-spot major rv-item">
            <div class="major__bd">
              <div class="major__hd">
                <span class="cap__icon"><AppIcon :name="c.icon" :size="20" /></span>
                <div>
                  <p class="qt-eyebrow major__no">{{ c.no }}</p>
                  <h3 class="pg-h3">{{ c.title }}</h3>
                </div>
              </div>
              <p class="pg-body">{{ c.desc }}</p>
              <ul class="major__list">
                <li v-for="p in c.points" :key="p" class="qt-row pg-cap">{{ p }}</li>
              </ul>
            </div>
            <!-- 可视化：map = 等高线 + 火点；mesh = 智能体网格 -->
            <svg v-if="c.visual === 'map'" class="major__vis" viewBox="0 0 360 160" aria-hidden="true">
              <g fill="none" stroke-width="0.8">
                <path v-for="i in 6" :key="i" :d="mapRing(i)" stroke="var(--fs-hairline-strong)" :opacity="0.62 - i * 0.07" />
              </g>
              <circle cx="196" cy="74" r="4" fill="var(--fs-risk-4)" />
              <circle cx="252" cy="92" r="3" fill="var(--fs-risk-3)" />
              <circle cx="132" cy="96" r="3" fill="var(--fs-risk-2)" />
              <circle cx="210" cy="60" r="2.4" fill="var(--fs-risk-5)" />
            </svg>
            <svg v-else class="major__vis" viewBox="0 0 360 160" aria-hidden="true">
              <g stroke="var(--fs-hairline-strong)" stroke-width="0.8" fill="none">
                <path d="M70 80 L180 45 L290 80 L180 115 Z" opacity="0.7" />
                <path d="M70 80 L180 115 M180 45 L180 115 M290 80 L180 115" opacity="0.4" />
              </g>
              <g font-family="var(--fs-font-mono)" font-size="9" fill="var(--fs-ink-500)" text-anchor="middle">
                <circle cx="70" cy="80" r="5" fill="var(--fs-risk-1)" />
                <circle cx="180" cy="45" r="5" fill="var(--fs-risk-2)" />
                <circle cx="290" cy="80" r="5" fill="var(--fs-risk-3)" />
                <circle cx="180" cy="115" r="5" fill="var(--fs-accent)" />
                <text x="70" y="99">DATA</text>
                <text x="180" y="32">ORCH</text>
                <text x="290" y="99">GIS</text>
                <text x="180" y="134">REPORT</text>
              </g>
            </svg>
          </article>
        </div>
      </div>
    </section>

    <!-- 4 小能力 -->
    <section class="pg-sec">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">02</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">SUPPORT · 次能力</p>
            <h2 class="pg-head__title pg-h2">四个支撑能力</h2>
            <p class="pg-head__lead pg-body">数据、查询、知识、成文，把主能力喂饱并落到纸面。</p>
          </div>
          <span class="pg-head__meta">4 / 6</span>
        </div>
        <div class="minors" data-stagger>
          <article v-for="c in minors" :key="c.title" class="pg-card minor rv-item">
            <span class="cap__icon cap__icon--sm"><AppIcon :name="c.icon" :size="17" /></span>
            <div class="minor__bd">
              <h3 class="pg-h3">{{ c.title }}</h3>
              <p class="pg-cap">{{ c.desc }}</p>
            </div>
          </article>
        </div>
      </div>
    </section>

    <!-- 场景（tab 手动切换，160–220ms 过渡，不自动轮播） -->
    <section class="pg-sec pg-sec--sunken">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">03</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">SCENARIOS · 场景</p>
            <h2 class="pg-head__title pg-h2">三个真实使用场景</h2>
            <p class="pg-head__lead pg-body">从早班会研判到制度问答，覆盖值班日的三个高频时刻。</p>
          </div>
          <span class="pg-head__meta">MANUAL SWITCH</span>
        </div>
        <div class="scene pg-card">
          <div ref="tabsRef" class="scene__tabs" role="tablist" aria-label="使用场景">
            <button
              v-for="s in scenes"
              :key="s.key"
              type="button"
              role="tab"
              class="scene__tab qt-focus"
              :class="{ 'is-active': activeScene === s.key }"
              :aria-selected="activeScene === s.key"
              @click="switchScene(s.key)"
            >{{ s.label }}</button>
            <i class="scene__ink" aria-hidden="true" :style="{ transform: `translateX(${ink.left}px)`, width: `${ink.width}px` }"></i>
          </div>
          <div class="scene__body">
            <div :key="activeScene" class="scene__pane" role="tabpanel">
              <div class="scene__tx">
                <h3 class="pg-h3">{{ curScene.title }}</h3>
                <p class="pg-body">{{ curScene.desc }}</p>
              </div>
              <ol class="scene__steps">
                <li v-for="(st, i) in curScene.steps" :key="st">
                  <span class="qt-num scene__stepNo">{{ String(i + 1).padStart(2, '0') }}</span>
                  <span class="pg-cap">{{ st }}</span>
                </li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </section>
  </PubPage>
</template>

<style scoped>
.pg-sec--sunken { background: var(--fs-bg-sunken); }

.cap__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px; height: 42px;
  flex: none;
  color: var(--fs-accent);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md);
  background: var(--fs-bg-sunken);
}
.cap__icon--sm { width: 34px; height: 34px; }

/* ---- 2 大能力：左文右图编辑式卡 ---- */
.majors {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.major {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 24px;
  align-items: center;
}
.major__bd { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.major__hd { display: flex; align-items: center; gap: 14px; }
.major__no { margin: 0 0 2px; color: var(--fs-accent); }
.major__list { list-style: none; margin: 0; padding: 0; }
.major__vis { width: 100%; height: 160px; display: block; }

/* ---- 4 小能力：紧凑横向条目 ---- */
.minors {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.minor {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 20px;
}
.minor__bd { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.minor__bd .pg-cap { margin: 0; }

/* ---- 场景 tab ---- */
.scene { padding: 0; overflow: hidden; }
.scene__tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--fs-hairline);
}
.scene__tab {
  flex: none;
  padding: 14px 22px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fs-ink-500);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: color 0.18s var(--fs-ease), border-color 0.18s var(--fs-ease);
}
.scene__tab:hover { color: var(--fs-ink-900); }
.scene__tab.is-active { color: var(--fs-ink-900); }
/* 滑动指示条（JS 量位 + transform 滑动） */
.scene__tabs { position: relative; }
.scene__ink {
  position: absolute;
  left: 0;
  bottom: -1px;
  height: 2px;
  background: var(--fs-accent);
  transition: transform 0.2s var(--fs-ease), width 0.2s var(--fs-ease);
  pointer-events: none;
}
/* 主卡 hover：示意图线条点亮 + 点位脉冲（非整卡倾斜） */
.major__vis path, .major__vis circle { transition: stroke 0.25s var(--fs-ease), opacity 0.25s var(--fs-ease); }
.major:hover .major__vis path { stroke: var(--fs-accent); }
.major:hover .major__vis circle { animation: viz-pulse 1.6s var(--fs-ease) infinite; }
@keyframes viz-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
/* 小卡 hover：图标上浮 + 底部细线展开 */
.minor { position: relative; }
.minor::after {
  content: '';
  position: absolute;
  left: 20px;
  right: 20px;
  bottom: -1px;
  height: 1px;
  background: var(--fs-accent);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.25s var(--fs-ease);
}
.minor:hover::after, .minor:focus-within::after { transform: scaleX(1); }
.cap__icon--sm { transition: transform 0.25s var(--fs-ease), color 0.25s var(--fs-ease); }
.minor:hover .cap__icon--sm { transform: translateY(-2px); color: var(--fs-accent); }
.scene__pane {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 32px;
  padding: 28px;
  animation: scene-in 0.2s var(--fs-ease) both;
}
@keyframes scene-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.scene__tx { display: flex; flex-direction: column; gap: 12px; }
.scene__steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.scene__steps li { display: flex; align-items: baseline; gap: 12px; }
.scene__stepNo { font-size: 11px; letter-spacing: 0.12em; color: var(--fs-accent); }

@media (max-width: 900px) {
  .majors { grid-template-columns: 1fr; }
  .major { grid-template-columns: 1fr; }
  .major__vis { max-width: 320px; }
  .minors { grid-template-columns: 1fr; }
  .scene__pane { grid-template-columns: 1fr; gap: 20px; }
}
html[data-motion-allowed="false"] .scene__pane { animation: none; }
html[data-motion-allowed="false"] .major:hover .major__vis circle { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .scene__pane { animation: none; }
  html:not([data-motion="on"]) .major:hover .major__vis circle { animation: none; }
}
</style>
