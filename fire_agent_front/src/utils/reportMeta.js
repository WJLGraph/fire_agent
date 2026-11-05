/**
 * 报告中心 · 报告元信息映射（类型标签 / LLM 提供商标签 / Agent 生成标记）
 *
 * 阶段 4g：从 views/report-center/index.vue 提取，供「报告列表」与「报告详情」两个区块共用，
 * 消除原单文件内两处重复定义。文案与取值逻辑一字未改。
 */

// ====== 报告类型选项 ======
export const REPORT_TYPE_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'daily', label: '日报' },
  { value: 'weekly', label: '周报' },
  { value: 'monthly', label: '月报' },
  { value: 'special', label: '专项' },
]

export const typeLabel = (t) => {
  const found = REPORT_TYPE_OPTIONS.find(o => o.value === t)
  return found ? found.label : (t || '')
}

// ====== LLM 审计元数据（模型来源 / Token / 降级） ======
const PROVIDER_LABELS = {
  aliyun: '阿里百炼',
  bailian: '阿里百炼',
  amd: 'AMD GPU Cloud',
  ollama: '本地 Ollama',
  deepseek: 'DeepSeek',
  openai: 'OpenAI',
}

// 完整名称（详情头部）；无 provider 说明是模板兜底
export const providerLabel = (p) => (p ? PROVIDER_LABELS[p] || p : '模板生成')

// 列表内短标签
export const providerShort = (p) => (p ? PROVIDER_LABELS[p] || p : '模板')

// ====== 是否由 Agent 自动生成（tags 含 "Agent生成"） ======
export const isAgentGenerated = (item) => {
  const tags = item && item.tags
  return Array.isArray(tags) && tags.includes('Agent生成')
}
