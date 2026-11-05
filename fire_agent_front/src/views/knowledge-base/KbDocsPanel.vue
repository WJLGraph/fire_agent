<script setup>
/**
 * 知识库 · 左栏（文档库 + 问答历史）— v0 §kb 同构
 *
 * 文档库：sec-t 标题 + kb-drop 虚线投放区 + kb-doc 条目（mono 元信息 + 状态徽标，失败删除线）；
 * 问答历史：hist-item 卡片常驻列表（2 行截断 + mono 时间 + 真实模型徽标 + 命中数 + 删除）。
 * 两列表均带本地分页（文档 3 条/页、历史 4 条/页）：与 Agent 中心历史同款翻页器
 * （el-pagination small · prev/pager/next）。
 * 受控组件：文档/历史数据由父组件持有，请求与状态变更由事件上抛。
 */
import { ref, computed, watch } from 'vue'

const props = defineProps({
  documents: { type: Array, default: () => [] },
  loadingDocs: { type: Boolean, default: false },
  // 上传进度：null=空闲；{ percent: 0-100, phase: 'upload'|'process', filename }
  uploadProgress: { type: Object, default: null },
  askHistory: { type: Array, default: () => [] },
  question: { type: String, default: '' },
  answerResult: { type: Object, default: null },
})
const emit = defineEmits(['upload', 'open-doc', 'delete-doc', 'history-click', 'history-delete', 'history-clear'])

// 历史条目回答模型：item.llm_model 由后端从存储结果透出（真实模型）；
// 旧记录无此字段：llm_used 显示通用「LLM」，未用 LLM 显示「检索」
const histModel = (item) => item.llm_model || (item.llm_used ? 'LLM' : '检索')

// 时间展示（年月日 + 时间，单行等宽；悬停 title 可看完整含秒时间）
const shortTime = (t) => {
  const m = String(t || '').match(/(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/)
  return m ? `${m[1]} ${m[2]}` : String(t || '')
}

// 文档状态 → 徽标文案 / 色系
const statusLabel = (s) => ({ ready: '已索引', processing: '处理中', failed: '提取失败' }[s] || s)
const statusKind = (s) => ({ ready: 'ok', processing: 'wait', failed: 'err' }[s] || 'wait')
// 分片数（后端字段名可能为 chunks / chunk_count，缺失则不显示）
const chunkCount = (doc) => doc.chunk_count ?? doc.chunks ?? null

// ====== 本地分页：文档库 3 条/页 ======
const DOC_PAGE_SIZE = 3
const docPage = ref(1)
const docTotalPages = computed(() => Math.max(1, Math.ceil(props.documents.length / DOC_PAGE_SIZE)))
const pagedDocs = computed(() =>
  props.documents.slice((docPage.value - 1) * DOC_PAGE_SIZE, docPage.value * DOC_PAGE_SIZE),
)
watch(() => props.documents.length, () => {
  if (docPage.value > docTotalPages.value) docPage.value = docTotalPages.value
})
const goDocPage = (p) => { docPage.value = p }

// ====== 本地分页：问答历史 3 条/页（与 Agent 中心历史任务同页容量） ======
const HIST_PAGE_SIZE = 3
const histPage = ref(1)
const histTotalPages = computed(() => Math.max(1, Math.ceil(props.askHistory.length / HIST_PAGE_SIZE)))
const pagedHistory = computed(() =>
  props.askHistory.slice((histPage.value - 1) * HIST_PAGE_SIZE, histPage.value * HIST_PAGE_SIZE),
)
watch(() => props.askHistory.length, () => {
  if (histPage.value > histTotalPages.value) histPage.value = histTotalPages.value
})
const goHistPage = (p) => { histPage.value = p }
</script>

<template>
  <div class="kd">
    <!-- ===== 文档库 ===== -->
    <section class="kd__sec">
      <div class="kd__hd">
        <span class="kd__t">文档库</span>
        <span class="kd__n">{{ documents.length }}</span>
        <span class="kd__sp"></span>
      </div>

      <!-- 投放上传（el-upload 保留原生交互，视觉对齐 v0 kb-drop） -->
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".pdf,.txt,.md"
        :on-change="(file) => emit('upload', file)"
        class="kd__upload"
      >
        <div class="kd-drop" :class="{ busy: loadingDocs }">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11.5 3H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V6.5z"/><path d="M11.5 3v3.5H15"/><path d="M8 11h4M8 13.5h4"/></svg>
          <span>{{ loadingDocs ? '正在处理文档…' : '点击 / 拖拽上传文档' }}</span>
          <em>PDF · TXT · MD</em>
        </div>
      </el-upload>

      <!-- 上传进度条（v0 细线风格：上传阶段真实字节进度 → 服务器解析索引不确定态） -->
      <div v-if="uploadProgress" class="kd__progress">
        <div class="kd__progress-hd">
          <span class="kd__progress-name" :title="uploadProgress.filename">{{ uploadProgress.filename }}</span>
          <span class="kd__progress-phase">
            {{ uploadProgress.phase === 'process' ? '服务器解析索引中…' : `上传中 ${uploadProgress.percent}%` }}
          </span>
        </div>
        <div class="kd__progress-bar" :class="{ indeterminate: uploadProgress.phase === 'process' }">
          <i :style="{ width: (uploadProgress.phase === 'process' ? 100 : uploadProgress.percent) + '%' }"></i>
        </div>
      </div>

      <!-- 文档列表（本地分页 3 条/页） -->
      <div class="kd__list" v-loading="loadingDocs">
        <div v-if="documents.length === 0" class="kd__empty">暂无文档，上传后自动建立索引</div>
        <div
          v-for="doc in pagedDocs"
          :key="doc.id"
          class="kb-doc"
          :class="{ 'is-err': doc.status === 'failed' }"
          @click="emit('open-doc', doc)"
        >
          <span class="kb-doc__t" :title="doc.title">{{ doc.title }}</span>
          <span class="kb-doc__m">
            <span v-if="chunkCount(doc) !== null" class="mono">{{ chunkCount(doc) }} chunks</span>
            <span class="kb-doc__badge" :class="statusKind(doc.status)"><i></i>{{ statusLabel(doc.status) }}</span>
          </span>
          <button class="kd__del" title="删除文档" @click.stop="emit('delete-doc', doc)">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5.5h13"/><path d="M8 2.8h4"/><path d="M5.2 5.5 5.9 17h8.2l.7-11.5"/><path d="M8.4 8.4v5.4M11.6 8.4v5.4"/></svg>
          </button>
        </div>
      </div>

      <!-- 翻页器（常显 · 文档库 3 条/页） -->
      <div v-if="documents.length" class="kd__pager">
        <el-pagination
          size="small"
          layout="prev, pager, next"
          :total="documents.length"
          :page-size="DOC_PAGE_SIZE"
          :current-page="docPage"
          @current-change="goDocPage"
        />
      </div>
    </section>

    <!-- ===== 问答任务（历史存档 · 任务管理入口） ===== -->
    <section class="kd__sec">
      <div class="kd__hd" title="每次提问自动存档，可随时回看 / 删除（数据持久化于服务端）">
        <span class="kd__t">问答任务</span>
        <span class="kd__n">{{ askHistory.length }}</span>
        <span class="kd__sp"></span>
        <button v-if="askHistory.length" class="kd__clear" title="清空全部历史" @click="emit('history-clear')">清空</button>
      </div>

      <div v-if="askHistory.length === 0" class="kd__empty">暂无问答任务<br /><span class="kd__empty-h">每次提问自动存档于此，可随时回看</span></div>
      <div v-else class="kd__hist">
        <div
          v-for="item in pagedHistory"
          :key="item.id"
          class="hist-item"
          :class="{ 'is-on': item.text === question && answerResult }"
          @click="emit('history-click', item)"
        >
          <div class="hist-item__t" :title="item.text">{{ item.text }}</div>
          <div class="hist-item__m">
            <span class="hist-item__time" :title="item.time">{{ shortTime(item.time) }}</span>
            <span class="hist-item__model" :class="{ 'is-plain': !item.llm_model }" :title="`回答模型 ${histModel(item)}${item.llm_model ? '' : '（旧记录未存模型名）'}`">{{ histModel(item) }}</span>
            <span class="hist-item__sp"></span>
            <span class="hist-item__hit" :class="{ ok: item.matched > 0 }">
              {{ item.matched > 0 ? `命中 ${item.matched}` : '未命中' }}
            </span>
            <button class="kd__del kd__del--sm" title="删除该记录" @click.stop="emit('history-delete', item)">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5.5h13"/><path d="M8 2.8h4"/><path d="M5.2 5.5 5.9 17h8.2l.7-11.5"/><path d="M8.4 8.4v5.4M11.6 8.4v5.4"/></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- 翻页器（常显 · 问答历史 3 条/页） -->
      <div v-if="askHistory.length" class="kd__pager">
        <el-pagination
          size="small"
          layout="prev, pager, next"
          :total="askHistory.length"
          :page-size="HIST_PAGE_SIZE"
          :current-page="histPage"
          @current-change="goHistPage"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.kd {
  flex: 1; /* 占满左列：文档库区定高，问答历史区弹性，翻页器常显沉底 */
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.kd__sec {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kd__sec:last-child {
  flex: 1; /* 问答历史区占满剩余高度 */
  min-height: 0;
}

/* 标题行（sec-t 同构：刻度条标题 + 计数 + 延伸发丝线 + 清除） */
.kd__hd {
  display: flex;
  align-items: center;
  gap: 6px;
}
.kd__t {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--fs-ink-500);
}
/* 2px 刻度条：静息发丝、悬停转强调（与大屏图表卡同语言） */
.kd__t::before {
  content: '';
  width: 2px;
  height: 11px;
  margin-right: 6px;
  border-radius: 1px;
  background: var(--fs-hairline-strong);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, ease);
}
.kd__hd:hover .kd__t::before { background: var(--fs-accent); }
.kd__n {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
}
.kd__sp { flex: 1; height: 1px; background: var(--fs-hairline); }
.kd__clear {
  height: 20px;
  padding: 0 7px;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  color: var(--fs-ink-500);
  background: transparent;
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease);
}
.kd__clear:hover { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 8%, transparent); }

/* 投放上传（v0 kb-drop：虚线发丝框） */
.kd__upload :deep(.el-upload) { width: 100%; }
.kd__upload :deep(.el-upload-dragger) {
  width: 100%;
  height: auto;
  padding: 0;
  background: transparent !important;
  border: none !important;
  border-radius: 0;
}
.kd-drop {
  padding: 10px 12px; /* 紧凑投放区：为问答任务列表腾出高度，整列无滚动 */
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  border: 1px dashed var(--fs-hairline-strong);
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  color: var(--fs-ink-500);
  cursor: pointer;
  transition:
    border-color var(--fs-dur-micro) var(--fs-ease),
    color var(--fs-dur-micro) var(--fs-ease),
    background-color var(--fs-dur-micro) var(--fs-ease);
}
.kd-drop svg {
  width: 16px;
  height: 16px;
  color: var(--fs-ink-400);
  transition: transform var(--up-dur-fast, 120ms) var(--up-ease, ease);
}
.kd-drop em {
  font-style: normal;
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
  color: var(--fs-ink-400);
}
.kd-drop:hover, .kd-drop.busy {
  border-color: var(--fs-accent);
  color: var(--fs-accent);
  background: rgba(var(--fs-accent-rgb), 0.04);
}
.kd-drop:hover svg { transform: translateY(-1px); }
.kd-drop.busy svg { color: var(--fs-accent); }

/* 文档列表 */
.kd__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 24px;
}

/* 文档条目（v0 kb-doc：hist-item 同构；悬停读数条 + 微移） */
.kb-doc {
  box-sizing: border-box;
  position: relative;
  height: 38px; /* 固定行高：padding 18 + 单行文本 */
  padding: 9px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  transition:
    background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
  cursor: pointer; /* 点击进入阅读 */
}
.kb-doc::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  bottom: 7px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--fs-accent);
  transform: scaleY(0);
  transform-origin: center;
  transition: transform var(--up-dur-slow, 320ms) var(--up-ease, ease);
}
.kb-doc:hover { background: var(--fs-bg-sunken); transform: translateX(2px); }
.kb-doc:hover::before { transform: scaleY(1); }

/* ===== 上传进度条（v0 细线风格） ===== */
.kd__progress {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 7px 10px 8px;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  background: var(--fs-bg-sunken);
}
.kd__progress-hd {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 10px;
}
.kd__progress-name {
  flex: 1;
  min-width: 0;
  color: var(--fs-ink-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kd__progress-phase {
  flex-shrink: 0;
  font-family: var(--fs-font-mono);
  color: var(--fs-ink-500);
  letter-spacing: 0.02em;
}
.kd__progress-bar {
  height: 3px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--fs-hairline-strong) 45%, transparent);
  overflow: hidden;
}
.kd__progress-bar i {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: var(--fs-accent);
  transition: width var(--fs-dur-micro, 150ms) ease-out;
}
.kd__progress-bar.indeterminate i {
  width: 100% !important;
  transform-origin: left;
  animation: kd-indet 1.1s var(--fs-ease, ease-in-out) infinite;
}
@keyframes kd-indet {
  0% { transform: translateX(-100%) scaleX(0.55); }
  55% { transform: translateX(55%) scaleX(0.55); }
  100% { transform: translateX(130%) scaleX(0.55); }
}
.kb-doc__t {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--fs-ink-900);
}
.kb-doc.is-err .kb-doc__t {
  color: var(--fs-ink-400);
  text-decoration: line-through;
  text-decoration-color: var(--fs-hairline-strong);
}
.kb-doc__m {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
}
.kb-doc__m .mono { font-family: var(--fs-font-mono); }
.kb-doc__badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 16px;
  padding: 0 6px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 10px;
  white-space: nowrap;
}
.kb-doc__badge i {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: currentColor;
}
.kb-doc__badge.ok { background: color-mix(in srgb, var(--fs-success) 10%, transparent); color: var(--fs-success); }
.kb-doc__badge.wait { background: color-mix(in srgb, var(--fs-warning) 12%, transparent); color: var(--fs-warning); }
.kb-doc__badge.err { background: var(--fs-bg-sunken); color: var(--fs-ink-400); }

/* 删除按钮（sunken 常显底色，暗色可辨） */
.kd__del {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--fs-r-xs, 3px);
  color: var(--fs-ink-500);
  background: var(--fs-bg-sunken);
  cursor: pointer;
  transition: color var(--fs-dur-micro) var(--fs-ease), background var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.kd__del svg { width: 11px; height: 11px; }
.kd__del:hover { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 12%, transparent); }

/* 历史列表（hist-item 卡片：与智能查询「查询历史」/ Agent 中心「历史任务」共用同一套规范，仅行高不同） */
.kd__hist {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto; /* 兜底：极小视口时内部滚动（滚动条隐藏，滚轮可用），常规尺寸下整列无滑动 */
  overflow-x: hidden; /* 悬停 translateX(2px) 不该顶出横向滚动条 */
  padding-right: 2px; /* 给 2px 位移留出余量 */
  scrollbar-width: none;
}
.kd__hist::-webkit-scrollbar { display: none; }
.hist-item {
  box-sizing: border-box;
  position: relative;
  flex-shrink: 0; /* 行高固定：装不下宁可分页也不压扁 */
  height: 75px; /* 固定行高：padding 16 + 文本 36（2 行）+ meta 上边距 5 + meta 18；单行/双行条目等高，翻页不跳动 */
  padding: 8px 12px;
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  transition:
    background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
/* 左沿 2px 强调竖轨：静息收起、悬停/选中展开 */
.hist-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--fs-accent);
  transform: scaleY(0);
  transform-origin: center;
  transition: transform 0.32s var(--fs-ease);
}
.hist-item:hover { background-color: var(--fs-bg-sunken); transform: translateX(2px); }
.hist-item:hover::before { transform: scaleY(1); }
.hist-item:active { transform: translateX(2px) scale(0.995); }
/* 选中条目：accent 环 + 竖轨常驻 */
.hist-item.is-on { box-shadow: inset 0 0 0 1px var(--fs-accent); }
.hist-item.is-on::before { transform: scaleY(1); }
.hist-item__t {
  height: 36px; /* 固定 2 行（12px × 1.5 × 2）：与 Agent 中心历史同款行高基准 */
  font-size: 12px;
  color: var(--fs-ink-700);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hist-item__m {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 5px;
  min-width: 0;
}
.hist-item__time {
  font-family: var(--fs-font-mono);
  font-size: 10px;
  color: var(--fs-ink-400);
  white-space: nowrap; /* 年月日+时间 单行等宽，不折行 */
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.hist-item__model {
  height: 16px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-accent-soft);
  color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  font-size: 10px;
  letter-spacing: 0.02em;
  max-width: 104px;
  overflow: hidden;
  white-space: nowrap; /* 模型名单行省略，不再折行 */
  text-overflow: ellipsis;
  flex-shrink: 1;
  min-width: 0;
}
.hist-item__model.is-plain {
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-400);
}
.hist-item__sp { flex: 1; }
.hist-item__hit {
  font-size: 10px;
  color: var(--fs-ink-400);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.hist-item__hit.ok { color: var(--fs-success); }
.kd__del--sm { width: 18px; height: 18px; }
.kd__del:active { transform: scale(0.9); }

/* 空态 */
.kd__empty {
  padding: 14px 10px;
  text-align: center;
  font-size: 11px;
  line-height: 1.6;
  color: var(--fs-ink-400);
  border: 1px dashed var(--fs-hairline);
  border-radius: var(--fs-r-sm, 6px);
}
.kd__empty-h { font-size: 10px; opacity: 0.8; }

/* ===== 翻页器（el-pagination small，与 Agent 中心历史/报告中心左栏同款） ===== */
/* 翻页器：margin-top:auto 沉底（与报告中心左栏同款）——
   条目不足一页时钉在栏底不跟着上跳；空间吃紧时 auto 边距自动归零，不会挤压列表 */
.kd__pager {
  flex-shrink: 0;
  margin-top: auto;
  padding: 2px 0 0;
  display: flex;
  justify-content: center;
}
.kd__pager :deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--fs-ink-500);
  --el-pagination-button-color: var(--fs-ink-500);
  --el-pagination-button-disabled-color: var(--fs-ink-400);
  --el-pagination-hover-color: var(--fs-accent);
  --el-pagination-font-size: 12px;
  font-family: var(--fs-font-mono);
}
.kd__pager :deep(.el-pager li) {
  min-width: 24px;
  height: 24px;
  border-radius: var(--fs-r-xs, 3px);
  background: transparent;
}
.kd__pager :deep(.el-pager li.is-active) {
  color: var(--fs-accent);
  background: var(--fs-accent-soft);
}
.kd__pager :deep(.el-pagination .btn-prev),
.kd__pager :deep(.el-pagination .btn-next) {
  background: transparent;
}

/* ===== 动效闸门：关闭时循环进度条落静态、悬停位移与读数条归零 ===== */
html[data-motion-allowed="false"] .kd__progress-bar.indeterminate i { animation: none; }
html[data-motion-allowed="false"] .kb-doc:hover,
html[data-motion-allowed="false"] .hist-item:hover,
html[data-motion-allowed="false"] .hist-item:active,
html[data-motion-allowed="false"] .kd__del:active,
html[data-motion-allowed="false"] .kd-drop:hover svg { transform: none; }
html[data-motion-allowed="false"] .kb-doc:hover::before,
html[data-motion-allowed="false"] .hist-item:hover::before { transform: scaleY(0); }

@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .kd__progress-bar.indeterminate i { animation: none; }
  html:not([data-motion="on"]) .kb-doc:hover,
  html:not([data-motion="on"]) .hist-item:hover,
  html:not([data-motion="on"]) .hist-item:active,
  html:not([data-motion="on"]) .kd__del:active,
  html:not([data-motion="on"]) .kd-drop:hover svg { transform: none; }
  html:not([data-motion="on"]) .kb-doc:hover::before,
  html:not([data-motion="on"]) .hist-item:hover::before { transform: scaleY(0); }
}
</style>
