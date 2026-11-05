<script setup>
/**
 * ============================================================================
 * 焰哨 FlameSentry · 智慧火险预警监测平台 · 作战大屏
 *
 * 页面布局（三栏 flex 填充视口）：
 *   顶栏(56px) → 主体(左右侧栏+地图) → 底栏
 *
 * 核心数据流：
 *   fireDataJson / predictDailyJson / predictMonthJson → processedPredictData → displayFireData → map.vue
 *   地图点击聚合点 → clusterData → el-drawer（火点详情表格）
 *
 * 依赖：Vue3 | OpenLayers | ECharts | Element Plus | Turf.js | 天地图 | 高德天气API
 *
 * 拆分说明（阶段 4c）：本文件只保留「数据编排 + 地图实例生命周期」，
 *   展示区块分别下沉到 DashboardTopBar / FireWarningBar / VisionRail / MapToolbar / ClusterDrawer。
 * ============================================================================
 */
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import MapModule from '@/components/map/Map2D.vue'                   // OpenLayers 地图核心
import Map3D from '@/components/map/Map3D.vue'                       // Three.js 3D 地图（sc-datav 风格）
import { downloadMap } from '@/utils/downLoad'                    // 地图导出 PNG
import { upDateCurrentTime, upDateCurrentDate } from '@/utils/timeWeather'
import { createDraw } from '@/utils/draw'                        // OL Draw 交互
import { calculateArea, calculateDistance } from '@/utils/computed' // Turf.js 量测
import { ElMessage } from 'element-plus'
import { useFireWarning, usePredictData } from '@/composables/useRiskAnalytics'

// ========== 本页展示区块子组件 ==========
import DashboardTopBar   from './DashboardTopBar.vue'   // 顶栏（单行 64px：字标/KPI/天气/时钟）
import RailFilterPanel   from './RailFilterPanel.vue'   // 右栏筛选面板（数据模式 seg + 日期/行政区 + 预警）
import MapOverlays       from './MapOverlays.vue'       // 地图浮层（数据源徽标 + 火险图例）
import VisionRail        from './VisionRail.vue'        // AI 火情识别侧栏（自包含）
import MapToolbar        from './MapToolbar.vue'        // 地图底栏工具坞
import ClusterDrawer     from './ClusterDrawer.vue'     // 火点/火险详情抽屉

// ========== API 服务 ==========
import { fetchHistoryFires, fetchPredictRisks } from '@/api/dashboard'

// ========== 图表组件（ECharts） ==========
import RightFirstChart  from '../chart/proportionFireRiskWarnings.vue'  // 预测火险占比（右上）
import RightSecondChart from '../chart/distributionFireRiskWarning.vue' // 预测火险分布（右下）
import LeftFirstChart   from '../chart/historicalFireHazardLevel.vue'   // 历史火险等级（左上）
import LeftSecondChart  from '../chart/historicalFireFrequency.vue'      // 历史火点频次（左下）

// ========== OpenLayers ==========
import VectorSource from 'ol/source/Vector'
import VectorLayer from 'ol/layer/Vector'
import { Heatmap as HeatmapLayer } from 'ol/layer'
import GeoJSON from 'ol/format/GeoJSON'

// ========== 数据文件（本地 JSON 作为 API 降级兜底） ==========
import fireDataJson     from '@/assets/Yunnan_fire.json'        // 历史火点（NASA FIRMS MODIS）
import borderDataJson   from '@/assets/Yunnan_border.json'       // 州市行政边界 GeoJSON
import predictMonthJson  from '@/assets/predict_2025_2026_month.json' // 逐月预测火险
import predictDailyJson  from '@/assets/predict_2025_2026_daily.json' // 逐日预测火险（含Day字段）

// ====== API 数据状态（ref 包装，computed 自动追踪） ======
const apiLoading = ref(false)
// DataAgent 数据管线状态：loading（同步中）/ api（后端数据）/ local（本地降级）
const dataSource = ref('loading')
const syncedAt   = ref('')  // 数据同步完成时刻（HH:MM，用于地图数据源徽标）
const historyFireData = ref(fireDataJson)       // 初始值为本地 JSON
const predictDailyData = ref(predictDailyJson)
const predictMonthData = ref(predictMonthJson)

/** 分页拉取全部历史火点（后端 page_size 上限 5000，库中 5411 条，单次拉不全） */
async function fetchAllHistoryFires() {
  const PAGE_SIZE = 5000
  const first = await fetchHistoryFires({ page: 1, page_size: PAGE_SIZE }).catch(() => null)
  if (!first) return null
  let items = [...(first.items || [])]
  const total = Number(first.total) || items.length
  let page = 2
  while (items.length < total) {
    const next = await fetchHistoryFires({ page, page_size: PAGE_SIZE }).catch(() => null)
    if (!next || !(next.items || []).length) break
    items = items.concat(next.items)
    page += 1
  }
  return { total: items.length, items }
}

/** 从后端 API 加载大屏数据，失败时自动降级到本地 JSON */
async function loadDashboardData() {
  apiLoading.value = true
  dataSource.value = 'loading'
  try {
    const [historyResult, dailyResult, monthlyResult] = await Promise.all([
      fetchAllHistoryFires(),
      fetchPredictRisks({ view_mode: 'daily' }).catch(() => null),
      fetchPredictRisks({ view_mode: 'monthly' }).catch(() => null),
    ])

    // 任一数据源成功即视为「后端数据」，全部失败才降级本地
    dataSource.value = (historyResult || dailyResult || monthlyResult) ? 'api' : 'local'

    // 如果 API 成功，将后端返回的 items 转换为本地一致的格式
    if (historyResult) {
      historyFireData.value = {
        type: 'FeatureCollection',
        features: (historyResult.items || []).map(item => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [item.longitude, item.latitude],
          },
          properties: item,
        })),
      }
    }
    if (dailyResult) {
      predictDailyData.value = (dailyResult.items || []).map(item => ({
        City: item.city,
        Year: item.year,
        Month: item.month,
        Day: item.day,
        Base_Fire_Index: item.base_fire_index,
        Final_Fire_Index: item.final_fire_index,
        Fire_Level: item.fire_level,
        Pred_Fire_Count: item.pred_fire_count,
      }))
    }
    if (monthlyResult) {
      predictMonthData.value = (monthlyResult.items || []).map(item => ({
        City: item.city,
        Year: item.year,
        Month: item.month,
        Pred_Fire_Risk: item.pred_fire_risk ?? item.risk_score,
        Risk_Score: item.risk_score,
      }))
    }
  } catch {
    // 静默降级，保持本地 JSON
  } finally {
    apiLoading.value = false
    const now = new Date()
    syncedAt.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  }
}

// ====== 界面状态 ======
const currentTime   = ref('')
const currentDate   = ref('')
const activeTool    = ref('')  // 当前展开的工具菜单（'layer' | 'draw' | 'measure' | ''）
const layers        = ref([])

// ====== 州市选项（从边界 GeoJSON 提取，用于下拉选择） ======
const cityOptions = computed(() => borderDataJson.features.map(f => f.properties.name))

// ====== 地图实例引用 ======
let drawSource = {}
let map = null
const mapRef   = ref(null)

// ====== Draw / Measure 交互 ======
let drawInteraction    = null
let measureInteraction = null
let measureSource = new VectorSource()
let measureLayer  = new VectorLayer({ source: measureSource, title: '测量图层' })

// ====== 火点详情抽屉 ======
const drawerVisible = ref(false)
const clusterData   = ref([])

// ====== 数据切换与筛选 ======
const currentDataType = ref('history') // 'history' | 'predict'
const predictViewMode = ref('daily') // 'daily' | 'monthly' — 预测火险的逐日/逐月视图
const searchDate      = ref('')

// 日期选择器可选年份：历史火点与预测火险数据范围不同
const HISTORY_FIRE_YEAR_MIN = 2021
const HISTORY_FIRE_YEAR_MAX = 2025
const PREDICT_YEAR_MIN = 2025
const PREDICT_YEAR_MAX = 2026

const searchCity      = ref('')

// 右栏图表分组与数据模式合一：筛选面板的「历史火点/预测火险」seg 即总开关，
// 图表分组直接跟随 currentDataType（地图、图表、KPI、预警同源联动）
const railTab = computed(() => (currentDataType.value === 'predict' ? 'predict' : 'history'))

// ====== 火险预警 / 预测数据计算（纯计算逻辑，见 composables/useRiskAnalytics.js） ======
const { fireWarning } = useFireWarning({
  currentDataType, searchDate, predictViewMode, predictDailyData, predictMonthData,
})
const { processedPredictData, cityRiskData, predictDataForChart } = usePredictData({
  currentDataType, searchDate, predictViewMode, predictDailyData, predictMonthData,
})

// ====== 顶栏预警兜底：无论当前处于历史/预测模式，预警始终基于最新预测日期有值 ======
// 预测数据最新可用日期（daily 精确到日，作为预警默认口径）
const latestPredictDate = computed(() => {
  const d = predictDailyData.value
  if (!d.length) return ''
  let max = d[0]
  for (const r of d) {
    const y = Number(r.Year), m = Number(r.Month), dd = Number(r.Day)
    const my = Number(max.Year), mm = Number(max.Month), md = Number(max.Day)
    if (y > my || (y === my && m > mm) || (y === my && m === mm && dd > md)) max = r
  }
  return `${max.Year}-${String(Number(max.Month)).padStart(2, '0')}-${String(Number(max.Day)).padStart(2, '0')}`
})
// 预警计算用日期：预测模式且所选日期在预测范围内 → 用所选（逐月 YYYY-MM 同样可用，逐月口径只取年月）；
// 否则 → 最新预测日期（YYYY-MM-DD，逐日口径可直接用，逐月口径亦只取年月，兼容）
const warningDate = computed(() => {
  if (currentDataType.value === 'predict' && searchDate.value) {
    const y = Number(searchDate.value.split('-')[0])
    if (y >= PREDICT_YEAR_MIN && y <= PREDICT_YEAR_MAX) return searchDate.value
  }
  return latestPredictDate.value
})
// 预警粒度跟随当前预测视图；历史模式下按逐日最新数据出预警
const kpiViewMode = computed(() =>
  currentDataType.value === 'predict' ? predictViewMode.value : 'daily'
)
const { fireWarning: kpiWarning } = useFireWarning({
  currentDataType: ref('predict'),
  searchDate: warningDate,
  predictViewMode: kpiViewMode,
  predictDailyData,
  predictMonthData,
})




const predictFireData = processedPredictData


// ====== 当前显示的火点数据（按日期 + 行政区筛选，2D/3D/热力/KPI 全部联动） ======
// 历史模式：按 acq_date 精确过滤 searchDate；预测模式：processedPredictData 已按 searchDate 过滤
// 行政区：历史数据带 city 字段（后端）时按城市过滤；预测数据天然带 city
const displayFireData = computed(() => {
  const matchCity = (props) => {
    if (!searchCity.value) return true
    const c = props?.city || props?.City
    if (!c) return true // 本地降级数据无 city 字段，不过滤（保持全量展示）
    return c === searchCity.value || c.includes(searchCity.value) || searchCity.value.includes(c)
  }
  if (currentDataType.value === 'history') {
    let features = historyFireData.value.features
    if (searchDate.value) {
      features = features.filter(f => f.properties.acq_date && f.properties.acq_date === searchDate.value)
    }
    features = features.filter(f => matchCity(f.properties))
    return { ...historyFireData.value, features }
  }
  const pred = predictFireData.value
  if (!searchCity.value) return pred
  return { ...pred, features: (pred.features || []).filter(f => matchCity(f.properties)) }
})

// ====== 顶栏 KPI（§10.6：顶栏只留字标 / 时间 / 天气 / 3 个 KPI） ======
// 当前火点：跟随当前模式与筛选（历史=筛选后火点数；预测=预测火点数）
// 高风险州市 / 预警等级：始终基于预警数据（预测口径，未选日期时兜底最新预测日期），不再恒为 0 / —
const topKpis = computed(() => {
  const fireCount = displayFireData.value?.features?.length || 0
  const w = kpiWarning.value
  const highRisk = w && typeof w.highRiskCount === 'number' ? w.highRiskCount : 0
  return [
    { key: 'fires', label: '当前火点', value: fireCount.toLocaleString(), unit: '处' },
    { key: 'high', label: '高风险州市', value: String(highRisk), unit: '个', hot: true },
    // 预警等级读数取预警口径的等级色（与右栏预警条、地图图例同源，不引入新色值）
    { key: 'level', label: '预警等级', value: w?.summary?.label || '—', color: w?.summary?.color || '' },
  ]
})

// ====== 切换历史/预测模式 ======
// 进入预测模式时，若未选日期或日期越界，自动落到最新预测日期：
// 地图火点、右侧图表、预警条、顶栏 KPI 立即有数据（联动而非空屏）
const applyPredictDefaultDate = () => {
  if (predictViewMode.value === 'monthly') {
    const d = predictMonthData.value
    if (d.length && !searchDate.value) {
      const max = d.reduce((m, r) =>
        (Number(r.Year) * 100 + Number(r.Month)) > (Number(m.Year) * 100 + Number(m.Month)) ? r : m, d[0])
      searchDate.value = `${max.Year}-${String(Number(max.Month)).padStart(2, '0')}`
    }
  } else if (!searchDate.value) {
    searchDate.value = latestPredictDate.value
  }
}
const toggleDataType = (type) => {
  currentDataType.value = type
  // 两个模式的数据范围不同（历史 2021–2025 / 预测 2025–2026），切换时校验已选日期：
  // 越界即重置 —— 历史模式空日期 = 显示全部火点；预测模式空日期由下方自动落最新预测日期
  if (searchDate.value) {
    const y = Number(searchDate.value.split('-')[0])
    const ok = type === 'history'
      ? y >= HISTORY_FIRE_YEAR_MIN && y <= HISTORY_FIRE_YEAR_MAX
      : y >= PREDICT_YEAR_MIN && y <= PREDICT_YEAR_MAX
    if (!ok) searchDate.value = ''
  }
  if (type === 'predict') applyPredictDefaultDate()
  ElMessage.success({
    message: type === 'predict' ? '已切换至预测火点数据模式' : '已切换至历史火点数据模式',
    duration: 500
  })
}

// 逐日/逐月切换时，粒度格式不同（YYYY-MM-DD vs YYYY-MM），清空并补默认日期
watch(predictViewMode, () => {
  if (currentDataType.value !== 'predict') return
  searchDate.value = ''
  applyPredictDefaultDate()
})

// ====== 地图模式：3D（Three.js） / 2D（OpenLayers 完整工具） ======
const mapMode = ref('3d')
const visionRailOpen = ref(false)  // AI 火情图片识别抽屉展开态（控制地图徽标避让）
const map3dRef = ref(null)
const switchMapMode = (m) => {
  mapMode.value = m
  if (m === '3d') {
    // 图层/标绘/量测/热力均为 OL 2D 专属，切 3D 时收起展开中的菜单
    activeTool.value = ''
  } else {
    // v-show 从隐藏到显示后，OpenLayers 需重算画布尺寸
    nextTick(() => { try { mapRef.value?.resize?.() } catch { /* 忽略 */ } })
  }
}
// 3D 模式点击州市 → 与 2D「检索」同链路（筛选 + 预警联动）
const handleMap3DCityClick = (city) => {
  searchCity.value = city
  handleSearch()
}
// 3D 模式下导出按钮守卫（OL 画布隐藏）
const handleDownload = () => {
  if (mapMode.value === '3d') return
  downloadMap(map)
}
// 「全省」按钮：3D 走 Three.js 复位，2D 走 OpenLayers 动画
const handleResetView = () => {
  if (mapMode.value === '3d') map3dRef.value?.resetView()
  else animateView()
}

// ====== 检索：定位州市 + 筛选日期 ======
const handleSearch = () => {
  if (searchCity.value) {
    const cityFeature = borderDataJson.features.find(f => f.properties.name.includes(searchCity.value))
    if (cityFeature) {
      const geometry = new GeoJSON().readFeature(cityFeature).getGeometry()
      const extent   = geometry.getExtent()
      if (mapRef.value) {
        mapRef.value.flyToExtent(extent)
        mapRef.value.highlightCity(cityFeature)
        ElMessage.success({ message: `已定位到 ${cityFeature.properties.name}`, duration: 1800 })
      }
    } else {
      ElMessage.warning({ message: '未找到该城市，请检查输入', duration: 2000 })
    }
  } else if (searchDate.value) {
    ElMessage.success({ message: `已筛选 ${searchDate.value} 的火点数据`, duration: 1800 })
  }
}

// ====== 地图加载完成回调 ======
const handleMapLoaded = (mapInstance) => {
  map = mapInstance
  layers.value = map.getLayers().getArray()

  // 为每种几何类型创建独立画笔图层（点/线/面/圆）
  drawSource = {
    Point: new VectorSource(), LineString: new VectorSource(),
    Polygon: new VectorSource(), Circle: new VectorSource()
  }
  for (const [type, source] of Object.entries(drawSource)) {
    map.addLayer(new VectorLayer({ source, title: '画笔图层' }))
  }
  map.addLayer(measureLayer) // 测量图层
}

// ====== 聚合点击 → 打开抽屉 ======
const handleClusterClick = (data) => {
  clusterData.value = data
  drawerVisible.value = true
}

// ====== 定位到云南省中心 ======
const animateView = () => {
  if (!map) return
  const view = map.getView()
  view.cancelAnimations()
  view.animate({ center: [102.42, 25.02], zoom: 6, duration: 1000 })
}

// ====== 标绘工具 ======
const activeDrawTool = (type) => {
  if (!map) return
  if (measureInteraction) { map.removeInteraction(measureInteraction); measureInteraction = null }
  if (drawInteraction)    { map.removeInteraction(drawInteraction); drawInteraction = null }
  drawInteraction = createDraw({ type, source: drawSource[type] })
  map.addInteraction(drawInteraction)
}

// ====== 清空标绘与测量 ======
const clearDraw = () => {
  for (const key in drawSource) drawSource[key].clear()
  measureSource.clear()
  map.getOverlays().getArray().slice(0).forEach(overlay => map.removeOverlay(overlay))
}

// ====== 测量工具 ======
const activeMeasureTool = (type) => {
  if (!map) return
  if (drawInteraction)    { map.removeInteraction(drawInteraction);    drawInteraction = null }
  if (measureInteraction) { map.removeInteraction(measureInteraction); measureInteraction = null }
  measureInteraction = createDraw({ type, source: measureSource })
  map.addInteraction(measureInteraction)
  measureInteraction.on('drawend', (e) => {
    const geometry = e.feature.getGeometry()
    const coords   = geometry.getCoordinates()
    if (type === 'LineString') calculateDistance(coords)
    else if (type === 'Polygon') calculateArea(coords[0])
    map.removeInteraction(measureInteraction)
    measureInteraction = null
  })
}

// ====== 生命周期 ======
onMounted(() => {
  upDateCurrentTime(currentTime)
  upDateCurrentDate(currentDate)

  // 从后端 API 加载大屏数据（失败自动降级到本地 JSON）
  loadDashboardData()

  // 每秒更新时间
  const timer = setInterval(() => {
    upDateCurrentTime(currentTime)
    upDateCurrentDate(currentDate)
  }, 1000)

  onUnmounted(() => {
    clearInterval(timer)
    if (map) {
      if (drawInteraction)    map.removeInteraction(drawInteraction)
      if (measureInteraction) map.removeInteraction(measureInteraction)
    }
  })
})

// ====== 工具菜单切换 ======
const toggleToolMenu = (tool) => {
  if (mapMode.value === '3d') return // 3D 模式下 OL 专属工具不可用
  activeTool.value = activeTool.value === tool ? '' : tool
}

// ====== 图层显隐切换 ======
const toggleLayer = (layer) => {
  layer.setVisible(!layer.getVisible())
}

// ====== 图层查找/移除工具 ======
const removeLayerByTitle = (title) => {
  if (!map) return
  map.getLayers().getArray().forEach(layer => {
    if (layer.get('title') === title) map.removeLayer(layer)
  })
}
const getLayerByTitle = (title) => {
  if (!map) return null
  return map.getLayers().getArray().find(layer => layer.get('title') === title)
}

// ====== 热力图 ======
const showHeatmap      = ref(false)
let heatMapLayerInst  = ref(null)

const performHeatmapAnalysis = () => {
  if (!map || mapMode.value === '3d') return // 3D 模式下热力分析不可用（OL 画布隐藏）
  const pointLayer  = getLayerByTitle('火点分布')
  const predictLayer = getLayerByTitle('预测火险图层')

  if (showHeatmap.value) {
    // 关闭：移除热力图，恢复点位图层
    removeLayerByTitle('热力图')
    if (currentDataType.value === 'history' && pointLayer)  pointLayer.setVisible(true)
    if (currentDataType.value === 'predict' && predictLayer) predictLayer.setVisible(true)
  } else {
    // 开启：创建热力图层，隐藏点位图层
    const heatSource = new VectorSource({
      features: new GeoJSON().readFeatures(displayFireData.value)
    })
    heatMapLayerInst.value = new HeatmapLayer({
      source: heatSource,
      blur:   currentDataType.value === 'predict' ? 25 : 15,
      radius: currentDataType.value === 'predict' ? 12 : 8,
      // 渐变色：透明 → 青色 → 橙色 → 红色
      gradient: ['rgba(0,0,0,0)', '#0e7490', '#0891b2', '#f97316', '#dc2626'],
      weight: (feature) => {
        if (currentDataType.value === 'predict') {
          // 逐日/逐月均带 risk_level；逐日 risk_score 为指数量级，不宜直接作权重
          const rl = feature.get('risk_level')
          if (rl != null) return 0.12 + (Math.min(5, Math.max(1, Number(rl))) / 5) * 0.75
          const rs = feature.get('risk_score')
          return rs != null ? Math.min(Number(rs) * 0.8, 0.95) : 0.15
        }
        const frp = feature.get('frp')
        return frp ? Math.min(frp / 150, 0.8) : 0.1
      },
      zIndex: 1
    })
    heatMapLayerInst.value.set('title', '热力图')
    map.addLayer(heatMapLayerInst.value)
    if (pointLayer)   pointLayer.setVisible(false)
    if (predictLayer) predictLayer.setVisible(false)
  }

  showHeatmap.value = !showHeatmap.value
  map.render()
}
</script>

<template>
  <div class="gis-shell">
    <!-- ======================= 顶栏（v0 dash-top 同构：字标/KPI/天气/时钟） ======================= -->
    <DashboardTopBar :kpis="topKpis" />

    <!-- ======================= 主体三栏 ======================= -->
    <div class="gis-body">
      <!-- 中栏：地图 + 工具栏（地图是唯一主角，AI 识别/图例/徽标均浮于其上） -->
      <div class="gis-map-stage">
        <div class="gis-map-frame">
          <div class="gis-map-inner">
            <!-- AI 火情图片识别：左缘浮层（v0 vision-tab + drawer，折叠为 34px 竖条） -->
            <VisionRail class="vision-overlay" @expand="visionRailOpen = $event" />
            <!-- 3D 模式：Three.js 场景（sc-datav 风格：挤出面片 + 扫光 + 飞线 + 光柱） -->
            <Map3D
              v-show="mapMode === '3d'"
              ref="map3dRef"
              :city-polygons="borderDataJson"
              :city-risk-data="cityRiskData"
              :fire-points="displayFireData"
              @city-click="handleMap3DCityClick"
            />
            <!-- 2D 模式：OpenLayers（完整工具链） -->
            <MapModule
              v-show="mapMode === '2d'"
              ref="mapRef"
              :fireData="currentDataType === 'history' ? displayFireData : { type: 'FeatureCollection', features: [] }"
              :predictData="currentDataType === 'predict' ? displayFireData : { type: 'FeatureCollection', features: [] }"
              :currentDataType="currentDataType"
              :cityRiskData="cityRiskData"
              @map-loaded="handleMapLoaded"
              @cluster-click="handleClusterClick"
            />
            <!-- 数据源徽标 + 火险等级图例（visual-v0 §10.7；抽屉展开时徽标右移避让） -->
            <MapOverlays
              :current-data-type="currentDataType"
              :data-source="dataSource"
              :api-loading="apiLoading"
              :synced-at="syncedAt"
              :src-shift="visionRailOpen"
            />
          </div>
        </div>
        <!-- 底部浮动工具条（v0 map-tools 同构；2D 专属工具仅 2D 模式渲染） -->
        <MapToolbar
          :layers="layers"
          :active-tool="activeTool"
          :show-heatmap="showHeatmap"
          :map-mode="mapMode"
          @toggle-tool-menu="toggleToolMenu"
          @toggle-layer="toggleLayer"
          @draw="activeDrawTool"
          @clear-draw="clearDraw"
          @measure="activeMeasureTool"
          @toggle-heatmap="performHeatmapAnalysis"
          @download="handleDownload"
          @reset-view="handleResetView"
          @switch-mode="switchMapMode"
        />
      </div>

      <!-- 右栏：筛选区 + 图表按「历史 / 预测」分组，同屏仅 2 张（D9，v0 chart-card 同构） -->
      <aside class="gis-rail gis-rail-right">
        <!-- 筛选区：数据模式 seg 即总开关，地图/图表/KPI 全联动 -->
        <RailFilterPanel
          :current-data-type="currentDataType"
          v-model:predict-view-mode="predictViewMode"
          v-model:search-date="searchDate"
          v-model:search-city="searchCity"
          :city-options="cityOptions"
          :fire-warning="fireWarning"
          @toggle-data-type="toggleDataType"
          @search="handleSearch"
        />

        <div class="rail-scroll">
          <!-- 数据同步骨架（apiLoading 时占位，防图表区闪空） -->
          <template v-if="apiLoading">
            <section v-for="n in 2" :key="`sk${n}`" class="chart-skel" aria-hidden="true">
              <div class="chart-skel__hd">
                <span class="chart-skel__bar mo-loop" style="width: 96px"></span>
                <span class="chart-skel__bar chart-skel__bar--short mo-loop"></span>
              </div>
              <div class="chart-skel__body">
                <span class="chart-skel__wave mo-loop"></span>
              </div>
            </section>
          </template>
          <template v-else-if="railTab === 'history'">
            <section class="chart-card">
              <div class="chart-card__hd">
                <span class="chart-card__t">历史火点危害等级</span>
                <span class="chart-card__sp"></span>
                <span class="chart-card__n">HIST · LEVEL</span>
              </div>
              <div class="chart-box"><LeftFirstChart :fireData="historyFireData" /></div>
            </section>
            <section class="chart-card">
              <div class="chart-card__hd">
                <span class="chart-card__t">历史火点发生频次</span>
                <span class="chart-card__sp"></span>
                <span class="chart-card__n">HIST · FREQ</span>
              </div>
              <div class="chart-box"><LeftSecondChart :fireData="historyFireData" /></div>
            </section>
          </template>

          <template v-else>
            <section class="chart-card">
              <div class="chart-card__hd">
                <span class="chart-card__t">预测火险等级占比</span>
                <span class="chart-card__sp"></span>
                <span class="chart-card__n">PRED · SHARE</span>
              </div>
              <div class="chart-box"><RightFirstChart :searchDate="searchDate" :viewMode="predictViewMode" :predictData="predictDataForChart" /></div>
            </section>
            <section class="chart-card">
              <div class="chart-card__hd">
                <span class="chart-card__t">预测火险等级频次分布</span>
                <span class="chart-card__sp"></span>
                <span class="chart-card__n">PRED · DIST</span>
              </div>
              <div class="chart-box"><RightSecondChart :searchDate="searchDate" :viewMode="predictViewMode" :predictData="predictDataForChart" /></div>
            </section>
          </template>
        </div>
      </aside>
    </div>

    <!-- ======================= 火点详情抽屉 ======================= -->
    <ClusterDrawer
      v-model="drawerVisible"
      :cluster-data="clusterData"
      :current-data-type="currentDataType"
      :predict-view-mode="predictViewMode"
    />

    <!-- ======================= 底栏 ======================= -->
    <footer class="gis-footer">
      <span class="gis-footer-coord">EPSG:4326 · WGS84 · wjl · 19136220923@163.com</span>
      <span class="gis-footer-copy">© 2026 焰哨多Agent与可视化平台</span>
      <a class="gis-footer-link" href="https://gitee.com/wjl2004/fire_agent_front" target="_blank">Gitee</a>
    </footer>
  </div>
</template>

<style lang="scss" scoped>
.gis-shell {
  user-select: none;
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 100%;
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  background: var(--fs-bg-canvas);
  color: var(--fs-ink-900);
  overflow: hidden;
}
.gis-body {
  position: relative;
  z-index: 10;
  display: flex;
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  width: 100%;
  padding: 0;
  gap: 0;
  overflow: hidden;
}
.gis-rail {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  z-index: 15;
  min-height: 0;
  background: var(--fs-bg-surface);
  border-left: 1px solid var(--fs-hairline);
  overflow: hidden;
}
/* v0 rail-scroll：图表卡 qt 面板化（hairline 边 + 内边距，与公开页数据卡同语言） */
.rail-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--fs-s4, 16px);
  display: flex;
  flex-direction: column;
  gap: var(--fs-s5, 20px);
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
  background: var(--fs-bg-sunken);
}
.chart-card {
  /* flex-shrink 归零：筛选区/预警详情变高时不再把图表压成扁条，改由 rail-scroll 滚动 */
  flex: 1 0 210px;
  min-height: 210px;
  display: flex;
  flex-direction: column;
  gap: var(--fs-s3, 12px);
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md);
  padding: 14px 14px 10px;
  transition:
    border-color 0.16s var(--fs-ease),
    box-shadow 0.16s var(--fs-ease),
    transform 0.16s var(--fs-ease);
}
.chart-card:hover {
  border-color: var(--fs-hairline-strong);
  box-shadow: var(--fs-e1);
  transform: translateY(-1px);
}

/* 数据同步骨架（shimmer：只动 transform/opacity 的伪元素平移） */
.chart-skel {
  flex: 1 0 210px;
  min-height: 210px;
  display: flex;
  flex-direction: column;
  gap: var(--fs-s3, 12px);
  background: var(--fs-bg-surface);
  border: 1px solid var(--fs-hairline);
  border-radius: var(--fs-r-md);
  padding: 14px;
  overflow: hidden;
}
.chart-skel__hd { display: flex; justify-content: space-between; }
.chart-skel__bar {
  height: 12px;
  border-radius: 3px;
  background: var(--fs-bg-sunken);
  position: relative;
  overflow: hidden;
}
.chart-skel__bar--short { width: 64px; }
.chart-skel__body { flex: 1; position: relative; overflow: hidden; }
.chart-skel__wave {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, transparent calc(100% - 46px), var(--fs-hairline) calc(100% - 46px)),
    repeating-linear-gradient(90deg, transparent 0 15%, var(--fs-hairline) 15% calc(15% + 1px));
}
.chart-skel__bar::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(var(--fs-ink-900-rgb), 0.05), transparent);
  animation: skel-sweep 1.4s var(--fs-ease) infinite;
}
.chart-skel__wave::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(var(--fs-ink-900-rgb), 0.045), transparent);
  animation: skel-sweep 1.6s var(--fs-ease) infinite;
}
@keyframes skel-sweep {
  to { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
  .chart-skel__bar::after, .chart-skel__wave::after { animation: none; }
}
.chart-card__hd {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-shrink: 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: border-color 0.16s var(--fs-ease);
}
.chart-card:hover .chart-card__hd { border-bottom-color: var(--fs-hairline-strong); }
.chart-card__t {
  position: relative;
  padding-left: 9px;
  font-size: 13px;
  font-weight: 500;
  color: var(--fs-ink-900);
  letter-spacing: 0.02em;
}
/* 标题前置 2px 刻度条：静息为发丝强线色，悬停转强调色（与 app-section-title 同语言） */
.chart-card__t::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 2px;
  height: 11px;
  transform: translateY(-50%);
  background: var(--fs-hairline-strong);
  transition: background-color 0.16s var(--fs-ease);
}
.chart-card:hover .chart-card__t::before { background: var(--fs-accent); }
.chart-card__n {
  font-family: var(--fs-font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  color: var(--fs-ink-400);
  white-space: nowrap;
  transition: color 0.16s var(--fs-ease);
}
.chart-card:hover .chart-card__n { color: var(--fs-ink-500); }
.chart-card__sp { flex: 1; }
.chart-box {
  flex: 1;
  min-height: 0;
}
.gis-map-stage {
  position: relative;
  flex: 1;
  min-width: 0;
  min-height: 0;
  z-index: 5;
  padding: 0;
  display: flex;
  flex-direction: column;
}
/* 工具条浮于地图底部居中（v0 map-tools 同构） */
.gis-map-stage > .map-tools {
  position: absolute;
  left: 50%;
  bottom: 12px;
  transform: translateX(-50%);
  margin-top: 0;
  z-index: 25;
  box-shadow: var(--fs-e2);
}
/* 地图是唯一主角：无容器边框、无投影、无圆角遮罩 */
.gis-map-frame {
  position: relative;
  flex: 1;
  min-height: 0;
  background: var(--fs-bg-canvas);
}
.gis-map-inner {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
/* AI 火情识别浮层：左缘（v0 vision-tab + drawer），折叠为 34px 竖条、展开为抽屉 */
.vision-overlay {
  position: absolute;
  left: 8px;
  top: 8px;
  bottom: 8px;
  margin-right: 0;
  z-index: 25;
}
.gis-footer {
  user-select: text;
  position: relative;
  flex-shrink: 0;
  z-index: 25;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 5px 12px;
  font-size: 11px;
  font-family: ui-monospace, "Consolas", monospace;
  color: var(--fs-ink-500);
  background: var(--fs-bg-raised, rgba(var(--fs-bg-canvas-rgb), 0.92));
  border-top: 1px solid var(--fs-hairline);
}
.gis-footer-coord { color: var(--fs-accent); }
.gis-footer-link {
  position: relative;
  color: var(--fs-ink-500);
  text-decoration: none;
}
/* 外链下划线由左向右绘出（与公开页导航同语言） */
.gis-footer-link::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: currentColor;
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform var(--fs-dur-panel, 280ms) var(--fs-ease);
}
.gis-footer-link:hover { color: var(--fs-accent); }
.gis-footer-link:hover::after { transform: scaleX(1); }
/* ==================== V7 入场微动效（挂载/数据到位各播一次，零 JS） ====================
   图表卡错峰升起；KPI 计数由 AnimNumber 组件承担（仅首次）；骨架 shimmer 由 .mo-loop 降级 */
.rail-scroll .chart-card { animation: chart-in 0.5s var(--fs-ease-out) both; }
.rail-scroll .chart-card:nth-child(2) { animation-delay: 0.08s; }
@keyframes chart-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
}
/* 动效三态闸门：off / 系统 reduce 下静态呈现终态，悬停位移一并关闭 */
html[data-motion-allowed="false"] .rail-scroll .chart-card { animation: none; }
html[data-motion-allowed="false"] .chart-card:hover { transform: none; }
html[data-motion-allowed="false"] .gis-footer-link::after { transition: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .rail-scroll .chart-card { animation: none; }
  html:not([data-motion="on"]) .chart-card:hover { transform: none; }
  html:not([data-motion="on"]) .gis-footer-link::after { transition: none; }
}
</style>
