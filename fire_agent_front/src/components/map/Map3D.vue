<script setup>
/**
 * Map3D — sc-datav 风格 3D 省级地图（Three.js，参照 sc-datav-main/Demo2 实现）
 *
 * 视觉要素：
 * - 州市面片挤出（ExtrudeGeometry）：顶面 MeshStandardMaterial 按火险等级着色，叠云南地形法线贴图
 *   （AWS Terrain Tiles 高程离线生成，与全局 UV 逐像素对齐，呈现地形浮雕），
 *   侧面自定义扫光 shader（自底向顶渐变 + 周期性光带上扫）
 * - 省会（昆明）→ 各州市 贝塞尔飞线（TubeGeometry + 流光贴图滚动）
 * - 上升光柱粒子（AdditiveBlending 辉光圆柱）
 * - 底部旋转光环（quan1 贴图，AdditiveBlending）
 * - 州市名称标签（CSS2DRenderer）
 * - 火点总数柱状图（按州市聚合：柱高=火点数，青→琥珀→红渐变，柱顶数值标签，16 州市全覆盖）
 * - 悬停州市抬升（scale.z lerp 1.5）+ 点击州市向上冒泡 city-click
 * - 明暗主题联动（stores/theme）：背景/雾/扫光/描边/飞线/氛围元素双套配色
 *
 * 投影：Web Mercator（手写，避免引入 d3-geo）→ 归一化至最长边 TARGET 单位，中心在原点。
 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { MAP3D_THEME_COLORS as THEME_COLORS } from '@/utils/map3dTheme'
import { buildProjection as buildProjectionUtil, featurePolys, ringsToShape, topColorFor as topColorForUtil, applyBboxUV as applyBboxUVUtil, cityOfPoint } from '@/utils/map3dGeo'
import { makeSweepMaterial, makeBeamMaterial, disposeGroup as disposeGroupUtil } from '@/utils/map3dMaterial'
import { useThemeStore } from '@/stores/theme'

// sc-datav 原版贴图资产复用（飞线流光 / 底部光环）
// 注意：资源位于项目根 sc-datav-main/，组件移入 components/map/ 后相对层级 +1
import flyLineUrl from '../../../sc-datav-main/src/assets/fly_line.png'
import ringUrl from '../../../sc-datav-main/src/assets/quan1.png'
// 云南省地形法线贴图：由 AWS Terrain Tiles 公开高程瓦片（terrarium 编码，zoom 8）按本组件
// Mercator 投影公式反演 UV 对齐后中心差分生成，图片顶行 = v=1 = 北，与 applyBboxUV 全局包络严格对齐
import terrainNormalUrl from '@/assets/yunnan_terrain_normal.png'

const props = defineProps({
  /** 16 州市行政边界 GeoJSON（与 2D 地图共用 Yunnan_border.json） */
  cityPolygons: { type: Object, required: true },
  /** { 州市名: 1-5 } 火险等级映射（预测模式选日期后才有值，null 时用中性底色） */
  cityRiskData: { type: Object, default: null },
  /** 火点 FeatureCollection（历史/预测当前筛选结果） */
  firePoints: { type: Object, default: null },
})
const emit = defineEmits(['city-click'])

const themeStore = useThemeStore()
const hostRef = ref(null)

// ====== 常量 ======
const TARGET = 16          // 地图归一化后最长边（世界单位）
const DEPTH = 1.1          // 挤出厚度

let themeMode = 'dark'     // 当前主题（init/watch 同步）
function themeC() { return THEME_COLORS[themeMode] || THEME_COLORS.dark }

// ====== Three 核心对象 ======
let renderer, labelRenderer, scene, camera, controls, rafId = 0
let mapGroup               // 旋转 -90° 的地图根组
let regionMeshes = []      // 州市挤出网格（含 userData.name / center / lngLat）
let clusterGroup = null    // 火点聚类柱组（随缩放重建，镜像 2D Cluster 行为）
let underlayMats = []      // 底座垫层材质（主题切换统一调色）
let rebuildTimer = null    // 聚类重建防抖
let introClusterDone = false // 入场动画结束后的首建标记
let edgesMats = []         // 州市轮廓描边材质（主题切换统一调色）
let flyMats = []           // 飞线材质（主题切换统一调色）
let flyTex, ringTex, normalTex
let bottomRing             // 底部旋转光环
let beams                  // 上升光柱组
let sweepMat               // 共享侧面扫光材质
let projFn = null          // 经纬度 → 世界坐标 (x, y)
let geoBBox = null         // 全省几何投影包络 { minX, maxX, minY, maxY }（法线贴图 UV 基准）
let clock = new THREE.Clock()
let resizeObserver = null
let introProgress = 0      // 入场动画进度 0→1
const CAM_START = new THREE.Vector3(0, 26, 1.2)
const CAM_END = new THREE.Vector3(0, 12.5, 13.5)
let hovered = null
let raycaster = new THREE.Raycaster()
let pointerNdc = new THREE.Vector2()
let downXY = null

// ====== 构建地图 ======
function buildMap() {
  // 重建时刷新主题态，确保垫层/描边取到当前主题配色
  themeMode = themeStore.isDark() ? 'dark' : 'light'
  // 清空旧场景内容
  if (mapGroup) {
    scene.remove(mapGroup)
    disposeGroupUtil(mapGroup, sweepMat)
  }
  regionMeshes = []
  edgesMats = []
  flyMats = []
  underlayMats = []
  const _p = buildProjectionUtil(props.cityPolygons, TARGET)
  projFn = _p.proj
  geoBBox = _p.bbox

  mapGroup = new THREE.Group()
  mapGroup.rotation.x = -Math.PI / 2   // xy 平面铺到 XZ 地面，挤出方向朝上
  scene.add(mapGroup)

  const features = (props.cityPolygons.features || []).filter(f => f.geometry)

  features.forEach(feature => {
    const name = feature.properties?.name || ''
    const polys = featurePolys(feature)
    if (!polys.length) return
    const shapes = polys.map(rings => ringsToShape(rings, projFn))

    // 州市中心（外环顶点均值）：世界坐标 + 原始经纬度（供火点就近归簇）
    let cx = 0, cy = 0, n = 0
    let clng = 0, clat = 0
    polys[0][0].forEach(c => {
      const [x, y] = projFn(c)
      cx += x; cy += y; clng += c[0]; clat += c[1]; n++
    })
    cx /= n; cy /= n; clng /= n; clat /= n

    // 挤出网格：材质数组 [顶/底盖, 侧面]
    const geo = new THREE.ExtrudeGeometry(shapes, { depth: DEPTH, bevelEnabled: false })
    applyBboxUVUtil(geo, geoBBox)
    const topMat = new THREE.MeshStandardMaterial({
      color: topColorForUtil(name, props.cityRiskData, themeC().neutral),
      // 顶面地形浮雕：云南高程法线贴图 + 哑光底色（近零金属度防背光发黑，高粗糙度保持哑光质感）
      metalness: 0.05,
      roughness: 0.92,
      normalMap: normalTex,
      normalScale: new THREE.Vector2(0.85, 0.85),
    })
    const mesh = new THREE.Mesh(geo, [topMat, sweepMat])
    mesh.userData = { name, center: new THREE.Vector3(cx, cy, 0), lngLat: [clng, clat] }
    mapGroup.add(mesh)
    regionMeshes.push(mesh)

    // 顶面描边（省界轮廓增强：高亮色 + 高不透明度，随主题切换调色）
    const topGeo = new THREE.ShapeGeometry(shapes)
    const edgeMat = new THREE.LineBasicMaterial({
      color: themeC().edge,
      transparent: true,
      opacity: themeC().edgeOpacity,
    })
    edgesMats.push(edgeMat)
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(topGeo), edgeMat)
    edges.position.z = DEPTH + 0.02
    mapGroup.add(edges)
    topGeo.dispose()

    // 底座基座：各多边形轮廓放大 8% 挤出成实心垫块（厚 0.3，位于地图正下方），
    // 彻底填死相邻州市边界不重合的裂缝，任何角度都不透背景色；
    // 相邻垫块会重叠，用逐块递增的 polygonOffset 错开深度避免共面闪烁
    shapes.forEach((shape, si) => {
      const pg = new THREE.ExtrudeGeometry(shape, { depth: 0.3, bevelEnabled: false })
      pg.computeBoundingBox()
      const bb = pg.boundingBox
      const bx = (bb.min.x + bb.max.x) / 2
      const by = (bb.min.y + bb.max.y) / 2
      pg.translate(-bx, -by, 0)
      pg.scale(1.08, 1.08, 1)
      pg.translate(bx, by, 0)
      const pmat = new THREE.MeshBasicMaterial({
        color: themeC().underlay,
        polygonOffset: true,
        polygonOffsetFactor: si * 2,
        polygonOffsetUnits: si * 2,
      })
      underlayMats.push(pmat)
      const plate = new THREE.Mesh(pg, pmat)
      plate.position.z = -0.34   // 垫块顶面 -0.04，与地图底面留阴影缝
      plate.renderOrder = -1
      mapGroup.add(plate)
    })

    // 州市名标签（CSS2D）
    const labelDiv = document.createElement('div')
    labelDiv.className = 'm3d-label'
    labelDiv.textContent = name
    const labelObj = new CSS2DObject(labelDiv)
    labelObj.position.set(cx, cy, DEPTH + 0.25)
    mapGroup.add(labelObj)
  })

  buildFlyLines(features)
  buildClusters()
}

// ====== 飞线：省会 → 各州市 ======
function buildFlyLines(features) {
  const centers = regionMeshes.map(m => m.userData)
  if (centers.length < 2) return
  const hub = centers.find(c => c.name && c.name.includes('昆明')) || centers[0]

  const group = new THREE.Group()
  group.renderOrder = 10
  group.position.z = DEPTH + 0.1
  centers.forEach(c => {
    if (c === hub) return
    const a = new THREE.Vector3(hub.center.x, hub.center.y, 0.15)
    const b = new THREE.Vector3(c.center.x, c.center.y, 0.15)
    const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5)
    mid.z = 4.2
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b)
    const flyMat = new THREE.MeshBasicMaterial({
      map: flyTex,
      transparent: true,
      color: themeC().fly,
      depthTest: false,
      blending: THREE.AdditiveBlending,
    })
    flyMats.push(flyMat)
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 32, 0.045, 6, false), flyMat)
    tube.renderOrder = 10
    group.add(tube)
  })
  mapGroup.add(group)
}

// 单根柱（顶亮底暗渐变 + 沿口描边，基柱/聚类柱/单点柱共用）
function makeBar(x, y, count, max) {
  const h = count >= 2 ? 0.35 + (count / max) * 3.4 : (count === 1 ? 0.22 : 0.12)
  const ratio = Math.min(1, count / max)
  const cLow = new THREE.Color('#38bdf8')
  const cMid = new THREE.Color('#fbbf24')
  const cHigh = new THREE.Color('#ef4444')
  const color = ratio < 0.5
    ? cLow.clone().lerp(cMid, ratio / 0.5)
    : cMid.clone().lerp(cHigh, (ratio - 0.5) / 0.5)
  const r = count >= 2 ? 0.3 : 0.14

  const geo = new THREE.CylinderGeometry(r, r, 1, 20)
  geo.rotateX(Math.PI / 2)   // 柱轴对齐地图局部 +Z（挤出方向）
  // 顶亮底暗顶点色渐变：unlit 也自带立体感，任何视角都能读出「立柱」
  const cBot = color.clone().multiplyScalar(0.4)
  const cTop = color.clone().lerp(new THREE.Color('#ffffff'), 0.42)
  const posAttr = geo.attributes.position
  const colArr = new Float32Array(posAttr.count * 3)
  const vc = new THREE.Color()
  for (let i = 0; i < posAttr.count; i++) {
    const t = THREE.MathUtils.clamp(posAttr.getZ(i) + 0.5, 0, 1)
    vc.copy(cBot).lerp(cTop, t)
    colArr[i * 3] = vc.r
    colArr[i * 3 + 1] = vc.g
    colArr[i * 3 + 2] = vc.b
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colArr, 3))
  const bar = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true }))
  // 顶/底沿高亮圆环描边（阈值 30° 只保留棱边：两道圆环，不含侧面经线）
  bar.add(new THREE.LineSegments(
    new THREE.EdgesGeometry(geo, 30),
    new THREE.LineBasicMaterial({ color: cTop, transparent: true, opacity: 0.95 }),
  ))
  bar.position.set(x, y, DEPTH + h / 2)
  bar.scale.z = h
  bar.renderOrder = 12
  clusterGroup.add(bar)

  // 数量标签：只有聚合簇（≥2）才标数字，单点/基柱保持画面干净
  if (count >= 2) {
    const labelDiv = document.createElement('div')
    labelDiv.className = 'm3d-bar-label'
    labelDiv.textContent = String(count)
    const labelObj = new CSS2DObject(labelDiv)
    labelObj.position.set(x, y, DEPTH + h + 0.28)
    clusterGroup.add(labelObj)
  }
}

// 聚类重建防抖（缩放/旋转/视口/数据变化时触发）
function scheduleClusters() {
  if (rebuildTimer) clearTimeout(rebuildTimer)
  rebuildTimer = setTimeout(() => {
    rebuildTimer = null
    buildClusters()
  }, 120)
}

// 火点屏幕空间聚类柱 —— 镜像 2D 地图 OL Cluster（distance=40px）的缩放联动：
// 拉远合并成大柱（≈州市总数）、拉近拆分成小柱/单点，数字随缩放变化
function buildClusters() {
  if (clusterGroup) {
    mapGroup.remove(clusterGroup)
    disposeGroupUtil(clusterGroup, sweepMat)
    clusterGroup = null
  }
  if (!projFn || !regionMeshes.length || !camera) return
  clusterGroup = new THREE.Group()
  clusterGroup.renderOrder = 12

  const centers = regionMeshes.map(m => m.userData)

  // 1) 0 火点州市保留基柱，保证全省 16 州市全覆盖
  const cityCounts = {}
  centers.forEach(c => { cityCounts[c.name] = 0 })
  const feats = (props.firePoints && props.firePoints.features) || []
  feats.forEach(f => {
    const name = cityOfPoint(f, centers)
    if (name && cityCounts[name] != null) cityCounts[name]++
  })
  Object.entries(cityCounts).forEach(([name, count]) => {
    if (count === 0) {
      const center = centers.find(c => c.name === name)
      if (center) makeBar(center.center.x, center.center.y, 0, 1)
    }
  })

  // 2) 火点投影到屏幕像素后贪心聚类（阈值 40px，与 2D 一致）
  const host = hostRef.value
  const vw = (host && host.clientWidth) || 800
  const vh = (host && host.clientHeight) || 600
  camera.updateMatrixWorld()
  mapGroup.updateWorldMatrix(true, false)
  const CLUSTER_PX = 40
  const local = []
  const screen = []
  feats.forEach(f => {
    const c = f.geometry && f.geometry.coordinates
    if (!c || typeof c[0] !== 'number') return
    const [px, py] = projFn([c[0], c[1]])
    const wp = new THREE.Vector3(px, py, DEPTH).applyMatrix4(mapGroup.matrixWorld)
    const ndc = wp.clone().project(camera)
    if (ndc.z < -1 || ndc.z > 1) return
    local.push([px, py])
    screen.push({ x: (ndc.x + 1) / 2 * vw, y: (1 - ndc.y) / 2 * vh })
  })

  const clusters = []
  for (let i = 0; i < screen.length; i++) {
    const s = screen[i]
    let best = null
    let bestD = CLUSTER_PX * CLUSTER_PX
    for (let j = 0; j < clusters.length; j++) {
      const cl = clusters[j]
      const dx = cl.sx / cl.n - s.x
      const dy = cl.sy / cl.n - s.y
      const d = dx * dx + dy * dy
      if (d < bestD) { bestD = d; best = cl }
    }
    if (best) { best.sx += s.x; best.sy += s.y; best.n++; best.idx.push(i) }
    else clusters.push({ sx: s.x, sy: s.y, n: 1, idx: [i] })
  }

  let max = 1
  clusters.forEach(cl => { if (cl.n > max) max = cl.n })
  clusters.forEach(cl => {
    let ax = 0, ay = 0
    cl.idx.forEach(k => { ax += local[k][0]; ay += local[k][1] })
    makeBar(ax / cl.n, ay / cl.n, cl.n, max)
  })

  mapGroup.add(clusterGroup)
}


// ====== 底部旋转光环 + 上升光柱（世界坐标，不随地图组旋转） ======
function buildAmbience() {
  const ringGeo = new THREE.PlaneGeometry(19, 19)
  bottomRing = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
    map: ringTex,
    transparent: true,
    color: themeC().ring,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  }))
  bottomRing.rotation.x = -Math.PI / 2
  bottomRing.position.y = -0.05
  scene.add(bottomRing)

  beams = new THREE.Group()
  const RANGE = 15
  const beamGeo = new THREE.CylinderGeometry(0.03, 0.03, 1, 6, 1, true)
  for (let k = 0; k < 18; k++) {
    const baseOpacity = 0.35 + Math.random() * 0.25
    const mat = makeBeamMaterial(baseOpacity)
    const beam = new THREE.Mesh(beamGeo, mat)
    beam.position.set(
      (Math.random() - 0.5) * RANGE,
      Math.random() * 8,
      (Math.random() - 0.5) * RANGE,
    )
    beam.scale.y = 2 + Math.random() * 3
    beam.userData = { speed: 1.2 + Math.random(), resetHeight: 10 + Math.random() * 8, range: RANGE, baseOpacity }
    beams.add(beam)
  }
  scene.add(beams)
}

// ====== 主题应用（明暗切换：背景/雾/扫光/描边/飞线/氛围元素统一调色） ======
function applySceneTheme() {
  if (!scene) return
  themeMode = themeStore.isDark() ? 'dark' : 'light'
  const c = themeC()
  const dark = themeMode === 'dark'

  // 场景底色与雾
  scene.background = new THREE.Color(c.bg)
  if (scene.fog) scene.fog.color.set(c.bg)
  else scene.fog = new THREE.Fog(c.bg, 20, 46)

  // 侧面扫光
  if (sweepMat) {
    sweepMat.uniforms.baseTopColor.value.set(c.sweepTop)
    sweepMat.uniforms.baseBottomColor.value.set(c.sweepBottom)
    sweepMat.uniforms.scanColor.value.set(c.scan)
  }

  // 州市轮廓描边（省界增强）
  edgesMats.forEach(m => { m.color.set(c.edge); m.opacity = c.edgeOpacity })

  // 底座垫层
  underlayMats.forEach(m => { m.color.set(c.underlay) })

  // 顶面中性底色（有火险数据的州市保持等级色）
  regionMeshes.forEach(m => {
    const top = Array.isArray(m.material) ? m.material[0] : m.material
    top.color.copy(topColorForUtil(m.userData.name, props.cityRiskData, themeC().neutral))
  })

  // 飞线：浅色下改普通混合（叠加混合在浅底上会发白失真）
  flyMats.forEach(m => {
    m.color.set(c.fly)
    m.blending = dark ? THREE.AdditiveBlending : THREE.NormalBlending
    m.opacity = dark ? 1 : 0.6
    m.needsUpdate = true
  })

  // 底部光环
  if (bottomRing) {
    bottomRing.material.color.set(c.ring)
    bottomRing.material.blending = dark ? THREE.AdditiveBlending : THREE.NormalBlending
    bottomRing.material.opacity = dark ? 1 : 0.4
    bottomRing.material.needsUpdate = true
  }

  // 上升光柱
  if (beams) {
    beams.children.forEach(b => {
      b.material.uniforms.uColor.value.set(c.beam)
      b.material.blending = dark ? THREE.AdditiveBlending : THREE.NormalBlending
      b.material.uniforms.uOpacity.value = dark ? b.userData.baseOpacity : b.userData.baseOpacity * 0.4
      b.material.needsUpdate = true
    })
  }
}

// ====== 交互：悬停抬升 / 点击选中 ======
function setPointer(e) {
  const rect = hostRef.value.getBoundingClientRect()
  pointerNdc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  pointerNdc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
}
function pickRegion() {
  raycaster.setFromCamera(pointerNdc, camera)
  const hits = raycaster.intersectObjects(regionMeshes, false)
  return hits.length ? hits[0].object : null
}
function onPointerMove(e) {
  if (!regionMeshes.length) return
  setPointer(e)
  const hit = pickRegion()
  if (hit !== hovered) {
    hovered = hit
    hostRef.value.style.cursor = hit ? 'pointer' : 'grab'
  }
}
function onPointerDown(e) { downXY = [e.clientX, e.clientY] }
function onPointerUp(e) {
  if (!downXY) return
  const moved = Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1])
  downXY = null
  if (moved > 6) return
  setPointer(e)
  const hit = pickRegion()
  if (hit) emit('city-click', hit.userData.name)
}

// ====== 渲染循环 ======
function tick() {
  rafId = requestAnimationFrame(tick)
  const delta = Math.min(clock.getDelta(), 0.1)
  const elapsed = clock.elapsedTime

  // 入场：相机从高空俯视降轨至斜视（2.2s ease-out）
  if (introProgress < 1) {
    introProgress = Math.min(1, introProgress + delta / 2.2)
    const t = 1 - Math.pow(1 - introProgress, 3)
    camera.position.lerpVectors(CAM_START, CAM_END, t)
    if (introProgress >= 1 && !introClusterDone) {
      introClusterDone = true
      controls.enabled = true
      scheduleClusters()   // 入场结束按最终视角重建聚类
    }
  }

  // 侧面扫光 + 飞线流光
  sweepMat.uniforms.time.value = elapsed / 3
  flyTex.offset.x -= delta / 5
  // 底部光环旋转
  if (bottomRing) bottomRing.rotation.z += delta / 5
  // 光柱上升
  if (beams) {
    beams.children.forEach(beam => {
      beam.position.y += beam.userData.speed * delta
      if (beam.position.y > beam.userData.resetHeight) {
        beam.position.x = (Math.random() - 0.5) * beam.userData.range
        beam.position.z = (Math.random() - 0.5) * beam.userData.range
        beam.position.y = -1 - Math.random() * 2
        beam.scale.y = 2 + Math.random() * 3
      }
    })
  }
  // 悬停州市抬升
  regionMeshes.forEach(m => {
    const target = m === hovered ? 1.5 : 1
    m.scale.z += (target - m.scale.z) * 0.12
  })

  controls.update()
  renderer.render(scene, camera)
  labelRenderer.render(scene, camera)
}

// ====== 初始化 / 销毁 ======
function init() {
  const host = hostRef.value
  const w = host.clientWidth || 800
  const h = host.clientHeight || 600

  themeMode = themeStore.isDark() ? 'dark' : 'light'
  scene = new THREE.Scene()
  scene.background = new THREE.Color(themeC().bg)
  scene.fog = new THREE.Fog(themeC().bg, 20, 46)

  camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 200)
  camera.position.copy(CAM_START)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h)
  host.appendChild(renderer.domElement)

  labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(w, h)
  labelRenderer.domElement.className = 'm3d-label-layer'
  host.appendChild(labelRenderer.domElement)

  // 灯光（位置/配色沿用 sc-datav，强度按 0.1 重调：只有顶面 topMat 受光照影响，
  // 原强度下白顶漫反射≈9 倍饱和裁剪，法线浮雕会被完全淹没；现平顶总亮度≈0.95，
  // 北坡变亮/南坡变暗的浮雕调制才能显现在哑光顶面上）
  scene.add(new THREE.AmbientLight(0xffffff, 0.25))
  const dir1 = new THREE.DirectionalLight(0xffffff, 0.8)
  dir1.position.set(0, 50, -50)
  scene.add(dir1)
  const dir2 = new THREE.DirectionalLight(0x88ccff, 0.25)
  dir2.position.set(-30, 40, 30)
  scene.add(dir2)

  // 贴图
  const loader = new THREE.TextureLoader()
  flyTex = loader.load(flyLineUrl, (t) => {
    t.wrapS = t.wrapT = THREE.RepeatWrapping
    t.repeat.set(0.5, 2)
  })
  ringTex = loader.load(ringUrl)
  ringTex.colorSpace = THREE.SRGBColorSpace
  // 地形法线贴图：保持线性色彩空间（法线数据不做 sRGB 解码），各向异性过滤提升斜视角清晰度
  normalTex = loader.load(terrainNormalUrl)
  normalTex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy())

  sweepMat = makeSweepMaterial(DEPTH)
  buildMap()
  buildAmbience()
  applySceneTheme()

  // 控制器（入场动画结束后启用）
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 6
  controls.maxDistance = 34
  controls.maxPolarAngle = 1.42
  controls.minPolarAngle = 0.52   // 禁止转到近天顶：俯视时柱体投影会退化成空白圆片
  controls.zoomSpeed = 0.6
  controls.target.set(0, 0.4, 0)
  controls.enabled = false
  controls.addEventListener('change', scheduleClusters)

  // 事件
  host.addEventListener('pointermove', onPointerMove)
  host.addEventListener('pointerdown', onPointerDown)
  host.addEventListener('pointerup', onPointerUp)

  resizeObserver = new ResizeObserver(() => {
    const nw = host.clientWidth, nh = host.clientHeight
    if (!nw || !nh) return
    camera.aspect = nw / nh
    camera.updateProjectionMatrix()
    renderer.setSize(nw, nh)
    labelRenderer.setSize(nw, nh)
    scheduleClusters()
  })
  resizeObserver.observe(host)

  clock.start()
  tick()
}

function dispose() {
  cancelAnimationFrame(rafId)
  if (rebuildTimer) { clearTimeout(rebuildTimer); rebuildTimer = null }
  const host = hostRef.value
  if (host) {
    host.removeEventListener('pointermove', onPointerMove)
    host.removeEventListener('pointerdown', onPointerDown)
    host.removeEventListener('pointerup', onPointerUp)
  }
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
  if (controls) { controls.dispose(); controls = null }
  if (mapGroup) { scene.remove(mapGroup); disposeGroupUtil(mapGroup, sweepMat); mapGroup = null }
  if (bottomRing) { scene.remove(bottomRing); bottomRing.geometry.dispose(); bottomRing.material.dispose() }
  if (beams) {
    beams.children.forEach(b => b.material.dispose())
    beams.geometry && beams.geometry.dispose()
    scene.remove(beams)
  }
  if (sweepMat) { sweepMat.dispose(); sweepMat = null }
  if (flyTex) flyTex.dispose()
  if (ringTex) ringTex.dispose()
  if (normalTex) normalTex.dispose()
  if (renderer) { renderer.dispose(); renderer.domElement && renderer.domElement.remove(); renderer = null }
  if (labelRenderer) { labelRenderer.domElement && labelRenderer.domElement.remove(); labelRenderer = null }
  regionMeshes = []
  edgesMats = []
  flyMats = []
}

// ====== 响应外部数据 ======
watch(() => props.cityRiskData, (rd) => {
  regionMeshes.forEach(m => {
    const top = Array.isArray(m.material) ? m.material[0] : m.material
    top.color.copy(topColorForUtil(m.userData.name, rd, themeC().neutral))
  })
}, { deep: true })

watch(() => props.firePoints, () => scheduleClusters())

// 明暗主题联动
watch(() => themeStore.mode, () => applySceneTheme())

/** 复位视角（dock「全省」按钮在 3D 模式下调用） */
function resetView() {
  introProgress = 0
  introClusterDone = false
  controls.enabled = false
  controls.target.set(0, 0.4, 0)
}

defineExpose({ resetView })

onMounted(init)
onBeforeUnmount(dispose)
</script>

<template>
  <div ref="hostRef" class="m3d-root">
    <div class="m3d-hint">拖拽旋转 · 滚轮缩放 · 点击州市检索</div>
  </div>
</template>

<style scoped>
.m3d-root {
  position: absolute;
  inset: 0;
  overflow: hidden;
  cursor: grab;
}

.m3d-root :deep(canvas) {
  display: block;
}

.m3d-hint {
  position: absolute;
  right: 12px;
  bottom: 10px;
  font-size: 10px;
  letter-spacing: 0.08em;
  color: rgba(148, 197, 235, 0.55);
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  pointer-events: none;
  z-index: 5;
}

html:not(.dark) .m3d-hint {
  color: rgba(30, 90, 138, 0.6);
}
</style>

<!-- CSS2D 标签由 three 动态插入，无法被 scoped 编译，需全局样式 -->
<style>
.m3d-label-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.m3d-label {
  color: #e8f4ff;
  font-size: 11px;
  letter-spacing: 0.06em;
  white-space: nowrap;
  text-shadow: 0 0 6px rgba(56, 189, 248, 0.9), 0 1px 3px rgba(0, 0, 0, 0.9);
  transform: translateY(-6px);
}

/* 柱顶火点总数标签 */
.m3d-bar-label {
  color: #fcd34d;
  font-size: 10px;
  font-weight: 600;
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  white-space: nowrap;
  text-shadow: 0 0 6px rgba(251, 191, 36, 0.75), 0 1px 2px rgba(0, 0, 0, 0.85);
  transform: translateY(-2px);
}

/* 浅色主题：深字 + 白色柔光，保证可读性 */
html:not(.dark) .m3d-label {
  color: #14456e;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.92), 0 0 6px rgba(255, 255, 255, 0.75);
}

html:not(.dark) .m3d-bar-label {
  color: #b45309;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.92);
}
</style>
