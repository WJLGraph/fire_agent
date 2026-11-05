/* =============================================================================
 * 焰哨 FlameSentry · 视觉 V0 原型交互
 *
 * 纯展示逻辑：屏幕切换 / Tweaks 令牌调节 / 地图示意绘制 / 顶刊级图表绘制
 * 不含任何业务数据请求——所有数值均为版面示意。
 * ========================================================================== */

const $ = (s, r = document) => r.querySelector(s)
const $$ = (s, r = document) => [...r.querySelectorAll(s)]
const html = document.documentElement

const cv = (n) => getComputedStyle(html).getPropertyValue(n).trim()

/* ============================== 1. 舞台自适应缩放 ============================== */

function fitStage() {
  const stage = $('#stage')
  const w = window.innerWidth
  const h = window.innerHeight
  const fit = Math.min((w - 48) / 1440, (h - 96) / 900)
  stage.style.setProperty('--fit', String(Math.max(fit, 0.25)))
}
window.addEventListener('resize', fitStage)
fitStage()

/* ============================== 2. 地图示意（等高线 + 州市 + 火点） ============================== */

const MAP_W = 1000
const MAP_H = 620

// 云南轮廓（示意，非真实行政边界）
const PROVINCE = [
  [140, 120], [300, 90], [430, 120], [520, 175], [580, 230], [660, 270],
  [720, 330], [760, 400], [780, 470], [740, 540], [690, 585], [650, 545],
  [620, 470], [560, 420], [480, 390], [400, 400], [320, 370], [250, 320],
  [190, 250], [150, 180],
]

const CITIES = [
  { n: '丽江', x: 300, y: 150 },
  { n: '昭通', x: 620, y: 92 },
  { n: '大理', x: 330, y: 245 },
  { n: '楚雄', x: 468, y: 282 },
  { n: '昆明', x: 566, y: 322 },
  { n: '保山', x: 296, y: 302 },
  { n: '临沧', x: 430, y: 442 },
  { n: '文山', x: 758, y: 402 },
  { n: '普洱', x: 618, y: 470 },
  { n: '西双版纳', x: 676, y: 556 },
]

// 火点（示意）：[x, y, 等级 1-4]
const FIRES = [
  [462, 268, 4], [478, 296, 3], [452, 312, 4], [496, 258, 3], [508, 288, 2],
  [426, 336, 2], [540, 300, 3], [572, 348, 2], [588, 322, 3], [612, 366, 2],
  [404, 300, 2], [368, 258, 1], [320, 292, 1], [648, 424, 3], [664, 452, 2],
  [700, 486, 2], [686, 540, 1], [744, 408, 2], [766, 436, 1], [292, 168, 1],
  [612, 108, 2], [636, 138, 1], [452, 452, 1], [500, 404, 2],
]

const pathOf = (pts) =>
  pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ') + ' Z'

/** 绕种子点生成一圈不规则的闭合等高线 */
function contour(cx, cy, r, seed) {
  const n = 64
  const pts = []
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2
    const wob =
      1 +
      0.16 * Math.sin(a * 3 + seed) +
      0.10 * Math.sin(a * 5 - seed * 1.7) +
      0.06 * Math.sin(a * 8 + seed * 0.6)
    pts.push([cx + Math.cos(a) * r * wob * 1.35, cy + Math.sin(a) * r * wob * 0.82])
  }
  return pathOf(pts)
}

function renderMap() {
  const box = $('#mapCanvas')
  if (!box) return
  const stroke = cv('--fs-hairline-strong')
  const ink400 = cv('--fs-ink-400')
  const ink500 = cv('--fs-ink-500')
  const accent = cv('--fs-accent')
  const surf = cv('--fs-bg-surface')
  const r = {
    low: cv('--fs-risk-low'), mid: cv('--fs-risk-mid'),
    high: cv('--fs-risk-high'), ext: cv('--fs-risk-extreme'),
  }
  const colors = [r.low, r.mid, r.high, r.ext]

  let contours = ''
  const seeds = [
    { cx: 300, cy: 200, s: 0.7 }, { cx: 640, cy: 430, s: 2.1 },
    { cx: 470, cy: 300, s: 3.4 }, { cx: 700, cy: 250, s: 5.2 },
  ]
  seeds.forEach((sd) => {
    for (let i = 1; i <= 9; i++) {
      contours += `<path d="${contour(sd.cx, sd.cy, i * 15, sd.s + i * 0.35)}" fill="none" stroke="${ink400}" stroke-width="0.7" opacity="0.38" clip-path="url(#provClip)"/>`
    }
  })

  const dots = FIRES.map(([x, y, lv]) => {
    const c = colors[lv - 1]
    const rr = lv >= 3 ? 3.6 : 2.8
    return `<circle cx="${x}" cy="${y}" r="${rr}" fill="${c}" opacity="0.92"/>` +
      (lv === 4 ? `<circle cx="${x}" cy="${y}" r="${rr + 4}" fill="none" stroke="${c}" stroke-width="1" opacity="0.45"/>` : '')
  }).join('')

  const labels = CITIES.map(
    (c) =>
      `<text x="${c.x}" y="${c.y}" font-size="11" font-family="${cv('--fs-font-sans')}" fill="${ink500}" text-anchor="middle" opacity="0.9">${c.n}</text>`
  ).join('')

  box.innerHTML = `
    <svg viewBox="0 0 ${MAP_W} ${MAP_H}" preserveAspectRatio="xMidYMid slice">
      <defs>
        <clipPath id="provClip"><path d="${pathOf(PROVINCE)}"/></clipPath>
      </defs>
      <rect width="${MAP_W}" height="${MAP_H}" fill="none"/>
      ${contours}
      <path d="${pathOf(PROVINCE)}" fill="${surf}" fill-opacity="0.35" stroke="${stroke}" stroke-width="1.2" stroke-linejoin="round"/>
      ${dots}
      ${labels}
      <g opacity="0.5">
        <circle cx="566" cy="322" r="9" fill="none" stroke="${accent}" stroke-width="1"/>
      </g>
    </svg>`
}

/* ============================== 3. 顶刊级图表（细线 / 低饱和 / 高数据-墨比） ============================== */

const CHART_DATA = {
  history: {
    title: '历史火险等级',
    note: '2025 全年逐月',
    labels: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
    values: [42, 58, 96, 128, 154, 121, 88, 76, 94, 132, 168, 186],
  },
  predict: {
    title: '预测火险指数',
    note: '2026-03 · 逐州市',
    labels: ['楚雄', '昆明', '普洱', '大理', '文山', '临沧', '丽江', '昭通'],
    values: [0.58, 0.44, 0.39, 0.34, 0.31, 0.28, 0.22, 0.19],
    levels: [3, 2, 2, 2, 2, 1, 1, 1],
  },
  share: {
    title: '预测火险占比',
    note: '按等级构成',
    segs: [
      { label: '低', v: 28 }, { label: '中', v: 34 },
      { label: '高', v: 26 }, { label: '极高', v: 12 },
    ],
  },
  freq: {
    title: '历史火点频次',
    note: 'Top 5 州市',
    items: [
      { n: '楚雄州', v: 412, c: 'high' },
      { n: '昆明市', v: 286, c: 'mid' },
      { n: '普洱市', v: 231, c: 'mid' },
      { n: '文山州', v: 178, c: 'mid' },
      { n: '丽江市', v: 96, c: 'low' },
    ],
  },
}

function lineChart(w, h, d) {
  const ink500 = cv('--fs-ink-500')
  const hair = cv('--fs-hairline')
  const accent = cv('--fs-accent')
  const pl = 30, pr = 6, pt = 12, pb = 20
  const iw = w - pl - pr, ih = h - pt - pb
  const max = Math.max(...d.values) * 1.12
  const min = 0
  const X = (i) => pl + (i / (d.values.length - 1)) * iw
  const Y = (v) => pt + ih - ((v - min) / (max - min)) * ih

  let grid = ''
  for (let g = 0; g <= 3; g++) {
    const v = (max / 3) * g
    const y = Y(v)
    grid += `<line x1="${pl}" y1="${y}" x2="${w - pr}" y2="${y}" stroke="${hair}" stroke-width="1" stroke-dasharray="${g === 0 ? '0' : '2 3'}"/>`
    grid += `<text x="${pl - 6}" y="${y + 3.5}" font-size="9" font-family="${cv('--fs-font-mono')}" fill="${ink500}" text-anchor="end">${Math.round(v)}</text>`
  }

  const pts = d.values.map((v, i) => [X(i), Y(v)])
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ')
  const area = `${line} L${X(d.values.length - 1).toFixed(1)} ${Y(min).toFixed(1)} L${pl} ${Y(min).toFixed(1)} Z`

  const xlab = d.labels
    .map((t, i) =>
      i % 2 === 0
        ? `<text x="${X(i)}" y="${h - 5}" font-size="9" font-family="${cv('--fs-font-mono')}" fill="${ink500}" text-anchor="middle">${t}</text>`
        : ''
    )
    .join('')
  const dots = pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="1.8" fill="${accent}"/>`).join('')

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    ${grid}
    <path d="${area}" fill="${accent}" opacity="0.10"/>
    <path d="${line}" fill="none" stroke="${accent}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
    ${dots}${xlab}
  </svg>`
}

function barChart(w, h, d) {
  const ink500 = cv('--fs-ink-500')
  const hair = cv('--fs-hairline')
  const vars = { low: cv('--fs-risk-low'), mid: cv('--fs-risk-mid'), high: cv('--fs-risk-high') }
  const pl = 26, pr = 6, pt = 10, pb = 20
  const iw = w - pl - pr, ih = h - pt - pb
  const max = 0.65
  const step = iw / d.values.length
  const bw = Math.min(step * 0.5, 22)

  let grid = ''
  for (let g = 0; g <= 2; g++) {
    const v = (max / 2) * g
    const y = pt + ih - (v / max) * ih
    grid += `<line x1="${pl}" y1="${y}" x2="${w - pr}" y2="${y}" stroke="${hair}" stroke-width="1" stroke-dasharray="${g === 0 ? '0' : '2 3'}"/>`
    grid += `<text x="${pl - 6}" y="${y + 3.5}" font-size="9" font-family="${cv('--fs-font-mono')}" fill="${ink500}" text-anchor="end">${v.toFixed(2)}</text>`
  }

  const sparse = step < 26   // 窄容器下隔一显示，避免标签相撞
  const bars = d.values
    .map((v, i) => {
      const bh = Math.max((v / max) * ih, 1)
      const x = pl + step * i + (step - bw) / 2
      const y = pt + ih - bh
      const c = vars[d.levels[i] === 3 ? 'high' : d.levels[i] === 2 ? 'mid' : 'low']
      const lab = sparse && i % 2 === 1 ? '' :
        `<text x="${(x + bw / 2).toFixed(1)}" y="${h - 6}" font-size="9" font-family="${cv('--fs-font-sans')}" fill="${ink500}" text-anchor="middle">${d.labels[i]}</text>`
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="${c}" opacity="0.88"/>${lab}`
    })
    .join('')

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${grid}${bars}</svg>`
}

function donutChart(w, h, d) {
  const ink500 = cv('--fs-ink-500')
  const ink900 = cv('--fs-ink-900')
  const sunken = cv('--fs-bg-sunken')
  const cols = [cv('--fs-risk-low'), cv('--fs-risk-mid'), cv('--fs-risk-high'), cv('--fs-risk-extreme')]
  const total = d.segs.reduce((a, s) => a + s.v, 0)
  const size = Math.min(h, 150)
  const cx = w * 0.28, cy = h / 2, R = size / 2 - 6, r0 = R - 11

  let a0 = -Math.PI / 2
  let arcs = ''
  d.segs.forEach((s, i) => {
    const a1 = a0 + (s.v / total) * Math.PI * 2
    const p = (ang, rad) => [cx + Math.cos(ang) * rad, cy + Math.sin(ang) * rad]
    const [x1, y1] = p(a0, R), [x2, y2] = p(a1, R)
    const [x3, y3] = p(a1, r0), [x4, y4] = p(a0, r0)
    const large = a1 - a0 > Math.PI ? 1 : 0
    arcs += `<path d="M${x1.toFixed(1)} ${y1.toFixed(1)} A${R} ${R} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} L${x3.toFixed(1)} ${y3.toFixed(1)} A${r0} ${r0} 0 ${large} 0 ${x4.toFixed(1)} ${y4.toFixed(1)} Z" fill="${cols[i]}"/>`
    a0 = a1
  })

  const lx = cx + R + 18
  const legend = d.segs
    .map(
      (s, i) =>
        `<g><rect x="${lx}" y="${cy - 30 + i * 17}" width="7" height="7" rx="2" fill="${cols[i]}"/>` +
        `<text x="${lx + 12}" y="${cy - 24 + i * 17}" font-size="10" font-family="${cv('--fs-font-sans')}" fill="${ink500}">${s.label}</text>` +
        `<text x="${lx + 96}" y="${cy - 24 + i * 17}" font-size="10" font-family="${cv('--fs-font-mono')}" fill="${ink900}" text-anchor="end">${s.v}%</text></g>`
    )
    .join('')

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${sunken}" stroke-width="11"/>
    ${arcs}${legend}
  </svg>`
}

function freqChart(w, h, d) {
  const ink500 = cv('--fs-ink-500')
  const ink700 = cv('--fs-ink-700')
  const sunken = cv('--fs-bg-sunken')
  const vars = { low: cv('--fs-risk-low'), mid: cv('--fs-risk-mid'), high: cv('--fs-risk-high') }
  const max = d.items[0].v
  const rowH = Math.min(h / d.items.length, 30)
  const lx = 56, bx = w - 52, bw = bx - lx

  const rows = d.items
    .map((it, i) => {
      const y = i * rowH + rowH / 2
      const bwid = (it.v / max) * bw
      return (
        `<text x="0" y="${y + 3.5}" font-size="11" font-family="${cv('--fs-font-sans')}" fill="${ink700}">${it.n}</text>` +
        `<rect x="${lx}" y="${y - 2}" width="${bw}" height="4" rx="2" fill="${sunken}"/>` +
        `<rect x="${lx}" y="${y - 2}" width="${bwid.toFixed(1)}" height="4" rx="2" fill="${vars[it.c]}"/>` +
        `<text x="${w}" y="${y + 3.5}" font-size="10" font-family="${cv('--fs-font-mono')}" fill="${ink500}" text-anchor="end">${it.v}</text>`
      )
    })
    .join('')

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${rows}</svg>`
}

/* ============================== 4. 右栏渲染 ============================== */

let railTab = 'history'
const RANK = {
  history: [
    ['楚雄州', '0.58', 'high', 100], ['昆明市', '0.44', 'mid', 76],
    ['普洱市', '0.39', 'mid', 67], ['文山州', '0.31', 'low', 53],
    ['丽江市', '0.22', 'low', 38],
  ],
  predict: [
    ['楚雄州', '0.61', 'high', 100], ['昆明市', '0.47', 'mid', 78],
    ['文山州', '0.42', 'mid', 69], ['临沧市', '0.35', 'low', 57],
    ['丽江市', '0.24', 'low', 39],
  ],
}

function rankHtml(tab) {
  const cvar = { low: 'var(--fs-risk-low)', mid: 'var(--fs-risk-mid)', high: 'var(--fs-risk-high)' }
  return `<div style="display:flex;flex-direction:column;gap:12px">
    <div class="chart-card__hd"><span class="chart-card__t">州市风险排序</span><span class="chart-card__sp"></span><span class="chart-card__n">Top 5</span></div>
    <div class="rank">
      ${RANK[tab]
        .map(
          ([n, i, lv, pct]) => `<div class="rank__r">
            <span class="rank__n">${n}</span>
            <span class="rank__i">${i}</span>
            <span class="rank__b"><i style="width:${pct}%;background:${cvar[lv]}"></i></span>
          </div>`
        )
        .join('')}
    </div>
  </div>`
}

function renderRail() {
  const scroll = $('#railScroll')
  if (!scroll) return
    const four = html.dataset.charts === 'four'
  const seg = $('#railSeg')

  if (four) {
    seg.style.display = 'none'
    scroll.innerHTML = `
      <div class="chart-grid-2">
        <div class="chart-card"><div class="chart-card__hd"><span class="chart-card__t">${CHART_DATA.history.title}</span><span class="chart-card__sp"></span><span class="chart-card__n">${CHART_DATA.history.note}</span></div><div class="chart-box" data-c="line"></div></div>
        <div class="chart-card"><div class="chart-card__hd"><span class="chart-card__t">${CHART_DATA.predict.title}</span><span class="chart-card__sp"></span><span class="chart-card__n">${CHART_DATA.predict.note}</span></div><div class="chart-box" data-c="bar"></div></div>
        <div class="chart-card"><div class="chart-card__hd"><span class="chart-card__t">${CHART_DATA.share.title}</span><span class="chart-card__sp"></span><span class="chart-card__n">${CHART_DATA.share.note}</span></div><div class="chart-box" data-c="donut"></div></div>
        <div class="chart-card"><div class="chart-card__hd"><span class="chart-card__t">${CHART_DATA.freq.title}</span><span class="chart-card__sp"></span><span class="chart-card__n">${CHART_DATA.freq.note}</span></div><div class="chart-box" data-c="freq"></div></div>
      </div>`
    drawIn($('[data-c="line"]', scroll), (bw, bh) => lineChart(bw, bh, CHART_DATA.history))
    drawIn($('[data-c="bar"]', scroll), (bw, bh) => barChart(bw, bh, CHART_DATA.predict))
    drawIn($('[data-c="donut"]', scroll), (bw, bh) => donutChart(bw, bh, CHART_DATA.share))
    drawIn($('[data-c="freq"]', scroll), (bw, bh) => freqChart(bw, bh, CHART_DATA.freq))
    return
  }

  seg.style.display = ''
  const isH = railTab === 'history'
  scroll.innerHTML = `
    <div class="chart-card">
      <div class="chart-card__hd">
        <span class="chart-card__t">${isH ? CHART_DATA.history.title : CHART_DATA.predict.title}</span>
        <span class="chart-card__sp"></span>
        <span class="chart-card__n">${isH ? CHART_DATA.history.note : CHART_DATA.predict.note}</span>
      </div>
      <div class="chart-box" data-c="main"></div>
    </div>
    ${rankHtml(railTab)}`
  drawIn($('[data-c="main"]', scroll), (bw, bh) =>
    isH ? lineChart(bw, bh, CHART_DATA.history) : barChart(bw, bh, CHART_DATA.predict)
  )
}

function drawIn(el, fn) {
  if (!el) return
  const w = Math.max(el.clientWidth, 80)
  const h = Math.max(el.clientHeight, 60)
  el.innerHTML = fn(w, h)
}

/* ============================== 5. 登录页视觉面 ============================== */

function renderLogin() {
  const box = $('#loginBg')
  if (!box) return
  const ink400 = cv('--fs-ink-400')
  const accent = cv('--fs-accent')
  const c = [cv('--fs-risk-low'), cv('--fs-risk-mid'), cv('--fs-risk-high'), cv('--fs-risk-extreme')]

  let lines = ''
  const seeds = [{ x: 300, y: 620, s: 0.5 }, { x: 720, y: 240, s: 2.4 }]
  seeds.forEach((sd) => {
    for (let i = 1; i <= 12; i++) {
      lines += `<path d="${contour(sd.x, sd.y, i * 17, sd.s + i * 0.28)}" fill="none" stroke="${ink400}" stroke-width="0.7" opacity="0.4"/>`
    }
  })
  const dots = [
    [420, 300, 3], [505, 355, 2], [560, 250, 3], [640, 400, 2], [700, 300, 1],
    [350, 450, 2], [480, 520, 1], [610, 530, 2], [760, 460, 1], [290, 240, 1],
  ]
    .map(([x, y, lv]) => `<circle cx="${x}" cy="${y}" r="${lv >= 3 ? 4 : 3}" fill="${c[lv - 1]}"/>`)
    .join('')

  box.innerHTML = `<svg viewBox="0 0 840 900" preserveAspectRatio="xMidYMid slice">
    ${lines}${dots}
    <circle cx="505" cy="355" r="14" fill="none" stroke="${accent}" stroke-width="1" opacity="0.55"/>
  </svg>`
}

/* ============================== 6. 屏幕切换 / 入场动效 ============================== */

let currentScreen = 'dashboard'

const KNOWN = ['dashboard', 'smartquery', 'kb', 'agent', 'report', 'admin', 'profile', 'login', 'kit']

function showScreen(name) {
  if (!KNOWN.includes(name)) return   // 原型只实现 5 张屏，其余导航项保持当前屏
  currentScreen = name
  const app = $('#app')
  app.dataset.screen = name
  $$('.screen').forEach((s) => s.classList.toggle('is-on', s.dataset.screen === name))
  $$('.chrome-bar .seg-btn[data-screen]').forEach((b) => b.classList.toggle('is-on', b.dataset.screen === name))
  $$('.nav-item').forEach((a) => a.classList.toggle('is-on', a.dataset.screen === name))

  // 入场分组推进（60–80ms stagger）
  if (html.dataset.motion === 'on') {
    $$('.screen.is-on .anim').forEach((el, i) => {
      el.style.animation = 'none'
      void el.offsetWidth
      el.style.animation = ''
      el.style.setProperty('--d', `${i * 70}ms`)
    })
  }

  if (name === 'dashboard') { renderMap(); renderRail(); runCountUp() }
  if (name === 'agent') runStream()
  if (name === 'login') renderLogin()
  if (name === 'kit') renderRail()
}

document.addEventListener('click', (e) => {
  const nav = e.target.closest('[data-screen]')
  if (nav && !nav.classList.contains('tw-opt')) {
    e.preventDefault()
    showScreen(nav.dataset.screen)
  }
})

/* ============================== 7. KPI 数字动画 ============================== */

function runCountUp() {
  $$('.kpi__v[data-count]').forEach((el) => {
    const target = parseInt(el.dataset.count, 10)
    if (html.dataset.motion !== 'on') { el.textContent = target.toLocaleString(); return }
    const dur = 900
    const t0 = performance.now()
    const tick = (t) => {
      const p = Math.min((t - t0) / dur, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      el.textContent = Math.round(target * eased).toLocaleString()
      if (p < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

/* ============================== 8. 报告流式打字机 ============================== */

const STREAM_TEXT = `一、总体研判

2026 年 10 月 1 日至 10 月 30 日，楚雄彝族自治州累计监测到火点 412 处，较上月同期上升 18.6%，火险综合指数由 0.42 升至 0.58，整体处于较高风险区间。

从空间分布看，火点高度集中于元谋、永仁、大姚三县，合计占全州火点总数的 63.4%，与干热河谷地貌高度重合。`

let streamTimer = null
function runStream() {
  const el = $('#streamBody')
  if (!el) return
  clearInterval(streamTimer)
  if (html.dataset.motion !== 'on') {
    el.innerHTML = STREAM_TEXT + '<span class="caret"></span>'
    return
  }
  let i = 0
  el.innerHTML = '<span class="caret"></span>'
  streamTimer = setInterval(() => {
    i += 2
    el.innerHTML =
      STREAM_TEXT.slice(0, i).replace(/\n/g, '\n') + '<span class="caret"></span>'
    if (i >= STREAM_TEXT.length) clearInterval(streamTimer)
  }, 18)
}

/* ============================== 9. Tweaks ============================== */

const KEYS = ['theme', 'accent', 'serif', 'sidebar', 'charts', 'radius', 'density', 'motion']

$$('.tw-opts').forEach((group) => {
  group.addEventListener('click', (e) => {
    const b = e.target.closest('.tw-opt')
    if (!b) return
    const key = group.dataset.key
    $$('.tw-opt', group).forEach((x) => x.classList.toggle('is-on', x === b))
    html.dataset[key] = b.dataset.val
    afterTweak(key)
  })
})

function afterTweak(key) {
  if (key === 'theme') {
    const dark = html.dataset.theme === 'dark'
    $('#sideTheme use').setAttribute('href', dark ? '#i-sun' : '#i-moon')
    localStorage.setItem('fs-v0-theme', html.dataset.theme)
  }
  if (key === 'theme' || key === 'accent' || key === 'charts') {
    renderMap(); renderRail(); renderLogin()
  }
  if (key === 'motion') {
    if (html.dataset.motion === 'on') { runCountUp(); if (currentScreen === 'agent') runStream() }
    else { runCountUp(); if (currentScreen === 'agent') runStream() }
  }
}

$('#tweaksFab').addEventListener('click', () => $('#tweaksPanel').classList.toggle('is-open'))
$('#tweaksClose').addEventListener('click', () => $('#tweaksPanel').classList.remove('is-open'))

$('#chromeTheme').addEventListener('click', () => {
  const next = html.dataset.theme === 'dark' ? 'light' : 'dark'
  html.dataset.theme = next
  $$('.tw-opts[data-key="theme"] .tw-opt').forEach((x) =>
    x.classList.toggle('is-on', x.dataset.val === next))
  afterTweak('theme')
})

$('#sideTheme').addEventListener('click', (e) => {
  e.preventDefault(); e.stopPropagation()
  $('#chromeTheme').click()
})

/* 火情识别抽屉 */
$('#visionTab').addEventListener('click', (e) => {
  e.stopPropagation()
  $('#app').dataset.vision = 'open'
})
$('#visionClose').addEventListener('click', (e) => {
  e.stopPropagation()
  $('#app').dataset.vision = 'closed'
})

/* 右栏 tab */
$('#railSeg').addEventListener('click', (e) => {
  const b = e.target.closest('.seg__i')
  if (!b) return
  $$('#railSeg .seg__i').forEach((x) => x.classList.toggle('is-on', x === b))
  railTab = b.dataset.tab
  renderRail()
})

/* ============================== 10. 其他 ============================== */

// 顶栏时钟
setInterval(() => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  const el = $('#dashClock')
  if (el) el.textContent =
    `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}, 1000)

// 尺寸变化时重绘图表
new ResizeObserver(() => {
  if (currentScreen === 'dashboard' || currentScreen === 'kit') renderRail()
}).observe($('#railScroll'))

// 恢复上次主题
const saved = localStorage.getItem('fs-v0-theme')
if (saved) {
  html.dataset.theme = saved
  $$('.tw-opts[data-key="theme"] .tw-opt').forEach((x) => x.classList.toggle('is-on', x.dataset.val === saved))
}

// 初始渲染
renderMap()
renderRail()
renderLogin()
showScreen('dashboard')
