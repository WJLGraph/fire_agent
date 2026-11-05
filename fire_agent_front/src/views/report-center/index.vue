<script setup>
/**
 * 报告中心 — 查看历史分析报告、预览 Markdown、导出、删除
 *
 * 后端 API:
 *   GET    /api/v1/reports/list?page=&page_size=&report_type=
 *   GET    /api/v1/reports/{id}
 *   DELETE /api/v1/reports/{id}
 *
 * 视觉 V6：按 docs/design/visual-v0.html §report 屏重做展示层——
 *   - 页头改 v0 page-head（64px 单行：28px 大标题 + 副题 + 类型 seg + 刷新 ghost）
 *   - 通栏两栏（v0 rep-body：左 340 报告列表 surface+右缘线 / 右 详情 canvas）
 *   - 列表项改 rep-item 发丝行（去浮卡），详情改 rep-bar + 760px 纸张阅读区
 * 数据请求（分页/详情防竞态/导出/打印/删除确认/播报）零改动。
 */
import BackHomeButton from '@/components/base/BackHomeButton.vue'
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchList, fetchDetailRaw, remove, exportRaw } from '@/api/report'
import { speakText, cleanupSpeech } from '@/utils/speech'
import { REPORT_TYPE_OPTIONS as typeOptions } from '@/utils/reportMeta'
import ReportListPanel from './ReportListPanel.vue'
import ReportDetailPanel from './ReportDetailPanel.vue'

// ====== 列表状态 ======
const reports = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(6)
const reportType = ref('') // '' | daily | weekly | monthly | special

// ====== 详情状态 ======
const currentReport = ref(null)
const detailLoading = ref(false)
const detailError = ref('') // 详情加载错误（404 / 请求失败）
let detailSeq = 0 // 请求序号：快速切换报告时丢弃过期响应，防竞态覆盖

// ====== 拉取列表 ======
const fetchReports = async () => {
  loading.value = true
  try {
    const json = await fetchList({
      page: page.value,
      page_size: pageSize.value,
      report_type: reportType.value,
    })
    if (json.code === 200) {
      reports.value = json.data.items || []
      total.value = json.data.total || 0
    }
  } catch (e) {
    ElMessage.error('加载报告列表失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// ====== 拉取详情 ======
const fetchDetail = async (id) => {
  const seq = ++detailSeq // 本次请求序号
  detailLoading.value = true
  detailError.value = ''
  try {
    const res = await fetchDetailRaw(id)
    if (seq !== detailSeq) return // 已被更新的请求取代，丢弃本次结果
    if (res.status === 404) {
      currentReport.value = null
      detailError.value = '报告不存在或无权限查看'
      return
    }
    const json = await res.json().catch(() => ({}))
    if (seq !== detailSeq) return
    if (json.code === 200 && json.data) {
      currentReport.value = json.data
    } else {
      currentReport.value = null
      detailError.value = json.detail || json.message || '加载详情失败'
    }
  } catch (e) {
    if (seq !== detailSeq) return
    currentReport.value = null
    detailError.value = '加载详情失败：' + e.message
  } finally {
    if (seq === detailSeq) detailLoading.value = false
  }
}

// ====== 选择报告 ======
const selectReport = async (item) => {
  await fetchDetail(item.id)
}

// ====== 删除报告 ======
const handleDelete = async (item) => {
  try {
    await ElMessageBox.confirm(`确定删除报告「${item.title}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    const json = await remove(item.id)
    if (json.code === 200) {
      ElMessage.success('删除成功')
      if (currentReport.value && currentReport.value.id === item.id) {
        currentReport.value = null
        detailError.value = ''
      }
      fetchReports()
    } else {
      ElMessage.error(json.detail || '删除失败')
    }
  } catch {
    // 用户取消
  }
}

// ====== 导出 ======
// format: html（打印/存PDF）| md（Markdown）
const handleExport = async (item, format = 'md') => {
  const id = item.id
  const fileName = `${item.title || `report_${id}`}.${format === 'md' ? 'md' : 'html'}`
  try {
    const res = await exportRaw(id, format)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(err.detail || '导出失败')
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(format === 'md' ? '已导出 Markdown 文件' : '已导出 HTML 文件（可直接打印另存为 PDF）')
  } catch (e) {
    ElMessage.error('导出失败: ' + e.message)
  }
}

// 打开打印预览（浏览器"另存为 PDF"）——通过 authFetch 获取 HTML 再打开，避免无鉴权窗口
const handlePrint = async (item) => {
  try {
    const res = await exportRaw(item.id, 'html')
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(err.detail || '获取打印内容失败')
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const win = window.open('', '_blank')
    if (win) {
      // 先断开 opener 再导航：导出的 HTML 里含模型产出的内容，不能让它拿到
      // window.opener 反过来操控本站页面；同时也省掉 document.write 注入占位文档。
      win.opener = null
      win.location.href = url
      const timer = setInterval(() => {
        try {
          if (win.closed) return clearInterval(timer)   // 用户直接关了窗口，别再空转
          if (win.document.readyState === 'complete') {
            clearInterval(timer)
            win.focus()
            win.print()
          }
        } catch {
          // 断链后若浏览器限制跨文档访问，放弃自动打印，用户在新窗口里 Ctrl+P 即可
          clearInterval(timer)
        }
      }, 500)
    } else {
      ElMessage.warning('浏览器拦截了弹窗，请允许后重试')
    }
  } catch (e) {
    ElMessage.error('获取打印内容失败: ' + e.message)
  }
}

// ====== 类型 seg 切换（v0 seg：typeOptions 自带「全部」项） ======
const typeSegs = typeOptions
const handleTypeChange = (val) => {
  reportType.value = val
  page.value = 1
  fetchReports()
}

// ====== 分页 ======
const handlePageChange = (val) => {
  page.value = val
  fetchReports()
}

// ====== 语音播报报告（摘要 + 正文前段） ======
const speakReport = () => {
  const r = currentReport.value
  if (!r) return
  const text = (r.summary ? `报告摘要：${r.summary}。` : '') + (r.content || '')
  speakText(text)
}

// ====== 初始化 ======
onMounted(() => {
  fetchReports()
})
onUnmounted(() => {
  cleanupSpeech() // 停止语音播报
})
</script>

<template>
  <div class="rc-page">
    <!-- ===== 页头（v0 page-head 同构：64px 单行） ===== -->
    <header class="rc-head">
      <div class="rc-head__t">
        <h1 class="rc-head__h1">报告中心</h1>
        <p class="rc-head__sub">火险研判报告 · 值班简报 · Agent 生成归档</p>
      </div>
      <BackHomeButton />
      <span class="rc-head__sp"></span>
      <!-- 类型 seg（v0 seg 同构：sunken 轨道 + 浮起激活态） -->
      <div class="rc-seg">
        <button
          v-for="seg in typeSegs"
          :key="seg.value"
          class="rc-seg__i"
          :class="{ 'is-on': reportType === seg.value }"
          @click="handleTypeChange(seg.value)"
        >{{ seg.label }}</button>
      </div>
      <button class="rc-btn" title="刷新报告列表" @click="fetchReports">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16.4 8.4A6.6 6.6 0 1 0 10 16.6a6.6 6.6 0 0 0 4.6-1.9"/><path d="M16.6 3.6v5h-5"/></svg>
        刷新
      </button>
    </header>

    <!-- ===== 主体通栏两栏（v0 rep-body：列表 340 + 详情弹性） ===== -->
    <div class="rc-body">
      <ReportListPanel
        :reports="reports"
        :total="total"
        :loading="loading"
        :page-size="pageSize"
        :page="page"
        :current-id="currentReport ? currentReport.id : null"
        @select="selectReport"
        @delete="handleDelete"
        @page-change="handlePageChange"
      />

      <ReportDetailPanel
        :report="currentReport"
        :detail-error="detailError"
        :loading="detailLoading"
        @speak="speakReport"
        @export="(item, format) => handleExport(item, format)"
        @print="handlePrint"
        @delete="handleDelete"
      />
    </div>
  </div>
</template>

<style scoped>
.rc-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fs-bg-canvas);
  /* 指挥台网格底纹（hairline 级，随亮暗主题取色） */
  background-image:
    linear-gradient(rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px);
  background-size: 48px 48px;
  color: var(--fs-ink-900);
  overflow: hidden;
}

/* ===== 页头（v0 page-head） ===== */
.rc-head {
  flex-shrink: 0;
  height: var(--fs-topbar-h, 64px);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--fs-bg-surface);
  border-bottom: 1px solid var(--fs-hairline);
}
.rc-head__t { min-width: 0; }
.rc-head__h1 {
  margin: 0;
  font-size: var(--fs-t-h1, 28px);
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.2;
  color: var(--fs-ink-900);
}
.rc-head__sub {
  margin: 2px 0 0;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
}
.rc-head__sp { flex: 1; }

/* 类型 seg（v0 .seg 同构） */
.rc-seg {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border-radius: var(--fs-r-sm, 6px);
  background: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
}
.rc-seg__i {
  height: 24px;
  padding: 0 10px;
  border: none;
  border-radius: var(--fs-r-xs, 4px);
  font-size: 11px;
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.rc-seg__i:hover { color: var(--fs-ink-900); }
.rc-seg__i.is-on {
  color: var(--fs-ink-900);
  background: var(--fs-bg-surface);
  box-shadow: var(--fs-e1), inset 0 1px 0 rgba(255, 255, 255, 0.14), inset 0 0 0 1px var(--fs-hairline);
  font-weight: 500;
}

/* 刷新（v0 .btn 同构：发丝环） */
.rc-btn {
  height: 28px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.rc-btn svg { width: 13px; height: 13px; transition: transform var(--fs-dur-micro) var(--fs-ease); }
.rc-btn:hover { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.rc-btn:active { transform: translateY(0.5px); }

/* ===== 主体通栏（v0 rep-body：发丝分隔，无浮卡） ===== */
.rc-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
@media (max-width: 1100px) {
  .rc-body { flex-direction: column; overflow-y: auto; }
}
/* ==================== V7 入场微动效（挂载即播，零 JS；双闸门静态化） ====================
   内容区两栏错峰升起（右栏延后 90ms）；刷新图标 hover 微旋作可点暗示 */
.rc-body > * { animation: panel-in 0.5s var(--fs-ease-out) both; }
.rc-body > :nth-child(2) { animation-delay: 90ms; }
@keyframes panel-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
}
.rc-btn:hover svg { transform: rotate(-30deg); }
html[data-motion-allowed="false"] .rc-body > * { animation: none; opacity: 1; transform: none; }
html[data-motion-allowed="false"] .rc-btn:hover svg,
html[data-motion-allowed="false"] .rc-btn:active { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .rc-body > * { animation: none; opacity: 1; transform: none; }
  html:not([data-motion="on"]) .rc-btn:hover svg,
  html:not([data-motion="on"]) .rc-btn:active { transform: none; }
}
</style>
