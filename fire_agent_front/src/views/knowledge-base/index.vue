<script setup>
/**
 * 知识库 RAG 页面 — 文档管理 + 检索问答
 *
 * 后端 API: /api/v1/rag/documents (GET/POST/DELETE)
 *          /api/v1/rag/ask (POST)
 *
 * 视觉 V6：按 docs/design/visual-v0.html §kb 屏全面重做展示层——
 *   - 页头改 v0 page-head（64px 单行：标题 + 副题 + 右侧状态徽标）
 *   - 左栏（340px）：文档库（kb-drop 投放 + kb-doc 条目）+ 问答历史（hist-item 卡片常驻）
 *   - 右主区（居中 980px）：提问卡 kb-q → RAG 回答卡 kb-ans → 引用溯源 kb-cite
 *   - 空态改 v0 empty（虚线发丝框）
 * 状态机 + 数据请求（含流式解析）零改动。
 */
import BackHomeButton from '@/components/base/BackHomeButton.vue'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchDocuments as fetchDocumentsApi,
  uploadDocument,
  deleteDocument,
  fetchDocumentContent,
  fetchHistory,
  fetchHistoryDetail,
  deleteHistoryItem as deleteHistoryItemApi,
  clearHistory as clearHistoryApi,
} from '@/api/rag'
import { useKbQa, cancelKbTask } from '@/composables/useKbQa'
import { recordState, startRecord, cleanupSpeech } from '@/utils/speech'
import KbDocsPanel from './KbDocsPanel.vue'
import KbDocReader from './KbDocReader.vue'
import KbQaInput from './KbQaInput.vue'
import KbAnswerPanel from './KbAnswerPanel.vue'
import KbTaskProcessDrawer from './KbTaskProcessDrawer.vue'

// ====== 文档管理 ======
const documents = ref([])
const loadingDocs = ref(false)
const uploadLoading = ref(false)
// 上传进度：null=空闲；{ percent, phase: 'upload'|'process', filename }
const uploadProgress = ref(null)

// ====== 文档阅读（点击左栏文档条目） ======
// PDF → 原件内嵌预览（KbDocReader 自行拉流）；其他类型 → 分片拼接文本
const docReader = ref({ title: '', content: '', chunks: 0, loading: false, error: '', docId: null, fileType: '' })
const isPdfDoc = (doc) => (doc.file_type || doc.title || '').toLowerCase().endsWith('.pdf') || (doc.file_type || '') === 'pdf'
const openDocReader = async (doc) => {
  if (isPdfDoc(doc)) {
    docReader.value = { title: doc.title, content: '', chunks: doc.chunk_count || 0, loading: false, error: '', docId: doc.id, fileType: 'pdf' }
    return
  }
  docReader.value = { title: doc.title, content: '', chunks: 0, loading: true, error: '', docId: doc.id, fileType: doc.file_type || '' }
  try {
    const json = await fetchDocumentContent(doc.id)
    if (json.code === 200 && json.data) {
      docReader.value = {
        ...docReader.value,
        title: json.data.title || doc.title,
        content: json.data.content || '',
        chunks: json.data.chunks || 0,
        loading: false,
        error: json.data.content ? '' : '该文档没有可读文本（可能提取失败）',
      }
    } else {
      docReader.value = { ...docReader.value, loading: false, error: json.detail || json.message || '读取失败' }
    }
  } catch (e) {
    docReader.value = { ...docReader.value, loading: false, error: e.message || '读取失败' }
  }
}
const closeDocReader = () => {
  docReader.value = { title: '', content: '', chunks: 0, loading: false, error: '', docId: null, fileType: '' }
}

const fetchDocuments = async () => {
  loadingDocs.value = true
  try {
    const json = await fetchDocumentsApi()
    if (json.code === 200) {
      documents.value = json.data || []
    }
  } catch {
    // 静默失败
  } finally {
    loadingDocs.value = false
  }
}

const handleUpload = async (file) => {
  uploadLoading.value = true
  const raw = file.raw || file
  uploadProgress.value = { percent: 0, phase: 'upload', filename: file.name || raw.name }
  try {
    const formData = new FormData()
    formData.append('file', raw)
    formData.append('category', 'other')

    const json = await uploadDocument(formData, (loaded, total) => {
      // 字节上传进度；完成后切到「服务器解析索引中」不确定态
      uploadProgress.value = {
        percent: Math.round((loaded / total) * 100),
        phase: loaded >= total ? 'process' : 'upload',
        filename: file.name || raw.name,
      }
    })
    if (json.code === 200) {
      if (json.data && json.data.status === 'failed') {
        // 文档上传成功但文本提取失败（扫描件/无文字层），明确提醒用户
        ElMessage.warning(`文档 "${file.name}" 已上传，但文本提取失败：${json.data.error || '可能为扫描件或无文字层'}`)
      } else {
        ElMessage.success(`文档 "${file.name}" 上传成功`)
      }
      await fetchDocuments()
    } else {
      ElMessage.error('上传失败: ' + (json.detail || json.message))
    }
  } catch (e) {
    ElMessage.error('上传失败: ' + e.message)
  } finally {
    uploadLoading.value = false
    uploadProgress.value = null
  }
}

const handleDelete = async (doc) => {
  try {
    await ElMessageBox.confirm(`确定删除 "${doc.title}"？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const json = await deleteDocument(doc.id)
    if (json.code === 200) {
      ElMessage.success('删除成功')
      await fetchDocuments()
    }
  } catch {
    // 取消删除
  }
}

// ====== RAG 问答（状态在 useKbQa 模块单例：切页/返回不丢进度，流式继续打字） ======
const {
  question, asking, answerResult, streamAnswer, streamMeta, streamThink, kbTasks, askQuestion,
} = useKbQa({ onFinished: () => loadHistory() })

// 页头徽标：展示真实回答模型（随 result 更新），无回答时不硬编码模型名
const headBadge = computed(() => {
  if (!answerResult.value) return '流式回答 · 向量检索就绪'
  if (!answerResult.value.llm_used) return '关键词·向量检索'
  return `${answerResult.value.llm_model || 'LLM'} · 流式回答`
})

const handleAsk = askQuestion

// ====== 语音提问：识别完成自动提交 ======
const handleMicClick = () => {
  if (recordState.recording) {
    startRecord() // 录音中再次调用 = 停止并识别
    return
  }
  startRecord((text) => {
    question.value = text
    handleAsk()
  })
}

const handleExample = (ex) => {
  question.value = ex
  handleAsk()
}

// ====== 问答历史（后端数据库持久化，按用户隔离） ======
const askHistory = ref([])

const loadHistory = async () => {
  try {
    const json = await fetchHistory()
    if (json.code === 200) {
      askHistory.value = json.data || []
    }
  } catch {
    /* 静默 */
  }
}

// ====== 点击历史：直接回显数据库存储的问答结果，不重新检索 ======
const handleHistoryClick = async (item) => {
  question.value = item.text
  try {
    const json = await fetchHistoryDetail(item.id)
    if (json.code === 200 && json.data.result) {
      answerResult.value = json.data.result
      return
    }
  } catch {
    /* 接口失败则回退为重新提问 */
  }
  // 旧记录无存储结果（升级前的数据），回退为重新执行提问
  handleAsk()
}

const deleteHistoryItem = async (item) => {
  try {
    const json = await deleteHistoryItemApi(item.id)
    if (json.code === 200) {
      askHistory.value = askHistory.value.filter(h => h.id !== item.id)
    }
  } catch {
    /* 静默 */
  }
}

const clearHistory = async () => {
  try {
    const json = await clearHistoryApi()
    if (json.code === 200) {
      askHistory.value = []
      ElMessage.success('历史已清空')
    }
  } catch {
    /* 静默 */
  }
}

// ====== 问答任务进程（页头入口 → 抽屉，对齐 Agent 中心「任务进程」交互） ======
const taskDrawer = ref(false)
const openTaskDrawer = () => {
  loadHistory() // 打开时刷新一次，反映最新存档
  taskDrawer.value = true
}
// 查看 → 回显存档回答并收起抽屉；终止/删除/清空走 useKbQa 与历史接口
const viewTask = (item) => {
  handleHistoryClick(item)
  taskDrawer.value = false
}
const onCancelTask = (t) => {
  cancelKbTask(t.key)
  ElMessage.success('已终止该问答任务')
}
// 进行中任务数（页头徽标点亮）
const runningCount = computed(() => kbTasks.value.filter(t => t.status === 'running').length)

// ====== 初始化 ======
onMounted(() => {
  fetchDocuments()
  loadHistory()
})
onUnmounted(() => {
  cleanupSpeech() // 停止语音播报/录音
})
</script>

<template>
  <div class="kb-page">
    <!-- ===== 页头（v0 page-head 同构：64px 单行） ===== -->
    <header class="kb-head">
      <div class="kb-head__t">
        <h1 class="kb-head__h1">知识库</h1>
        <p class="kb-head__sub">文档上传 · RAG 检索问答 · 引用溯源</p>
      </div>
      <BackHomeButton />
      <span class="kb-head__sp"></span>
      <!-- 问答任务进程入口（对齐 Agent 中心「任务进程」）：抽屉承载进行中任务与全部存档 -->
      <button class="kb-head__tasks" title="问答任务进程：实时进度 / 终止 / 查看存档 / 删除" @click="openTaskDrawer">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5h8v13H6z"/><path d="M8.2 7h3.6M8.2 10h3.6"/><path d="M9 13.5h2"/></svg>
        任务进程
        <span v-if="runningCount" class="kb-head__tasks-n is-live mono">{{ runningCount }}</span>
        <span v-else-if="askHistory.length" class="kb-head__tasks-n mono">{{ askHistory.length }}</span>
      </button>
      <span class="kb-head__badge mono">{{ headBadge }}</span>
      <span class="kb-head__live"><i class="kb-head__dot"></i>向量检索 就绪</span>
    </header>

    <!-- ===== 主体：左栏（文档库 + 历史）/ 右主区（提问 → 回答 → 引用） ===== -->
    <div class="kb-body">
      <!-- 左栏 -->
      <aside class="kb-side">
        <div class="kb-side__scroll">
          <KbDocsPanel
            :documents="documents"
            :loading-docs="loadingDocs"
            :upload-progress="uploadProgress"
            :ask-history="askHistory"
            :question="question"
            :answer-result="answerResult"
            @upload="handleUpload"
            @open-doc="openDocReader"
            @delete-doc="handleDelete"
            @history-click="handleHistoryClick"
            @history-delete="deleteHistoryItem"
            @history-clear="clearHistory"
          />
        </div>
      </aside>

      <!-- 右主区 -->
      <div class="kb-main">
        <div class="kb-main__scroll">
          <!-- 提问卡 -->
          <KbQaInput
            v-model="question"
            :asking="asking"
            :recording="recordState.recording"
            @ask="handleAsk"
            @mic="handleMicClick"
            @example="handleExample"
          />

          <!-- 回答区（检索过程 → 思考/流式 → 终态回答 → 引用溯源） -->
          <KbAnswerPanel
            v-if="answerResult || streamAnswer || streamThink"
            :result="answerResult"
            :stream-text="streamAnswer"
            :stream-meta="streamMeta"
            :stream-think="streamThink"
            :asking="asking"
          />

          <!-- 空态（v0 empty：虚线发丝框） -->
          <div v-else class="kb-empty">
            <svg class="kb-empty__ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 6.5 10 3l6 3.5v7L10 17l-6-3.5z"/><path d="M10 10v7"/><path d="m4 6.5 6 3.5 6-3.5"/>
            </svg>
            上传知识库文档后，输入问题获取智能回答
            <span class="kb-empty__hint">回答基于文档检索生成，附带引用溯源可点击展开原文</span>
            <button class="kb-empty__btn" @click="handleMicClick">
              {{ recordState.recording ? '停止录音' : '试试语音提问' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 文档阅读浮层（点击左栏文档条目弹出） -->
    <KbDocReader
      v-if="docReader.loading || docReader.error || docReader.content || docReader.docId"
      :doc-id="docReader.docId"
      :file-type="docReader.fileType"
      :title="docReader.title"
      :content="docReader.content"
      :chunks="docReader.chunks"
      :loading="docReader.loading"
      :error="docReader.error"
      @close="closeDocReader"
    />

    <!-- 问答任务进程抽屉（进行中：实时阶段/终止；已结束：存档查看/删除/清空） -->
    <KbTaskProcessDrawer
      v-model="taskDrawer"
      :tasks="kbTasks"
      :history="askHistory"
      @cancel="onCancelTask"
      @view="viewTask"
      @delete="deleteHistoryItem"
      @clear="clearHistory"
    />
  </div>
</template>

<style scoped>
.kb-page {
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
.kb-head {
  flex-shrink: 0;
  height: var(--fs-topbar-h, 64px);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--fs-bg-surface);
  border-bottom: 1px solid var(--fs-hairline);
}
.kb-head__t { min-width: 0; }
.kb-head__h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.2;
  color: var(--fs-ink-900);
}
.kb-head__sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--fs-ink-500);
}
.kb-head__sp { flex: 1; }
/* 问答任务管理入口（页头按钮，参考 Agent 中心"任务进程"） */
.kb-head__tasks {
  height: 30px;
  padding: 0 11px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background-color var(--fs-dur-micro) var(--fs-ease),
    color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.kb-head__tasks svg { width: 13px; height: 13px; }
.kb-head__tasks:hover { background: var(--fs-accent); color: #fff; box-shadow: var(--fs-e1); transform: translateY(-1px); }
.kb-head__tasks:active { transform: translateY(0); box-shadow: none; }
.kb-head__tasks-n {
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--fs-accent);
  color: #fff;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}
.kb-head__tasks:hover .kb-head__tasks-n { background: rgb(255 255 255 / 25%); }
/* 进行中徽标（accent 底 + 呼吸）：有问答任务在跑时点亮 */
.kb-head__tasks-n.is-live { animation: kb-live-pulse 1.4s ease-in-out infinite; }
@keyframes kb-live-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
.kb-head__badge {
  font-family: var(--fs-font-mono);
  font-size: 11px;
  color: var(--fs-ink-500);
  white-space: nowrap;
}
.kb-head__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  font-size: 11px;
  color: var(--fs-ink-700);
  white-space: nowrap;
}
.kb-head__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--fs-success);
}

/* ===== 主体（v0 sq-body 同构） ===== */
.kb-body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.kb-side {
  flex: none;
  width: 340px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--fs-bg-surface);
  border-right: 1px solid var(--fs-hairline);
  overflow: hidden;
}
.kb-side__scroll {
  flex: 1;
  min-height: 0;
  overflow: hidden; /* 整列不滚动：上传+文档库定高，问答历史弹性 + 内部滚动，翻页器常显沉底 */
  padding: 24px 16px 14px; /* 顶部 24px：与页头之间留出呼吸，整列不再顶格（智能查询/Agent 中心左列同款） */
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.kb-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-canvas);
}
.kb-main__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  width: 100%;
  max-width: 980px;
  margin: 0 auto;
  padding: 20px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

/* ===== 空态（v0 empty：虚线发丝框） ===== */
.kb-empty {
  flex: 1;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-md, 10px);
  color: var(--fs-ink-500);
  font-size: 13px;
  text-align: center;
}
.kb-empty__ic {
  width: 22px;
  height: 22px;
  color: var(--fs-ink-400);
}
.kb-empty__hint {
  font-size: 11px;
  color: var(--fs-ink-400);
}
.kb-empty__btn {
  margin-top: 8px;
  height: 28px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  font-weight: 500;
  color: var(--fs-ink-700);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  cursor: pointer;
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.kb-empty__btn:hover {
  color: var(--fs-accent);
  background: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-accent);
  transform: translateY(-1px);
}
/* 问答任务进程抽屉样式已随组件迁移至 KbTaskProcessDrawer.vue */
/* ==================== V7 入场微动效（挂载即播，零 JS；基线即终态） ====================
   双栏面板升起 + 空态浮出；文档/问答列表错峰由子面板容器淡入承担 */
.kb-main, .kb-side { animation: panel-in 0.5s var(--fs-ease-out) both; }
.kb-side { animation-delay: 0.08s; }
@keyframes panel-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
}
.kb-empty { animation: kb-empty-in 0.45s var(--fs-ease-out) both; }
@keyframes kb-empty-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}

/* ===== 动效闸门：关闭时入场停于终态、循环全停、悬停位移归零 ===== */
html[data-motion-allowed="false"] .kb-main,
html[data-motion-allowed="false"] .kb-side,
html[data-motion-allowed="false"] .kb-empty,
html[data-motion-allowed="false"] .kb-head__tasks-n.is-live { animation: none; }
html[data-motion-allowed="false"] .kb-head__tasks:hover,
html[data-motion-allowed="false"] .kb-empty__btn:hover { transform: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .kb-main,
  html:not([data-motion="on"]) .kb-side,
  html:not([data-motion="on"]) .kb-empty,
  html:not([data-motion="on"]) .kb-head__tasks-n.is-live { animation: none; }
  html:not([data-motion="on"]) .kb-head__tasks:hover,
  html:not([data-motion="on"]) .kb-empty__btn:hover { transform: none; }
}
</style>
