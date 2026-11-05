<script setup>
/**
 * HeroGL — 指挥台 WebGL 首屏场景（three 动态导入，仅公开路由加载）
 *
 * 场景构成（全部程序化，零素材）：
 *   1. 地形等高面：Plane 顶点噪声起伏 + 自定义 ShaderMaterial，
 *      片元里按高度画等高线带（指挥台图例语言），边缘呼吸淡出
 *   2. 火险热场：fbm 流动热点叠在地形上，颜色映射 risk-4/risk-5，
 *      强度 uHeat 由滚动进度驱动（滚动编排：越滚热场越强）
 *   3. 余烬粒子：Points 上升漂移，soft sprite，risk-3→risk-4 渐变
 *   4. 相机：慢速横移 + setProgress(p) 推进（pinned 段 3D→DOM 连续过渡）
 *
 * 颜色纪律：运行时从 CSS 令牌读取（--fs-bg-canvas / --fs-ink-900 / --fs-risk-1..5），
 *          不新增色值；主题切换即时换色。
 *
 * 工程：
 *   - DPR ≤ 1.5；IntersectionObserver 离屏暂停；visibilitychange 暂停
 *   - 卸载全量 dispose（geometry/material/renderer + loseContext）
 *   - three 通过 import('three') 动态加载：内部页/登录页 chunk 不含 three
 *   - prefers-reduced-motion 或 WebGL 不可用：不初始化 three，
 *     渲染静态等高线 SVG 回退（同构图语言）
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { motionAllowed } from '@/composables/useMotionPreference'

const props = defineProps({
  /** 静态回退时的高度（px），默认撑满父容器 */
  fallbackLabel: { type: String, default: '' },
})

const theme = useThemeStore()
const wrapRef = ref(null)
const canvasRef = ref(null)
const fallback = ref(false)

let THREE = null
let renderer = null
let scene = null
let camera = null
let terrain = null
let embers = null
let raf = 0
let io = null
let running = false
let progress = 0
let disposed = false
const clock = { t0: 0, prev: 0 }

/* ---------- 令牌取色（hex → 0..1 rgb） ---------- */
const hexToVec = (hex, fb) => {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim())
  if (!m) return fb
  const n = parseInt(m[1], 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}
const tk = (name, fb) => hexToVec(
  getComputedStyle(document.documentElement).getPropertyValue(name).trim(), fb)

/* ---------- 着色器 ---------- */
const TERRAIN_VERT = `
varying float vElev;
varying vec2 vUv;
void main(){
  vElev = position.y;
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const TERRAIN_FRAG = `
precision highp float;
varying float vElev;
varying vec2 vUv;
uniform vec3 uBase;
uniform vec3 uLine;
uniform vec3 uR1;
uniform vec3 uR3;
uniform vec3 uR4;
uniform vec3 uR5;
uniform float uHeat;
uniform float uTime;
uniform vec2 uPointer;
uniform float uPointerStrength;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++){ v += a * vnoise(p); p = p * 2.03 + 17.1; a *= 0.5; }
  return v;
}
void main(){
  float h = clamp(vElev * 1.4 + 0.5, 0.0, 1.0);
  // 地形基色：画布底 → 一级松绿（低明度差，克制）
  vec3 col = mix(uBase * 0.96, uR1, 0.10 + h * 0.22);
  // 等高线带：按高度量化（与作战大屏图例同一套语言）
  float band = fract(vElev * 10.0);
  float line = smoothstep(0.08, 0.0, min(band, 1.0 - band));
  col = mix(col, uLine, line * 0.14);
  // 火险热场：fbm 流动热点，risk-4 → risk-5，滚动增强
  float heat = fbm(vUv * 3.0 + vec2(uTime * 0.02, -uTime * 0.026));
  heat = smoothstep(0.60, 0.86, heat);
  // 指针热场：指针附近热斑增强（阻尼跟随，离开回中性；半径与幅度已按实测调高）
  float pdist = distance(vUv, uPointer);
  float pboost = smoothstep(0.45, 0.0, pdist) * uPointerStrength;
  heat = clamp(heat + pboost * 0.75, 0.0, 1.0);
  vec3 hot = mix(uR4, uR5, smoothstep(0.7, 1.0, heat));
  col = mix(col, hot, heat * uHeat * 0.6);
  // 边缘呼吸淡出
  float edge = smoothstep(0.52, 0.16, distance(vUv, vec2(0.5)));
  gl_FragColor = vec4(col, edge * (0.42 + uHeat * 0.25));
}
`

const EMBER_VERT = `
attribute float aSeed;
uniform float uTime;
varying float vA;
void main(){
  vec3 p = position;
  p.y = mod(p.y + uTime * (0.14 + aSeed * 0.22), 3.4) - 0.2;
  p.x += sin(uTime * 0.5 + aSeed * 41.0) * 0.10;
  p.z += cos(uTime * 0.4 + aSeed * 23.0) * 0.08;
  vA = clamp(1.0 - p.y / 3.2, 0.0, 1.0);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = (2.0 + aSeed * 3.4) * (26.0 / -mv.z);
  gl_Position = projectionMatrix * mv;
}
`

const EMBER_FRAG = `
precision mediump float;
uniform vec3 uC1;
uniform vec3 uC2;
varying float vA;
void main(){
  vec2 d = gl_PointCoord - 0.5;
  float m = smoothstep(0.5, 0.08, length(d));
  gl_FragColor = vec4(mix(uC1, uC2, vA), m * 0.32 * (1.0 - vA * 0.55));
}
`

/* ---------- 静态回退：等高线环（确定性生成，与登录页同族） ---------- */
const fallbackRing = (i) => {
  const n = 48
  let d = ''
  for (let k = 0; k < n; k++) {
    const a = (k / n) * Math.PI * 2
    const wob = 1 + 0.14 * Math.sin(a * 3 + i * 0.4) + 0.08 * Math.sin(a * 5 - i)
    const x = 470 + Math.cos(a) * i * 26 * wob
    const y = 280 + Math.sin(a) * i * 17 * wob
    d += `${k ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
  }
  return d + 'Z'
}

/* ---------- 场景装配 ---------- */
const buildScene = () => {
  const c = canvasRef.value
  const wrap = wrapRef.value
  renderer = new THREE.WebGLRenderer({ canvas: c, alpha: true, antialias: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.setSize(wrap.clientWidth || 1, wrap.clientHeight || 1, false)

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(55, (wrap.clientWidth || 1) / (wrap.clientHeight || 1), 0.1, 100)
  camera.position.set(0, 2.3, 6.2)
  camera.lookAt(0, 0, 0)

  applyColors()

  // 地形：确定性叠波起伏（无随机重排，刷新一致）
  const geo = new THREE.PlaneGeometry(16, 10, 130, 88)
  geo.rotateX(-Math.PI / 2)
  const pos = geo.attributes.position
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i)
    const e =
      0.42 * Math.sin(x * 0.52 + 1.7) +
      0.30 * Math.sin(z * 0.83 + 4.2) +
      0.20 * Math.sin((x + z) * 0.62 + 0.6) +
      0.12 * Math.sin(x * 1.7 - z * 1.1)
    pos.setY(i, e * 0.85)
  }
  geo.computeVertexNormals()
  const tmat = new THREE.ShaderMaterial({
    vertexShader: TERRAIN_VERT,
    fragmentShader: TERRAIN_FRAG,
    transparent: true,
    depthWrite: false,
    uniforms: {
      uBase:  { value: new THREE.Color(0.06, 0.07, 0.08) },
      uLine:  { value: new THREE.Color(0.7, 0.74, 0.78) },
      uR1:    { value: new THREE.Color(0.43, 0.6, 0.53) },
      uR3:    { value: new THREE.Color(0.79, 0.6, 0.24) },
      uR4:    { value: new THREE.Color(0.82, 0.4, 0.23) },
      uR5:    { value: new THREE.Color(0.66, 0.21, 0.18) },
      uHeat:  { value: 0.35 },
      uTime:  { value: 0 },
      uPointer: { value: new THREE.Vector2(0.5, 0.55) },
      uPointerStrength: { value: 0 },
    },
  })
  terrain = new THREE.Mesh(geo, tmat)
  terrain.position.y = -0.4
  scene.add(terrain)

  // 余烬粒子：确定性伪随机（mulberry32）；密度已降密（240 枚），集中于地形底部区域
  let seed = 20260416
  const rnd = () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const N = 240
  const pgeo = new THREE.BufferGeometry()
  const parr = new Float32Array(N * 3)
  const sarr = new Float32Array(N)
  for (let i = 0; i < N; i++) {
    parr[i * 3] = (rnd() - 0.5) * 13
    parr[i * 3 + 1] = rnd() * 2.4
    parr[i * 3 + 2] = (rnd() - 0.5) * 8
    sarr[i] = rnd()
  }
  pgeo.setAttribute('position', new THREE.BufferAttribute(parr, 3))
  pgeo.setAttribute('aSeed', new THREE.BufferAttribute(sarr, 1))
  const pmat = new THREE.ShaderMaterial({
    vertexShader: EMBER_VERT,
    fragmentShader: EMBER_FRAG,
    transparent: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
    uniforms: {
      uTime: { value: 0 },
      uC1:   { value: new THREE.Color(0.79, 0.6, 0.24) },
      uC2:   { value: new THREE.Color(0.82, 0.4, 0.23) },
    },
  })
  embers = new THREE.Points(pgeo, pmat)
  scene.add(embers)

  // DEV 探针：运行态诊断用（生产构建被剔除，零开销）
  if (import.meta.env.DEV) {
    window.__heroGl = {
      pointer: () => ({ ...tu2(tmat).uPointer.value }),
      strength: () => tu2(tmat).uPointerStrength.value,
      heat: () => tu2(tmat).uHeat.value,
    }
  }
}
const tu2 = (m) => m.material.uniforms

/** 主题令牌 → 着色器 uniform（主题切换即时换色） */
const applyColors = () => {
  if (!terrain) return
  const tu = terrain.material.uniforms
  const pu = embers.material.uniforms
  tu.uBase.value.fromArray(tk('--fs-bg-canvas', [0.06, 0.07, 0.08]))
  tu.uLine.value.fromArray(tk('--fs-ink-900', [0.7, 0.74, 0.78]))
  tu.uR1.value.fromArray(tk('--fs-risk-1', [0.43, 0.6, 0.53]))
  tu.uR3.value.fromArray(tk('--fs-risk-3', [0.79, 0.6, 0.24]))
  tu.uR4.value.fromArray(tk('--fs-risk-4', [0.82, 0.4, 0.23]))
  tu.uR5.value.fromArray(tk('--fs-risk-5', [0.66, 0.21, 0.18]))
  pu.uC1.value.fromArray(tk('--fs-risk-3', [0.79, 0.6, 0.24]))
  pu.uC2.value.fromArray(tk('--fs-risk-4', [0.82, 0.4, 0.23]))
}

/* ---------- 渲染循环 ---------- */
const tick = (ts) => {
  if (!running || disposed) return
  if (!clock.t0) { clock.t0 = ts; clock.prev = ts }
  const t = (ts - clock.t0) / 1000
  const dt = Math.min((ts - clock.prev) / 1000, 1 / 30)
  clock.prev = ts

  // 指针热场：坐标与强度双阻尼（0.18），离开时强度回落 0，不抖动
  const tu = terrain.material.uniforms
  const damp = 1 - Math.exp(-dt * 10)
  ptr.x += (ptrTarget.x - ptr.x) * damp * 0.9
  ptr.y += (ptrTarget.y - ptr.y) * damp * 0.9
  ptrS += (ptrTargetS - ptrS) * damp
  tu.uPointer.value.set(ptr.x, ptr.y)
  tu.uPointerStrength.value = ptrS
  tu.uTime.value = t
  tu.uHeat.value = 0.22 + progress * 0.5
  embers.material.uniforms.uTime.value = t

  // 相机：慢速横移 + 指针微视差（≤8px 等效）+ 滚动推近抬升
  camera.position.x = Math.sin(t * 0.05) * 0.7 + (ptr.x - 0.5) * 0.28
  camera.position.y = 2.3 + progress * 0.95 + (0.5 - ptr.y) * 0.12
  camera.position.z = 6.2 - progress * 1.7
  camera.lookAt(0, 0.2, 0)

  renderer.render(scene, camera)
  raf = requestAnimationFrame(tick)
}

const start = () => {
  if (running || disposed || !renderer) return
  running = true
  clock.prev = 0
  raf = requestAnimationFrame(tick)
}
const stop = () => {
  running = false
  if (raf) cancelAnimationFrame(raf)
  raf = 0
}

const onVis = () => { document.hidden ? stop() : start() }

/* ---------- 指针热场：坐标与 hero 容器 rect 比较（rect 缓存，零逐帧 DOM 读）。
   监听绑在 document：hero__inner 浮在场景之上，绑容器 leave 会在进入文案区时误清零 ---------- */
const ptr = { x: 0.5, y: 0.55 }
const ptrTarget = { x: 0.5, y: 0.55 }
let ptrS = 0
let ptrTargetS = 0
let ptrBound = false
let heroRect = null
const refreshHeroRect = () => {
  const wrap = wrapRef.value
  heroRect = wrap ? wrap.getBoundingClientRect() : null
}
const onPointerMove = (e) => {
  if (e.pointerType === 'touch') return
  if (!heroRect) refreshHeroRect()
  if (!heroRect) return
  const inside =
    e.clientX >= heroRect.left && e.clientX <= heroRect.right &&
    e.clientY >= heroRect.top && e.clientY <= heroRect.bottom
  if (!inside) { ptrTargetS = 0; return }
  ptrTarget.x = Math.min(1, Math.max(0, (e.clientX - heroRect.left) / heroRect.width))
  ptrTarget.y = Math.min(1, Math.max(0, 1 - (e.clientY - heroRect.top) / heroRect.height))
  ptrTargetS = 1
}
const bindPointer = () => {
  if (ptrBound) return
  ptrBound = true
  refreshHeroRect()
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  window.addEventListener('resize', refreshHeroRect, { passive: true })
  // capture 捕获 .wl 滚动容器的滚动事件，保证 heroRect 跟随滚动刷新
  window.addEventListener('scroll', refreshHeroRect, { passive: true, capture: true })
}
const unbindPointer = () => {
  if (!ptrBound) return
  ptrBound = false
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('resize', refreshHeroRect)
  window.removeEventListener('scroll', refreshHeroRect, { capture: true })
}
const onResize = () => {
  const wrap = wrapRef.value
  if (!wrap || !renderer) return
  const w = wrap.clientWidth || 1
  const h = wrap.clientHeight || 1
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

/** 滚动编排接口：父级 ScrollTrigger 调用 */
const setProgress = (p) => { progress = Math.max(0, Math.min(1, p)) }
defineExpose({ setProgress })

watch(() => theme.mode, () => applyColors())

onMounted(async () => {
  const wrap = wrapRef.value
  if (!wrap) return
  const reduced = !motionAllowed.value
  const glOk = !!document.createElement('canvas').getContext('webgl')
  if (reduced || !glOk) { fallback.value = true; return }

  try {
    THREE = await import('three') // 仅公开路由 chunk 携带 three
    if (disposed) return
    buildScene()
  } catch {
    fallback.value = true // 动态加载失败 / WebGL 初始化失败：静态回退
    return
  }

  window.addEventListener('resize', onResize, { passive: true })
  document.addEventListener('visibilitychange', onVis)
  io = new IntersectionObserver((es) => {
    es.forEach((e) => (e.isIntersecting ? start() : stop()))
  }, { threshold: 0.02 })
  io.observe(wrap)
  bindPointer()
  start()
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
  <div ref="wrapRef" class="hero-gl" aria-hidden="true">
    <canvas v-show="!fallback" ref="canvasRef" class="hero-gl__canvas"></canvas>
    <!-- 静态回退：等高线 SVG（与登录页/大屏同一构图语言，无动画） -->
    <svg v-if="fallback" class="hero-gl__fallback" viewBox="0 0 840 560" preserveAspectRatio="xMidYMid slice">
      <g fill="none" stroke-width="0.8">
        <path
          v-for="i in 12"
          :key="i"
          :d="fallbackRing(i)"
          stroke="var(--fs-hairline-strong)"
          :opacity="0.5 - i * 0.03"
        />
      </g>
      <circle cx="470" cy="250" r="5" fill="var(--fs-risk-4)" opacity="0.8" />
      <circle cx="560" cy="300" r="4" fill="var(--fs-risk-3)" opacity="0.7" />
      <circle cx="380" cy="320" r="4" fill="var(--fs-risk-2)" opacity="0.6" />
    </svg>
    <span v-if="fallback && fallbackLabel" class="hero-gl__label qt-eyebrow">{{ fallbackLabel }}</span>
  </div>
</template>

<style scoped>
.hero-gl {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.hero-gl__canvas,
.hero-gl__fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}
.hero-gl__label {
  position: absolute;
  right: 16px;
  bottom: 12px;
}
</style>
