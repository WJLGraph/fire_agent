/**
 * 3D 地图（Three.js）· 双主题配色
 *
 * 阶段 4h：从 components/map/Map3D.vue 中原样搬出（数值一字未改）。
 * 深色 = 深空科技风，浅色 = 清爽大屏风。
 */
export const MAP3D_THEME_COLORS = {
  dark: {
    bg: 0x04101f,          // 场景底色
    // 无火险数据顶面底色：顶面是场景唯一受光材质，灯光按物理亮度调低后颜色即最终显示色，
    // 深空背景上必须亮色才清晰（原深蓝 0x1c3346 在旧饱和光照下从未真实显示过，实显一直是亮白）
    neutral: 0xd8e6f2,
    sweepTop: '#27506b', sweepBottom: '#0d1b2c', scan: '#4cc9f0',
    edge: 0xd9f2ff, edgeOpacity: 0.9,   // 州市轮廓描边（省界增强）
    underlay: 0x13273e,    // 底座垫层（覆盖州市边界裂缝）
    fly: 0x8fc2ff, ring: 0x3fa9f5, beam: '#7dd3fc',
  },
  light: {
    bg: 0xe3ecf6,
    neutral: 0xffffff,
    sweepTop: '#ffffff', sweepBottom: '#f2f7fc', scan: '#2563eb',
    edge: 0x1e5a8a, edgeOpacity: 0.85,
    underlay: 0xffffff,
    fly: 0x1d4ed8, ring: 0x2563eb, beam: '#3b82f6',
  },
}
