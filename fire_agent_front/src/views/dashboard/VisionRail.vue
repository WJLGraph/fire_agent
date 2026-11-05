<script setup>
/**
 * 作战大屏 · AI 火情识别抽屉（视觉模型，visual-v0 §vision-drawer 同构）
 *
 * 折叠为地图左缘 34px 竖条，展开为 v0 vision-drawer：
 *   头部（火焰图标 + 标题 + 记录数徽标 + 收起钮）
 *   → 上传区（虚线 hairline，无 Emoji）
 *   → 识别详情（task-card：文件名 + mono 时间 + 缩略图 + markdown 结论）
 *   → 识别历史（task-card 式条目 + 悬停删除）
 *
 * 自包含区块：上传识别 / 结果详情 / 语音播报 / 识别历史，全部状态与请求在本组件内闭环。
 * 由父组件拆分而来，逻辑未做任何修改。
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import renderMarkdown from '@/utils/markdown'
import { speakState, speakText, cleanupSpeech } from '@/utils/speech'
import {
  fetchHistory as fetchVisionHistory,
  fetchImageRaw,
  deleteHistory as deleteVisionRecord,
  analyze as analyzeVisionImage,
} from '@/api/vision'

const visionOpen = ref(false)
const emit = defineEmits(['expand'])
// 展开状态上抛：父组件据此平移地图左上的数据源徽标，避免抽屉遮挡
watch(visionOpen, (v) => emit('expand', v))
const visionAnalyzing = ref(false)
const visionFile = ref(null)
const visionDetail = ref(null)   // 当前展示详情：{ id, filename, model, analysis, created_at, imageSrc }
const visionHistory = ref([])
const visionError = ref('')

// 拉取识别历史（带鉴权）
const loadVisionHistory = async () => {
  try {
    const json = await fetchVisionHistory()
    if (json.code === 200) visionHistory.value = json.data || []
  } catch { /* 静默失败 */ }
}

// 通过鉴权接口加载历史图片（blob → objectURL）
const loadVisionImage = async (id) => {
  try {
    const res = await fetchImageRaw(id)
    if (!res.ok) return ''
    const blob = await res.blob()
    return URL.createObjectURL(blob)
  } catch { return '' }
}

// 点击历史条目 → 加载详情 + 图片
const openVisionRecord = async (h) => {
  visionError.value = ''
  visionDetail.value = { ...h, imageSrc: '' }
  if (h.has_image) {
    visionDetail.value.imageSrc = await loadVisionImage(h.id)
  }
}

// 删除历史记录
const deleteVisionHistory = async (h) => {
  try {
    const json = await deleteVisionRecord(h.id)
    if (json.code === 200) {
      visionHistory.value = visionHistory.value.filter(x => x.id !== h.id)
      if (visionDetail.value && visionDetail.value.id === h.id) visionDetail.value = null
      ElMessage.success('已删除')
    } else {
      ElMessage.error(json.detail || '删除失败')
    }
  } catch { ElMessage.error('删除失败') }
}

// 选择图片（新识别）
const onVisionFile = (uploadFile) => {
  const raw = uploadFile.raw
  if (!raw) return
  if (raw.size > 10 * 1024 * 1024) { ElMessage.error('图片不能超过 10MB'); return }
  visionFile.value = raw
  visionError.value = ''
  // 先本地预览
  visionDetail.value = {
    id: null, filename: raw.name, model: '', created_at: '待识别',
    analysis: '> 已选择图片，点击「开始识别」进行火情分析', imageSrc: URL.createObjectURL(raw),
  }
}

// 执行识别
const analyzeVision = async () => {
  if (!visionFile.value) return
  visionAnalyzing.value = true
  visionError.value = ''
  try {
    const fd = new FormData()
    fd.append('file', visionFile.value)
    const json = await analyzeVisionImage(fd)
    if (json.code === 200 && json.data.ok) {
      visionDetail.value = {
        id: json.data.id,
        filename: json.data.filename,
        model: json.data.model,
        analysis: json.data.analysis,
        created_at: '刚刚',
        imageSrc: visionDetail.value?.imageSrc || '',
      }
      visionFile.value = null
      loadVisionHistory()
    } else {
      visionError.value = json.data?.detail || '识别失败'
    }
  } catch {
    visionError.value = '识别请求失败，请检查后端服务'
  } finally {
    visionAnalyzing.value = false
  }
}

onMounted(() => {
  loadVisionHistory()
})

onUnmounted(() => {
  cleanupSpeech() // 停止语音播报/录音
})
</script>

<template>
  <!-- AI 火情识别：左缘折叠竖条 + 展开抽屉（v0 vision-tab + vision-drawer 同构） -->
  <aside class="vision-rail" :class="{ open: visionOpen }">
    <!-- 折叠竖条 -->
    <button
      class="vr-tab"
      :title="visionOpen ? '收起 AI 火情图片识别' : '展开 AI 火情图片识别（视觉模型）'"
      @click="visionOpen = !visionOpen"
    >
      <svg class="vr-tab__flame" :class="{ blink: visionAnalyzing, 'mo-loop': visionAnalyzing }" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 2.2s4.4 3.4 4.4 7.2a4.4 4.4 0 1 1-8.8 0c0-1.6.8-2.8.8-2.8s.6 1.4 1.6 1.4c1.4 0 1.6-2.4 2-5.8z"/>
      </svg>
      <span class="vr-tab__text">火情图片识别</span>
      <span class="vr-tab__arrow">{{ visionOpen ? '‹' : '›' }}</span>
    </button>

    <!-- 展开抽屉 -->
    <div v-show="visionOpen" class="vr-panel">
      <!-- 头部：火焰图标 + 标题 + 记录数徽标 + 收起钮（v0 vision-drawer__hd 同构） -->
      <header class="vr-head">
        <svg class="vr-head__flame" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 2.2s4.4 3.4 4.4 7.2a4.4 4.4 0 1 1-8.8 0c0-1.6.8-2.8.8-2.8s.6 1.4 1.6 1.4c1.4 0 1.6-2.4 2-5.8z"/>
        </svg>
        <h3 class="vr-head__t">AI 火情图片识别</h3>
        <span class="vr-head__sp"></span>
        <span class="vr-head__badge">{{ visionHistory.length }} 条记录</span>
        <button class="vr-icon-btn" title="收起" @click="visionOpen = false">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="m5.5 5.5 9 9M14.5 5.5l-9 9"/></svg>
        </button>
      </header>

      <!-- 主体滚动区 -->
      <div class="vr-body">
        <!-- 上传识别 -->
        <div class="vr-upload">
          <el-upload
            drag
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            :on-change="onVisionFile"
            class="vr-upload-box"
          >
            <div class="vu-inner">
              <svg class="vu-inner__ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2.8" y="3.6" width="14.4" height="12.8" rx="1.6"/>
                <circle cx="7.4" cy="8.2" r="1.4"/>
                <path d="m2.8 14.2 4.4-4 3.2 2.8 3-2.6 3.8 3.4"/>
              </svg>
              <div class="vu-inner__text">点击 / 拖拽上传火场照片</div>
              <div class="vu-inner__tip">JPG · PNG · WEBP ≤ 10MB</div>
            </div>
          </el-upload>
          <button
            class="vr-run"
            :disabled="!visionFile || visionAnalyzing"
            @click="analyzeVision"
          >{{ visionAnalyzing ? '视觉模型识别中…' : '开始识别' }}</button>
          <div v-if="visionError" class="vr-error">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3.2 2.8 16.4h14.4z"/><path d="M10 8v3.6"/><path d="M10 14.1h.01"/></svg>
            {{ visionError }}
          </div>
        </div>

        <!-- 当前详情（新识别 / 历史）：task-card 同构 -->
        <div v-if="visionDetail" class="vr-card">
          <div class="vr-card__hd">
            <span class="vr-card__t" :title="visionDetail.filename">{{ visionDetail.filename || '识别结果' }}</span>
            <span class="vr-card__sp"></span>
            <span class="vr-card__m">{{ visionDetail.created_at }}</span>
          </div>
          <img v-if="visionDetail.imageSrc" :src="visionDetail.imageSrc" class="vr-card__img" alt="识别图片" />
          <div class="vr-card__analysis markdown-body" v-html="renderMarkdown(visionDetail.analysis)" />
          <div class="vr-card__ops">
            <button
              class="vr-ghost-btn"
              :class="{ speaking: speakState.speaking || speakState.loading }"
              @click="speakText(visionDetail.analysis)"
            >
              <svg v-if="!(speakState.speaking || speakState.loading)" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8v4h2.6l3.4 3V5L6.6 8z"/><path d="M13.2 7.6a3.6 3.6 0 0 1 0 4.8"/></svg>
              <svg v-else viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="5.5" y="4.5" width="9" height="11" rx="1.2"/></svg>
              {{ speakState.speaking || speakState.loading ? '停止播报' : '语音播报' }}
            </button>
            <span v-if="visionDetail.model" class="vr-card__model">{{ visionDetail.model }}</span>
          </div>
        </div>

        <!-- 识别历史 -->
        <div class="vr-history">
          <div class="vr-history__hd">
            <span>识别历史</span>
            <span class="vr-history__n">{{ visionHistory.length }}</span>
          </div>
          <div v-if="!visionHistory.length" class="vr-history__empty">
            暂无识别记录，上传图片开始识别
          </div>
          <div
            v-for="h in visionHistory" :key="h.id"
            class="vr-item"
            :class="{ active: visionDetail && visionDetail.id === h.id }"
            @click="openVisionRecord(h)"
          >
            <div class="vr-item__info">
              <div class="vr-item__t">{{ h.filename || '未命名图片' }}</div>
              <div class="vr-item__m">{{ h.created_at }} · {{ h.model }}</div>
            </div>
            <button class="vr-item__del" title="删除记录" @click.stop="deleteVisionHistory(h)">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5.5h13"/><path d="M8 2.8h4"/><path d="M5.2 5.5 5.9 17h8.2l.7-11.5"/><path d="M8.4 8.4v5.4M11.6 8.4v5.4"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style lang="scss" scoped>
/* ===== 折叠竖条（34px，v0 vision-tab 同构气质） ===== */
.vision-rail {
  width: 34px;
  flex-shrink: 0;
  display: flex;
  margin-right: 6px;
  z-index: 20;
  min-height: 0;
}
.vision-rail.open {
  width: min(330px, 26vw);
}
.vr-tab {
  width: 34px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  cursor: pointer;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-sm);
  box-shadow: var(--fs-e1), inset 0 0 0 1px var(--fs-hairline);
  color: var(--fs-ink-500);
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.vr-tab:hover {
  color: var(--fs-accent);
  box-shadow: var(--fs-e2), inset 0 0 0 1px var(--fs-hairline-strong);
  transform: translateY(-1px);
}
.vr-tab:active { transform: translateY(-1px) scale(0.98); }
.vr-tab__flame {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
.vr-tab:hover .vr-tab__flame { transform: scale(1.12); }
.vr-tab__flame.blink {
  animation: vr-blink 1s ease-in-out infinite;
}
@keyframes vr-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
.vr-tab__text {
  writing-mode: vertical-rl;
  letter-spacing: 0.28em;
  font-size: 11px;
  font-weight: 500;
}
.vr-tab__arrow {
  font-size: 12px;
  color: var(--fs-ink-400);
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
/* 悬停时箭头朝展开方向轻推（折叠向右、展开向左） */
.vr-tab:hover .vr-tab__arrow { transform: translateX(var(--arw, 2px)); }
.vision-rail.open .vr-tab__arrow { --arw: -2px; }

/* ===== 展开抽屉 ===== */
.vr-panel {
  flex: 1;
  min-width: 0;
  margin-left: 6px;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-sm);
  box-shadow: var(--fs-e2), inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
/* 仅在 open 态命中，故每次展开都会重播一次自左淡入 */
.vision-rail.open .vr-panel {
  animation: vr-panel-in 0.26s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) both;
}

/* 头部（v0 vision-drawer__hd：图标 + 标题 + 徽标 + 关闭钮） */
.vr-head {
  flex-shrink: 0;
  height: 44px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px 0 12px;
  border-bottom: 1px solid var(--fs-hairline);
}
.vr-head__flame {
  width: 15px;
  height: 15px;
  color: var(--fs-accent);
  flex-shrink: 0;
}
.vr-head__t {
  font-size: 13px;
  font-weight: 600;
  color: var(--fs-ink-900);
  letter-spacing: 0.01em;
}
.vr-head__sp { flex: 1; }
.vr-head__badge {
  height: 20px;
  display: inline-flex;
  align-items: center;
  padding: 0 7px;
  border-radius: var(--fs-r-xs);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-size: 11px;
  white-space: nowrap;
}
.vr-icon-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--fs-r-xs);
  color: var(--fs-ink-400);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.vr-icon-btn svg { width: 13px; height: 13px; }
.vr-icon-btn:hover { color: var(--fs-ink-900); background: var(--fs-bg-sunken); }

/* 主体滚动区 */
.vr-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden; /* 行悬停 translateX(2px) 不该顶出横向滚动条 */
  padding: 10px 8px 10px 10px; /* 右侧留 2px 余量：位移后仍完整可见，无需裁切 */
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}

/* —— 上传区（虚线 hairline，无 Emoji） —— */
.vr-upload { flex-shrink: 0; }
.vr-upload-box :deep(.el-upload) { width: 100%; }
.vr-upload-box :deep(.el-upload-dragger) {
  padding: 14px 8px;
  background: transparent;
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-sm);
  transition: border-color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.vr-upload-box :deep(.el-upload-dragger:hover) {
  border-color: var(--fs-accent);
  background: var(--fs-accent-soft);
}
.vu-inner { text-align: center; }
.vu-inner__ic {
  width: 20px;
  height: 20px;
  color: var(--fs-ink-400);
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
/* 悬停上传框时图标轻抬，提示可点击/可拖拽 */
.vr-upload-box :deep(.el-upload-dragger:hover) .vu-inner__ic { transform: scale(1.08); }
.vu-inner__text {
  margin-top: 6px;
  font-size: 12px;
  color: var(--fs-ink-500);
}
.vu-inner__tip {
  margin-top: 3px;
  font-size: 10px;
  letter-spacing: 0.04em;
  color: var(--fs-ink-400);
  font-family: var(--fs-font-mono);
}
/* 开始识别（v0 btn--primary 同构） */
.vr-run {
  position: relative;
  overflow: hidden;
  width: 100%;
  height: 30px;
  margin-top: 8px;
  border-radius: var(--fs-r-sm);
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
  transition:
    background var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.vr-run:hover:not(:disabled) {
  background: var(--fs-accent-hover);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
  transform: translateY(-1px);
}
.vr-run:active:not(:disabled) { transform: translateY(0.5px); }
/* hover 扫光：与全局主按钮同一语言（单次 0.62s） */
.vr-run::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.22) 50%, transparent 62%);
  transform: translateX(-130%);
}
.vr-run:hover:not(:disabled)::after {
  animation: vr-sheen 0.62s var(--up-ease, cubic-bezier(0.32, 0.72, 0, 1));
}
.vr-run:disabled {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-400);
  box-shadow: none;
  cursor: not-allowed;
}
.vr-error {
  margin-top: 8px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--fs-danger);
}
.vr-error svg { width: 13px; height: 13px; flex-shrink: 0; margin-top: 1px; }

/* —— 详情卡（v0 task-card 同构） —— */
.vr-card {
  flex-shrink: 0;
  padding: 10px;
  background: var(--fs-bg-canvas);
  border-radius: var(--fs-r-sm);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  display: flex;
  flex-direction: column;
  gap: 8px;
  /* v-if 重建 → 每次打开新记录都自底部淡入一次 */
  animation: vr-card-in 0.3s var(--fs-ease-out, cubic-bezier(0.22, 1, 0.36, 1)) both;
}
.vr-card__hd {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.vr-card__t {
  font-size: 12px;
  font-weight: 500;
  color: var(--fs-ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vr-card__sp { flex: 1; }
.vr-card__m {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--fs-ink-400);
  font-family: var(--fs-font-mono);
}
.vr-card__img {
  width: 100%;
  max-height: 168px;
  object-fit: contain;
  border-radius: var(--fs-r-xs);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
}
.vr-card__analysis {
  font-size: 12px;
  line-height: 1.8;
  color: var(--fs-ink-500);
  word-break: break-word;
}
.vr-card__analysis :deep(h1),
.vr-card__analysis :deep(h2),
.vr-card__analysis :deep(h3),
.vr-card__analysis :deep(h4) {
  margin: 10px 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fs-ink-900);
}
.vr-card__analysis :deep(p) { margin: 6px 0; }
.vr-card__analysis :deep(ul), .vr-card__analysis :deep(ol) { padding-left: 18px; margin: 6px 0; }
.vr-card__analysis :deep(li) { margin: 3px 0; }
.vr-card__analysis :deep(strong) { color: var(--fs-ink-900); font-weight: 600; }
.vr-card__analysis :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 10px;
  border-left: 2px solid var(--fs-accent);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
}
.vr-card__analysis :deep(table) { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 11px; }
.vr-card__analysis :deep(th), .vr-card__analysis :deep(td) {
  padding: 4px 8px;
  text-align: left;
  border-bottom: 1px solid var(--fs-hairline);
}
.vr-card__analysis :deep(th) { color: var(--fs-ink-500); font-weight: 500; border-bottom: 1px solid var(--fs-hairline-strong); }
.vr-card__analysis :deep(code) {
  background: var(--fs-bg-sunken);
  padding: 1px 5px;
  border-radius: var(--fs-r-xs);
  font-family: var(--fs-font-mono);
  font-size: 11px;
  color: var(--fs-accent);
}
.vr-card__ops {
  display: flex;
  align-items: center;
  gap: 8px;
}
.vr-ghost-btn {
  height: 24px;
  padding: 0 9px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--fs-r-xs);
  font-size: 11px;
  color: var(--fs-ink-500);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.vr-ghost-btn svg { width: 12px; height: 12px; }
.vr-ghost-btn:hover { color: var(--fs-ink-900); background: var(--fs-bg-sunken); }
.vr-ghost-btn.speaking { color: var(--fs-danger); }
.vr-card__model {
  margin-left: auto;
  font-size: 10px;
  font-family: var(--fs-font-mono);
  color: var(--fs-ink-400);
}

/* —— 识别历史 —— */
.vr-history {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.vr-history__hd {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
/* 区块刻度条：与图表卡标题、章节标题同一标识语言 */
.vr-history__hd::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 1px;
  background: var(--fs-accent);
}
.vr-history__n {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
}
.vr-history__empty {
  padding: 12px 8px;
  text-align: center;
  font-size: 11px;
  color: var(--fs-ink-400);
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-sm);
}
.vr-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 9px;
  border-radius: var(--fs-r-sm);
  cursor: pointer;
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  transition:
    background var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
/* 悬停轻推 2px：与表格行左侧读数条同义（当前行被「拿起」） */
.vr-item:hover {
  background: var(--fs-bg-sunken);
  transform: translateX(2px);
}
.vr-item.active {
  background: var(--fs-accent-soft);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong), inset 2px 0 0 var(--fs-accent);
}
.vr-item__info { flex: 1; min-width: 0; }
.vr-item__t {
  font-size: 12px;
  color: var(--fs-ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vr-item__m {
  margin-top: 2px;
  font-size: 10px;
  color: var(--fs-ink-400);
  font-family: var(--fs-font-mono);
}
.vr-item__del {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--fs-r-xs);
  color: var(--fs-ink-400);
  opacity: 0;
  cursor: pointer;
  transition: opacity var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.vr-item:hover .vr-item__del { opacity: 1; }
.vr-item__del svg { width: 13px; height: 13px; }
.vr-item__del:hover { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 8%, transparent); }

/* ==================== 入场与关键帧（终态即基线，动效关闭时静态就位） ==================== */
@keyframes vr-panel-in {
  from { opacity: 0; translate: -8px 0; }
  to   { opacity: 1; translate: 0 0; }
}
@keyframes vr-card-in {
  from { opacity: 0; translate: 0 6px; }
  to   { opacity: 1; translate: 0 0; }
}
@keyframes vr-sheen {
  to { transform: translateX(130%); }
}

/* 动效三态闸门：blink 循环由 .mo-loop 统一降级，此处关闭入场与位移反馈 */
html[data-motion-allowed="false"] .vr-panel,
html[data-motion-allowed="false"] .vr-card,
html[data-motion-allowed="false"] .vr-run::after { animation: none; }
html[data-motion-allowed="false"] .vr-tab:hover,
html[data-motion-allowed="false"] .vr-tab:active,
html[data-motion-allowed="false"] .vr-run:hover:not(:disabled),
html[data-motion-allowed="false"] .vr-item:hover,
html[data-motion-allowed="false"] .vr-tab:hover .vr-tab__flame,
html[data-motion-allowed="false"] .vr-tab:hover .vr-tab__arrow,
html[data-motion-allowed="false"] .vr-upload-box :deep(.el-upload-dragger:hover) .vu-inner__ic { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .vr-panel,
  html:not([data-motion="on"]) .vr-card,
  html:not([data-motion="on"]) .vr-run::after { animation: none; }
  html:not([data-motion="on"]) .vr-tab:hover,
  html:not([data-motion="on"]) .vr-tab:active,
  html:not([data-motion="on"]) .vr-run:hover:not(:disabled),
  html:not([data-motion="on"]) .vr-item:hover,
  html:not([data-motion="on"]) .vr-tab:hover .vr-tab__flame,
  html:not([data-motion="on"]) .vr-tab:hover .vr-tab__arrow { transform: none; }
}
</style>
