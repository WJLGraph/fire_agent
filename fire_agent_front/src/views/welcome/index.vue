<script setup>
/**
 * 公开总览页 /welcome（站点根路径指向此处）
 *
 * 叙事顺序（每屏一个焦点）：Hero（主张 + 系统态势面板） → 01 现状痛点 →
 * 02 核心能力 → 03 协同工作流 → 04 可信度数据 → 05 六模块入口 → 结尾 CTA。
 *
 * 口径（硬性）：16 州市 · 5,411 历史火点 · 6 协作智能体 · 火险五级
 * （正常/注意/警告/高度/极度，与 utils/riskLevel.js LEVEL_INFO_MAP 一致）·
 * 七环节流水线 · 六模块。
 *
 * 动效（全部接 motionAllowed 三态）：
 *   - HeroGL WebGL 地形 + 指针热场（粒子已降密、只在地形底部）
 *   - 章节线条 scrub 绘制（usePubMotion）
 *   - 数字滚轮 DigitRoll（进入视口才滚）
 *   - 管线连接线逐段点亮（flowST）
 *   - HUD 经纬度读数（示意）
 *   - View Transitions 页面转场（router 层）
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { fetchSummary } from '@/api/dashboard'
import AppIcon from '@/components/base/AppIcon.vue'
import PubHeader from '@/components/welcome/PubHeader.vue'
import PubFooter from '@/components/welcome/PubFooter.vue'
import PubPager from '@/components/welcome/PubPager.vue'
import HeroGL from '@/components/welcome/HeroGL.vue'
import TerrainGL from '@/components/welcome/TerrainGL.vue'
import FlowField from '@/components/welcome/FlowField.vue'
import DigitRoll from '@/components/welcome/DigitRoll.vue'
import QtCursor from '@/components/welcome/QtCursor.vue'
import { usePubMotion } from '@/composables/usePubMotion'
import { useAuthStore } from '@/stores/auth'
import { motionAllowed, motionPref } from '@/composables/useMotionPreference'

gsap.registerPlugin(ScrollTrigger)

const auth = useAuthStore()
const rootRef = ref(null)
const heroRef = ref(null)
const glRef = ref(null)
const glWrapRef = ref(null)
const copyRef = ref(null)
const { scrollToId, scrollPct } = usePubMotion(rootRef)

const enterTarget = computed(() => (auth.isLoggedIn ? '/dashboard' : '/login'))
const enterLabel = computed(() => (auth.isLoggedIn ? '进入系统' : '进入指挥平台'))

/* ==================== 真实口径统计（/dashboard/summary，5s 超时降级） ==================== */
const SAFE_STATS = { cities: 16, fires: 5411, agents: 6 }
const statsTarget = ref({ ...SAFE_STATS })
const statNum = ref({ cities: 0, fires: 0, agents: 0 })
let statsReady = false
let statsInView = false
let statsAnimated = false

const formatNum = (v) => {
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? Math.round(n) : null
}
const prefersReduced = () => !motionAllowed.value
const sanitizedTargets = () => ({
  cities: formatNum(statsTarget.value.cities) ?? SAFE_STATS.cities,
  fires: formatNum(statsTarget.value.fires) ?? SAFE_STATS.fires,
  agents: formatNum(statsTarget.value.agents) ?? SAFE_STATS.agents,
})
const runStatsAnim = () => {
  if (statsAnimated) return
  statsAnimated = true
  /* DigitRoll 内部按位滚动；reduced/off 直显终值 */
  statNum.value = sanitizedTargets()
}

/* 渲染层格式化：数值 → 千分位文本（计数铁律：格式化只在渲染出口，不回流数值运算） */
const fmtStat = (n, fallback) => {
  const v = formatNum(n) ?? fallback
  return Number(v).toLocaleString('en-US')
}

/* ==================== 内容数据（真实口径） ==================== */
const agentNodes = ['Orchestrator', 'DataAgent', 'GisAgent', 'RagAgent', 'ReportAgent', 'Reviewer']

const riskLevels = [
  { cls: 'is-r1', label: '正常' },
  { cls: 'is-r2', label: '注意' },
  { cls: 'is-r3', label: '警告' },
  { cls: 'is-r4', label: '高度' },
  { cls: 'is-r5', label: '极度' },
]

const flowSteps = [
  { label: '拆解任务', agent: 'Orchestrator' },
  { label: '查询数据', agent: 'DataAgent' },
  { label: '分析 GIS', agent: 'GisAgent' },
  { label: '检索知识', agent: 'RagAgent' },
  { label: '生成报告', agent: 'ReportAgent' },
  { label: '质量评审', agent: 'Reviewer' },
  { label: '人工审核通过', agent: 'HITL', hitl: true },
]

/* 01 现状痛点（编辑式三条，mono 注记） */
const painPoints = [
  { no: 'P1', title: '火点数据分散', desc: '卫星火点、气象要素与地形数据分散在不同系统，值班时人工汇总耗时。', meta: 'DATA · 3 源' },
  { no: 'P2', title: '研判依赖经验', desc: '火险研判依赖人工读图与经验判断，夜间与高峰时段响应慢。', meta: 'OPS · 24h' },
  { no: 'P3', title: '报告链路断点多', desc: '简报撰写、核对、归档环节手工衔接，易出错、难追溯。', meta: 'PIPE · 7 节点' },
]

/* 02 核心能力（详解见 /welcome/features） */
const capabilities = [
  { icon: 'layers', title: '多源数据融合', desc: '卫星火点、气象要素与地形数据统一时空基线，历史序列与预测火险同屏可比。' },
  { icon: 'map', title: 'GIS 作战大屏', desc: '二三维一体化地图，火点聚合、风险分级与趋势联动，态势一屏总览。' },
  { icon: 'nodes', title: '多智能体协同', desc: '编排 Agent 拆解任务，数据 / GIS / 检索 / 报告 Agent 并行协作，过程全程可视。' },
  { icon: 'file', title: '报告评审闭环', desc: '报告自动生成、质量评审、人工审批定稿归档，每一份报告可追溯。' },
]

/* 05 六大功能入口（来自 router/navItems.js 的六个真实模块，统一导向登录页） */
const moduleEntries = [
  { path: '/login', icon: 'map', label: '作战大屏', desc: '火点态势一屏总览，二三维地图联动研判。' },
  { path: '/login', icon: 'crosshair', label: '智能查询', desc: '自然语言问数，解析、查询、成图一步完成。' },
  { path: '/login', icon: 'layers', label: '知识库', desc: '防火文档 RAG 问答，答案附引用溯源。' },
  { path: '/login', icon: 'nodes', label: 'Agent 中心', desc: '多智能体任务编排、流式过程与审批闸口。' },
  { path: '/login', icon: 'file', label: '报告中心', desc: '值班简报与专题报告的生成、评审与归档。' },
  { path: '/login', icon: 'sliders', label: '系统管理', desc: '用户、数据源、模型与日志的集中管控。' },
]

/* 态势面板等高线小视觉：确定性生成（刷新一致，无动画） */
const mapRing = (i) => {
  const n = 40
  let d = ''
  for (let k = 0; k < n; k++) {
    const a = (k / n) * Math.PI * 2
    const wob = 1 + 0.13 * Math.sin(a * 3 + i * 0.4) + 0.07 * Math.sin(a * 5 - i)
    const x = 186 + Math.cos(a) * i * 22 * wob
    const y = 76 + Math.sin(a) * i * 13 * wob
    d += `${k ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
  }
  return d + 'Z'
}

/* ==================== 右侧章节导轨（滚动定位 + 一键跳章） ====================
   长滚动页缺少「我在哪一章」的坐标感：右侧 6 个 mono 序号即当前章节读数，
   悬停/命中时向左展开章节名（名称为页内既有小节标题，非新增文案口径）。
   激活判定用纯滚动位置比较（Lenis 与原生滚动都会更新 wrapper.scrollTop），
   动效 off 时依旧可用；导轨本身 fade-in 属于淡入，不做位移。 */
const railSections = [
  { id: 'terrain', no: '00', label: '全域地形' },
  { id: 'problem', no: '01', label: '现状痛点' },
  { id: 'capabilities', no: '02', label: '核心能力' },
  { id: 'pipeline', no: '03', label: '协同工作流' },
  { id: 'data', no: '04', label: '平台数据' },
  { id: 'modules', no: '05', label: '功能入口' },
]
const activeSection = ref('')
const railVisible = ref(false)
const railPct = computed(() => `${String(Math.min(100, Math.round((scrollPct.value || 0) * 100))).padStart(3, '0')}%`)

const onScrollSpy = () => {
  const root = rootRef.value
  if (!root) return
  const line = root.scrollTop + root.clientHeight * 0.4
  let cur = ''
  for (const s of railSections) {
    const el = document.getElementById(s.id)
    if (el && el.offsetTop <= line) cur = s.id
  }
  activeSection.value = cur
  /* 首屏（Hero）不显示导轨：出屏后才浮出，避免与 hero HUD 读数打架 */
  railVisible.value = root.scrollTop > root.clientHeight * 0.5
}

/* ==================== 滚动编排（hero：WebGL 推进 + 轻视差；管线：逐段点亮） ==================== */
let heroST = null
let statsObserver = null

const flowRef = ref(null)
let flowST = null
let terrainST = null
const terrRef = ref(null)
const terrainGLRef = ref(null)
let flowStepEls = []

/* ==================== Hero 技术读数 HUD（经纬度示意，随指针映射 + 0.15s 阻尼） ==================== */
const hudRef = ref(null)
const hudText = ref('VIEW · 25.04°N 102.71°E · 示意')
const HUD_CENTER = { lat: 25.04, lon: 102.71 }
const HUD_LAT = { min: 21.1, max: 29.3 }
const HUD_LON = { min: 97.5, max: 106.2 }
let hudCur = { ...HUD_CENTER }
let hudTarget = { ...HUD_CENTER }
let hudRaf = 0
const finePointer = window.matchMedia && window.matchMedia('(pointer: fine)').matches
const hudVisible = computed(() => motionAllowed.value && finePointer)

const hudTick = () => {
  hudCur.lat += (hudTarget.lat - hudCur.lat) * 0.15
  hudCur.lon += (hudTarget.lon - hudCur.lon) * 0.15
  hudText.value = `VIEW · ${hudCur.lat.toFixed(2)}°N ${hudCur.lon.toFixed(2)}°E · 示意`
  hudRaf = requestAnimationFrame(hudTick)
}
const onHeroPointerMove = (e) => {
  if (e.pointerType === 'touch') return
  const r = heroRef.value?.getBoundingClientRect()
  if (!r || !r.width || !r.height) return
  const px = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
  const py = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))
  hudTarget.lon = HUD_LON.min + px * (HUD_LON.max - HUD_LON.min)
  hudTarget.lat = HUD_LAT.max - py * (HUD_LAT.max - HUD_LAT.min)
}
const onHeroPointerLeave = () => { hudTarget = { ...HUD_CENTER } }

/** Hero 滚动联动：仅 WebGL 相机/热场推进 + 左栏 ≤10px 轻视差，文字不淡出不换位 */
const applyHeroStage = (p) => {
  glRef.value?.setProgress(p)
  if (!copyRef.value || !glWrapRef.value) return
  copyRef.value.style.transform = `translate3d(0, ${(-p * 10).toFixed(1)}px, 0)`
  glWrapRef.value.style.transform = `translate3d(0, ${(p * 6).toFixed(1)}px, 0)`
  glWrapRef.value.style.opacity = (1 - p * 0.18).toFixed(3)
}

onMounted(async () => {
  rootRef.value?.addEventListener('scroll', onScrollSpy, { passive: true })
  onScrollSpy()

  if (import.meta.env.DEV) {
    console.info('[welcome-motion]', {
      pref: motionPref.value,
      allowed: motionAllowed.value,
      reduced: !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches),
      pointerFine: !!(window.matchMedia && window.matchMedia('(pointer: fine)').matches),
      webgl: !!document.createElement('canvas').getContext('webgl'),
      viewTransition: typeof document.startViewTransition === 'function',
    })
  }

  try {
    const timeout = new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 5000))
    const data = await Promise.race([fetchSummary(), timeout])
    statsTarget.value = {
      cities: formatNum(data?.city_count) ?? SAFE_STATS.cities,
      fires: formatNum(data?.total_fire_points) ?? SAFE_STATS.fires,
      agents: formatNum(data?.agent_count) ?? SAFE_STATS.agents,
    }
  } catch {
    /* 静默降级：保持真实默认口径 */
  } finally {
    statsReady = true
    if (statsReady && statsInView) runStatsAnim()
  }

  const band = rootRef.value?.querySelector('[data-stats-band]')
  if (!band || !('IntersectionObserver' in window)) {
    statsInView = true
    if (statsReady) runStatsAnim()
  } else {
    statsObserver = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return
        statsInView = true
        if (statsReady) runStatsAnim()
        statsObserver?.disconnect()
      })
    }, { threshold: 0.4 })
    statsObserver.observe(band)
  }

  const desktop = window.matchMedia('(min-width: 1025px)').matches
  if (!prefersReduced() && desktop && heroRef.value) {
    heroST = ScrollTrigger.create({
      trigger: heroRef.value,
      scroller: rootRef.value,
      start: 'top top',
      end: 'bottom top',
      scrub: true,
      onUpdate: (self) => applyHeroStage(self.progress),
    })
    applyHeroStage(0)

    if (flowRef.value) {
      flowStepEls = Array.from(flowRef.value.querySelectorAll('.flow__step'))
      flowST = ScrollTrigger.create({
        trigger: flowRef.value,
        scroller: rootRef.value,
        start: 'top 85%',
        end: 'top 35%',
        scrub: 0.4,
        onUpdate: (self) => {
          const p = self.progress * (flowStepEls.length - 1)
          flowStepEls.forEach((s, i) => {
            if (i < flowStepEls.length - 1) {
              s.style.setProperty('--seg', Math.max(0, Math.min(1, p - i)).toFixed(3))
            }
            s.classList.toggle('is-lit', p >= i)
          })
        },
      })
    }

    heroRef.value.addEventListener('pointermove', onHeroPointerMove, { passive: true })
    heroRef.value.addEventListener('pointerleave', onHeroPointerLeave, { passive: true })
    hudRaf = requestAnimationFrame(hudTick)
  }

  // 地形场景滚动推进（独立小节：进入视口到底部离开驱动相机轻微推近）
  if (!prefersReduced() && terrRef.value) {
    terrainST = ScrollTrigger.create({
      trigger: terrRef.value,
      scroller: rootRef.value,
      start: 'top bottom',
      end: 'bottom top',
      scrub: 0.4,
      onUpdate: (self) => terrainGLRef.value?.setProgress?.(self.progress),
    })
  }
})

onBeforeUnmount(() => {
  rootRef.value?.removeEventListener('scroll', onScrollSpy)
  heroST?.kill()
  heroST = null
  flowST?.kill()
  flowST = null
  terrainST?.kill()
  terrainST = null
  flowStepEls.forEach((s) => { s.style.removeProperty('--seg'); s.classList.remove('is-lit') })
  flowStepEls = []
  if (hudRaf) { cancelAnimationFrame(hudRaf); hudRaf = 0 }
  heroRef.value?.removeEventListener('pointermove', onHeroPointerMove)
  heroRef.value?.removeEventListener('pointerleave', onHeroPointerLeave)
  statsObserver?.disconnect()
  statsObserver = null
})
</script>

<template>
  <div ref="rootRef" class="wl">
    <div class="grain" aria-hidden="true"></div>
    <div class="wl-content">
      <div class="wl-progress" aria-hidden="true"><i data-progress class="wl-progress__bar"></i></div>

      <PubHeader :show-back="false" />
      <QtCursor />

      <main>
        <!-- ==================== Hero：左主张 + 右系统态势面板 ==================== -->
        <section ref="heroRef" class="hero">
          <div ref="glWrapRef" class="hero__gl">
            <HeroGL ref="glRef" fallback-label="CONTOUR FIELD · STATIC" />
          </div>

          <!-- 持续动效：等高线漂移层（11s 循环，幅度 ≤2%，不盖字；off 静止） -->
          <svg class="hero__drift mo-loop" viewBox="0 0 600 480" aria-hidden="true">
            <g fill="none" stroke="var(--fs-ink-400)" stroke-width="0.8">
              <ellipse cx="240" cy="250" rx="210" ry="150" opacity="0.16" />
              <ellipse cx="260" cy="240" rx="150" ry="106" opacity="0.2" />
              <ellipse cx="250" cy="255" rx="92" ry="66" opacity="0.24" />
              <path d="M60 380 Q 180 340 300 372 T 540 356" opacity="0.2" />
            </g>
          </svg>

          <div class="pg-wrap hero__inner">
            <div ref="copyRef" class="hero__copy">
              <p class="qt-eyebrow hero__eyebrow rv">SITUATION OVERVIEW · YUNNAN WILDFIRE COMMAND</p>
              <h1 class="pg-display hero__claim rv" data-rv-delay="0.06">
                在火情发生之前，<br />把<span class="hero__metal">风险</span>看清楚。
              </h1>
              <p class="pg-body hero__desc rv" data-rv-delay="0.12">
                融合卫星火点、气象要素与行政区划边界数据，由多智能体协同完成火险研判、值班简报与归档发布的全链路闭环。
              </p>
              <div class="hero__acts rv" data-rv-delay="0.18">
                <router-link class="btn btn--primary magnetic qt-focus" :to="enterTarget" data-no-vt>
                  {{ enterLabel }}
                  <AppIcon name="chevron-right" :size="15" />
                </router-link>
                <router-link class="btn btn--ghost qt-focus" to="/welcome/features" data-no-vt>了解核心能力</router-link>
              </div>
              <div class="hero__ctx rv" data-rv-delay="0.24">
                <span class="qt-status"><i></i>SUMMARY · 摘要口径</span>
                <span class="qt-status"><i></i>EPSG:4326 · WGS84</span>
              </div>
            </div>

            <!-- 系统态势面板：五级刻度 + 核心数字 + 等高线小视觉（4.6s 扫描高光） -->
            <aside class="sit pg-card qt-corner rv-item" data-rv-delay="0.12" aria-label="系统态势">
              <i class="sit__scan mo-loop" aria-hidden="true"></i>
              <div class="sit__hd">
                <span class="qt-eyebrow">SITUATION · 系统态势</span>
                <span class="qt-status is-r4"><i></i>五级语义</span>
              </div>
              <div class="sit__levels">
                <span v-for="r in riskLevels" :key="r.cls" class="sit__chip" :class="r.cls">{{ r.label }}</span>
              </div>
              <div class="sit__nums">
                <div class="sit__num"><b class="qt-num">16</b><span>州市覆盖</span></div>
                <div class="sit__num"><b class="qt-num">5,411</b><span>历史火点</span></div>
                <div class="sit__num"><b class="qt-num">6</b><span>协作智能体</span></div>
              </div>
              <!-- 等高线小视觉（SVG，确定性生成，无动画） -->
              <svg class="sit__map" viewBox="0 0 360 150" aria-hidden="true">
                <g fill="none" stroke-width="0.8">
                  <path v-for="i in 7" :key="i" :d="mapRing(i)" stroke="var(--fs-hairline-strong)" :opacity="0.6 - i * 0.06" />
                </g>
                <circle cx="186" cy="70" r="3.5" fill="var(--fs-risk-4)" />
                <circle cx="246" cy="92" r="2.5" fill="var(--fs-risk-3)" />
                <circle cx="126" cy="98" r="2.5" fill="var(--fs-risk-2)" />
              </svg>
              <p class="sit__note pg-cap">火险五级与作战大屏图例同口径 · 口径数据非实时监测</p>
            </aside>
          </div>

          <span class="hero__scrollhint qt-eyebrow" aria-hidden="true">SCROLL</span>
          <i class="hero__scrollrail" aria-hidden="true"><i class="mo-loop"></i></i>
          <span v-show="hudVisible" ref="hudRef" class="hero__hud qt-eyebrow" aria-hidden="true">{{ hudText }}</span>
        </section>

        <!-- ==================== 云南火险地形（深色仪表带：WebGL 为底 + 左侧读数 + 右侧图例） ==================== -->
        <section ref="terrRef" class="pg-sec terr pg-band" id="terrain" aria-label="云南火险地形态势">
          <div class="pg-wrap">
            <div class="pg-head">
              <span class="pg-head__no">00</span>
              <div class="pg-head__main">
                <p class="pg-head__eyebrow">TERRAIN · 全域地形</p>
                <h2 class="pg-head__title pg-h2">一张会呼吸的云南地形</h2>
                <p class="pg-head__lead pg-body">16 个州市真实行政边界挤出成图，点位光柱按火险五级语义着色；滚动推进、指针移入可见局部视差。</p>
              </div>
              <span class="pg-head__meta">16 PREFECTURES</span>
            </div>
            <div class="terr__grid">
              <div class="terr__readouts rv" data-rv-delay="0.05">
                <div class="terr__ro"><b class="qt-num">{{ fmtStat(statNum.cities, SAFE_STATS.cities) }}</b><span class="pg-cap">州市覆盖</span></div>
                <div class="terr__ro"><b class="qt-num">{{ fmtStat(statNum.fires, SAFE_STATS.fires) }}</b><span class="pg-cap">历史火点</span></div>
                <div class="terr__ro"><b class="qt-num">{{ fmtStat(statNum.agents, SAFE_STATS.agents) }}</b><span class="pg-cap">协作智能体</span></div>
              </div>
              <div class="terr__stage rv" data-rv-delay="0.12">
                <TerrainGL ref="terrainGLRef" />
              </div>
            </div>
            <div class="terr__foot">
              <span class="qt-status is-r1"><i></i>正常</span>
              <span class="qt-status is-r2"><i></i>注意</span>
              <span class="qt-status is-r3"><i></i>警告</span>
              <span class="qt-status is-r4"><i></i>高度</span>
              <span class="qt-status is-r5"><i></i>极度</span>
              <span class="terr__note pg-cap">点位等级为五级语义示意 · 口径数据非实时监测 · 边界与作战大屏同源</span>
            </div>
          </div>
        </section>

        <!-- ==================== 01 现状痛点 ==================== -->
        <section class="pg-sec" id="problem">
          <div class="pg-wrap">
            <div class="pg-head">
              <span class="pg-head__no">01</span>
              <div class="pg-head__main">
                <p class="pg-head__eyebrow">PROBLEM · 现状</p>
                <h2 class="pg-head__title pg-h2">火险值班的三处断点</h2>
                <p class="pg-head__lead pg-body">数据分散、研判靠经验、报告手工衔接——焰哨把这三段接成一条自动化链路。</p>
              </div>
              <span class="pg-head__meta">YUNNAN · FOREST FIRE DUTY</span>
            </div>
            <div class="pains" data-stagger>
              <article v-for="p in painPoints" :key="p.no" class="pg-card pain rv-item">
                <div class="pain__top">
                  <span class="pain__no qt-num">{{ p.no }}</span>
                  <span class="pain__meta qt-eyebrow">{{ p.meta }}</span>
                </div>
                <h3 class="pg-h3">{{ p.title }}</h3>
                <p class="pg-body">{{ p.desc }}</p>
              </article>
            </div>
          </div>
        </section>

        <!-- ==================== 02 核心能力 ==================== -->
        <section class="pg-sec" id="capabilities">
          <div class="pg-wrap">
            <div class="pg-head">
              <span class="pg-head__no">02</span>
              <div class="pg-head__main">
                <p class="pg-head__eyebrow">CAPABILITIES · 能力</p>
                <h2 class="pg-head__title pg-h2">核心能力</h2>
                <p class="pg-head__lead pg-body">四层能力各司其职：数据、空间、智能体、报告，覆盖研判到成文。</p>
              </div>
              <router-link class="pg-head__meta pg-link qt-focus" to="/welcome/features">能力详解 →</router-link>
            </div>
            <div class="caps" data-stagger>
              <article v-for="c in capabilities" :key="c.title" class="pg-card qt-spot cap rv-item">
                <span class="cap__icon"><AppIcon :name="c.icon" :size="20" /></span>
                <h3 class="pg-h3">{{ c.title }}</h3>
                <p class="pg-body">{{ c.desc }}</p>
              </article>
            </div>
          </div>
        </section>

        <!-- ==================== 03 协同工作流 ==================== -->
        <section class="pg-sec pg-sec--sunken" id="pipeline">
          <div class="pg-wrap">
            <div class="pg-head">
              <span class="pg-head__no">03</span>
              <div class="pg-head__main">
                <p class="pg-head__eyebrow">PIPELINE · 工作流</p>
                <h2 class="pg-head__title pg-h2">协同工作流</h2>
                <p class="pg-head__lead pg-body">七个环节一条可追溯的报告流水线；连接线随滚动逐段点亮。</p>
              </div>
              <router-link class="pg-head__meta pg-link qt-focus" to="/welcome/workflow">工作流详解 →</router-link>
            </div>
            <ol class="flow" data-stagger ref="flowRef">
              <li
                v-for="(s, i) in flowSteps"
                :key="s.agent"
                class="flow__step pg-card rv-item"
                :class="{ 'is-hitl': s.hitl }"
              >
                <span class="flow__idx qt-num">{{ String(i + 1).padStart(2, '0') }}</span>
                <span class="flow__label">{{ s.label }}</span>
                <span class="flow__agent qt-num">{{ s.agent }}</span>
              </li>
            </ol>
            <p class="flow__note pg-cap">注：查询数据与知识检索并行执行，汇合后进入成文；口径与 Agent 中心流水线一致。</p>
          </div>
        </section>

        <!-- ==================== 04 可信度数据（深色仪表带，滚轮计数 + 刻度呼吸） ==================== -->
        <section class="pg-sec stats pg-band" id="data" data-stats-band aria-label="平台数据">
          <div class="pg-wrap stats__grid">
            <div class="stat rv" data-rv-delay="0">
              <div class="stat__v"><DigitRoll :value="statNum.cities" :fallback="SAFE_STATS.cities" label="覆盖州市 16" /></div>
              <div class="stat__k">覆盖州市</div>
              <div class="stat__d pg-cap">云南省 16 个州市全域网格</div>
              <div class="stat__ticks mo-loop" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
            </div>
            <div class="stat rv" data-rv-delay="0.08">
              <div class="stat__v"><DigitRoll :value="statNum.fires" :fallback="SAFE_STATS.fires" label="历史火点 5,411" /></div>
              <div class="stat__k">历史火点</div>
              <div class="stat__d pg-cap">MODIS 卫星火点 · 2021–2025 归集</div>
              <div class="stat__ticks mo-loop" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
            </div>
            <div class="stat rv" data-rv-delay="0.16">
              <div class="stat__v"><DigitRoll :value="statNum.agents" :fallback="SAFE_STATS.agents" label="协作智能体 6" /></div>
              <div class="stat__k">协作智能体</div>
              <div class="stat__d pg-cap">编排 · 数据 · GIS · 检索 · 报告 · 评审</div>
              <div class="stat__ticks mo-loop" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
            </div>
          </div>
          <!-- data-dense 纪律：读数带附 mono 来源脚注，口径可溯源 -->
          <p class="stats__src pg-cap">SOURCE · 作战大屏 SUMMARY 接口 · 接口异常时降级为本地口径兜底</p>
        </section>

        <!-- ==================== 05 六大功能入口 ==================== -->
        <section id="modules" class="pg-sec">
          <div class="pg-wrap">
            <div class="pg-head">
              <span class="pg-head__no">05</span>
              <div class="pg-head__main">
                <p class="pg-head__eyebrow">MODULES · 入口</p>
                <h2 class="pg-head__title pg-h2">六大功能入口</h2>
                <p class="pg-head__lead pg-body">六个模块覆盖监测、研判、生产与管控全链路；登录后按角色进入对应模块。</p>
              </div>
              <span class="pg-head__meta">ROLE-BASED ACCESS</span>
            </div>
            <div class="mods" data-stagger>
              <router-link v-for="m in moduleEntries" :key="m.label" :to="m.path" class="pg-card pg-card--lift qt-spot mod rv-item">
                <span class="mod__hd">
                  <span class="mod__icon"><AppIcon :name="m.icon" :size="20" /></span>
                  <span class="mod__label">{{ m.label }}</span>
                </span>
                <span class="mod__desc pg-body">{{ m.desc }}</span>
                <span class="mod__foot">
                  <em>登录进入</em>
                  <AppIcon name="chevron-right" :size="14" class="mod__arr" />
                </span>
              </router-link>
            </div>
          </div>
        </section>

        <!-- ==================== 结尾 CTA（深色带 + 低对比流场，不干扰文字） ==================== -->
        <section class="final pg-band">
          <FlowField class="final__bg" />
          <div class="pg-wrap final__inner">
            <i class="final__line" aria-hidden="true"></i>
            <h2 class="pg-h2 final__claim rv">现在就开始，把<span class="hero__metal">风险</span>看清楚。</h2>
            <div class="rv" data-rv-delay="0.1">
              <router-link class="btn btn--primary btn--lg magnetic qt-focus" :to="enterTarget" data-no-vt>
                {{ enterLabel }}
                <AppIcon name="chevron-right" :size="15" />
              </router-link>
            </div>
          </div>
        </section>
      </main>

      <!-- 右侧章节导轨：mono 序号 = 当前章节坐标，悬停向左展开章名并跳转 -->
      <nav class="srail" :class="{ 'is-on': railVisible }" aria-label="页面章节导航">
        <button
          v-for="s in railSections"
          :key="s.id"
          type="button"
          class="srail__item qt-focus"
          :class="{ 'is-on': activeSection === s.id }"
          :aria-current="activeSection === s.id ? 'location' : undefined"
          :aria-label="`跳转到第 ${s.no} 章：${s.label}`"
          @click="scrollToId(s.id)"
        >
          <span class="srail__lb">{{ s.label }}</span>
          <span class="srail__no qt-num">{{ s.no }}</span>
          <i class="srail__tick" aria-hidden="true"></i>
        </button>
        <span class="srail__pct qt-num" aria-hidden="true">{{ railPct }}</span>
      </nav>

      <PubPager :index="0" />
      <PubFooter />
    </div>
  </div>
</template>

<style scoped>
/* ==================== 页面骨架：自建滚动容器（Lenis wrapper） ==================== */
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

/* ==================== CTA 按钮 ==================== */
.btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 42px;
  padding: 0 22px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-decoration: none;
  border-radius: var(--fs-r-md);
  cursor: pointer;
  transition:
    background var(--fs-dur-micro) var(--fs-ease),
    border-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform 0.1s var(--fs-ease),
    filter 0.1s var(--fs-ease);
}
.btn--primary {
  overflow: hidden;
  color: var(--fs-on-accent);
  background: var(--fs-accent);
  border: 1px solid transparent;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e2);
}
.btn--primary::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(120px circle at var(--mx, 50%) var(--my, 50%), rgba(255, 255, 255, 0.22), transparent 65%);
  opacity: 0;
  transition: opacity var(--fs-dur-micro) var(--fs-ease);
  pointer-events: none;
}
.btn--primary:hover { background: var(--fs-accent-hover); }
.btn--primary:hover::after { opacity: 1; }
.btn--primary:active { transform: translateY(1px) scale(0.985); filter: brightness(0.9); }
.btn--ghost {
  color: var(--fs-ink-700);
  background: transparent;
  border: 1px solid var(--fs-hairline-strong);
}
.btn--ghost:hover {
  color: var(--fs-ink-900);
  border-color: var(--fs-ink-400);
  background: rgba(var(--fs-ink-900-rgb), 0.03);
}
.btn--ghost:active { transform: translateY(1px) scale(0.985); filter: brightness(0.94); }
.btn--lg { height: 48px; padding: 0 28px; font-size: 14px; }

.pg-link { text-decoration: none; color: var(--fs-accent); transition: color var(--fs-dur-micro) var(--fs-ease); }
.pg-link:hover { color: var(--fs-accent-hover); }

/* ==================== Hero ==================== */
.hero {
  position: relative;
  padding-top: 64px;
  overflow: hidden;
}
.hero__gl { position: absolute; inset: 0; will-change: transform, opacity; }
/* 等高线漂移层：11s 循环，幅度 ≤2%，z 序在 WebGL 之上、文案之下 */
.hero__drift {
  position: absolute;
  left: -4%;
  top: 10%;
  width: 54%;
  height: 76%;
  z-index: 1;
  pointer-events: none;
  animation: hero-drift 11s ease-in-out infinite alternate;
}
@keyframes hero-drift {
  from { transform: translate3d(0, -1%, 0); }
  to { transform: translate3d(1.6%, 1%, 0); }
}
.hero__inner {
  position: relative;
  z-index: 2;
  min-height: calc(100vh - 64px);
  display: flex;
  align-items: center;
  gap: 64px;
  padding: 56px 0 72px;
}
.hero__copy {
  width: 52%;
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.hero__eyebrow { margin: 0; }
.hero__claim { margin: 0; text-wrap: pretty; }
.hero__metal {
  background: linear-gradient(115deg, var(--fs-accent) 0%, var(--fs-risk-high) 55%, var(--fs-risk-mid) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
.hero__desc { margin: 0; max-width: 480px; text-wrap: pretty; }
.hero__acts { display: flex; flex-wrap: wrap; gap: 12px; }
.hero__ctx { display: flex; flex-wrap: wrap; gap: var(--fs-s4); }

/* 系统态势面板 */
.sit {
  margin-left: auto;
  width: min(420px, 40%);
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 28px 28px 24px;
  overflow: hidden;
}
/* 4.6s 一次低对比扫描高光（双主题：ink-900-rgb 浅色主题为深色纹、深色主题为浅纹） */
.sit__scan {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 32%, rgba(var(--fs-ink-900-rgb), 0.05) 46%, rgba(var(--fs-ink-900-rgb), 0.09) 50%, rgba(var(--fs-ink-900-rgb), 0.05) 54%, transparent 68%);
  transform: translateX(-160%);
  animation: sit-scan 4.6s var(--fs-ease) infinite;
}
@keyframes sit-scan {
  0% { transform: translateX(-160%); }
  26% { transform: translateX(160%); }
  100% { transform: translateX(160%); }
}
.sit__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.sit__levels { display: flex; flex-wrap: wrap; gap: 8px; }
.sit__chip {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--fs-r-sm);
  color: var(--fs-on-accent);
}
.sit__chip.is-r1 { background: var(--fs-risk-1); }
.sit__chip.is-r2 { background: var(--fs-risk-2); }
.sit__chip.is-r3 { background: var(--fs-risk-3); }
.sit__chip.is-r4 { background: var(--fs-risk-4); }
.sit__chip.is-r5 { background: var(--fs-risk-5); }
.sit__nums {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--fs-hairline);
  border-bottom: 1px solid var(--fs-hairline);
  padding: 16px 0;
}
.sit__num { display: flex; flex-direction: column; gap: 4px; }
.sit__num + .sit__num { border-left: 1px solid var(--fs-hairline); padding-left: 16px; }
.sit__num b { font-size: 22px; font-weight: 600; color: var(--fs-ink-900); }
.sit__num span { font-size: 11px; letter-spacing: 0.05em; color: var(--fs-ink-500); }
.sit__map { width: 100%; height: 110px; display: block; }
.sit__note { margin: 0; }

.hero__scrollhint {
  position: absolute;
  left: 18px;
  bottom: 18px;
  z-index: 3;
  writing-mode: vertical-rl;
  opacity: 0.7;
}
/* SCROLL 旁的坐标尺：1px 轨道 + 16px 高光条自上而下循环扫过（mo-loop 三态降级） */
.hero__scrollrail {
  position: absolute;
  left: 30px;
  bottom: 18px;
  z-index: 3;
  width: 1px;
  height: 52px;
  overflow: hidden;
  background: var(--fs-hairline-strong);
  pointer-events: none;
}
.hero__scrollrail i {
  display: block;
  width: 1px;
  height: 16px;
  background: var(--fs-accent);
  animation: hero-scroll-run 2.4s var(--fs-ease) infinite;
}
@keyframes hero-scroll-run {
  from { transform: translateY(-16px); }
  to { transform: translateY(52px); }
}
.hero__hud {
  position: absolute;
  left: 44px;
  bottom: 18px;
  z-index: 3;
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
  pointer-events: none;
}

/* 等高线小视觉由 JS 确定性生成 */
/* ==================== 01 痛点 ==================== */
/* 非对称编辑栅格：5/4/3 栏宽 + 纵向错落，卡片 hover 位移 + 序号点亮 */
.pains {
  display: grid;
  grid-template-columns: 5fr 4fr 3fr;
  gap: 20px;
  align-items: start;
}
.pain { display: flex; flex-direction: column; gap: 12px; transition: transform 0.3s var(--fs-ease), border-color 0.3s var(--fs-ease), box-shadow 0.3s var(--fs-ease); }
.pain:nth-child(2) { margin-top: 28px; }
.pain:nth-child(3) { margin-top: 56px; }
.pain:hover { transform: translateY(-4px); border-color: var(--fs-hairline-strong); box-shadow: var(--fs-e2); }
.pain__top { display: flex; align-items: baseline; justify-content: space-between; }
.pain__no { font-size: 12px; letter-spacing: 0.14em; color: var(--fs-accent); transition: transform 0.3s var(--fs-ease); }
.pain:hover .pain__no { transform: translateX(3px); }
.pain__meta { opacity: 0.8; }

/* ==================== 02 能力（非对称 7/5 两列） ==================== */
.caps {
  display: grid;
  grid-template-columns: 7fr 5fr;
  gap: 18px;
}
.cap { display: flex; flex-direction: column; gap: 14px; }
.cap__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px; height: 42px;
  color: var(--fs-accent);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md);
  background: var(--fs-bg-sunken);
  transition:
    transform 0.3s var(--fs-ease),
    color 0.3s var(--fs-ease),
    background-color 0.3s var(--fs-ease),
    border-color 0.3s var(--fs-ease);
}
/* 图标牌 hover 反相为强调色底（accent-soft 令牌双主题自适应），与卡片聚光同时到位 */
.cap:hover .cap__icon {
  transform: translateY(-2px);
  background: var(--fs-accent-soft);
  border-color: rgba(var(--fs-accent-rgb), 0.32);
}

/* ==================== 03 工作流 ==================== */
.pg-sec--sunken { background: var(--fs-bg-sunken); }
.flow {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 12px;
}
.flow__step {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 16px 14px;
  transition:
    border-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.flow__step::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -12px;
  width: 12px;
  height: 1px;
  background: var(--fs-hairline-strong);
  transform: scaleX(var(--seg, 1));
  transform-origin: left center;
}
.flow__step:last-child::after { display: none; }
.flow__step.is-hitl { border-color: rgba(var(--fs-accent-rgb), 0.4); }
.flow__step.is-lit {
  border-color: rgba(var(--fs-accent-rgb), 0.35);
  box-shadow: 0 0 14px rgba(var(--fs-accent-rgb), 0.07);
}
.flow__step.is-lit .flow__idx { color: var(--fs-accent); }
.flow__step.is-lit .flow__agent { color: var(--fs-ink-700); }
.flow__step:hover {
  transform: translateY(-2px);
  border-color: var(--fs-hairline-strong);
  box-shadow: var(--fs-e1);
}
.flow__step:hover .flow__idx { letter-spacing: 0.2em; }
.flow__idx {
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--fs-ink-400);
  transition: color var(--fs-dur-micro) var(--fs-ease), letter-spacing var(--fs-dur-micro) var(--fs-ease);
}
.flow__label { font-size: 13px; font-weight: 600; color: var(--fs-ink-900); }
.flow__agent {
  font-size: 10px;
  letter-spacing: 0.03em;
  color: var(--fs-ink-400);
  transition: color var(--fs-dur-micro) var(--fs-ease);
}
.flow__note { margin: 18px 0 0; }

/* ==================== 04 数据带（干净读数，滚轮计数） ==================== */
.stats__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}
.stat { text-align: left; padding: 0 32px; }
.stat:first-child { padding-left: 0; }
.stat + .stat { border-left: 1px solid var(--fs-hairline); }
.stat__v {
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 52px;
  font-weight: 600;
  line-height: 1.1;
  color: var(--fs-ink-900);
}
.stat__k { margin-top: 12px; font-size: 14px; font-weight: 600; color: var(--fs-ink-900); }
.stat__d { margin-top: 6px; }
/* 深色带内读数配色（band 反相） */
.pg-band .stat__v, .pg-band .stat__k { color: rgb(var(--fs-bg-canvas-rgb)); }
.pg-band .stat__d { color: rgba(var(--fs-bg-canvas-rgb), 0.6); }
.pg-band .stat + .stat { border-left-color: rgba(var(--fs-bg-canvas-rgb), 0.16); }
.pg-band .stats__src { border-top-color: rgba(var(--fs-bg-canvas-rgb), 0.16); color: rgba(var(--fs-bg-canvas-rgb), 0.5); }
html.dark .pg-band .stat__v, html.dark .pg-band .stat__k { color: rgb(var(--fs-ink-900-rgb)); }
html.dark .pg-band .stat__d { color: var(--fs-ink-500); }
html.dark .pg-band .stat + .stat { border-left-color: var(--fs-hairline); }
html.dark .pg-band .stats__src { border-top-color: var(--fs-hairline); color: var(--fs-ink-500); }
/* 数字下方 5 条刻度呼吸（错峰点亮语义；off 静止满格） */
.stat__ticks {
  display: flex;
  align-items: flex-end;
  gap: 5px;
  height: 14px;
  margin-top: 16px;
}
.stat__ticks i {
  width: 1px;
  height: 8px;
  background: rgba(var(--fs-bg-canvas-rgb), 0.4);
  transform-origin: bottom center;
  animation: tick-breathe 3.2s ease-in-out infinite;
}
html.dark .stat__ticks i { background: var(--fs-ink-400); }
.stat__ticks i:nth-child(2) { height: 12px; animation-delay: 0.35s; }
.stat__ticks i:nth-child(3) { height: 6px; animation-delay: 0.7s; }
.stat__ticks i:nth-child(4) { height: 11px; animation-delay: 1.05s; }
.stat__ticks i:nth-child(5) { height: 7px; animation-delay: 1.4s; }
@keyframes tick-breathe {
  0%, 100% { opacity: 0.4; transform: scaleY(0.55); }
  50% { opacity: 1; transform: scaleY(1); }
}
/* 读数带来源脚注（data-dense 纪律：口径可溯源） */
.stats__src {
  width: min(1240px, 100% - 96px);
  margin: 32px auto 0;
  padding-top: 14px;
  border-top: 1px solid var(--fs-hairline);
  font-family: var(--fs-font-mono);
  letter-spacing: 0.08em;
  text-align: right;
}
@media (max-width: 768px) {
  .stats__src { width: calc(100% - 48px); text-align: left; }
}

/* ==================== 05 模块入口 ==================== */
.mods {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}
.mod {
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-decoration: none;
}
.mod::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: linear-gradient(90deg, var(--fs-accent), var(--fs-risk-mid), transparent);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.3s var(--fs-ease);
}
.mod:hover::before, .mod:focus-visible::before { transform: scaleX(1); }
.mod__hd { display: flex; align-items: center; gap: 12px; min-width: 0; }
.mod__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px; height: 40px;
  flex: none;
  color: var(--fs-ink-700);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md);
  background: var(--fs-bg-sunken);
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background-color var(--fs-dur-micro) var(--fs-ease),
    border-color var(--fs-dur-micro) var(--fs-ease);
}
.mod__label { font-size: 15px; font-weight: 600; color: var(--fs-ink-900); min-width: 0; }
.mod__desc {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: calc(1.9em * 2);
}
.mod__foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--fs-hairline);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-400);
  transition: color var(--fs-dur-micro) var(--fs-ease), border-color var(--fs-dur-micro) var(--fs-ease);
}
.mod__foot em { font-style: normal; }
.mod__arr { transition: transform var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease); }
.mod:hover .mod__foot, .mod:focus-visible .mod__foot { color: var(--fs-ink-900); border-top-color: var(--fs-hairline-strong); }
.mod:hover .mod__arr, .mod:focus-visible .mod__arr { transform: translateX(3px); color: var(--fs-accent); }
/* hover/focus 图标牌反相 + 图标 90° 旋转一次（键盘同效） */
.mod:hover .mod__icon, .mod:focus-visible .mod__icon {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  border-color: rgba(var(--fs-accent-rgb), 0.32);
}
.mod__icon svg { transition: transform 0.4s var(--fs-ease); }
.mod:hover .mod__icon svg, .mod:focus-visible .mod__icon svg { transform: rotate(90deg); }
@media (min-width: 761px) {
  .mods { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1281px) {
  .mods { grid-template-columns: repeat(3, 1fr); }
}

/* ==================== 结尾 CTA ==================== */
.final { position: relative; padding: 88px 0 64px; text-align: center; overflow: hidden; }
.final__bg { position: absolute; inset: 0; pointer-events: none; }
.final__inner { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; }
.final__line {
  display: block;
  width: min(560px, 80%);
  height: 1px;
  margin-bottom: 32px;
  background: linear-gradient(90deg, transparent, var(--fs-hairline-strong), transparent);
}
.final__claim { margin: 0 0 28px; }
/* 深色带内分隔线/流场降密度 */
.pg-band .final__line { background: linear-gradient(90deg, transparent, rgba(var(--fs-bg-canvas-rgb), 0.3), transparent); }
html.dark .pg-band .final__line { background: linear-gradient(90deg, transparent, var(--fs-hairline-strong), transparent); }
.final__bg { opacity: 0.55; }
/* 按钮 hover 扫光（一次，0.6s；off 时静止） */
.btn--primary::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, transparent 35%, rgba(255, 255, 255, 0.32) 50%, transparent 65%);
  transform: translateX(-160%);
  pointer-events: none;
}
.btn--primary:hover::before { animation: btn-sweep 0.6s var(--fs-ease); }
@keyframes btn-sweep { to { transform: translateX(160%); } }
html[data-motion-allowed="false"] .btn--primary:hover::before { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .btn--primary:hover::before { animation: none; }
}

/* ==================== 云南火险地形场景（深色仪表带：左读数 3 栏 + 右地形 9 栏） ==================== */
.terr__grid {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 40px;
  align-items: stretch;
}
.terr__readouts {
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.terr__ro { padding: 22px 0; }
.terr__ro + .terr__ro { border-top: 1px solid rgba(var(--fs-bg-canvas-rgb), 0.16); }
html.dark .terr__ro + .terr__ro { border-top-color: var(--fs-hairline); }
.terr__ro b {
  display: block;
  font-size: 40px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: inherit;
}
.terr__ro span { display: block; margin-top: 4px; }
.terr__stage {
  position: relative;
  height: 480px;
  overflow: hidden;
  border: 1px solid rgba(var(--fs-bg-canvas-rgb), 0.14);
  border-radius: var(--fs-r-lg);
  background: rgba(var(--fs-bg-canvas-rgb), 0.03);
}
html.dark .terr__stage {
  border-color: var(--fs-hairline);
  background: rgba(var(--fs-ink-900-rgb), 0.02);
}
.terr__foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin-top: 16px;
}
.terr__note { margin: 0 0 0 auto; }
@media (max-width: 900px) {
  .terr__grid { grid-template-columns: 1fr; gap: 20px; }
  .terr__readouts { flex-direction: row; gap: 24px; }
  .terr__ro { padding: 0; }
  .terr__ro + .terr__ro { border-top: none; border-left: 1px solid rgba(var(--fs-bg-canvas-rgb), 0.16); padding-left: 24px; }
  html.dark .terr__ro + .terr__ro { border-left-color: var(--fs-hairline); }
  .terr__ro b { font-size: 28px; }
}
@media (max-width: 768px) {
  .terr__stage { height: 340px; }
  .terr__note { margin-left: 0; }
}

/* ==================== 等高线小视觉生成 ==================== */

/* ==================== 右侧章节导轨 ====================
   固定在视口右缘，首屏不出现；命中章刻度转强调色并加长。
   收起态宽度 ≤26px，落进版心 ≥48px 的左右留白里，任何宽度下都不压卡片；
   悬停/键盘聚焦才展开为带底色浮层（序号 + 章名 + 滚动百分比）。
   展开只动 max-width/gap/opacity，不做位移动画，动效 off 时功能与读数均可用。 */
.srail {
  position: fixed;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--fs-dur-panel) var(--fs-ease);
}
.srail.is-on { opacity: 1; pointer-events: auto; }
/* 展开浮层底（::before 垫在导轨自身层内，压在页面内容之上、序号之下） */
.srail::before {
  content: '';
  position: absolute;
  inset: -7px -8px;
  z-index: -1;
  border-radius: var(--fs-r-md);
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  box-shadow: var(--fs-e2);
  opacity: 0;
  transition: opacity var(--fs-dur-micro) var(--fs-ease);
}
.srail:hover::before, .srail:focus-within::before { opacity: 1; }
.srail__item {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0;
  height: 22px;
  padding: 0 5px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--fs-ink-400);
  border-radius: var(--fs-r-sm);
  transition: color var(--fs-dur-micro) var(--fs-ease), gap 0.26s var(--fs-ease);
}
.srail__item:hover { color: var(--fs-ink-900); background: rgba(var(--fs-ink-900-rgb), 0.045); }
.srail__item.is-on { color: var(--fs-accent); }
/* 序号与章名共用「宽度闸门」：收起时 max-width 0 不占位，展开时逐级放开 */
.srail__no, .srail__lb {
  white-space: nowrap;
  overflow: hidden;
  max-width: 0;
  opacity: 0;
  transition: max-width 0.26s var(--fs-ease), opacity 0.18s var(--fs-ease);
}
.srail__no { font-size: 10px; letter-spacing: 0.12em; }
.srail__lb { font-size: 11px; letter-spacing: 0.06em; }
.srail:hover .srail__item, .srail:focus-within .srail__item { gap: 8px; }
.srail:hover .srail__no, .srail:focus-within .srail__no { max-width: 20px; opacity: 1; }
.srail:hover .srail__lb, .srail:focus-within .srail__lb { max-width: 84px; opacity: 1; }
.srail__tick {
  width: 10px;
  height: 1px;
  flex: none;
  background: var(--fs-hairline-strong);
  transition: width 0.26s var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.srail__item:hover .srail__tick { width: 16px; background: var(--fs-ink-500); }
.srail__item.is-on .srail__tick { width: 20px; background: var(--fs-accent); }
.srail__pct {
  max-width: 0;
  overflow: hidden;
  white-space: nowrap;
  opacity: 0;
  margin-top: 0;
  font-size: 10px;
  letter-spacing: 0.1em;
  font-variant-numeric: tabular-nums;
  color: var(--fs-ink-400);
  transition: max-width 0.26s var(--fs-ease), opacity 0.18s var(--fs-ease);
}
.srail:hover .srail__pct, .srail:focus-within .srail__pct {
  max-width: 44px;
  opacity: 1;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--fs-hairline);
}
@media (max-width: 1180px) {
  .srail { display: none; }
}

/* ==================== 响应式 ==================== */
@media (max-width: 1024px) {
  .hero__inner { flex-direction: column; align-items: flex-start; gap: 40px; }
  .hero__copy { width: 100%; }
  .sit { margin-left: 0; width: 100%; max-width: 480px; }
  .caps { grid-template-columns: repeat(2, 1fr); }
  .pains { grid-template-columns: 1fr; }
  .pain:nth-child(2), .pain:nth-child(3) { margin-top: 0; }
  .flow { grid-template-columns: repeat(4, 1fr); }
  .flow__step:nth-child(4n)::after { display: none; }
  .hero__scrollhint { display: none; }
  .hero__scrollrail { display: none; }
}
@media (max-width: 640px) {
  .caps { grid-template-columns: 1fr; }
  .flow { grid-template-columns: repeat(2, 1fr); }
  .flow__step::after { display: none; }
  .stats__grid { grid-template-columns: 1fr; gap: 28px; }
  .stat { padding: 0; }
  .stat + .stat { border-left: none; border-top: 1px solid var(--fs-hairline); padding-top: 28px; }
  .stat__v { font-size: 40px; }
}

/* ==================== reduced/off 静态兜底（on 覆盖系统 reduce） ==================== */
html[data-motion-allowed="false"] .sit { animation: none; }
</style>
