<script setup>
/**
 * 智能查询 · 结果地图（OpenLayers 点位渲染）
 *
 * 自包含区块：地图实例 / 云南省州市边界图层 / 点位图层 / 尺寸自适应 / 卸载清理，全部在本组件内闭环。
 * 由 views/smart-query/index.vue 拆分而来，渲染逻辑未做任何修改：
 * 原本「点击地图 Tab 后 nextTick(renderMap())」的触发方式，改为「Tab 挂载本组件即渲染」，等价。
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useResizeObserver } from '@/composables/useResizeObserver'

// OpenLayers 地图
import Map from 'ol/Map.js'
import View from 'ol/View.js'
import TileLayer from 'ol/layer/Tile.js'
import { OSM } from 'ol/source.js'
import VectorLayer from 'ol/layer/Vector.js'
import VectorSource from 'ol/source/Vector.js'
import GeoJSON from 'ol/format/GeoJSON.js'
import { Point } from 'ol/geom.js'
import Feature from 'ol/Feature.js'
import { Style, Fill, Circle as CircleStyle, Text, Stroke } from 'ol/style.js'

// 云南省州市行政边界 GeoJSON（16 个州市）
import yunnanBorder from '@/assets/Yunnan_border.json'

const props = defineProps({
  geoData: { type: Object, default: null },
})

// OpenLayers 地图实例
let mapInstance = null
let mapVectorLayer = null
const mapRef = ref(null)

// ====== 地图渲染（OpenLayers） ======
const renderMap = () => {
  if (!mapRef.value) return
  const features = (props.geoData && props.geoData.features) || []
  if (!features.length) return // 无点位时由模板展示提示文案

  // 首次初始化底图
  if (!mapInstance) {
    // 云南省州市行政边界图层（描边 + 半透明填充 + 州市名标注）
    const borderLayer = new VectorLayer({
      source: new VectorSource({
        features: new GeoJSON().readFeatures(yunnanBorder, {
          dataProjection: 'EPSG:4326',
          featureProjection: 'EPSG:4326',
        }),
      }),
      style: (feature) => new Style({
        stroke: new Stroke({ color: '#22d3ee', width: 1.5 }),
        fill: new Fill({ color: 'rgba(34, 211, 238, 0.05)' }),
        text: new Text({
          text: feature.get('name') || '',
          font: '11px sans-serif',
          fill: new Fill({ color: 'rgba(148, 163, 184, 0.9)' }),
          stroke: new Stroke({ color: '#000000', width: 3 }),
        }),
      }),
    })

    mapInstance = new Map({
      target: mapRef.value,
      layers: [
        new TileLayer({
          source: new OSM(),
          opacity: 0.85,
        }),
        borderLayer,
      ],
      view: new View({
        center: [99.5, 24.5],
        zoom: 5,
        projection: 'EPSG:4326',
      }),
    })
  }

  // 清除旧图层
  if (mapVectorLayer) mapInstance.removeLayer(mapVectorLayer)

  // 构建点位 Feature
  const olFeatures = props.geoData.features
    .filter(f => f.geometry && f.geometry.coordinates)
    .map(f => {
      const [lng, lat] = f.geometry.coordinates
      const feat = new Feature({ geometry: new Point([lng, lat]) })
      const props_ = f.properties || {}
      feat.setProperties(props_)
      return feat
    })

  mapVectorLayer = new VectorLayer({
    source: new VectorSource({ features: olFeatures }),
    style: (feature) => {
      const color = feature.get('color') || '#0ea5e9'
      const name = feature.get('name') || ''
      return new Style({
        image: new CircleStyle({
          radius: 7,
          fill: new Fill({ color }),
          stroke: new Stroke({ color: '#ffffff', width: 1.5 }),
        }),
        text: new Text({
          text: name,
          font: '11px sans-serif',
          fill: new Fill({ color: '#ffffff' }),
          stroke: new Stroke({ color: '#000000', width: 3 }),
          offsetY: -14,
        }),
      })
    },
  })
  mapInstance.addLayer(mapVectorLayer)

  // 自适应视图到点位范围
  if (olFeatures.length > 0) {
    const extent = mapVectorLayer.getSource().getExtent()
    mapInstance.getView().fit(extent, { padding: [40, 40, 40, 40], maxZoom: 10, duration: 300 })
  } else {
    mapInstance.getView().setCenter([99.5, 24.5])
    mapInstance.getView().setZoom(5)
  }
  mapInstance.updateSize()
}

// ====== 尺寸自适应（useResizeObserver 内置 watch 兜住晚挂载；不支持的环境降级为 window.resize） ======
useResizeObserver(mapRef, () => {
  if (mapInstance) setTimeout(() => mapInstance.updateSize(), 100)
})

onMounted(() => {
  renderMap()
})
// 同一次查询内 geoData 变更（如切换历史记录）时重绘
watch(() => props.geoData, () => renderMap(), { flush: 'post' })

onUnmounted(() => {
  if (mapInstance) { mapInstance.setTarget(undefined); mapInstance = null }
})
</script>

<template>
  <div class="tab-content tab-fill">
    <div
      v-if="geoData && geoData.features && geoData.features.length"
      ref="mapRef"
      class="map-container"
    />
    <div v-else class="map-empty">
      该查询结果未包含地理坐标信息，暂无法展示地图点位
    </div>
  </div>
</template>

<style scoped>
/* Tab 内容 */
.tab-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  backdrop-filter: none;
  border: 1px solid var(--fs-hairline);
  box-shadow: inset 0 1px 0 transparent;
  border-radius: var(--fs-r-md, 10px);
  padding: 12px;
  overflow: hidden;
  transition: border-color var(--fs-dur-micro) var(--fs-ease);
  animation: tc-in 0.3s var(--fs-ease-out) both;
}
.tab-content:hover { border-color: var(--fs-hairline-strong); }
@keyframes tc-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.tab-fill {
  padding: 4px;
}

/* 地图 */
.map-container {
  flex: 1;
  min-height: 0;
  width: 100%;
  border-radius: var(--fs-r-sm, 6px);
  overflow: hidden;
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  animation: rm-in 0.3s var(--fs-ease-out) both;
}
@keyframes rm-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.map-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  text-align: center;
  font-size: 12px;
  line-height: 1.6;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
  background: var(--fs-bg-sunken);
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-md, 10px);
}
.map-container :deep(.ol-attribution) {
  background: var(--fs-mask);
  font-size: 10px;
  letter-spacing: 0.02em;
  border-radius: var(--fs-r-xs, 3px) 0 0 0;
}
.map-container :deep(.ol-control button) {
  background: var(--fs-mask);
  border-radius: var(--fs-r-xs, 3px);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.map-container :deep(.ol-control button:hover) {
  background: var(--fs-accent);
}

/* 动效三态闸门 */
html[data-motion-allowed="false"] .map-container,
html[data-motion-allowed="false"] .tab-content { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .map-container,
  html:not([data-motion="on"]) .tab-content { animation: none; }
}
</style>
