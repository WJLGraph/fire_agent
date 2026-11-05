/**
 * 侧边导航配置（阶段 5：从 layout/MainLayout.vue 外置）
 *
 * 契约冻结：path / label / adminOnly 与外置前完全一致，不得改动。
 *
 * icon：AppIcon 图标名（内联 SVG，见 components/base/AppIcon.vue）。
 *   V2 视觉重做前这里存的是 iconfont 类名（icon-ditu01 等），
 *   现统一改为线性 SVG，跨平台字形一致，无外部字体依赖。
 */
export const allNavItems = [
  { path: '/dashboard',      label: '作战大屏',  icon: 'map' },
  { path: '/smart-query',    label: '智能查询',  icon: 'crosshair' },
  { path: '/knowledge-base', label: '知识库',    icon: 'layers' },
  { path: '/agent-center',   label: 'Agent中心', icon: 'nodes' },
  { path: '/report-center',  label: '报告中心',  icon: 'file' },
  { path: '/admin',          label: '系统管理',  icon: 'sliders', adminOnly: true },
]

/**
 * 按角色过滤导航项：系统管理仅管理员可见
 * @param {string|undefined} role - 当前用户角色
 */
export function filterNavItems(role) {
  return allNavItems.filter(item => !item.adminOnly || role === 'admin')
}
