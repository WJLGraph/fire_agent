<script setup>
/**
 * 作战大屏 · 地图底部浮动工具条（visual-v0 §map-tools 同构）
 *
 * 横排「线性 SVG + 文字」胶囊条，发丝分隔线分组：
 *   [图层 | 标绘 | 量测] ─ [热力 | 导出 PNG | 全省] ─ [2D | 3D]
 *
 * 模式约束：图层 / 标绘 / 量测 / 热力 / 导出 / 全省均为 OpenLayers 2D 专属，
 * 3D（Three.js）模式下整组不渲染，仅保留 2D/3D 模式切换。
 * 受控组件：实际操作（OL 实例）在父组件，本组件只负责渲染与上抛事件。
 */
defineProps({
  /** 图层列表（OpenLayers layer 实例数组，由 map-loaded 后父级填充） */
  layers: { type: Array, default: () => [] },
  /** 当前展开的工具菜单：'layer' | 'draw' | 'measure' | '' */
  activeTool: { type: String, default: '' },
  showHeatmap: { type: Boolean, default: false },
  mapMode: { type: String, default: '3d' },
})

const emit = defineEmits([
  'toggle-tool-menu',
  'toggle-layer',
  'draw',
  'clear-draw',
  'measure',
  'toggle-heatmap',
  'download',
  'reset-view',
  'switch-mode',
])
</script>

<template>
  <!-- 底部浮动工具条（v0 map-tools：胶囊 + 发丝分隔线） -->
  <div class="map-tools" role="toolbar" aria-label="地图工具">
    <!-- 2D 专属工具组：3D 模式整组不渲染 -->
    <template v-if="mapMode === '2d'">
      <!-- 图层 -->
      <div
        class="map-tools__i"
        :class="{ 'is-on': activeTool === 'layer' }"
        @click="emit('toggle-tool-menu', 'layer')"
      >
        <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 2.5 3 6l7 3.5L17 6z"/><path d="M3 10.2 10 13.7 17 10.2"/><path d="M3 14 10 17.5 17 14"/>
        </svg>图层
        <div v-if="activeTool === 'layer'" class="map-tools__menu" @click.stop>
          <div
            v-for="layer in layers" :key="layer.get('title')"
            :class="{ on: layer.getVisible() }"
            @click.stop="emit('toggle-layer', layer)"
          >{{ layer.get('title') }}</div>
        </div>
      </div>

      <!-- 标绘 -->
      <div
        class="map-tools__i"
        :class="{ 'is-on': activeTool === 'draw' }"
        @click="emit('toggle-tool-menu', 'draw')"
      >
        <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 17 14.5 5.5l2.4 2.4L5.4 19.4z"/><path d="m12.6 3.6 2.4 2.4"/>
        </svg>标绘
        <div v-if="activeTool === 'draw'" class="map-tools__menu" @click.stop>
          <div @click.stop="emit('draw', 'Point')">点</div>
          <div @click.stop="emit('draw', 'LineString')">线</div>
          <div @click.stop="emit('draw', 'Polygon')">面</div>
          <div class="map-tools__menu-danger" @click.stop="emit('clear-draw')">清空标绘</div>
        </div>
      </div>

      <!-- 量测 -->
      <div
        class="map-tools__i"
        :class="{ 'is-on': activeTool === 'measure' }"
        @click="emit('toggle-tool-menu', 'measure')"
      >
        <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M2.6 13.2 13.2 2.6"/><path d="M5.4 2.6h7.8v7.8"/><path d="M2.6 17.4h15"/>
        </svg>量测
        <div v-if="activeTool === 'measure'" class="map-tools__menu" @click.stop>
          <div @click.stop="emit('measure', 'LineString')">距离</div>
          <div @click.stop="emit('measure', 'Polygon')">面积</div>
        </div>
      </div>

      <span class="map-tools__sep" aria-hidden="true"></span>

      <!-- 热力 -->
      <div class="map-tools__i" :class="{ 'is-on': showHeatmap }" @click="emit('toggle-heatmap')">
        <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 2.2s4.4 3.4 4.4 7.2a4.4 4.4 0 1 1-8.8 0c0-1.6.8-2.8.8-2.8s.6 1.4 1.6 1.4c1.4 0 1.6-2.4 2-5.8z"/>
        </svg>{{ showHeatmap ? '关热力' : '热力' }}
      </div>

      <!-- 导出 PNG -->
      <div class="map-tools__i" @click="emit('download')">
        <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 3v8.6"/><path d="m6.4 8.2 3.6 3.6 3.6-3.6"/><path d="M3.5 15.4v1.1h13v-1.1"/>
        </svg>导出 PNG
      </div>

      <!-- 全省（复位视野） -->
      <div class="map-tools__i" title="定位到云南省范围" @click="emit('reset-view')">
        <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <circle cx="10" cy="10" r="5.5"/><path d="M10 1.5v3M10 15.5v3M1.5 10h3M15.5 10h3"/>
        </svg>全省
      </div>

      <span class="map-tools__sep" aria-hidden="true"></span>
    </template>

    <!-- 2D / 3D 模式切换（任何模式都可用） -->
    <div class="map-tools__i" :class="{ 'is-on': mapMode === '2d' }" @click="emit('switch-mode', '2d')">
      <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 5.6 7.6 4l4.8 1.5L17 4v11.2l-4.6 1.6-4.8-1.5L3 16.8z"/><path d="M7.6 4v11.7M12.4 5.5v11.3"/>
      </svg>2D
    </div>
    <div class="map-tools__i" :class="{ 'is-on': mapMode === '3d' }" @click="emit('switch-mode', '3d')">
      <svg class="mt-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 2.6 17 6.4v7.2L10 17.4 3 13.6V6.4z"/><path d="M3 6.4 10 10.2l7-3.8M10 10.2v7.2"/>
      </svg>3D
    </div>
  </div>
</template>

<style lang="scss" scoped>
/* ===== v0 map-tools：底部居中胶囊条 ===== */
.map-tools {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  background: var(--fs-bg-surface);
  border-radius: 999px;
  box-shadow: var(--fs-e2), inset 0 0 0 1px var(--fs-hairline);
  /* 挂载即自底部浮起（终态为基线，动效关闭时静态就位） */
  animation: mt-in 0.42s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) 0.1s both;
}
.map-tools__i {
  position: relative;
  display: flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.map-tools__i:hover {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
}
.map-tools__i:active { transform: scale(0.96); }
.map-tools__i.is-on {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14);
}
.mt-ic {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
/* 图标随悬停轻抬，与侧栏导航同一反馈语言 */
.map-tools__i:hover .mt-ic { transform: translateY(-1px); }
/* 发丝分隔线（v0 map-tools__sep） */
.map-tools__sep {
  width: 1px;
  height: 16px;
  background: var(--fs-hairline);
  margin: 0 3px;
  flex-shrink: 0;
}
/* 弹出菜单（图层列表 / 标绘 / 量测） */
.map-tools__menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 112px;
  padding: 6px;
  background: var(--fs-bg-raised);
  border-radius: var(--fs-r-sm);
  box-shadow: var(--fs-e2), inset 0 0 0 1px var(--fs-hairline);
  z-index: 50;
  /* 用独立 translate/scale 属性入场，避免与居中用的 transform 相互覆盖 */
  animation: mt-menu-in 0.18s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) both;
}
.map-tools__menu div {
  display: flex;
  align-items: center;
  height: 28px;
  padding: 0 9px;
  border-radius: var(--fs-r-xs);
  font-size: 12px;
  color: var(--fs-ink-700);
  white-space: nowrap;
  cursor: pointer;
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.map-tools__menu div:hover {
  color: var(--fs-ink-900);
  background: var(--fs-bg-sunken);
  transform: translateX(2px);
}
.map-tools__menu div.on {
  color: var(--fs-accent);
  font-weight: 600;
  box-shadow: inset 2px 0 0 var(--fs-accent);
}
.map-tools__menu-danger {
  margin-top: 3px;
  border-top: 1px solid var(--fs-hairline);
  border-radius: 0 0 var(--fs-r-xs) var(--fs-r-xs) !important;
  color: var(--fs-danger) !important;
}
.map-tools__menu-danger:hover {
  background: color-mix(in srgb, var(--fs-danger) 8%, transparent) !important;
}

/* ==================== 入场关键帧（终态即基线） ==================== */
@keyframes mt-in {
  from { opacity: 0; translate: 0 8px; }
  to   { opacity: 1; translate: 0 0; }
}
@keyframes mt-menu-in {
  from { opacity: 0; translate: 0 6px; scale: 0.98; }
  to   { opacity: 1; translate: 0 0; scale: 1; }
}

/* 动效三态闸门：off / 系统 reduce 下静态呈现终态 */
html[data-motion-allowed="false"] .map-tools,
html[data-motion-allowed="false"] .map-tools__menu { animation: none; }
html[data-motion-allowed="false"] .map-tools__i:active,
html[data-motion-allowed="false"] .map-tools__menu div:hover,
html[data-motion-allowed="false"] .map-tools__i:hover .mt-ic { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .map-tools,
  html:not([data-motion="on"]) .map-tools__menu { animation: none; }
  html:not([data-motion="on"]) .map-tools__i:active,
  html:not([data-motion="on"]) .map-tools__menu div:hover,
  html:not([data-motion="on"]) .map-tools__i:hover .mt-ic { transform: none; }
}
</style>
