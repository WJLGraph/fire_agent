<template>
  <!-- 全屏阅读浮层：v0 纸张阅读区同构（rep-bar 操作条 + rep-paper 纸张） -->
  <div class="dr" @click.self="emit('close')">
    <div class="dr__sheet">
      <!-- 操作条（56px surface + 发丝下缘） -->
      <div class="dr__bar">
        <span class="dr__t" :title="title">{{ title }}</span>
        <span v-if="chunks" class="dr__meta mono">{{ chunks }} chunks</span>
        <span v-if="isPdf && pdfUrl" class="dr__meta mono">PDF 原件</span>
        <span class="dr__sp"></span>
        <a
          v-if="pdfUrl"
          class="dr__dl"
          :href="pdfUrl"
          :download="title ? `${title}.pdf` : 'document.pdf'"
          title="下载 PDF 原件"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3v9.5"/><path d="m6 9 4 4 4-4"/><path d="M4 16.5h12"/></svg>
          下载原件
        </a>
        <button class="dr__close" title="关闭阅读 (Esc)" @click="emit('close')">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5l10 10M15 5 5 15"/></svg>
        </button>
      </div>

      <!-- PDF 原件：浏览器原生预览 -->
      <div v-if="isPdf" class="dr__pdf">
        <div v-if="pdfLoading" class="dr__state">正在载入 PDF 原件…</div>
        <div v-else-if="error" class="dr__state is-err">{{ error }}</div>
        <iframe
          v-else-if="pdfUrl"
          :src="pdfUrl"
          class="dr__frame"
          :title="title"
        />
      </div>

      <!-- 非 PDF：分片拼接文本（纸张正文） -->
      <div v-else class="dr__scroll">
        <article class="dr__paper">
          <div v-if="loading" class="dr__state">正在载入文档全文…</div>
          <div v-else-if="error" class="dr__state is-err">{{ error }}</div>
          <template v-else>
            <h1 class="dr__title">{{ title }}</h1>
            <div class="dr__doc-meta">
              <span>{{ chunks }} 个检索分片</span>
              <span>全文由分片按序拼接</span>
            </div>
            <div class="dr__body">{{ content }}</div>
          </template>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 知识库 · 文档阅读浮层
 *
 * PDF：内嵌浏览器原生阅读器加载「PDF 原件」（GET /rag/documents/{id}/file，
 *      Blob URL 注入 iframe），操作条提供「下载原件」；
 * 其他类型：56px 操作条 + 760px 纸张正文（RAG 分片按序拼接，pre-wrap）。
 * Esc / 点遮罩关闭。
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { authFetch } from '@/api/http'
import { API_V1 } from '@/utils/config'

const props = defineProps({
  docId: { type: Number, default: null },
  fileType: { type: String, default: '' },
  title: { type: String, default: '' },
  content: { type: String, default: '' },
  chunks: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const isPdf = computed(() => (props.fileType || '').toLowerCase() === 'pdf')

// ===== PDF 原件加载（Blob URL，带鉴权头拉流） =====
const pdfLoading = ref(false)
const pdfUrl = ref('')
const pdfError = ref('')

const loadPdf = async () => {
  if (!isPdf.value || !props.docId) return
  pdfLoading.value = true
  pdfError.value = ''
  releasePdf()
  try {
    const res = await authFetch(`${API_V1}/rag/documents/${props.docId}/file`)
    if (!res.ok) {
      let detail = `加载失败（${res.status}）`
      try {
        const j = await res.json()
        if (j?.detail) detail = j.detail
      } catch { /* 非 JSON 响应忽略 */ }
      throw new Error(detail)
    }
    const blob = await res.blob()
    if (!blob.size) throw new Error('原文件为空或已丢失')
    pdfUrl.value = URL.createObjectURL(blob)
  } catch (e) {
    pdfError.value = e.message || 'PDF 加载失败'
  } finally {
    pdfLoading.value = false
  }
}
const releasePdf = () => {
  if (pdfUrl.value) {
    URL.revokeObjectURL(pdfUrl.value)
    pdfUrl.value = ''
  }
}
const releaseAndClose = () => {
  releasePdf()
  emit('close')
}

watch(() => props.docId, loadPdf, { immediate: true })

const onKey = (e) => { if (e.key === 'Escape') releaseAndClose() }
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  releasePdf()
})
</script>

<style scoped>
.dr {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: color-mix(in srgb, var(--fs-bg, #000) 62%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}
.dr__sheet {
  width: min(960px, 100%);
  height: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: var(--fs-e3), inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
  animation: dr-sheet-in 0.36s var(--fs-ease-out) both;
}
@keyframes dr-sheet-in {
  from { opacity: 0; transform: translateY(10px) scale(0.985); }
  to { opacity: 1; transform: none; }
}

/* ===== 操作条（v0 rep-bar 同构） ===== */
.dr__bar {
  flex-shrink: 0;
  height: 56px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: inset 0 -1px 0 var(--fs-hairline);
}
.dr__t {
  font-size: 14px;
  font-weight: 600;
  color: var(--fs-ink-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dr__meta {
  flex-shrink: 0;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  padding: 2px 7px;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  font-variant-numeric: tabular-nums;
}
.dr__sp { flex: 1; }
.dr__dl {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
  color: var(--fs-ink-700);
  text-decoration: none;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  transition:
    background-color var(--fs-dur-micro) var(--fs-ease),
    color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.dr__dl:hover {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-900);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong), var(--fs-e1);
}
.dr__dl svg { width: 13px; height: 13px; }
.dr__close {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--fs-r-sm, 6px);
  background: transparent;
  color: var(--fs-ink-500);
  cursor: pointer;
  transition:
    background-color var(--fs-dur-micro) var(--fs-ease),
    color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.dr__close:hover { background: var(--fs-bg-sunken); color: var(--fs-ink-900); box-shadow: var(--fs-e1); }
.dr__close svg { width: 14px; height: 14px; }

/* ===== PDF 原件内嵌 ===== */
.dr__pdf {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-sunken);
}
.dr__frame {
  flex: 1;
  width: 100%;
  height: 100%;
  border: 0;
  background: transparent;
}

/* ===== 文本纸张（v0 rep-paper 同构：760px 居中 + 大留白） ===== */
.dr__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
.dr__scroll::-webkit-scrollbar { width: 8px; }
.dr__scroll::-webkit-scrollbar-thumb {
  background: var(--fs-hairline-strong);
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: content-box;
}
.dr__scroll::-webkit-scrollbar-thumb:hover { background: var(--fs-ink-400); background-clip: content-box; }
.dr__paper {
  max-width: 760px;
  margin: 0 auto;
  padding: 40px 32px 72px;
  animation: dr-paper-in 0.4s var(--fs-ease-out) both;
}
@keyframes dr-paper-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.dr__title {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.35;
  color: var(--fs-ink-900);
  padding-bottom: 16px;
  border-bottom: 1px solid var(--fs-hairline-strong);
}
.dr__doc-meta {
  margin-top: 12px;
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
}
.dr__body {
  margin-top: 28px;
  font-size: 15px;
  line-height: 1.95;
  color: var(--fs-ink-700);
  white-space: pre-wrap;
  word-break: break-word;
  text-wrap: pretty;
}
.dr__state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 64px 0;
  text-align: center;
  font-size: 12px;
  color: var(--fs-ink-400);
}
.dr__state.is-err { color: var(--fs-danger); }

/* ===== 动效闸门：关闭时浮层与纸张落终态 ===== */
html[data-motion-allowed="false"] .dr__sheet,
html[data-motion-allowed="false"] .dr__paper { animation: none; }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .dr__sheet,
  html:not([data-motion="on"]) .dr__paper { animation: none; }
}
</style>
