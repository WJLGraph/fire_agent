/**
 * 3D 地图（Three.js）· 几何与聚类工具
 *
 * 阶段 4h：从 components/map/Map3D.vue 中整段搬出，逻辑一字未改；
 * 仅把原本闭包内的模块级变量（TARGET / geoBBox / 主题中性色）改为显式入参/返回值。
 */
import * as THREE from 'three'
import { RISK_COLORS } from '@/utils/riskLevel'

// 地图归一化后最长边（世界单位）
export const MAP3D_TARGET = 16

/**
 * Mercator 投影 + 归一化
 * @param {Object} geojson 州市边界 GeoJSON
 * @param {number} target 归一化目标边长（默认 MAP3D_TARGET）
 * @returns {{ proj: Function, bbox: Object }} proj: 经纬度 → 世界坐标 [x, y]；bbox: 全省投影包络
 */
export function buildProjection(geojson, target = MAP3D_TARGET) {
  let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
  const scan = (coords) => {
    if (typeof coords[0] === 'number') {
      if (coords[0] < minLng) minLng = coords[0]
      if (coords[0] > maxLng) maxLng = coords[0]
      if (coords[1] < minLat) minLat = coords[1]
      if (coords[1] > maxLat) maxLat = coords[1]
      return
    }
    coords.forEach(scan)
  }
  geojson.features.forEach(f => scan(f.geometry.coordinates))

  const R = 6378137
  const c0 = (minLng + maxLng) / 2
  const c1 = (minLat + maxLat) / 2
  const raw = ([lng, lat]) => [
    R * (lng - c0) * Math.PI / 180,
    R * Math.log(Math.tan(Math.PI / 4 + (lat - c1) * Math.PI / 360)),
  ]
  // 用原始墨卡托包络计算缩放比
  const corners = [
    raw([minLng, minLat]), raw([maxLng, minLat]),
    raw([minLng, maxLat]), raw([maxLng, maxLat]),
  ]
  const xs = corners.map(p => p[0]), ys = corners.map(p => p[1])
  const s = target / Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys))
  // 全省几何包络（投影后世界坐标）：顶面法线贴图全局 UV 的基准
  const bbox = {
    minX: Math.min(...xs) * s, maxX: Math.max(...xs) * s,
    minY: Math.min(...ys) * s, maxY: Math.max(...ys) * s,
  }
  // y 不取负：北 = 局部 +Y；配合地图组 rotation.x = -PI/2（局部 +Y → 世界 -Z，远离相机），
  // 北指向屏幕上方、东指向屏幕右侧，与 2D 地图朝向一致
  const proj = ([lng, lat]) => {
    const [x, y] = raw([lng, lat])
    return [x * s, y * s]
  }
  return { proj, bbox }
}

// ====== GeoJSON 几何归一化（Polygon / MultiPolygon → 环数组列表） ======
export function featurePolys(feature) {
  const g = feature.geometry
  if (!g) return []
  if (g.type === 'Polygon') return [g.coordinates]
  if (g.type === 'MultiPolygon') return g.coordinates
  return []
}

export function ringsToShape(rings, proj) {
  const toVec2 = ring => ring.map(c => {
    const [x, y] = proj(c)
    return new THREE.Vector2(x, y)
  })
  const shape = new THREE.Shape(toVec2(rings[0]))
  for (let i = 1; i < rings.length; i++) {
    shape.holes.push(new THREE.Path(toVec2(rings[i])))
  }
  return shape
}

// 顶面颜色：有火险等级用等级色，否则中性色（随主题变化）
export function topColorFor(name, riskData, neutral) {
  const level = riskData && riskData[name]
  if (level >= 1 && level <= 5) return new THREE.Color(RISK_COLORS[level - 1])
  return new THREE.Color(neutral)
}

// 顶面全局 UV：以全省几何投影包络为基准归一化（侧面/底盖 UV 一并覆写，
// 但侧面扫光 shader 不采样 UV，无影响；顶面据此与地形法线贴图逐像素对齐）
export function applyBboxUV(geo, bbox) {
  if (!bbox || !geo.attributes.uv) return
  const pos = geo.attributes.position
  const uv = geo.attributes.uv
  const dx = bbox.maxX - bbox.minX
  const dy = bbox.maxY - bbox.minY
  for (let i = 0; i < pos.count; i++) {
    uv.setXY(i, (pos.getX(i) - bbox.minX) / dx, (pos.getY(i) - bbox.minY) / dy)
  }
  uv.needsUpdate = true
}

// ====== 火点聚合 ======
// 州市名归一：剥掉民族后缀/行政后缀后比对（西双版纳傣族自治州 ↔ 西双版纳州 ↔ 西双版纳）
export const normCity = s => String(s || '')
  .replace(/傣族|彝族|哈尼族|白族|壮族|苗族|藏族|傈僳族|景颇族|回族|纳西族|自治州|地区|市|州/g, '')

export function haversineKm(a, b) {
  const rad = Math.PI / 180
  const dLat = (b[1] - a[1]) * rad
  const dLng = (b[0] - a[0]) * rad
  const s = Math.sin(dLat / 2) ** 2 +
    Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLng / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(s))
}

// 火点归属州市：优先 properties.city 文本匹配，无 city 字段则就近州市中心归簇
export function cityOfPoint(feature, centers) {
  const p = feature.properties || {}
  const raw = p.city || p.region || p.adname || ''
  if (raw) {
    const key = normCity(raw)
    const hit = centers.find(c => {
      const rn = normCity(c.name)
      return (rn && key && (rn === key || rn.includes(key) || key.includes(rn)))
    })
    if (hit) return hit.name
  }
  const c = feature.geometry && feature.geometry.coordinates
  if (c && typeof c[0] === 'number' && centers.length) {
    let best = null, bestD = Infinity
    centers.forEach(ctr => {
      const d = haversineKm(ctr.lngLat, [c[0], c[1]])
      if (d < bestD) { bestD = d; best = ctr }
    })
    if (best) return best.name
  }
  return null
}
