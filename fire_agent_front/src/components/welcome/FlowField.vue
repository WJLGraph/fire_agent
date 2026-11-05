<script setup>
/**
 * FlowField — 原生 WebGL 流场章节背景（无 three 依赖，单 pass 片元着色器）
 *
 * 手法：value-noise fbm + domain warp 生成缓流场，按强度量化为细等值线带
 * （量化线场思路的着色器化），线色取自主题令牌（ink 发丝级对比，极克制）。
 *
 * 工程：
 *   - DPR 上限 1.5；IntersectionObserver 离屏暂停；visibilitychange 暂停
 *   - 卸载时 cancelAnimationFrame + loseContext 释放 GL 资源
 *   - prefers-reduced-motion：只渲染一帧静帧，不进动画循环
 *   - WebGL 不可用：静默保持透明（容器本无底色依赖）
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'

const canvasRef = ref(null)

const VERT = `
attribute vec2 aPos;
varying vec2 vUv;
void main(){
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`

const FRAG = `
precision mediump float;
varying vec2 vUv;
uniform float uTime;
uniform vec2 uRes;
uniform vec3 uInk;
uniform vec3 uWarm;

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
  for (int i = 0; i < 4; i++){ v += a * vnoise(p); p = p * 2.07 + 11.3; a *= 0.5; }
  return v;
}
void main(){
  vec2 uv = vUv;
  vec2 asp = vec2(uRes.x / uRes.y, 1.0);
  // 域扭曲缓流场（低频：密度压低，作氛围不作主角）
  vec2 q = vec2(fbm(uv * 1.7 * asp + vec2(0.0, uTime * 0.03)),
                fbm(uv * 1.7 * asp + vec2(5.2, -uTime * 0.024)));
  float n = fbm(uv * 2.3 * asp + q * 0.7);
  // 量化等值线带（低密度：12 带，细线弱对比）
  float band = fract(n * 12.0 - uTime * 0.04);
  float line = smoothstep(0.08, 0.0, min(band, 1.0 - band));
  float mid = smoothstep(0.22, 0.20, abs(fract(n * 3.0) - 0.5));
  // 热斑：火语义色，密度与强度都压到几乎不可察觉（veil 之下只余余温）
  float hot = smoothstep(0.86, 0.98, fbm(uv * 1.2 * asp + q * 0.4 + 7.7)) * line;
  vec3 col = uInk * (line * 0.7 + mid * 0.08) + uWarm * hot * 0.35;
  // 边缘呼吸淡出
  float edge = smoothstep(0.55, 0.24, distance(uv, vec2(0.5, 0.55)));
  float alpha = (line * 0.12 + mid * 0.03 + hot * 0.04) * edge;
  gl_FragColor = vec4(col, alpha);
}
`

let gl = null
let raf = 0
let io = null
let running = false
let startTs = 0
let reduced = false

const hexToVec = (hex, fb) => {
  const h = (hex || '').trim()
  const m = /^#?([0-9a-f]{6})$/i.exec(h) || /^#?([0-9a-f]{3})$/i.exec(h)
  if (!m) return fb
  const s = m[1].length === 3 ? m[1].split('').map((c) => c + c).join('') : m[1]
  const n = parseInt(s, 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}

const token = (name, fb) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return hexToVec(v, fb)
}

const draw = (t) => {
  if (!gl) return
  const c = canvasRef.value
  gl.viewport(0, 0, c.width, c.height)
  gl.uniform1f(uTime, t)
  gl.uniform2f(uRes, c.width, c.height)
  gl.drawArrays(gl.TRIANGLES, 0, 3)
}
let uTime = null
let uRes = null

const loop = (ts) => {
  if (!running) return
  if (!startTs) startTs = ts
  draw((ts - startTs) / 1000)
  raf = requestAnimationFrame(loop)
}

const start = () => {
  if (running || !gl) return
  running = true
  if (reduced) { draw(12.0); running = false; return } // 静帧
  raf = requestAnimationFrame(loop)
}
const stop = () => {
  running = false
  if (raf) cancelAnimationFrame(raf)
  raf = 0
}

const resize = () => {
  const c = canvasRef.value
  if (!c || !gl) return
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
  const w = Math.max(1, Math.round(c.clientWidth * dpr))
  const h = Math.max(1, Math.round(c.clientHeight * dpr))
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h }
  draw(startTs ? (performance.now() - startTs) / 1000 : 12)
}

onMounted(() => {
  const c = canvasRef.value
  if (!c) return
  reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  gl = c.getContext('webgl', { alpha: true, antialias: false, depth: false, stencil: false })
  if (!gl) return // WebGL 不可用：保持透明

  const vs = gl.createShader(gl.VERTEX_SHADER)
  gl.shaderSource(vs, VERT); gl.compileShader(vs)
  const fs = gl.createShader(gl.FRAGMENT_SHADER)
  gl.shaderSource(fs, FRAG); gl.compileShader(fs)
  const prog = gl.createProgram()
  gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog)
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { gl = null; return }
  gl.useProgram(prog)

  const buf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, buf)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
  const loc = gl.getAttribLocation(prog, 'aPos')
  gl.enableVertexAttribArray(loc)
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)

  uTime = gl.getUniformLocation(prog, 'uTime')
  uRes = gl.getUniformLocation(prog, 'uRes')
  gl.uniform3fv(gl.getUniformLocation(prog, 'uInk'), token('--fs-ink-900', [0.09, 0.1, 0.1]))
  gl.uniform3fv(gl.getUniformLocation(prog, 'uWarm'), token('--fs-risk-4', [0.82, 0.4, 0.23]))
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)
  gl.clearColor(0, 0, 0, 0)

  resize()
  window.addEventListener('resize', resize, { passive: true })
  document.addEventListener('visibilitychange', onVis)
  io = new IntersectionObserver((es) => {
    es.forEach((e) => (e.isIntersecting ? start() : stop()))
  }, { threshold: 0.02 })
  io.observe(c)
  start()
})

const onVis = () => {
  if (document.hidden) stop()
  else start()
}

onBeforeUnmount(() => {
  stop()
  io?.disconnect()
  io = null
  window.removeEventListener('resize', resize)
  document.removeEventListener('visibilitychange', onVis)
  if (gl) {
    const ext = gl.getExtension('WEBGL_lose_context')
    ext && ext.loseContext()
    gl = null
  }
})
</script>

<template>
  <canvas ref="canvasRef" class="ff" aria-hidden="true"></canvas>
</template>

<style scoped>
.ff {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
}
</style>
