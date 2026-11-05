<script setup>
/**
 * /welcome/technology — 技术与部署（公开）
 *
 * 顶部为 CSS/SVG 绘制的分层架构图（前端 → API → Agent 编排 → 数据/模型 → 报告/SSE），
 * 下方三栏：技术栈 / 部署形态 / 安全与边界；附数据口径表与 FAQ。
 * 全部口径来自仓库真实依赖与实现。
 */
import { ref, computed } from 'vue'
import AppIcon from '@/components/base/AppIcon.vue'
import PubPage from '@/components/welcome/PubPage.vue'
import AgentNetGL from '@/components/welcome/AgentNetGL.vue'

/* 架构图层（自上而下数据流；duty/io 供交互层右栏展示） */
const archLayers = [
  { id: 'front', label: '前端', detail: 'Vue 3 · Vite · ECharts · OpenLayers · Three', tone: 'is-r1',
    duty: '指挥台交互与态势呈现', io: '输入 值班员操作 · 输出 请求与订阅' },
  { id: 'api', label: 'API', detail: 'FastAPI · REST · SSE 流式推送', tone: 'is-r2',
    duty: 'REST 查询与 SSE 事件通道', io: '输入 前端指令 · 输出 数据流与任务事件' },
  { id: 'agents', label: 'Agent 编排', detail: 'LangGraph · 6 智能体 · 七环节流水线（查询 ∥ 检索并行）', tone: 'is-r3',
    duty: '任务拆解与六智能体协作', io: '输入 自然语言任务 · 输出 执行计划与节点产物' },
  { id: 'data', label: '数据与模型', detail: 'PostgreSQL + PostGIS · Qwen 大模型 · 向量检索', tone: 'is-r4',
    duty: '存储、检索与推理底座', io: '输入 查询与写入 · 输出 记录与向量片段' },
  { id: 'out', label: '报告与推送', detail: '报告生成 · 质量评审 · 人工审批归档', tone: 'is-r5',
    duty: '成文、评审与人工闸口', io: '输入 结论与草稿 · 输出 归档报告' },
]
/* 交互层：hover/点击单层聚焦，其余降到 40%（再点取消） */
const activeLayer = ref(null)
const setLayer = (id) => { activeLayer.value = activeLayer.value === id ? null : id }
const curLayer = computed(() => archLayers.find((l) => l.id === activeLayer.value) || null)
/* FAQ 手风琴：一次只开一项 */
const faqOpen = ref(0)
const toggleFaq = (i) => { faqOpen.value = faqOpen.value === i ? -1 : i }

/* 三栏 */
const cols = [
  {
    title: '技术栈',
    items: [
      '前端 Vue 3 + Vite，地图 OpenLayers + Three',
      '图表 ECharts，动效 GSAP + Lenis',
      '后端 FastAPI + LangGraph 编排',
      '大模型 Qwen（可切换 AMD / Ollama / LongCat），知识库向量检索',
    ],
  },
  {
    title: '部署形态',
    items: [
      '前后端分离，内网可部署',
      'PostgreSQL + PostGIS 空间库，Docker Compose 一键拉起',
      '大模型 / 数据库密钥仅存服务端 .env；地图瓦片 Key 为前端公开配置',
      '静态资源一键构建 dist',
    ],
  },
  {
    title: '安全与边界',
    items: [
      '登录鉴权 + 角色权限（管理员/值班员）',
      '公开页无内部权限内容',
      '审批闸口保证报告人工把关',
      'SSE 断线自动回查任务详情兜底',
    ],
  },
]

const faqs = [
  { q: '数据从哪里来？', a: '卫星火点为 MODIS 2021–2025 长序列归集（当前口径 5,411 条）；气象为高德接口实时查询，地形为 16 州市行政边界；接口异常时统计降级为本地默认口径并保持标注。' },
  { q: '六级还是五级火险？', a: '系统全站统一五级口径：正常 / 注意 / 警告 / 高度 / 极度，与作战大屏图例一致。' },
  { q: '智能体会自动发布报告吗？', a: '不会。所有报告必须经过人工审核闸口（HITL）通过后才归档发布；评审异常时自动降级转人工。' },
  { q: '能否部署在内网？', a: '可以。前后端分离，可用 Docker Compose 一键部署；大模型与天气接口均可配置内网代理或关闭降级。' },
]
</script>

<template>
  <PubPage
    eyebrow="TECHNOLOGY · 技术与部署"
    title="看得见的技术底座"
    lead="前后端栈、空间数据管线与安全机制全部来自仓库真实依赖；不堆砌名词，只列实际在用的技术。"
    :page-index="3"
  >
    <!-- 架构图（CSS/SVG 绘制，非截图） -->
    <section class="pg-sec">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">01</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">ARCHITECTURE · 架构</p>
            <h2 class="pg-head__title pg-h2">数据怎么流</h2>
            <p class="pg-head__lead pg-body">从前端指令到报告归档，一条自上而下的数据链路。</p>
          </div>
          <span class="pg-head__meta">5 LAYERS</span>
        </div>
        <!-- 可交互架构层：hover/点击单层聚焦（其余 40%），右栏显示职责与输入输出 -->
        <div class="arch-grid">
          <div class="arch pg-card mo-loop" data-stagger>
            <span class="arch__fig qt-eyebrow" aria-hidden="true">FIG.01 · DATA FLOW · TOP-DOWN</span>
            <div v-for="(l, i) in archLayers" :key="l.id" class="arch__row rv-item">
              <div
                class="arch__node qt-bp"
                :class="[l.tone, { 'is-on': activeLayer === l.id, 'is-dim': activeLayer && activeLayer !== l.id }]"
                tabindex="0"
                role="button"
                :aria-pressed="activeLayer === l.id"
                @mouseenter="setLayer(l.id)"
                @click="setLayer(l.id)"
                @keyup.enter="setLayer(l.id)"
              >
                <span class="arch__label">{{ l.label }}</span>
                <span class="arch__detail pg-cap">{{ l.detail }}</span>
              </div>
              <svg
                v-if="i < archLayers.length - 1"
                class="arch__link"
                :class="{ 'is-on': activeLayer && (activeLayer === archLayers[i].id || activeLayer === archLayers[i + 1].id) }"
                viewBox="0 0 24 20" aria-hidden="true"
              >
                <path d="M12 1 V19 M6 13 L12 19 L18 13" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="3 3" />
              </svg>
            </div>
          </div>
          <aside class="arch__info pg-card" aria-live="polite">
            <template v-if="curLayer">
              <p class="qt-eyebrow">LAYER · {{ curLayer.id.toUpperCase() }}</p>
              <h3 class="pg-h3">{{ curLayer.label }}</h3>
              <p class="pg-body">{{ curLayer.duty }}</p>
              <p class="pg-cap arch__io">{{ curLayer.io }}</p>
              <p class="pg-cap">{{ curLayer.detail }}</p>
            </template>
            <span v-else class="pg-cap">hover 或点击左侧某一层，查看该层职责与输入输出。</span>
          </aside>
        </div>
      </div>
    </section>

    <!-- 智能体网络（WebGL 场景） -->
    <section class="pg-sec">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">02</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">AGENT NETWORK · 智能体网络</p>
            <h2 class="pg-head__title pg-h2">六个智能体，一张编排网</h2>
            <p class="pg-head__lead pg-body">中枢编排、五方协作、末端人工闸口；连线上的光点是正在流动的数据包。hover 节点查看职责，点击定位到工作流。</p>
          </div>
          <span class="pg-head__meta">6 AGENTS + HITL</span>
        </div>
        <div class="anet-stage pg-card rv">
          <AgentNetGL />
        </div>
        <p class="anet__note pg-cap">示意：查询数据与知识检索并行执行后汇合；数据包仅表示调度关系，不代表实时流量。</p>
      </div>
    </section>

    <!-- 三栏 -->
    <section class="pg-sec pg-sec--sunken">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">03</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">STACK / DEPLOY / SECURITY</p>
            <h2 class="pg-head__title pg-h2">栈、部署与边界</h2>
          </div>
          <span class="pg-head__meta">3 COLUMNS</span>
        </div>
        <div class="tech-cols" data-stagger>
          <div v-for="c in cols" :key="c.title" class="pg-card tech-col rv-item">
            <h3 class="pg-h3">{{ c.title }}</h3>
            <ul class="tech-col__list">
              <li v-for="it in c.items" :key="it" class="qt-row pg-cap">{{ it }}</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- 数据口径 -->
    <section class="pg-sec">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">04</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">DATA · 数据口径</p>
            <h2 class="pg-head__title pg-h2">公开口径一览</h2>
          </div>
          <span class="pg-head__meta">VERIFIED</span>
        </div>
        <div class="pg-card data rv" data-rv-delay="0.06">
          <table class="data__table">
            <tbody>
              <tr class="qt-row"><th>覆盖州市</th><td class="qt-num">16</td><td>云南省全部州市，全域网格化</td></tr>
              <tr class="qt-row"><th>历史火点</th><td class="qt-num">5,411</td><td>MODIS 卫星火点，2021–2025 长序列</td></tr>
              <tr class="qt-row"><th>协作智能体</th><td class="qt-num">6</td><td>编排 / 数据 / GIS / 检索 / 报告 / 评审</td></tr>
              <tr class="qt-row"><th>流水线环节</th><td class="qt-num">7</td><td>8 个节点：查询 ∥ 检索并行后汇合，含 HITL</td></tr>
              <tr class="qt-row"><th>功能模块</th><td class="qt-num">6</td><td>作战大屏 / 智能查询 / 知识库 / Agent 中心 / 报告中心 / 系统管理</td></tr>
              <tr class="qt-row"><th>空间基准</th><td class="qt-num">EPSG:4326</td><td>WGS84 经纬度</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- FAQ -->
    <section class="pg-sec qsec--last">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">05</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">FAQ · 常见问题</p>
            <h2 class="pg-head__title pg-h2">你可能想问</h2>
          </div>
        </div>
        <div class="faq rv" data-rv-delay="0.06">
          <details v-for="(f, i) in faqs" :key="f.q" class="faq__item pg-card" :open="faqOpen === i">
            <summary class="qt-row" @click.prevent="toggleFaq(i)">{{ f.q }}</summary>
            <p class="faq__a pg-body">{{ f.a }}</p>
          </details>
        </div>
      </div>
    </section>
  </PubPage>
</template>

<style scoped>
.pg-sec--sunken { background: var(--fs-bg-sunken); }

/* ---- 智能体网络场景容器 ---- */
.anet-stage {
  height: 480px;
  padding: 0;
  overflow: hidden;
  background: var(--fs-bg-sunken);
}
@media (max-width: 768px) {
  .anet-stage { height: 340px; }
}
.anet__note { margin-top: 10px; color: var(--fs-ink-400); }

/* ---- 架构图：分层节点 + SVG 虚线连接（蓝图辅助线）+ FIG 编号标注 + 交互层 ---- */
.arch-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 20px;
  align-items: start;
}
.arch {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 32px 28px;
  gap: 0;
}
/* 交互层状态：选中层提边，其余降 40% */
.arch__node {
  cursor: pointer;
  transition:
    opacity 0.2s var(--fs-ease),
    border-color 0.2s var(--fs-ease),
    box-shadow 0.2s var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
/* 可点层：hover 上浮 1px，与「点击切换信息面板」的 affordance 对齐 */
.arch__node:hover { transform: translateY(-1px); box-shadow: var(--fs-e1); }
.arch__node:active { transform: translateY(0); }
.arch__node.is-dim { opacity: 0.4; }
.arch__node.is-on {
  border-color: rgba(var(--fs-accent-rgb), 0.5);
  box-shadow: 0 0 14px rgba(var(--fs-accent-rgb), 0.1);
}
.arch__node:focus-visible { outline: 2px solid var(--fs-accent); outline-offset: 2px; }
/* 右栏信息面板 */
.arch__info {
  position: sticky;
  top: 96px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 180px;
}
.arch__info .qt-eyebrow { color: var(--fs-accent); }
.arch__io { font-family: var(--fs-font-mono); letter-spacing: 0.04em; color: var(--fs-ink-700); }
/* 虚线缓慢流动（dash 周期 6px 无缝；mo-loop 降级） */
.arch__link { color: var(--fs-hairline-strong); transition: color 0.2s var(--fs-ease); }
.arch__link path { animation: arch-dash 2.4s linear infinite; }
.arch__link.is-on { color: var(--fs-accent); }
@keyframes arch-dash { to { stroke-dashoffset: -6; } }
.arch__fig {
  display: block;
  margin: 0 0 20px;
  color: var(--fs-ink-400);
}
.arch__row { display: flex; flex-direction: column; align-items: center; }
.arch__node {
  width: min(520px, 100%);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 22px;
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md);
  background: var(--fs-bg-canvas);
  border-left: 3px solid var(--fs-info);
}
.arch__node.is-r1 { border-left-color: var(--fs-risk-1); }
.arch__node.is-r2 { border-left-color: var(--fs-risk-2); }
.arch__node.is-r3 { border-left-color: var(--fs-risk-3); }
.arch__node.is-r4 { border-left-color: var(--fs-risk-4); }
.arch__node.is-r5 { border-left-color: var(--fs-risk-5); }
.arch__label { font-size: 15px; font-weight: 600; color: var(--fs-ink-900); }
.arch__detail { margin: 0; text-align: right; }
.arch__link { width: 24px; height: 20px; margin: 2px 0; }

/* ---- 三栏 ---- */
.tech-cols {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.tech-col { display: flex; flex-direction: column; gap: 14px; position: relative; }
/* 三栏 hover：底部细线展开 */
.tech-col::after {
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
.tech-col:hover::after, .tech-col:focus-within::after { transform: scaleX(1); }
/* 条目编号（LaTeX 小节编号纪律：mono 序号 + 悬挂对齐） */
.tech-col__list { list-style: none; margin: 0; padding: 0; counter-reset: tech-item; }
.tech-col__list li {
  padding: 7px 8px;
  display: flex;
  gap: 10px;
  border-radius: var(--fs-r-xs);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.tech-col__list li:hover { background: var(--fs-bg-sunken); }
.tech-col__list li::before {
  counter-increment: tech-item;
  content: counter(tech-item, decimal-leading-zero);
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--fs-ink-400);
  flex: none;
  padding-top: 2px;
}

/* ---- 数据口径表（booktabs 纪律：只横线，顶/底线加重，无竖线无斑马纹） ---- */
.data { padding: 0; overflow: hidden; }
.data__table { width: 100%; border-collapse: collapse; }
.data__table tbody tr:first-child th,
.data__table tbody tr:first-child td { border-top: 1.5px solid var(--fs-ink-900); }
.data__table tbody tr:last-child th,
.data__table tbody tr:last-child td { border-bottom: 1.5px solid var(--fs-ink-900); }
.data__table th, .data__table td {
  text-align: left;
  padding: 13px 20px;
  font-size: 13px;
  border-bottom: 1px solid var(--fs-hairline);
}
.data__table th { font-weight: 600; color: var(--fs-ink-900); width: 140px; }
.data__table td.qt-num { width: 130px; font-size: 14px; color: var(--fs-ink-900); }
.data__table td:last-child { color: var(--fs-ink-500); }
.data__table tr:last-child th, .data__table tr:last-child td { border-bottom: none; }

/* ---- FAQ ---- */
.faq { display: flex; flex-direction: column; gap: 10px; }
.faq__item { padding: 0; overflow: hidden; }
.faq__item summary {
  list-style: none;
  position: relative;
  padding: 15px 44px 15px 20px;
  font-size: 14px;
  font-weight: 600;
  color: var(--fs-ink-900);
  cursor: pointer;
}
/* 展开指示箭头（纯 CSS 折角，open 时翻转 180°并转强调色） */
.faq__item summary::after {
  content: '';
  position: absolute;
  right: 22px;
  top: 50%;
  width: 8px;
  height: 8px;
  margin-top: -5px;
  border-right: 1.5px solid var(--fs-ink-400);
  border-bottom: 1.5px solid var(--fs-ink-400);
  transform: rotate(45deg);
  transition: transform 0.24s var(--fs-ease), border-color var(--fs-dur-micro) var(--fs-ease);
}
.faq__item summary:hover::after { border-color: var(--fs-accent); }
.faq__item[open] summary::after { transform: rotate(-135deg); border-color: var(--fs-accent); }
.faq__item summary::-webkit-details-marker { display: none; }
.faq__a { margin: 0; padding: 0 20px 16px; }
/* FAQ 展开内容淡入（一次性；三态降级） */
.faq__item[open] .faq__a { animation: faq-in 0.2s var(--fs-ease) both; }
@keyframes faq-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: none; }
}
html[data-motion-allowed="false"] .faq__item[open] .faq__a { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .faq__item[open] .faq__a { animation: none; }
}

/* off（或 auto+系统减）：取消 hover 上浮，保留边框/阴影反馈 */
html[data-motion-allowed="false"] .arch__node:hover,
html[data-motion-allowed="false"] .arch__node:active { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .arch__node:hover,
  html:not([data-motion="on"]) .arch__node:active { transform: none; }
}

@media (max-width: 900px) {
  .tech-cols { grid-template-columns: 1fr; }
  .arch-grid { grid-template-columns: 1fr; }
  .arch__info { position: static; min-height: 0; }
  .arch__node { flex-direction: column; gap: 4px; }
  .arch__detail { text-align: left; }
}
</style>
