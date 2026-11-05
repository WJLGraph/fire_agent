<script setup>
/**
 * AgentNetGL — 智能体网络场景（技术页；three 动态导入，独立 chunk）
 *
 * 场景构成：
 *   - 7 节点：Orchestrator 编排中枢居中，DataAgent/GisAgent/RagAgent/ReportAgent/Reviewer
 *     五方环绕，HITL 人工闸口位于链路末端高位（与七环节流水线口径一致）
 *   - 边：编排调用（中枢 → 各 Agent，弱发丝）+ 主流水线（数据→分析→检索→成文→评审→人工）
 *     其中「数据→空间分析」为串行流，「空间分析 / 检索 → 成文」为并行汇合；查询与检索互不依赖
 *   - 数据包：每条边上一个小光点缓慢流动（additive，不全屏闪烁）
 *   - 交互：hover 节点高亮其邻边 + DOM 信息条显示角色职责；点击节点跳转 /welcome/workflow
 *   - 整组缓慢摆动 ±6°；移动端静态构图、数据包半速
 *
 * 工程纪律同 TerrainGL/HeroGL：DPR≤1.5、IO 离屏暂停、visibilitychange 暂停、
 * 卸载 dispose + loseContext、motionAllowed=false / WebGL 不可用 → 静态 SVG 网络图回退。
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { motionAllowed } from '@/composables/useMotionPreference'

const router = useRouter()
const theme = useThemeStore()
const wrapRef = ref(null)
const canvasRef = ref(null)
const fallback = ref(false)
const labels = ref([])
const hovered = ref(null) // 当前 hover 节点 key（DOM 信息条）

const NODES = [
  { key: 'ORCH', name: 'Orchestrator', zh: '编排中枢', desc: '拆解任务意图，为固定步骤生成描述', pos: [0, 0.12, 0] },
  { key: 'DATA', name: 'DataAgent', zh: '数据', desc: '查询历史火点与预测火险，按州市聚合', pos: [-2.2, 0, 0.9] },
  { key: 'GIS', name: 'GisAgent', zh: '空间分析', desc: '热点统计、行政区聚合与风险分布分析', pos: [-1.1, 0, -1.6] },
  { key: 'RAG', name: 'RagAgent', zh: '检索', desc: '防火文档向量检索，为报告补充依据', pos: [1.1, 0, -1.6] },
  { key: 'REPORT', name: 'ReportAgent', zh: '成文', desc: '汇总数据与结论生成报告草稿', pos: [2.2, 0, 0.9] },
  { key: 'REVIEW', name: 'Reviewer', zh: '评审', desc: '质量核查三态：通过 / 退回重写 / 降级转人工', pos: [0.9, 0, 2.3] },
  { key: 'HITL', name: 'HITL', zh: '人工闸口', desc: '值班员审批通过后报告定稿归档', pos: [1.7, 0.95, 3.1] },
]
/* 编排调用（弱发丝） + 主流水线（数据流，带数据包） */
const CALL_EDGES = [['ORCH', 'DATA'], ['ORCH', 'GIS'], ['ORCH', 'RAG'], ['ORCH', 'REPORT'], ['ORCH', 'REVIEW']]
const FLOW_EDGES = [['DATA', 'GIS'], ['GIS', 'REPORT'], ['RAG', 'REPORT'], ['REPORT', 'REVIEW'], ['REVIEW', 'HITL']]

let THREE = null
let renderer = null
let scene = null
let camera = null
let group = null
let raycaster = null
let nodeMeshes = []
let edgeRecs = [] // { line, a, b, flow, baseOpacity }
let packets = [] // { mesh, a, b, speed, phase }
let raf = 0
let io = null
let running = false
let disposed = false
let isMobile = false
const clock = { t0: 0, prev: 0 }
const nodeByKey = {}

const hexToVec = (hex, fb) => {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim())
  if (!m) return fb
  const n = parseInt(m[1], 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}
const tk = (name, fb) => hexToVec(getComputedStyle(document.documentElement).getPropertyValue(name).trim(), fb)

const buildScene = () => {
  const wrap = wrapRef.value
  renderer = new THREE.WebGLRenderer({ canvas: canvasRef.value, alpha: true, antialias: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.setSize(wrap.clientWidth || 1, wrap.clientHeight || 1, false)

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(40, (wrap.clientWidth || 1) / (wrap.clientHeight || 1), 0.1, 100)
  camera.position.set(0, 3.6, 6.6)
  camera.lookAt(0, 0, 0.4)

  group = new THREE.Group()
  scene.add(group)
  raycaster = new THREE.Raycaster()

  const nodeColor = tk('--fs-ink-900', [0.85, 0.87, 0.9])
  const hitlColor = tk('--fs-accent', [0.75, 0.45, 0.25])
  const lineColor = tk('--fs-hairline-strong', [0.4, 0.42, 0.46])
  const packColor = tk('--fs-accent', [0.75, 0.45, 0.25])

  /* 节点：小方块 + 光晕壳 */
  const boxGeo = new THREE.BoxGeometry(0.22, 0.22, 0.22)
  const haloGeo = new THREE.BoxGeometry(0.34, 0.34, 0.34)
  NODES.forEach((n) => {
    const isHitl = n.key === 'HITL'
    const mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(...(isHitl ? hitlColor : nodeColor)) })
    const mesh = new THREE.Mesh(boxGeo, mat)
    mesh.position.set(...n.pos)
    mesh.userData.key = n.key
    const haloMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(...(isHitl ? hitlColor : nodeColor)),
      transparent: true, opacity: 0.14, blending: THREE.AdditiveBlending, depthWrite: false,
    })
    const halo = new THREE.Mesh(haloGeo, haloMat)
    mesh.add(halo)
    group.add(mesh)
    nodeMeshes.push(mesh)
    nodeByKey[n.key] = { ...n, mesh, mat, haloMat }
  })

  /* 边 */
  const addEdge = (a, b, flow) => {
    const pa = new THREE.Vector3(...nodeByKey[a].pos)
    const pb = new THREE.Vector3(...nodeByKey[b].pos)
    const geo = new THREE.BufferGeometry().setFromPoints([pa, pb])
    const baseOpacity = flow ? 0.5 : 0.22
    const mat = new THREE.LineBasicMaterial({
      color: new THREE.Color(...lineColor),
      transparent: true, opacity: baseOpacity,
    })
    const line = new THREE.Line(geo, mat)
    group.add(line)
    edgeRecs.push({ line, a, b, flow, baseOpacity, mat })

    /* 数据包：每条流水边一个小光点，缓慢流动 */
    const pgeo = new THREE.SphereGeometry(0.045, 6, 6)
    const pmat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(...packColor),
      transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false,
    })
    const mesh = new THREE.Mesh(pgeo, pmat)
    group.add(mesh)
    packets.push({ mesh, pa, pb, speed: flow ? 0.16 : 0.08, phase: ((a.charCodeAt(0) + b.charCodeAt(0)) % 10) / 10 })
  }
  CALL_EDGES.forEach(([a, b]) => addEdge(a, b, false))
  FLOW_EDGES.forEach(([a, b]) => addEdge(a, b, true))

  updateLabels(true)
}

/* ---------- DOM label 投影 ---------- */
const updateLabels = (force = false) => {
  if (!camera || !wrapRef.value || (!running && !force)) return
  const w = wrapRef.value.clientWidth || 1
  const h = wrapRef.value.clientHeight || 1
  labels.value = NODES.map((n) => {
    const v = new THREE.Vector3(...n.pos)
    v.y += 0.3
    v.applyMatrix4(group.matrixWorld).project(camera)
    return { key: n.key, name: n.name, x: (v.x * 0.5 + 0.5) * w, y: (-v.y * 0.5 + 0.5) * h, v: v.z < 1 }
  })
}

/* ---------- hover / 点击 ---------- */
let hoverKey = null
const applyHover = (key) => {
  if (key === hoverKey) return
  hoverKey = key
  hovered.value = key
  Object.values(nodeByKey).forEach((r) => {
    const on = r.key === key
    r.mesh.scale.setScalar(on ? 1.35 : 1)
    r.haloMat.opacity = on ? 0.4 : 0.14
  })
  edgeRecs.forEach((e) => {
    const on = key && (e.a === key || e.b === key)
    e.mat.opacity = on ? 0.95 : e.baseOpacity
  })
  const wrap = wrapRef.value
  if (wrap) wrap.style.cursor = key ? 'pointer' : ''
}
const onPointerMove = (e) => {
  if (!renderer || disposed) return
  const rect = wrapRef.value?.getBoundingClientRect()
  if (!rect) return
  const inside = e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom
  if (!inside) { applyHover(null); return }
  if (e.pointerType === 'touch') return
  const ndc = {
    x: ((e.clientX - rect.left) / rect.width) * 2 - 1,
    y: -((e.clientY - rect.top) / rect.height) * 2 + 1,
  }
  raycaster.setFromCamera(ndc, camera)
  // recursive：halo 光晕壳是节点子网格，命中 halo 时向上取父节点 key（放大有效命中面）
  const hits = raycaster.intersectObjects(nodeMeshes, true)
  const obj = hits[0]?.object
  applyHover(obj ? (obj.userData.key || obj.parent?.userData.key || null) : null)
}
const onClick = (e) => {
  if (hoverKey) router.push('/welcome/workflow')
}

/* ---------- 渲染循环 ---------- */
const tick = (ts) => {
  if (!running || disposed) return
  if (!clock.t0) { clock.t0 = ts; clock.prev = ts }
  const t = (ts - clock.t0) / 1000

  // 整组缓慢摆动 ±6°；移动端静态构图
  if (!isMobile) group.rotation.y = Math.sin(t * 0.09) * 0.105

  // 数据包流动（移动端半速）
  const sp = isMobile ? 0.5 : 1
  packets.forEach((p) => {
    const k = (t * p.speed * sp + p.phase) % 1
    p.mesh.position.lerpVectors(p.pa, p.pb, k)
    p.mesh.material.opacity = 0.35 + 0.55 * Math.sin(k * Math.PI)
  })

  group.updateMatrixWorld()
  renderer.render(scene, camera)
  updateLabels()
  raf = requestAnimationFrame(tick)
}
const start = () => { if (running || disposed || !renderer) return; running = true; raf = requestAnimationFrame(tick) }
const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = 0 }
const onVis = () => { document.hidden ? stop() : start() }
const onResize = () => {
  const wrap = wrapRef.value
  if (!wrap || !renderer) return
  const w = wrap.clientWidth || 1, h = wrap.clientHeight || 1
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  updateLabels(true)
}

watch(() => theme.mode, () => {
  // 主题切换：重建材质色（节点/边/包全部来自令牌）
  if (!scene) return
  const nodeColor = tk('--fs-ink-900', [0.85, 0.87, 0.9])
  const hitlColor = tk('--fs-accent', [0.75, 0.45, 0.25])
  Object.values(nodeByKey).forEach((r) => {
    const c = r.key === 'HITL' ? hitlColor : nodeColor
    r.mat.color.setRGB(...c)
    r.haloMat.color.setRGB(...c)
  })
  const lc = tk('--fs-hairline-strong', [0.4, 0.42, 0.46])
  edgeRecs.forEach((e) => e.mat.color.setRGB(...lc))
  const pc = tk('--fs-accent', [0.75, 0.45, 0.25])
  packets.forEach((p) => p.mesh.material.color.setRGB(...pc))
})

onMounted(async () => {
  const wrap = wrapRef.value
  if (!wrap) return
  isMobile = window.matchMedia('(max-width: 768px)').matches
  const glOk = !!document.createElement('canvas').getContext('webgl')
  if (!motionAllowed.value || !glOk) { fallback.value = true; return }
  try {
    THREE = await import('three')
    if (disposed) return
    buildScene()
  } catch {
    fallback.value = true
    return
  }
  window.addEventListener('resize', onResize, { passive: true })
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  wrap.addEventListener('click', onClick)
  document.addEventListener('visibilitychange', onVis)
  io = new IntersectionObserver((es) => {
    es.forEach((e) => (e.isIntersecting ? start() : stop()))
  }, { threshold: 0.02 })
  io.observe(wrap)
  start()
})

onBeforeUnmount(() => {
  disposed = true
  stop()
  io?.disconnect(); io = null
  window.removeEventListener('resize', onResize)
  window.removeEventListener('pointermove', onPointerMove)
  wrapRef.value?.removeEventListener('click', onClick)
  document.removeEventListener('visibilitychange', onVis)
  if (scene) {
    scene.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material) o.material.dispose()
    })
    scene.clear()
    scene = null
  }
  if (renderer) {
    renderer.dispose()
    const lose = renderer.getContext().getExtension('WEBGL_lose_context')
    lose && lose.loseContext()
    renderer = null
  }
  THREE = null
})
</script>

<template>
  <div ref="wrapRef" class="anet">
    <canvas v-show="!fallback" ref="canvasRef" class="anet__canvas" aria-hidden="true"></canvas>

    <!-- 节点名 DOM 覆盖层 -->
    <div v-if="!fallback" class="anet__labels" aria-hidden="true">
      <span
        v-for="l in labels"
        :key="l.key"
        class="anet__label"
        :class="{ 'is-on': hovered === l.key }"
        :style="{ transform: `translate(${l.x}px, ${l.y}px)`, opacity: l.v ? undefined : 0 }"
      >{{ l.name }}</span>
    </div>

    <!-- hover 信息条：角色与职责（DOM，可读可访问） -->
    <div v-if="!fallback" class="anet__info" aria-live="polite">
      <template v-if="hovered && nodeByKey[hovered]">
        <b class="qt-num">{{ nodeByKey[hovered].name }}</b>
        <span class="pg-cap">{{ nodeByKey[hovered].zh }} · {{ nodeByKey[hovered].desc }}</span>
        <span class="anet__hint pg-cap">点击前往工作流 →</span>
      </template>
      <span v-else class="pg-cap">hover 节点查看职责 · 点击定位到工作流</span>
    </div>

    <!-- 静态回退：SVG 网络图 -->
    <svg v-if="fallback" class="anet__fallback" viewBox="0 0 640 400" role="img" aria-label="智能体网络示意：编排中枢连接五个智能体，链路末端为人工闸口">
      <g stroke="var(--fs-hairline-strong)" stroke-width="1" opacity="0.5">
        <line x1="320" y1="200" x2="120" y2="260" /><line x1="320" y1="200" x2="200" y2="80" />
        <line x1="320" y1="200" x2="440" y2="80" /><line x1="320" y1="200" x2="520" y2="260" />
        <line x1="320" y1="200" x2="400" y2="330" />
        <line x1="120" y1="260" x2="200" y2="80" /><line x1="200" y1="80" x2="440" y2="80" />
        <line x1="440" y1="80" x2="520" y2="260" /><line x1="520" y1="260" x2="400" y2="330" />
        <line x1="400" y1="330" x2="470" y2="60" stroke-dasharray="4 4" />
      </g>
      <g font-family="var(--fs-font-mono)" font-size="11" fill="var(--fs-ink-500)">
        <rect x="308" y="188" width="24" height="24" fill="var(--fs-ink-900)" /><text x="282" y="222">Orchestrator</text>
        <rect x="110" y="250" width="18" height="18" fill="var(--fs-ink-900)" /><text x="96" y="284">DataAgent</text>
        <rect x="191" y="70" width="18" height="18" fill="var(--fs-ink-900)" /><text x="180" y="62">GisAgent</text>
        <rect x="431" y="70" width="18" height="18" fill="var(--fs-ink-900)" /><text x="420" y="62">RagAgent</text>
        <rect x="511" y="250" width="18" height="18" fill="var(--fs-ink-900)" /><text x="492" y="284">ReportAgent</text>
        <rect x="391" y="320" width="18" height="18" fill="var(--fs-ink-900)" /><text x="376" y="354">Reviewer</text>
        <rect x="461" y="50" width="18" height="18" fill="var(--fs-accent)" /><text x="466" y="42">HITL</text>
      </g>
    </svg>

    <!-- 无障碍文本 -->
    <ul class="sr-only">
      <li v-for="n in NODES" :key="`sr-${n.key}`">{{ n.name }}（{{ n.zh }}）：{{ n.desc }}</li>
    </ul>
  </div>
</template>

<style scoped>
.anet {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.anet__canvas,
.anet__fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}
.anet__labels {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.anet__label {
  position: absolute;
  top: 0;
  left: 0;
  margin-left: 8px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--fs-ink-500);
  text-shadow: 0 1px 2px var(--fs-bg-canvas);
  will-change: transform;
  transition: color 0.16s var(--fs-ease);
}
.anet__label.is-on { color: var(--fs-accent); }
.anet__info {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 12px;
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--fs-hairline);
  pointer-events: none;
}
.anet__info b { color: var(--fs-ink-900); font-size: 12px; letter-spacing: 0.06em; }
.anet__hint { margin-left: auto; color: var(--fs-accent); }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
