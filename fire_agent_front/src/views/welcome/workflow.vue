<script setup>
/**
 * /welcome/workflow — 智能体与工作流（公开）
 *
 * 左侧粘性标题 + 右侧 7 步纵向轨道：滚动时当前步骤高亮，每步展示
 * Agent / 输入 / 输出 / 产物；连接线随滚动逐节点点亮；移动端折叠为纵向列表。
 * 七环节职责与评审三态均来自系统真实实现。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import AppIcon from '@/components/base/AppIcon.vue'
import PubPage from '@/components/welcome/PubPage.vue'
import { motionAllowed } from '@/composables/useMotionPreference'
import { usePubScrollPct } from '@/composables/usePubMotion'

/* 手风琴：同一时间只展开一项（默认展开当前高亮步之外的第 1 步） */
const openStep = ref('01')
const toggle = (no) => { openStep.value = openStep.value === no ? '' : no }
/* 左侧竖向滚动进度（usePubMotion 下发的全页滚动百分比） */
const pct = usePubScrollPct()

/* 七环节：label/agent 与 agent-center pipelineSteps 逐字一致；io 为真实职责描述 */
const steps = [
  { no: '01', label: '拆解任务', agent: 'Orchestrator', tone: 'is-r1',
    input: '自然语言任务', output: '结构化执行计划', artifact: '任务计划',
    desc: '编排 Agent 解析任务意图，为固定步骤生成描述（查询 / 空间分析 / 检索 / 成文）。' },
  { no: '02', label: '查询数据', agent: 'DataAgent', tone: 'is-r1',
    input: '执行计划', output: '火点与火险聚合数据', artifact: '州市维度统计',
    desc: '查询历史火点与预测火险，按州市聚合，为空间分析与成文提供数据。' },
  { no: '03', label: '分析 GIS', agent: 'GisAgent', tone: 'is-r2',
    input: '聚合数据', output: '空间分析结论', artifact: 'GIS 结论与图表素材',
    desc: '执行热点统计、行政区聚合与风险分布分析，产出图表素材。' },
  { no: '04', label: '检索知识', agent: 'RagAgent', tone: 'is-r2',
    input: '报告主题', output: '制度与经验依据', artifact: '引用片段集',
    desc: '对防火文档做向量检索，为报告补充依据；与查询数据并行执行，未命中时如实说明、不跳过。' },
  { no: '05', label: '生成报告', agent: 'ReportAgent', tone: 'is-r3',
    input: '数据 + 结论 + 依据', output: '报告草稿', artifact: '值班简报 / 专题报告',
    desc: '汇合数据、GIS 结论与检索依据后成文；思考按轮次落库，可展开回看。' },
  { no: '06', label: '质量评审', agent: 'Reviewer', tone: 'is-r4',
    input: '报告草稿', output: '评审结论（三态）', artifact: '问题清单 / 通过标记',
    desc: '逐项核查报告质量：通过、退回重写（最多 2 轮）、异常时降级转人工。' },
  { no: '07', label: '人工审核通过', agent: 'HITL', tone: 'is-r5',
    input: '评审后报告', output: '定稿与归档', artifact: '报告中心归档条目',
    desc: '审批闸口：值班员通过 / 编辑 / 驳回，定稿报告归档进入报告中心。' },
]

/* 评审三态（与 AgentPipeline 三态口径一致） */
const reviewStates = [
  { tone: 'is-ok', title: '评审通过 · 0 问题', desc: '未发现问题，报告直接进入人工审核闸口。' },
  { tone: 'is-warn', title: '退回重写 · 有问题', desc: '列出问题清单退回 ReportAgent，最多重写 2 轮，仍不通过转人工。' },
  { tone: 'is-mid', title: '评审降级 · 转人工', desc: '评审异常 / 超时 / 无有效输出时标记降级，直接转人工确认，不误判不阻塞。' },
]

/* 滚动高亮当前步骤：IO 监听轨道节点，进入视口中心带者获得 is-current */
const trackRef = ref(null)
let stepIO = null
onMounted(() => {
  if (!motionAllowed.value || !('IntersectionObserver' in window)) return
  const els = Array.from(trackRef.value?.querySelectorAll('.wf-step') ?? [])
  if (!els.length) return
  // 移动端横滑：中心带改为左右收缩（横画廊）；桌面纵轨：上下收缩
  const horiz = window.matchMedia('(max-width: 768px)').matches
  const rootMargin = horiz ? '0px -42% 0px -42%' : '-42% 0px -42% 0px'
  stepIO = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) en.target.classList.add('is-current')
      else en.target.classList.remove('is-current')
    })
  }, { root: horiz ? trackRef.value : trackRef.value?.closest('.wl'), rootMargin, threshold: 0 })
  els.forEach((el) => stepIO.observe(el))
})
onBeforeUnmount(() => { stepIO?.disconnect(); stepIO = null })
</script>

<template>
  <PubPage
    eyebrow="PIPELINE · 智能体与工作流"
    title="七个环节，一条可追溯的报告流水线"
    lead="从一句自然语言任务到一份定稿归档的报告：六个智能体分工协作，人在最后一步把关。口径与 Agent 中心流水线一致。"
    :page-index="2"
  >
    <!-- 左粘性标题 + 右 7 步纵向轨道 -->
    <section class="pg-sec">
      <div class="pg-wrap wf">
        <div class="wf__side">
          <div class="wf__sticky">
            <div class="pg-head pg-head--stack">
              <span class="pg-head__no">01</span>
              <div class="pg-head__main">
                <p class="pg-head__eyebrow">TRACK · 流水线</p>
                <h2 class="pg-head__title pg-h2">七个环节怎么走</h2>
                <p class="pg-head__lead pg-body">
                  每步标注负责的 Agent、输入与产出；滚动时当前步骤自动高亮，连接线与节点随进度点亮。
                </p>
              </div>
            </div>
            <div class="wf__legend pg-cap">
              <span class="qt-status is-r1"><i></i>编排 / 数据</span>
              <span class="qt-status is-r2"><i></i>分析 / 检索</span>
              <span class="qt-status is-r3"><i></i>成文</span>
              <span class="qt-status is-r4"><i></i>评审</span>
              <span class="qt-status is-r5"><i></i>人工闸口</span>
            </div>
            <!-- 竖向滚动进度线 -->
            <div class="wf__prog" aria-hidden="true"><i :style="{ transform: `scaleY(${pct})` }"></i></div>
          </div>
        </div>

        <ol ref="trackRef" class="wf__track mo-loop" data-stagger>
          <li v-for="s in steps" :key="s.no" class="wf-step rv-item">
            <i class="wf-step__dot" :class="s.tone" aria-hidden="true"></i>
            <!-- 手风琴卡：默认标题+Agent+摘要；点击/回车展开输入输出产物（单展开，240ms） -->
            <div
              class="pg-card wf-step__card qt-spot qt-bp"
              :class="{ 'is-open': openStep === s.no }"
              role="button"
              tabindex="0"
              :aria-expanded="openStep === s.no"
              @click="toggle(s.no)"
              @keyup.enter="toggle(s.no)"
            >
              <div class="wf-step__hd">
                <span class="wf-step__no qt-num">{{ s.no }}</span>
                <h3 class="pg-h3">{{ s.label }}</h3>
                <span class="wf-step__agent qt-num">{{ s.agent }}</span>
                <span class="wf-step__toggle qt-num" aria-hidden="true">{{ openStep === s.no ? '−' : '+' }}</span>
              </div>
              <p class="pg-body wf-step__desc">{{ s.desc }}</p>
              <div class="wf-step__drawer">
                <div class="wf-step__io">
                  <span class="pg-cap"><b>输入</b>{{ s.input }}</span>
                  <span class="pg-cap"><b>输出</b>{{ s.output }}</span>
                  <span class="pg-cap"><b>产物</b>{{ s.artifact }}</span>
                </div>
              </div>
            </div>
          </li>
        </ol>
      </div>
    </section>

    <!-- 评审三态 -->
    <section class="pg-sec pg-sec--sunken">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">02</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">REVIEW · 评审三态</p>
            <h2 class="pg-head__title pg-h2">质量评审的三种结局</h2>
            <p class="pg-head__lead pg-body">评审失败不会被误判为「未通过」：通过、退回、降级三态分离，报告流程永不失控。</p>
          </div>
          <span class="pg-head__meta">TRI-STATE</span>
        </div>
        <div class="review" data-stagger>
          <article v-for="r in reviewStates" :key="r.title" class="pg-card qt-spot review__card rv-item">
            <span class="qt-status" :class="r.tone"><i></i>{{ r.title }}</span>
            <p class="pg-body review__d">{{ r.desc }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- 过程可视 -->
    <section class="pg-sec qsec--last">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">03</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">OBSERVABILITY · 过程可视</p>
            <h2 class="pg-head__title pg-h2">过程全程可视</h2>
            <p class="pg-head__lead pg-body">任务过程不是黑盒：流式输出、逐轮回看、历史可检索。</p>
          </div>
          <span class="pg-head__meta">SSE / DETAIL FALLBACK</span>
        </div>
        <div class="observe" data-stagger>
          <div class="pg-card observe__item rv-item">
            <h3 class="pg-h3">SSE 流式输出</h3>
            <p class="pg-cap">节点思考与产出逐 token 推送，过程实时可见。</p>
          </div>
          <div class="pg-card observe__item rv-item">
            <h3 class="pg-h3">断线兜底</h3>
            <p class="pg-cap">SSE 断线自动回查任务详情兜底，状态不丢。</p>
          </div>
          <div class="pg-card observe__item rv-item">
            <h3 class="pg-h3">思考留存</h3>
            <p class="pg-cap">生成节点的思考按轮次落库，随时展开回看。</p>
          </div>
          <div class="pg-card observe__item rv-item">
            <h3 class="pg-h3">任务历史</h3>
            <p class="pg-cap">历史任务可检索、可重放，评审与审批记录同存。</p>
          </div>
        </div>
      </div>
    </section>
  </PubPage>
</template>

<style scoped>
.pg-sec--sunken { background: var(--fs-bg-sunken); }
.pg-head--stack {
  grid-template-columns: 56px 1fr;
  margin-bottom: 24px;
}

/* ---- 左粘性标题 + 右纵向轨道 ---- */
.wf {
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 64px;
  align-items: start;
}
.wf__sticky { position: sticky; top: 96px; }
.wf__legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 20px;
  border-top: 1px solid var(--fs-hairline);
}
/* 竖向滚动进度线（粘性列底部） */
.wf__prog {
  margin-top: 22px;
  width: 1px;
  height: 72px;
  background: var(--fs-hairline);
  overflow: hidden;
}
.wf__prog i {
  display: block;
  width: 100%;
  height: 100%;
  background: var(--fs-accent);
  transform: scaleY(0);
  transform-origin: top center;
  will-change: transform;
}

.wf__track {
  list-style: none;
  margin: 0;
  padding: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
/* 轨道连接线：蓝图虚线辅助线，缓慢向下流动（9px 周期无缝；mo-loop 三态降级） */
.wf__track::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 12px;
  bottom: 12px;
  width: 1px;
  background: repeating-linear-gradient(180deg, var(--fs-hairline-strong) 0 4px, transparent 4px 9px);
  animation: wf-track-flow 1.8s linear infinite;
}
@keyframes wf-track-flow {
  to { background-position-y: 9px; }
}
.wf-step {
  position: relative;
  padding-left: 28px;
}
.wf-step__dot {
  position: absolute;
  left: 0;
  top: 26px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid var(--fs-bg-canvas);
  box-shadow: 0 0 0 1px var(--fs-hairline-strong);
  background: var(--fs-ink-400);
}
.wf-step__dot.is-r1 { background: var(--fs-risk-1); }
.wf-step__dot.is-r2 { background: var(--fs-risk-2); }
.wf-step__dot.is-r3 { background: var(--fs-risk-3); }
.wf-step__dot.is-r4 { background: var(--fs-risk-4); }
.wf-step__dot.is-r5 { background: var(--fs-risk-5); }

.wf-step__card {
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition:
    border-color 0.3s var(--fs-ease),
    box-shadow 0.3s var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
/* 手风琴卡可点：hover 上浮 2px + 展开符放大，按下回位（与 .pg-card--lift 同参） */
.wf-step__card:hover { transform: translateY(-2px); }
.wf-step__card:active { transform: translateY(0); }
.wf-step:hover .wf-step__dot { transform: scale(1.25); }
.wf-step__dot { transition: box-shadow 0.3s var(--fs-ease), transform 0.3s var(--fs-ease); }
.wf-step.is-current .wf-step__card {
  border-color: rgba(var(--fs-accent-rgb), 0.45);
  box-shadow: 0 0 18px rgba(var(--fs-accent-rgb), 0.08);
}
/* 当前步骤的图纸十字标记点亮（蓝图标注语言） */
.wf-step.is-current .wf-step__card::before,
.wf-step.is-current .wf-step__card::after {
  opacity: 1;
  background:
    linear-gradient(var(--fs-accent), var(--fs-accent)) center / 1px 9px no-repeat,
    linear-gradient(var(--fs-accent), var(--fs-accent)) center / 9px 1px no-repeat;
}
.wf-step.is-current .wf-step__dot {
  box-shadow: 0 0 0 1px var(--fs-accent), 0 0 10px rgba(var(--fs-accent-rgb), 0.4);
}
.wf-step__hd { display: flex; align-items: baseline; gap: 12px; }
.wf-step__no { font-size: 11px; letter-spacing: 0.14em; color: var(--fs-accent); }
/* 当前步骤编号脉冲（滚动高亮语义；mo-loop 降级） */
.wf-step.is-current .wf-step__no { animation: wf-no-pulse 1.8s var(--fs-ease) infinite; }
@keyframes wf-no-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
.wf-step__toggle {
  margin-left: 10px;
  font-size: 13px;
  color: var(--fs-ink-400);
  transition: transform 0.24s var(--fs-ease), color 0.24s var(--fs-ease);
}
.wf-step__card { cursor: pointer; }
.wf-step__card:hover .wf-step__toggle { color: var(--fs-accent); transform: scale(1.2); }
.wf-step__card.is-open .wf-step__toggle { color: var(--fs-accent); }
/* 展开态：卡片提边 + 强调描边，让「哪一步是开着的」在长轨道里一眼可辨 */
.wf-step__card.is-open {
  border-color: rgba(var(--fs-accent-rgb), 0.4);
  box-shadow: 0 0 16px rgba(var(--fs-accent-rgb), 0.07);
}
.wf-step__card:focus-visible { outline: 2px solid var(--fs-accent); outline-offset: 2px; }
/* 手风琴抽屉：grid-rows 0fr→1fr 高度过渡（240ms） */
.wf-step__drawer {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.24s var(--fs-ease);
}
.wf-step__card.is-open .wf-step__drawer { grid-template-rows: 1fr; }
.wf-step__drawer > .wf-step__io { overflow: hidden; min-height: 0; }
.wf-step__io { border-top: none; padding-top: 0; margin-top: 0; }
.wf-step__card.is-open .wf-step__io { border-top: 1px solid var(--fs-hairline); padding-top: 12px; margin-top: 2px; }
.wf-step__agent {
  margin-left: auto;
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
}
.wf-step__desc { margin: 0; }
.wf-step__io {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
}
.wf-step__io b {
  font-weight: 600;
  color: var(--fs-ink-500);
  margin-right: 6px;
}

/* ---- 评审三态 ---- */
.review {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  align-items: stretch;
}
.review__card { display: flex; flex-direction: column; gap: 12px; }
.review__d { margin: 0; }
/* hover 底边强调线自左展开 + 状态标签提亮（与 .minor / .tech-col 同一语言） */
.review__card, .observe__item { position: relative; }
.review__card::before, .observe__item::before {
  content: '';
  position: absolute;
  left: 28px;
  right: 28px;
  bottom: -1px;
  height: 1px;
  background: var(--fs-accent);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.25s var(--fs-ease);
}
.review__card:hover::before, .observe__item:hover::before { transform: scaleX(1); }
.review__card:hover .qt-status { color: var(--fs-ink-900); }
.observe__item:hover .pg-cap { color: var(--fs-ink-700); }

/* ---- 过程可视 ---- */
.observe {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.observe__item { display: flex; flex-direction: column; gap: 8px; }
.observe__item .pg-cap { margin: 0; }

/* off（或 auto+系统减）：取消 hover 位移/缩放，只留颜色与描边反馈 */
html[data-motion-allowed="false"] .wf-step__card:hover,
html[data-motion-allowed="false"] .wf-step:hover .wf-step__dot,
html[data-motion-allowed="false"] .wf-step__card:hover .wf-step__toggle { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .wf-step__card:hover,
  html:not([data-motion="on"]) .wf-step:hover .wf-step__dot,
  html:not([data-motion="on"]) .wf-step__card:hover .wf-step__toggle { transform: none; }
}

@media (max-width: 900px) {
  .wf { grid-template-columns: 1fr; gap: 32px; }
  .wf__sticky { position: static; }
  .review, .observe { grid-template-columns: 1fr; }
}

/* 移动端轨道改横向画廊（horizontal-gallery 手法：snap 展线 + 留白即展墙） */
@media (max-width: 768px) {
  .wf__track {
    flex-direction: row;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    gap: 14px;
    padding: 6px 2px 14px;
    margin: 0 -2px;
    -webkit-overflow-scrolling: touch;
  }
  .wf__track::before { display: none; }
  .wf-step {
    flex: none;
    width: 80%;
    max-width: 320px;
    padding-left: 0;
    scroll-snap-align: start;
  }
  .wf-step__dot { display: none; }
  .wf-step__card { height: 100%; }
}
</style>
