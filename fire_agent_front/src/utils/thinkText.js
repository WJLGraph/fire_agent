/**
 * 思考过程文本清洗 / 多轮合并 — 供 Agent 协作中心第 5 节点「思考过程」面板使用
 *
 * 纯函数不持有状态：
 *   - mergeThinkText      前后缀对齐合并两段文本，避免同一段出现两遍；
 *   - normalizeThinkRounds 归一化后端 thinking_rounds / 旧 thinking 字段；
 *   - mergeThinkRounds     按轮次号合并（同轮取更长/对齐拼接），保证重写轮追加不覆盖；
 *   - composeThinkRounds   轮次拼接为展示文本（第 2 轮起加轻量小标题）；
 *   - dedupeThinkText      极端复读行折叠 + 超长保留尾部（仅作展示兜底）。
 */

const LINE_KEEP = 3          // 同一正文行最多保留次数（结构行/列表行不参与）
const LINE_MIN_CHARS = 12    // 参与去重的最小行长（短行不参与，避免误伤列表/序号）
const MAX_CHARS = 6000       // 展示上限（超出保留尾部）
// 纯 markdown 结构行（表格分隔线/代码围栏/水平线/标题井号等）不参与去重计数
const STRUCT_LINE_RE = /^[=\-|`#>*\s\d.]+$/
// 列表/标题/表格/引用前缀：Markdown 排版行不参与去重（去重只处理长正文行）
const MD_PREFIX_RE = /^\s*(?:[-*+•]|\d+[.)、]|#|>|\|)/

const TEXT = (v) => String(v == null ? '' : v)

/**
 * 前后缀对齐合并两段思考文本（同一段落不重复出现）
 * @param {string} prev 已展示文本
 * @param {string} next 新到文本（实时增量 / 落库回填）
 * @returns {string}
 */
export function mergeThinkText(prev, next) {
  const a = TEXT(prev)
  const b = TEXT(next)
  if (!a) return b
  if (!b) return a
  if (a === b) return a
  if (a.includes(b)) return a
  if (b.includes(a)) return b
  // 最长前后缀重叠：避免终态回填把实时已展示的尾段重复拼一遍
  const max = Math.min(a.length, b.length, 3000)
  for (let k = max; k >= 8; k--) {
    if (a.slice(-k) === b.slice(0, k)) return a + b.slice(k)
  }
  return `${a.replace(/\s+$/, '')}\n\n${b.replace(/^\s+/, '')}`
}

/**
 * 归一化轮次数据：兼容 [{round,text}] / ["文本"] / 旧 thinking 字段
 * @param {Array|string} rounds
 * @returns {Array<{round:number,text:string,note:string}>}
 */
export function normalizeThinkRounds(rounds) {
  if (typeof rounds === 'string') {
    return rounds.trim() ? [{ round: 1, text: rounds, note: '' }] : []
  }
  if (!Array.isArray(rounds)) return []
  const out = []
  rounds.forEach((r, i) => {
    if (typeof r === 'string') {
      if (r.trim()) out.push({ round: i + 1, text: r, note: '' })
      return
    }
    if (!r || typeof r !== 'object') return
    const text = TEXT(r.text ?? r.thinking ?? r.content)
    if (!text.trim()) return
    const n = Number(r.round)
    out.push({
      round: Number.isFinite(n) && n > 0 ? n : i + 1,
      text,
      note: TEXT(r.note || r.stream_note || ''),
    })
  })
  return out.sort((a, b) => a.round - b.round)
}

/**
 * 按轮次号合并两组思考（同轮：取更长 / 前后缀对齐拼接）
 * @param {Array} liveRounds 实时累积轮次
 * @param {Array} persistedRounds 落库轮次
 */
export function mergeThinkRounds(liveRounds, persistedRounds) {
  const map = new Map()
  for (const r of [...normalizeThinkRounds(liveRounds), ...normalizeThinkRounds(persistedRounds)]) {
    const cur = map.get(r.round)
    if (!cur) {
      map.set(r.round, { ...r })
      continue
    }
    map.set(r.round, {
      round: r.round,
      text: mergeThinkText(cur.text, r.text),
      note: r.note || cur.note || '',
    })
  }
  return [...map.values()].sort((a, b) => a.round - b.round)
}

/**
 * 轮次拼接为展示文本：第 2 轮起加「第 N 轮」轻量小标题，整体读起来是连续推理记录
 * @param {Array|string} rounds
 */
export function composeThinkRounds(rounds) {
  const list = normalizeThinkRounds(rounds)
  if (!list.length) return ''
  if (list.length === 1) return list[0].text.trim()
  return list.map((r, i) => {
    const body = r.text.trim()
    if (!i) return body
    return `**第 ${r.round} 轮思考**\n\n${body}`
  }).join('\n\n')
}

/**
 * 去重 + 折叠思考文本
 * 只对长正文行做行级去重（同一行最多保留 LINE_KEEP 次），Markdown 列表/标题/
 * 表格/引用行原样保留，避免去重破坏 Markdown 结构；超长仅保留尾部。
 * @param {string} text 累积的思考全文
 * @returns {{ body: string, dropped: number, trimmed: boolean }}
 *   body: 清洗后的展示文本；dropped: 被去重丢弃的行数；trimmed: 是否截断了前文
 */
export function dedupeThinkText(text) {
  const raw = TEXT(text)
  if (!raw) return { body: '', dropped: 0, trimmed: false }
  const lines = raw.replace(/\r\n/g, '\n').split('\n')
  const seen = new Map()
  const out = []
  let dropped = 0
  for (const line of lines) {
    const key = line.trim()
    if (!key) {
      // 连续空行折叠为一个，保持 Markdown 段落间距稳定
      if (out.length && !out[out.length - 1].trim()) continue
      out.push('')
      continue
    }
    if (key.length >= LINE_MIN_CHARS && !STRUCT_LINE_RE.test(key) && !MD_PREFIX_RE.test(key)) {
      const n = seen.get(key) || 0
      if (n >= LINE_KEEP) {
        dropped++
        continue
      }
      seen.set(key, n + 1)
    }
    out.push(line)
  }
  let body = out.join('\n').trim()
  let trimmed = false
  if (body.length > MAX_CHARS) {
    body = '…前文已折叠…\n' + body.slice(-MAX_CHARS)
    trimmed = true
  }
  return { body, dropped, trimmed }
}

/** 思考字数紧凑显示（展示层徽标用） */
export function thinkLenText(n) {
  if (typeof n !== 'number' || !isFinite(n)) return ''
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k 字` : `${n} 字`
}

/** 流式中断标记 → 展示文案（chips 与思考面板状态标签共用，避免两处各写一份跑偏） */
const STREAM_NOTES = {
  think_loop: '思考复读中断',
  think_limit: '思考超限截断',
  content_loop: '正文复读中断',
  cancelled: '取消中断',
}
export function streamNoteText(n) {
  return STREAM_NOTES[n] || n || ''
}
