/**
 * LLM 供应商展示名映射
 *
 * 阶段 5：原 agent-center 拆分后，TaskHistoryList 与 AgentStepTrace 各存一份
 * PROVIDER_NAMES / providerName，此处提取为共享模块去重。
 */

/** 供应商 key → 中文展示名（与后端 active_provider 取值一致） */
export const PROVIDER_NAMES = {
  aliyun: '阿里百炼',
  amd: 'AMD GPU Cloud',
  ollama: '本地 Ollama',
  longcat: 'LongCat',
}

/**
 * 取供应商展示名；未知 key 原样返回
 * @param {string} p - 供应商 key
 * @returns {string}
 */
export const providerName = (p) => PROVIDER_NAMES[p] || p || ''
