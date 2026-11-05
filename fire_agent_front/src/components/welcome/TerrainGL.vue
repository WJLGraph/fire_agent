<script setup>
/**
 * TerrainGL — 云南火险地形宽幅场景（首页中段；three 动态导入，独立 chunk）
 *
 * 场景构成（真实数据驱动，零素材）：
 *   1. 16 州市真实行政边界（@/assets/Yunnan_border.json，与作战大屏同源）
 *      → ExtrudeGeometry 低挤出板块，ShaderMaterial：深色金属底 + 发丝州界色 +
 *        缓慢扫描亮带（低对比，深色底金属感）
 *   2. 16 州市中心点（utils/cityCenter.js 真实坐标）竖直光柱 + 地面脉冲环，
 *      颜色严格取自 --fs-risk-1..5 令牌（等级为确定性语义示意，图注已声明非实时）
 *   3. 相机：缓慢环绕 ±7° + 滚动轻微推进 + 指针 ≤8px 等效视差（document 级判定）
 *   4. 州市名 DOM 覆盖层（canvas 内不画文字；列表同时以无障碍文本存在）
 *
 * 工程纪律（与 HeroGL 一致）：
 *   - DPR ≤ 1.5；IntersectionObserver 离屏暂停；visibilitychange 暂停
 *   - 卸载全量 dispose + loseContext；motionAllowed=false / WebGL 不可用 → 静态 SVG 回退
 *   - 颜色全部运行时读 CSS 令牌，主题切换即时换色
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { motionAllowed } from '@/composables/useMotionPreference'
import { CITY_CENTER_MAP } from '@/utils/cityCenter'

const theme = useThemeStore()
const wrapRef = ref(null)
const canvasRef = ref(null)
const fallback = ref(false)
const labels = ref([]) // [{ name, x, y, v }] DOM 覆盖层

let THREE = null
let renderer = null
let scene = null
let camera = null
let group = null
let blockMat = null
let pillarMats = []
let ringMats = []
let bloomComposer = null
let bloomPass = null
let bloomCam = null
let bloomQuad = null
let bloomQuadScene = null
let bloomQuadCam = null
let postEnabled = true
let emberMat = null
let emberCount = 0
const BLOOM_LAYER = 1
let raf = 0
let io = null
let running = false
let disposed = false
let progress = 0
const clock = { t0: 0, prev: 0 }
const cityWorld = [] // { name, v3 } 投影用

/* ---------- 令牌取色 ---------- */
const hexToVec = (hex, fb) => {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim())
  if (!m) return fb
  const n = parseInt(m[1], 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}
const tk = (name, fb) => hexToVec(getComputedStyle(document.documentElement).getPropertyValue(name).trim(), fb)

/* ---------- 着色器 ---------- */
const BLOCK_VERT = `
varying vec3 vWorld;
varying vec2 vUv;
void main(){
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  vUv = uv;
  gl_Position = projectionMatrix * viewMatrix * w;
}
`
/* 板块：深色金属底 + 顶面发丝线提亮 + 扫描亮带（沿南北向缓慢移动） */
const BLOCK_FRAG = `
precision highp float;
varying vec3 vWorld;
varying vec2 vUv;
uniform vec3 uBase;
uniform vec3 uLine;
uniform vec3 uAccent;
uniform float uTime;
uniform vec2 uPointer;
uniform float uProgress;
void main(){
  // 顶面（uv 有效区）比侧面略亮，形成板块体积感
  vec3 col = uBase * (0.92 + vUv.y * 0.10);
  // 扫描亮带：低频、低对比；指针纵向位置轻微影响相位（≤0.01）
  float scan = smoothstep(0.05, 0.0, abs(fract(vWorld.z * 0.08 - uTime * 0.02 + uPointer.y * 0.01) - 0.5) - 0.42);
  col += uAccent * scan * 0.08;
  // 滚动雾化：随进度极弱压暗（≤6%），不影响文字与读数
  col *= 1.0 - uProgress * 0.06;
  // 边缘发丝提亮
  float rim = smoothstep(0.48, 0.5, abs(vUv.x - 0.5)) + smoothstep(0.48, 0.5, abs(vUv.y - 0.5));
  col = mix(col, uLine, clamp(rim, 0.0, 1.0) * 0.10);
  gl_FragColor = vec4(col, 1.0);
}
`
/* 光柱：底部实、顶端淡出 */
const PILLAR_VERT = `
varying vec2 vUv;
void main(){
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`
const PILLAR_FRAG = `
precision mediump float;
varying vec2 vUv;
uniform vec3 uColor;
uniform float uTime;
uniform float uPhase;
void main(){
  float a = (1.0 - vUv.y) * 0.55;
  a *= 0.75 + 0.25 * sin(uTime * 1.6 + uPhase); // 慢呼吸
  gl_FragColor = vec4(uColor, a * smoothstep(0.0, 0.08, vUv.y));
}
`
/* 脉冲环：扩散 + 淡出循环 */
const RING_FRAG = `
precision mediump float;
varying vec2 vUv;
uniform vec3 uColor;
uniform float uTime;
uniform float uPhase;
void main(){
  float d = distance(vUv, vec2(0.5)) * 2.0; // 0..1
  float wave = fract(uTime * 0.22 + uPhase);
  float ring = smoothstep(0.06, 0.0, abs(d - wave * 0.96));
  gl_FragColor = vec4(uColor, ring * (1.0 - wave) * 0.5);
}
`
/* 火星粒子：单次 Points + 顶点着色器上升淡出（GPU 单 pass，无 CPU 逐帧写矩阵） */
const EMBER_VERT = `
precision mediump float;
attribute float aSeed;
attribute float aSpeed;
attribute float aPhase;
uniform float uTime;
uniform float uOpacity;
varying float vA;
void main(){
  float life = fract(uTime * aSpeed + aPhase);
  vec3 p = position;
  p.y += life * 0.85;
  p.x += sin(uTime * 0.35 + aSeed * 6.28) * 0.025 * life;
  p.z += cos(uTime * 0.30 + aSeed * 6.28) * 0.025 * life;
  vA = (1.0 - life) * smoothstep(0.0, 0.18, life) * uOpacity;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = (1.6 + aSeed * 2.2) * (7.0 / -mv.z);
  gl_Position = projectionMatrix * mv;
}
`
const EMBER_FRAG = `
precision mediump float;
varying float vA;
uniform vec3 uColor;
void main(){
  vec2 d = gl_PointCoord - 0.5;
  if (length(d) > 0.5) discard;
  float a = (1.0 - length(d) * 2.0) * vA;
  gl_FragColor = vec4(uColor, a * 0.55);
}
`
/* ---------- 确定性示意等级（mulberry32；图注声明「示意 · 非实时」） ---------- */
const levelOf = (name, i) => {
  let seed = 20261103 + i * 131
  seed |= 0; seed = (seed + 0x6D2B79F5) | 0
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
  const r = ((t ^ (t >>> 14)) >>> 0) / 4294967296
  return r < 0.36 ? 1 : r < 0.58 ? 2 : r < 0.76 ? 3 : r < 0.9 ? 4 : 5
}
const cityList = Object.entries(CITY_CENTER_MAP).map(([name, lngLat], i) => ({
  name, lngLat, level: levelOf(name, i),
}))

/* ---------- 火星粒子（仅桌面；低核设备降量；off/移动端不创建） ---------- */
const createEmbers = (cities) => {
  const cores = navigator.hardwareConcurrency || 8
  const count = cores <= 4 ? 3000 : 8000
  let seed = 20261103
  const rnd = () => {
    seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const pos = new Float32Array(count * 3)
  const aSeed = new Float32Array(count)
  const aSpeed = new Float32Array(count)
  const aPhase = new Float32Array(count)
  for (let i = 0; i < count; i++) {
    const c = cities[Math.floor(rnd() * cities.length)]
    pos[i * 3] = c.v3.x + (rnd() - 0.5) * 0.55
    pos[i * 3 + 1] = 0.26 + rnd() * 0.05
    pos[i * 3 + 2] = c.v3.z + (rnd() - 0.5) * 0.55
    aSeed[i] = rnd()
    aSpeed[i] = 0.16 + rnd() * 0.22
    aPhase[i] = rnd()
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.setAttribute('aSeed', new THREE.BufferAttribute(aSeed, 1))
  geo.setAttribute('aSpeed', new THREE.BufferAttribute(aSpeed, 1))
  geo.setAttribute('aPhase', new THREE.BufferAttribute(aPhase, 1))
  emberMat = new THREE.ShaderMaterial({
    vertexShader: EMBER_VERT,
    fragmentShader: EMBER_FRAG,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Color(...tk('--fs-risk-4', [0.8, 0.45, 0.2])) },
      uOpacity: { value: 0.42 },
    },
  })
  const points = new THREE.Points(geo, emberMat)
  points.frustumCulled = false
  group.add(points)
  emberCount = count
}

/* ---------- 场景装配 ---------- */
const buildScene = (border) => {
  const c = canvasRef.value
  const wrap = wrapRef.value
  renderer = new THREE.WebGLRenderer({ canvas: c, alpha: true, antialias: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.setSize(wrap.clientWidth || 1, wrap.clientHeight || 1, false)

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(42, (wrap.clientWidth || 1) / (wrap.clientHeight || 1), 0.1, 100)
  camera.position.set(0, 8.2, 8.6)
  camera.lookAt(0, 0, 0.2)

  group = new THREE.Group()
  scene.add(group)

  /* Mercator 投影 + 归一化（与 map3dGeo.buildProjection 同法，精简内联以免静态引入 three） */
  let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
  const scan = (co) => {
    if (typeof co[0] === 'number') {
      if (co[0] < minLng) minLng = co[0]
      if (co[0] > maxLng) maxLng = co[0]
      if (co[1] < minLat) minLat = co[1]
      if (co[1] > maxLat) maxLat = co[1]
      return
    }
    co.forEach(scan)
  }
  border.features.forEach((f) => scan(f.geometry.coordinates))
  const R = 6378137
  const c0 = (minLng + maxLng) / 2
  const c1 = (minLat + maxLat) / 2
  const raw = ([lng, lat]) => [
    R * ((lng - c0) * Math.PI) / 180,
    R * Math.log(Math.tan(Math.PI / 4 + ((lat - c1) * Math.PI) / 360)),
  ]
  const cs = [raw([minLng, minLat]), raw([maxLng, minLat]), raw([minLng, maxLat]), raw([maxLng, maxLat])]
  const xs = cs.map((p) => p[0]), ys = cs.map((p) => p[1])
  const s = 11 / Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys))
  const proj = ([lng, lat]) => { const [x, y] = raw([lng, lat]); return [x * s, y * s] }

  /* 板块材质（统一一份，扫描带共享 uTime） */
  blockMat = new THREE.ShaderMaterial({
    vertexShader: BLOCK_VERT,
    fragmentShader: BLOCK_FRAG,
    uniforms: {
      uBase: { value: new THREE.Color(0.08, 0.09, 0.11) },
      uLine: { value: new THREE.Color(0.7, 0.74, 0.78) },
      uAccent: { value: new THREE.Color(0.55, 0.58, 0.62) },
      uTime: { value: 0 },
      uPointer: { value: new THREE.Vector2(0.5, 0.5) },
      uProgress: { value: 0 },
    },
  })

  const riskColor = (lv) => new THREE.Color(...tk(`--fs-risk-${lv}`, [0.5, 0.5, 0.5]))

  /* 16 州市板块 + 州界轮廓线 */
  const lineMat = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.5 })
  lineMat.color = new THREE.Color(...tk('--fs-hairline-strong', [0.4, 0.42, 0.46]))
  border.features.forEach((f) => {
    const g = f.geometry
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : []
    polys.forEach((rings) => {
      const shape = new THREE.Shape(rings[0].map((co) => { const [x, y] = proj(co); return new THREE.Vector2(x, y) }))
      for (let i = 1; i < rings.length; i++) {
        shape.holes.push(new THREE.Path(rings[i].map((co) => { const [x, y] = proj(co); return new THREE.Vector2(x, y) })))
      }
      const geo = new THREE.ExtrudeGeometry(shape, { depth: 0.22, bevelEnabled: false })
      geo.rotateX(-Math.PI / 2) // 局部 +Y(北) → 世界 -Z，北朝屏幕上方
      group.add(new THREE.Mesh(geo, blockMat))
      // 州界轮廓（外环）发丝线
      const pts = rings[0].map((co) => { const [x, y] = proj(co); return new THREE.Vector3(x, 0.24, -y) })
      const lgeo = new THREE.BufferGeometry().setFromPoints(pts)
      group.add(new THREE.LineLoop(lgeo, lineMat))
    })
  })

  /* 16 州市光柱 + 脉冲环 */
  cityList.forEach((city) => {
    const [x, y] = proj(city.lngLat)
    const color = riskColor(city.level)
    const h = 0.5 + city.level * 0.22
    const pgeo = new THREE.CylinderGeometry(0.035, 0.05, h, 6, 1, true)
    const pmat = new THREE.ShaderMaterial({
      vertexShader: PILLAR_VERT,
      fragmentShader: PILLAR_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uColor: { value: color },
        uTime: { value: 0 },
        uPhase: { value: (city.level * 1.7) % 6.28 },
      },
    })
    const pillar = new THREE.Mesh(pgeo, pmat)
    pillar.position.set(x, 0.24 + h / 2, -y)
    pillar.layers.enable(BLOOM_LAYER)
    group.add(pillar)
    pillarMats.push(pmat)

    const rgeo = new THREE.PlaneGeometry(0.9, 0.9)
    rgeo.rotateX(-Math.PI / 2)
    const rmat = new THREE.ShaderMaterial({
      vertexShader: PILLAR_VERT,
      fragmentShader: RING_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uColor: { value: color },
        uTime: { value: 0 },
        uPhase: { value: (city.level * 0.37) % 1 },
      },
    })
    const ring = new THREE.Mesh(rgeo, rmat)
    ring.position.set(x, 0.245, -y)
    ring.layers.enable(BLOOM_LAYER)
    group.add(ring)
    ringMats.push(rmat)

    cityWorld.push({ name: city.name, v3: new THREE.Vector3(x, 0.9 + city.level * 0.1, -y) })
  })

  /* 火星粒子：仅桌面 + 允许动效；低核设备自动降量 */
  if (window.matchMedia('(min-width: 1025px)').matches) {
    createEmbers(cityWorld)
  }

  applyColors()
  updateLabels(true)
}

/** 主题令牌 → uniform */
const applyColors = () => {
  if (!blockMat) return
  blockMat.uniforms.uBase.value.fromArray(tk('--fs-bg-sunken', [0.08, 0.09, 0.11]))
  blockMat.uniforms.uLine.value.fromArray(tk('--fs-ink-500', [0.7, 0.74, 0.78]))
  blockMat.uniforms.uAccent.value.fromArray(tk('--fs-ink-400', [0.55, 0.58, 0.62]))
  cityList.forEach((city, i) => {
    const c = tk(`--fs-risk-${city.level}`, [0.5, 0.5, 0.5])
    pillarMats[i]?.uniforms.uColor.value.fromArray(c)
    ringMats[i]?.uniforms.uColor.value.fromArray(c)
  })
  if (emberMat) emberMat.uniforms.uColor.value.fromArray(tk('--fs-risk-4', [0.8, 0.45, 0.2]))
}

/* ---------- DOM label 投影 ---------- */
const tmpV = { x: 0, y: 0 }
const updateLabels = (force = false) => {
  if (!camera || !wrapRef.value || (!running && !force)) return
  const w = wrapRef.value.clientWidth || 1
  const h = wrapRef.value.clientHeight || 1
  labels.value = cityWorld.map((c, i) => {
    const p = c.v3.clone().applyMatrix4(group.matrixWorld).project(camera)
    return {
      name: c.name,
      x: (p.x * 0.5 + 0.5) * w,
      y: (-p.y * 0.5 + 0.5) * h + (i % 2 ? -14 : 6), // 交替偏移缓解滇中密集区重叠
      v: p.z < 1,
    }
  })
}

/* ---------- 渲染循环 ---------- */
const ptr = { x: 0.5, y: 0.5 }
const ptrTarget = { x: 0.5, y: 0.5 }
const tick = (ts) => {
  if (!running || disposed) return
  if (!clock.t0) { clock.t0 = ts; clock.prev = ts }
  const t = (ts - clock.t0) / 1000
  const dt = Math.min((ts - clock.prev) / 1000, 1 / 30)
  clock.prev = ts

  blockMat.uniforms.uTime.value = t
  pillarMats.forEach((m) => { m.uniforms.uTime.value = t })
  ringMats.forEach((m) => { m.uniforms.uTime.value = t })
  if (emberMat) emberMat.uniforms.uTime.value = t

  // 指针视差阻尼（≤8px 等效）
  const damp = 1 - Math.exp(-dt * 8)
  ptr.x += (ptrTarget.x - ptr.x) * damp
  ptr.y += (ptrTarget.y - ptr.y) * damp
  blockMat.uniforms.uPointer.value.set(ptr.x, ptr.y)
  blockMat.uniforms.uProgress.value = progress

  // 相机：缓慢环绕 ±7° + 滚动推进 + 指针微视差；不做大幅旋转
  const az = Math.sin(t * 0.06) * 0.12 + (ptr.x - 0.5) * 0.05
  const r = 11.8 - progress * 1.4
  camera.position.x = Math.sin(az) * r + (ptr.x - 0.5) * 0.3
  camera.position.z = Math.cos(az) * r
  camera.position.y = 8.2 - progress * 0.9 + (0.5 - ptr.y) * 0.2
  camera.lookAt(0, 0, 0.2)

  group.updateMatrixWorld()
  renderer.render(scene, camera)
  if (postEnabled && bloomComposer) {
    renderer.autoClear = false
    bloomComposer.render()
    /* composer 输出留在 readBuffer（UnrealBloomPass needsSwap=false）；
       用加色全屏四边形叠回已画好的底图，保留原始板块与州界 */
    if (bloomQuad && bloomQuadScene) {
      bloomQuad.material.uniforms.tDiffuse.value = bloomComposer.readBuffer.texture
      renderer.setRenderTarget(null)
      renderer.render(bloomQuadScene, bloomQuadCam)
    }
    renderer.autoClear = true
  }
  updateLabels()
  raf = requestAnimationFrame(tick)
}
const start = () => { if (running || disposed || !renderer) return; running = true; clock.prev = 0; raf = requestAnimationFrame(tick) }
const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = 0 }
const onVis = () => { document.hidden ? stop() : start() }

/* ---------- 指针（document 级 inside 判定，rect 缓存） ---------- */
let heroRect = null
let ptrBound = false
const refreshRect = () => { const w = wrapRef.value; heroRect = w ? w.getBoundingClientRect() : null }
const onPointerMove = (e) => {
  if (e.pointerType === 'touch') return
  if (!heroRect) refreshRect()
  if (!heroRect) return
  const inside = e.clientX >= heroRect.left && e.clientX <= heroRect.right && e.clientY >= heroRect.top && e.clientY <= heroRect.bottom
  if (!inside) { ptrTarget.x = 0.5; ptrTarget.y = 0.5; return }
  ptrTarget.x = Math.min(1, Math.max(0, (e.clientX - heroRect.left) / heroRect.width))
  ptrTarget.y = Math.min(1, Math.max(0, (e.clientY - heroRect.top) / heroRect.height))
}
const bindPointer = () => {
  if (ptrBound) return
  ptrBound = true
  refreshRect()
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  window.addEventListener('resize', refreshRect, { passive: true })
  window.addEventListener('scroll', refreshRect, { passive: true, capture: true })
}
const unbindPointer = () => {
  if (!ptrBound) return
  ptrBound = false
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('resize', refreshRect)
  window.removeEventListener('scroll', refreshRect, { capture: true })
}
const onResize = () => {
  const wrap = wrapRef.value
  if (!wrap || !renderer) return
  const w = wrap.clientWidth || 1, h = wrap.clientHeight || 1
  renderer.setSize(w, h, false)
  bloomComposer?.setSize(Math.round(w * 0.5), Math.round(h * 0.5))
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  if (bloomCam) {
    bloomCam.aspect = w / h
    bloomCam.updateProjectionMatrix()
  }
  updateLabels(true)
}

/** 滚动推进接口（父级 ScrollTrigger 调用） */
const setProgress = (p) => { progress = Math.max(0, Math.min(1, p)) }
defineExpose({ setProgress })

watch(() => theme.mode, () => applyColors())
/* 运行期切换动效：off 立即冻结（不重建场景），on 恢复 */
watch(motionAllowed, (v) => {
  if (!v) stop()
  else start()
})

/* 选择性 Bloom：仅桌面 + 允许动效 + WebGL2；底图与光柱分层，只有光柱/脉冲环泛光 */
const initBloom = async () => {
  if (!renderer || disposed) return
  if (!motionAllowed.value) return
  if (!window.matchMedia('(min-width: 1025px)').matches) return
  if (!renderer.capabilities.isWebGL2) return
  const wrap = wrapRef.value
  if (!wrap) return
  const w = wrap.clientWidth || 1
  const h = wrap.clientHeight || 1
  try {
    const [composerMod, renderMod, bloomMod] = await Promise.all([
      import('three/examples/jsm/postprocessing/EffectComposer.js'),
      import('three/examples/jsm/postprocessing/RenderPass.js'),
      import('three/examples/jsm/postprocessing/UnrealBloomPass.js'),
    ])
    if (disposed || !renderer) return

    bloomCam = camera.clone()
    bloomCam.layers.set(BLOOM_LAYER)

    /* 单 composer + 加色合成：底图由 renderer 正常绘制，composer 只渲染 layer 1 的光柱/脉冲环，
       输出留在 readBuffer，再用全屏四边形加色叠回（alpha 不叠加，保持画布透明底） */
    bloomComposer = new composerMod.EffectComposer(renderer)
    bloomComposer.renderToScreen = false
    bloomComposer.addPass(new renderMod.RenderPass(scene, bloomCam))
    bloomPass = new bloomMod.UnrealBloomPass(new THREE.Vector2(w, h), 1.4, 0.5, 0.0)
    bloomComposer.addPass(bloomPass)

    bloomQuadScene = new THREE.Scene()
    bloomQuadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    bloomQuad = new THREE.Mesh(
      new THREE.PlaneGeometry(2, 2),
      new THREE.ShaderMaterial({
        uniforms: { tDiffuse: { value: null } },
        vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
        fragmentShader: 'uniform sampler2D tDiffuse; varying vec2 vUv; void main(){ vec4 c = texture2D(tDiffuse, vUv); gl_FragColor = vec4(c.rgb, c.a); }',
        transparent: true,
        depthTest: false,
        depthWrite: false,
        blending: THREE.CustomBlending,
        blendEquation: THREE.AddEquation,
        blendSrc: THREE.SrcAlphaFactor,
        blendDst: THREE.OneFactor,
        blendEquationAlpha: THREE.AddEquation,
        blendSrcAlpha: THREE.ZeroFactor,
        blendDstAlpha: THREE.OneFactor,
      })
    )
    bloomQuad.frustumCulled = false
    bloomQuadScene.add(bloomQuad)

    /* 泛光半分辨率：模糊本身无损细节，软渲染/低端机显著降负载 */
    bloomComposer.setSize(Math.round(w * 0.5), Math.round(h * 0.5))
  } catch (err) {
    /* 导入失败或环境不支持：直接渲染兜底 */
    if (import.meta.env.DEV) console.warn('[TerrainGL] bloom init skipped:', err)
    bloomComposer?.dispose()
    bloomComposer = null
    bloomPass = null
    bloomQuad = null
    bloomQuadScene = null
    bloomQuadCam = null
  }
}

onMounted(async () => {
  const wrap = wrapRef.value
  if (!wrap) return
  const glOk = !!document.createElement('canvas').getContext('webgl')
  if (!motionAllowed.value || !glOk) { fallback.value = true; return }
  try {
    // three 与边界数据都走动态 import：不阻塞首屏 LCP，边界 JSON 独立 chunk
    const [threeMod, borderMod] = await Promise.all([
      import('three'),
      import('@/assets/Yunnan_border.json'),
    ])
    if (disposed) return
    THREE = threeMod
    buildScene(borderMod.default)
  } catch {
    fallback.value = true
    return
  }
  window.addEventListener('resize', onResize, { passive: true })
  document.addEventListener('visibilitychange', onVis)
  io = new IntersectionObserver((es) => {
    es.forEach((e) => (e.isIntersecting ? start() : stop()))
  }, { threshold: 0.02 })
  io.observe(wrap)
  bindPointer()
  initBloom()
  start()
  if (import.meta.env.DEV) {
    window.__terrainGl = {
      get composer() { return !!bloomComposer },
      get bloom() { return !!bloomPass },
      get embers() { return emberCount },
      get progress() { return progress },
      get pointer() { return [ptr.x, ptr.y] },
      get running() { return running },
      setPost: (v) => { postEnabled = !!v },
    }
  }
})

onBeforeUnmount(() => {
  disposed = true
  stop()
  unbindPointer()
  io?.disconnect(); io = null
  window.removeEventListener('resize', onResize)
  document.removeEventListener('visibilitychange', onVis)
  if (scene) {
    scene.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material) o.material.dispose()
    })
    scene.clear()
    scene = null
  }
  if (bloomComposer) {
    bloomComposer.dispose()
    bloomComposer = null
  }
  if (bloomPass) {
    bloomPass.dispose()
    bloomPass = null
  }
  if (bloomQuadScene) {
    bloomQuadScene.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material) o.material.dispose()
    })
    bloomQuadScene.clear()
    bloomQuadScene = null
  }
  bloomQuad = null
  bloomQuadCam = null
  bloomCam = null
  emberMat = null
  emberCount = 0
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
  <div ref="wrapRef" class="terrain-gl">
    <canvas v-show="!fallback" ref="canvasRef" class="terrain-gl__canvas" aria-hidden="true"></canvas>

    <!-- 州市名 DOM 覆盖层（canvas 不画文字；交替偏移防重叠） -->
    <div v-if="!fallback" class="terrain-gl__labels" aria-hidden="true">
      <span
        v-for="l in labels"
        :key="l.name"
        class="terrain-gl__label"
        :style="{ transform: `translate(${l.x}px, ${l.y}px)`, opacity: l.v ? 0.8 : 0 }"
      >{{ l.name }}</span>
    </div>

    <!-- 静态回退：等高线 + 16 点位 SVG -->
    <svg v-if="fallback" class="terrain-gl__fallback" viewBox="0 0 840 420" preserveAspectRatio="xMidYMid slice" role="img" aria-label="云南 16 州市点位示意">
      <g fill="none" stroke="rgba(var(--fs-bg-canvas-rgb), 0.42)" stroke-width="0.8">
        <ellipse cx="420" cy="210" rx="330" ry="150" opacity="0.9" />
        <ellipse cx="420" cy="210" rx="250" ry="112" opacity="0.7" />
        <ellipse cx="420" cy="210" rx="170" ry="76" opacity="0.55" />
        <ellipse cx="420" cy="210" rx="90" ry="40" opacity="0.4" />
      </g>
      <g v-for="(c, i) in cityList" :key="c.name">
        <circle
          :cx="120 + ((c.lngLat[0] - 97.5) / 8.7) * 600"
          :cy="360 - ((c.lngLat[1] - 21.1) / 8.2) * 300"
          :r="3.5"
          :fill="`var(--fs-risk-${c.level})`"
          opacity="0.85"
        />
      </g>
    </svg>

    <!-- 无障碍文本：16 州市与示意等级列表 -->
    <ul class="sr-only">
      <li v-for="c in cityList" :key="`sr-${c.name}`">{{ c.name }}：火险 {{ c.level }} 级（示意）</li>
    </ul>
  </div>
</template>

<style scoped>
.terrain-gl {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.terrain-gl__canvas,
.terrain-gl__fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}
.terrain-gl__labels {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.terrain-gl__label {
  position: absolute;
  top: 0;
  left: 0;
  margin-left: 6px;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-500);
  text-shadow: 0 1px 2px var(--fs-bg-canvas);
  will-change: transform;
  transition: opacity 0.3s var(--fs-ease);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
