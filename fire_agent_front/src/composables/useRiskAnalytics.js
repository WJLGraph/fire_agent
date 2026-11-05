/**
 * 作战大屏 · 火险分析计算（composable）
 *
 * 阶段 4h：从 views/dashboard/index.vue 中整段搬出两块纯计算逻辑，逻辑一字未改：
 *   1) useFireWarning  — 火险预警（整体评分 / 等级 / 州市风险列表 / 动态摘要）
 *   2) usePredictData  — 预测火点数据（逐日 / 逐月 GeoJSON）、州市火险等级映射、图表数据源
 *
 * 两者均为「输入 refs → 输出 computed」，不持有任何地图实例，抽取后不存在行为差异。
 */
import { computed } from 'vue'
import {
  fireIndexToLevel,
  getLevelInfoByScore,
  getLevelInfoByFireIndex,
  SUMMARY_MAP,
} from '@/utils/riskLevel'
import { CITY_CENTER_MAP } from '@/utils/cityCenter'

/**
 * 火险预警
 * @param {Object} ctx { currentDataType, searchDate, predictViewMode, predictDailyData, predictMonthData }
 */
export function useFireWarning(ctx) {
  // 预警等级：1=正常, 2=注意, 3=警告, 4=高度, 5=极度
  // ★★★ 图表/预警数据与 predictViewMode 同步：逐日用逐日数据，逐月用逐月数据 ★★★
  const fireWarning = computed(() => {
    if (ctx.currentDataType.value !== 'predict') return null

    const [year, month, day] = ctx.searchDate.value
      ? ctx.searchDate.value.split('-').map(Number)
      : [null, null, null]

    // 月份必须在 1-12 范围内（排除逐日模式选 13 日以上时 parts[1] 超出范围的问题）
    if (!year || !month || month < 1 || month > 12) return null

    // 生成动态摘要文本（使用 warningCount / highRiskCount）
    const generateSummaryText = (level, wCount, hCount) => {
      const texts = {
        1: '全省火险形势平稳，无明显风险区域，可正常开展各项生产活动。',
        2: `全省${wCount > 0 ? `${wCount}个州市` : '大部分地区'}需引起关注，建议加强火源管控和日常巡护。`,
        3: `全省火险等级升至警告水平，${wCount}个州市处于中高风险，需强化防控措施。`,
        4: `全省火险形势严峻，${wCount}个州市达中高风险，其中${hCount}个高度危险，需全面戒备。`,
        5: `全省已处于极度危险状态！${wCount}个州市全部告警，建议立即启动最高级别应急预案。`
      }
      return texts[level] || texts[1]
    }

    let records = []
    let isDaily = ctx.predictViewMode.value === 'daily'

    if (isDaily) {
      // —— 逐日数据：精确匹配 Year-Month-Day ——
      if (day === undefined || day === null) return null
      records = ctx.predictDailyData.value.filter(
        d => Number(d.Year) === year && Number(d.Month) === month && Number(d.Day) === day
      )
      if (records.length === 0) return null
    } else {
      // —— 逐月数据：精确匹配 Year-Month ——
      records = ctx.predictMonthData.value.filter(
        d => Number(d.Year) === year && Number(d.Month) === month
      )
      if (records.length === 0) return null
    }

    // ===== 整体评分计算 =====
    let avgScore, maxRecord, maxScore, overallLevel, regionList

    if (isDaily) {
      // 逐日：基于 Final_Fire_Index
      const indices = records.map(r => Number(r.Final_Fire_Index))
      avgScore = indices.reduce((s, v) => s + v, 0) / indices.length
      maxRecord = records.reduce((m, r) =>
        Number(r.Final_Fire_Index) > Number(m.Final_Fire_Index) ? r : m, records[0])
      maxScore = Number(maxRecord.Final_Fire_Index)
      overallLevel = fireIndexToLevel(avgScore)

      regionList = records.map(r => {
        const info = getLevelInfoByFireIndex(Number(r.Final_Fire_Index))
        return {
          city: r.City,
          riskScore: Number(r.Final_Fire_Index),
          riskLevel: info.level,
          label: info.label,
          color: info.color,
          desc: info.desc,
          measure: info.measure,
          predFireRisk: r.Pred_Fire_Count
        }
      }).sort((a, b) => Number(b.riskScore) - Number(a.riskScore))
    } else {
      // 逐月：基于 Risk_Score
      const scores = records.map(r => Number(r.Risk_Score))
      avgScore = scores.reduce((s, v) => s + v, 0) / scores.length
      maxRecord = records.reduce((m, r) =>
        Number(r.Risk_Score) > Number(m.Risk_Score) ? r : m, records[0])
      maxScore = Number(maxRecord.Risk_Score)
      overallLevel = Math.min(5, Math.max(1, Math.round((avgScore + maxScore * 0.5) / 0.2)))

      regionList = records.map(r => {
        const info = getLevelInfoByScore(r.Risk_Score)
        return {
          city: r.City,
          riskScore: Number(r.Risk_Score),
          riskLevel: info.level,
          label: info.label,
          color: info.color,
          desc: info.desc,
          measure: info.measure,
          predFireRisk: r.Pred_Fire_Risk
        }
      }).sort((a, b) => Number(b.riskScore) - Number(a.riskScore))
    }

    // ===== 整体摘要 =====
    const overallLevelInfo = isDaily
      ? getLevelInfoByFireIndex(avgScore)
      : getLevelInfoByScore(avgScore)
    const highRiskCount = regionList.filter(r => r.riskLevel >= 4).length
    const warningCount = regionList.filter(r => r.riskLevel >= 3).length

    return {
      year,
      month,
      day: isDaily ? day : null,
      viewMode: ctx.predictViewMode.value,
      overallLevel,
      overallLevelInfo,
      summary: { ...SUMMARY_MAP[overallLevel], summary: generateSummaryText(overallLevel, warningCount, highRiskCount) },
      regionList,
      avgScore: avgScore.toFixed(4),
      maxScore: maxScore.toFixed(4),
      topCity: maxRecord.City,
      highRiskCount,
      warningCount,
      totalRegions: records.length
    }
  })

  return { fireWarning }
}

/**
 * 预测数据处理（fireIndexToLevel 已从 riskLevel.js 导入）
 * 逐日：predict_2025_2026_daily.json → fireIndexToLevel(Final_Fire_Index) 为等级，Pred_Fire_Count 四舍五入整数
 * 逐月：predict_2025_2026_month.json → Risk_Score / Pred_Fire_Risk（原逻辑）
 * @param {Object} ctx { currentDataType, searchDate, predictViewMode, predictDailyData, predictMonthData }
 */
export function usePredictData(ctx) {
  const processedPredictData = computed(() => {
    if (ctx.predictViewMode.value === 'daily') {
      if (!ctx.searchDate.value) {
        return { type: 'FeatureCollection', features: [] }
      }
      const parts = ctx.searchDate.value.split('-').map(Number)
      const year = parts[0]
      const month = parts[1]
      const day = parts[2]
      if (!year || year < 2025 || year > 2026 || !month || day === undefined) {
        return { type: 'FeatureCollection', features: [] }
      }
      const filtered = ctx.predictDailyData.value.filter(item =>
        Number(item.Year) === year &&
        Number(item.Month) === month &&
        Number(item.Day) === day
      )
      const features = filtered.map(item => {
        const fireCount = Math.round(Number(item.Pred_Fire_Count))
        const fireIndex = Number(item.Final_Fire_Index)
        const riskLevel = fireIndexToLevel(fireIndex)
        const coords = CITY_CENTER_MAP[item.City] || [102, 25]
        const y = String(item.Year)
        const m = String(Number(item.Month)).padStart(2, '0')
        const d = String(Number(item.Day)).padStart(2, '0')
        const dateStr = `${y}-${m}-${d}`
        return {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: coords },
          properties: {
            city: item.City,
            acq_date: dateStr,
            acq_time: '逐日预测',
            frp: fireCount,
            fire_count: fireCount,
            fire_index: fireIndex,
            risk_level: riskLevel,
            conf: riskLevel >= 4 ? 'high' : (riskLevel >= 2 ? 'nominal' : 'low')
          }
        }
      })
      return { type: 'FeatureCollection', features }
    }

    // —— 逐月 ——
    const dataSrc = ctx.predictMonthData.value
    let filtered = dataSrc
    if (ctx.searchDate.value) {
      const parts = ctx.searchDate.value.split('-').map(Number)
      const year = parts[0]
      if (year >= 2025 && year <= 2026) {
        const month = parts[1]
        filtered = dataSrc.filter(
          item => Number(item.Year) === year && Number(item.Month) === month
        )
      }
    }

    const features = filtered
      .filter(item => Number(item.Pred_Fire_Risk) > 0)
      .map(item => {
        const fireCount = Math.round(Number(item.Pred_Fire_Risk))
        const rs = Number(item.Risk_Score)
        let riskLevel = Math.ceil(rs / 0.2)
        if (rs === 0) riskLevel = 1
        riskLevel = Math.max(1, Math.min(5, riskLevel))
        const coords = CITY_CENTER_MAP[item.City] || [102, 25]
        const dateStr = `${Number(item.Year)}-${String(Number(item.Month)).padStart(2, '0')}`
        return {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: coords },
          properties: {
            city: item.City,
            acq_date: dateStr,
            acq_time: '逐月预测',
            frp: fireCount,
            fire_count: fireCount,
            risk_score: rs,
            risk_level: riskLevel,
            conf: riskLevel >= 4 ? 'high' : (riskLevel >= 2 ? 'nominal' : 'low')
          }
        }
      })
    return { type: 'FeatureCollection', features }
  })

  // ====== 各州市火险等级映射（用于州市边界底色渲染） ======
  // 仅在预测模式 + 选了日期（且年份在 2025-2026）时生效
  // 逐日模式：精确匹配 Year-Month-Day（当天等级）；逐月模式：精确匹配 Year-Month
  const cityRiskData = computed(() => {
    if (ctx.currentDataType.value !== 'predict' || !ctx.searchDate.value) return null
    const parts = ctx.searchDate.value.split('-').map(Number)
    const year = parts[0]
    if (!year || year < 2025 || year > 2026) return null

    const riskMap = {}

    if (ctx.predictViewMode.value === 'daily') {
      const month = parts[1]
      const day = parts[2]
      if (month === undefined || day === undefined) return null
      ctx.predictDailyData.value.forEach(item => {
        if (
          Number(item.Year) !== year ||
          Number(item.Month) !== month ||
          Number(item.Day) !== day
        ) {
          return
        }
        riskMap[item.City] = fireIndexToLevel(Number(item.Final_Fire_Index))
      })
      return Object.keys(riskMap).length > 0 ? riskMap : null
    }

    ctx.predictMonthData.value.forEach(item => {
      if (Number(item.Year) !== year) return
      const month = parts[1]
      if (Number(item.Month) !== month) return

      const rs = Number(item.Risk_Score)
      let level = Math.ceil(rs / 0.2)
      if (rs === 0) level = 1
      level = Math.max(1, Math.min(5, level))
      riskMap[item.City] = level
    })
    return Object.keys(riskMap).length > 0 ? riskMap : null
  })

  // 为预测图表组件提供当前筛选后的数据
  const predictDataForChart = computed(() => {
    if (ctx.currentDataType.value !== 'predict') return null
    if (!ctx.searchDate.value) return null
    const parts = ctx.searchDate.value.split('-').map(Number)
    const year = parts[0]
    if (!year || year < 2025 || year > 2026) return null
    const month = parts[1]

    if (ctx.predictViewMode.value === 'daily') {
      const day = parts[2]
      if (day === undefined) return null
      return ctx.predictDailyData.value.filter(
        d => Number(d.Year) === year && Number(d.Month) === month && Number(d.Day) === day
      )
    }
    return ctx.predictMonthData.value.filter(
      d => Number(d.Year) === year && Number(d.Month) === month
    )
  })

  return { processedPredictData, cityRiskData, predictDataForChart }
}
