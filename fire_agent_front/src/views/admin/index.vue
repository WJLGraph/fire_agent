<script setup>
/**
 * 系统管理页 — 外壳与编排
 *
 * 阶段 4：原单文件 2,046 行按 Tab 边界拆分为 6 个子组件，本文件退化为「外壳 + 编排」：
 *   - Tab 导航
 *   - 跨 Tab 共享的数据与动作（status / config / logs / configForm / agentForm）
 *   - 子组件的挂载与事件编排
 *
 * ★ 行为等价要点：
 *   - configForm / agentForm 是父持有的 reactive 对象，以 prop 形式传给「模型接入」/「Agent 参数」，
 *     子组件读写其属性（非整体替换），与原单文件共享同一份状态完全一致。
 *   - 原 v-if / v-else-if 的 Tab 切换语义保留：切换即销毁/重建子组件，与原先一致。
 *   - 日志 30 秒轮询、初始化拉取顺序、用户管理 Tab 点击时才拉取（首挂载即拉）均保持原行为。
 */
import BackHomeButton from '@/components/base/BackHomeButton.vue'
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  fetchStatus as fetchStatusApi,
  fetchConfig as fetchConfigApi,
  fetchLogs as fetchLogsApi,
} from '@/api/admin'
import AdminOverview from './AdminOverview.vue'
import AdminDatasource from './AdminDatasource.vue'
import AdminModel from './AdminModel.vue'
import AdminAgent from './AdminAgent.vue'
import AdminLogs from './AdminLogs.vue'
import AdminUsers from './AdminUsers.vue'

const auth = useAuthStore()

// ====== 状态 ======
const activeTab = ref('overview')
const status = ref(null)
const config = ref(null)
const logs = ref([])
const loadingStatus = ref(false)
const loadingLogs = ref(false)

// ====== 可编辑配置表单（与「模型接入」Tab 共用同一份 reactive） ======
const configForm = reactive({
  active_provider: 'aliyun',
  // 阿里云
  llm_api_key: '',
  llm_api_base: '',
  llm_model: '',
  embedding_model: '',
  // 视觉 / 语音模型
  vision_provider: 'aliyun',
  vision_model: '',
  asr_model: '',
  tts_provider: 'aliyun',
  tts_model: '',
  // 文档识别 OCR（AMD 接入）
  ocr_provider: 'local',
  ocr_model: 'MinerU2.5-Pro',
  // AMD GPU Cloud
  amd_api_key: '',
  amd_api_base: 'https://developer.amd.com.cn/radeon/v1',
  amd_model: 'DeepSeek-V4-Flash',
  qwen3_8_flash_start: '',
  qwen3_8_flash_end: '',
  // 本地 Ollama（无需 API Key）
  ollama_api_base: 'http://localhost:11434/v1',
  ollama_model: 'qwen2.5:7b',
  longcat_api_key: '',
  longcat_api_base: 'https://api.longcat.chat/openai',
  longcat_model: 'LongCat-2.5-Preview',
  // 知识库
  kb_chunk_size: 500,
  kb_chunk_overlap: 50,
  kb_top_k: 5,
})

// ====== Agent 参数表单（与「Agent 参数」Tab 共用同一份 reactive） ======
const agentForm = reactive({
  orchestrator_temperature: 0.2,
  report_temperature: 0.4,
  max_agents: 5,
})

// ====== 拉取系统状态 ======
const fetchStatus = async () => {
  loadingStatus.value = true
  try {
    const json = await fetchStatusApi()
    if (json.code === 200) status.value = json.data
  } catch {
    ElMessage.error('获取系统状态失败')
  } finally {
    loadingStatus.value = false
  }
}

// ====== 拉取配置（回填 configForm / agentForm） ======
const fetchConfig = async () => {
  try {
    const json = await fetchConfigApi()
    if (json.code === 200) {
      config.value = json.data
      const m = json.data.model || {}
      Object.assign(configForm, {
        active_provider: m.active_provider || 'aliyun',
        // 阿里云
        llm_api_base: m.llm_api_base || '',
        llm_model: m.llm_model || '',
        embedding_model: m.embedding_model || '',
        vision_provider: m.vision_provider || 'aliyun',
        vision_model: m.vision_model || '',
        asr_model: m.asr_model || '',
        tts_provider: m.tts_provider || 'aliyun',
        tts_model: m.tts_model || '',
        ocr_provider: m.ocr_provider || 'local',
        ocr_model: m.ocr_model || 'MinerU2.5-Pro',
        // AMD
        amd_api_base: m.amd_api_base || 'https://developer.amd.com.cn/radeon/v1',
        amd_model: m.amd_model || 'DeepSeek-V4-Flash',
        qwen3_8_flash_start: m.qwen3_8_flash_start || '',
        qwen3_8_flash_end: m.qwen3_8_flash_end || '',
        // Ollama
        ollama_api_base: m.ollama_api_base || 'http://localhost:11434/v1',
        ollama_model: m.ollama_model || 'qwen2.5:7b',
        // longcat_api_key 不回填（后端返回的是脱敏值，回填后再保存会把掩码当真实密钥写回）
        longcat_api_base: m.longcat_api_base || 'https://api.longcat.chat/openai',
        longcat_model: m.longcat_model || 'LongCat-2.5-Preview',
        // 知识库
        kb_chunk_size: json.data.rag?.kb_chunk_size || 500,
        kb_chunk_overlap: json.data.rag?.kb_chunk_overlap || 50,
        kb_top_k: json.data.rag?.kb_top_k || 5,
      })
      Object.assign(agentForm, json.data.agent || {})
    }
  } catch {
    ElMessage.error('获取配置失败')
  }
}

// ====== 拉取日志 ======
const fetchLogs = async () => {
  loadingLogs.value = true
  try {
    const json = await fetchLogsApi()
    if (json.code === 200) logs.value = json.data
  } catch {
    ElMessage.error('获取日志失败')
  } finally {
    loadingLogs.value = false
  }
}

// ====== 用户管理 Tab 引用（重复点击 Tab 时复用原「点击即刷新」行为） ======
const adminUsersRef = ref(null)

// ====== 初始化 ======
let logsTimer = null
onMounted(() => {
  fetchStatus()
  fetchConfig()
  fetchLogs()
  // 管理员才拉取用户列表
  if (auth.user?.role === 'admin') {
    activeTab.value = 'overview'
  }
  // 每 30 秒刷新日志
  logsTimer = setInterval(fetchLogs, 30000)
})
onUnmounted(() => {
  if (logsTimer) clearInterval(logsTimer)
})
</script>

<template>
  <div class="admin-shell">
    <!-- v0 page-head（64px 单行：标题 + 副题 + 右侧状态徽标） -->
    <header class="page-head">
      <div class="page-head__t">
        <h1 class="page-head__h1">系统管理</h1>
        <p class="page-head__sub">系统总览 · 用户 · 模型接入 · 数据源 · Agent 参数 · 运行日志</p>
      </div>
      <BackHomeButton />
      <div class="page-head__sp"></div>
      <div class="page-head__ops">
        <span class="badge badge--muted mono">ROLE · {{ (auth.user?.role || 'USER').toUpperCase() }}</span>
        <span v-if="status" class="badge">
          <i class="badge__dot" :style="{ background: status.llm_available ? 'var(--fs-success)' : 'var(--fs-danger)' }"></i>
          {{ status.llm_available ? '模型服务正常' : '模型服务异常' }}
        </span>
        <span v-if="status" class="badge badge--muted mono">v{{ status.version }}</span>
      </div>
    </header>

    <!-- v0 sq-main + col-scroll：内容列 980px 居中，atabs 随内容滚动 -->
    <div class="sq-main">
      <div class="col-scroll" :class="{ 'col-scroll--fit': activeTab === 'overview' || activeTab === 'logs' }">
        <div class="atabs anim" style="--d:40ms">
          <button class="atabs__i" :class="{ 'is-on': activeTab === 'overview' }" @click="activeTab = 'overview'">系统总览</button>
          <button v-if="auth.user?.role === 'admin'" class="atabs__i" :class="{ 'is-on': activeTab === 'users' }" @click="activeTab = 'users'; adminUsersRef?.fetchUsers()">用户管理</button>
          <button class="atabs__i" :class="{ 'is-on': activeTab === 'model' }" @click="activeTab = 'model'">模型接入</button>
          <button class="atabs__i" :class="{ 'is-on': activeTab === 'datasource' }" @click="activeTab = 'datasource'">数据源</button>
          <button class="atabs__i" :class="{ 'is-on': activeTab === 'agent' }" @click="activeTab = 'agent'">Agent 参数</button>
          <button class="atabs__i" :class="{ 'is-on': activeTab === 'logs' }" @click="activeTab = 'logs'">运行日志</button>
        </div>

      <!-- ====== Tab 内容（各 Tab 已拆分为独立组件） ====== -->
      <AdminOverview
        v-if="activeTab === 'overview'"
        :status="status"
        :loading-status="loadingStatus"
      />
      <AdminDatasource
        v-else-if="activeTab === 'datasource'"
        :config="config"
        @refresh-status="fetchStatus"
      />
      <AdminModel
        v-else-if="activeTab === 'model'"
        :config-form="configForm"
        @refresh-status="fetchStatus"
        @refresh-config="fetchConfig"
      />
      <AdminAgent
        v-else-if="activeTab === 'agent'"
        :agent-form="agentForm"
        @refresh-config="fetchConfig"
      />
      <AdminLogs
        v-else-if="activeTab === 'logs'"
        :logs="logs"
        :loading-logs="loadingLogs"
        @refresh="fetchLogs"
      />
      <AdminUsers
        v-else-if="activeTab === 'users'"
        ref="adminUsersRef"
        @refresh-logs="fetchLogs"
      />
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-canvas);
  /* 指挥台网格底纹（hairline 级，随亮暗主题取色） */
  background-image:
    linear-gradient(rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--fs-ink-900-rgb), 0.025) 1px, transparent 1px);
  background-size: 48px 48px;
  color: var(--fs-ink-900);
  overflow: hidden;
}

/* ===== v0 page-head（64px 单行） ===== */
.page-head {
  flex-shrink: 0;
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  border-bottom: 1px solid var(--fs-hairline);
}
.page-head__t { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.page-head__h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.15;
  color: var(--fs-ink-900);
}
.page-head__sub {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.page-head__sp { flex: 1; }
.page-head__ops { display: flex; align-items: center; gap: 8px; }

/* ===== 徽标（v0 badge 同构） ===== */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 11px;
  font-weight: 500;
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-700);
  white-space: nowrap;
}
.badge--muted { color: var(--fs-ink-500); }
.badge__dot { width: 6px; height: 6px; border-radius: 999px; background: currentColor; }
.mono {
  font-family: var(--fs-font-mono);
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
}

/* ===== v0 sq-main + col-scroll（内容列 980px 居中） ===== */
.sq-main {
  flex: 1;
  min-width: 0;
  min-height: 0; /* 关键：允许收缩，否则 col-scroll 撑开整列被外壳裁剪，页面滚不动 */
  display: flex;
  flex-direction: column;
  background: var(--fs-bg-canvas);
}
.col-scroll {
  flex: 1;
  min-height: 0;
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
  overflow-y: auto;
  padding: 20px 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scrollbar-width: thin;
  scrollbar-color: var(--fs-hairline-strong) transparent;
}
/* 关键：纵向滚动容器内所有直接子项禁止 flex 压缩。
   否则 overflow:hidden 的卡片（自动最小高度=0）会被压矮，内容被卡片底边裁掉且页面滚不动 */
.col-scroll > * { flex-shrink: 0; }
/* 系统总览 / 运行日志 Tab：一屏展示，禁用页面滚动；内容组件填满剩余高度（其余 Tab 保持可滚动不回归） */
.col-scroll--fit {
  overflow: hidden;
  gap: 16px;
  padding-bottom: 20px;
}
.col-scroll--fit > :deep(.ov),
.col-scroll--fit > :deep(.al) {
  flex: 1 1 0;
  min-height: 0;
}
.anim {
  animation: rise 0.4s var(--fs-ease-out) both;
  animation-delay: var(--d, 0ms);
}
@keyframes rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.atabs {
  flex-shrink: 0;
  display: flex;
  gap: 2px;
  padding: 2px;
  width: fit-content;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-md, 10px);
}
.atabs__i {
  height: 28px;
  padding: 0 14px;
  border: none;
  background: transparent;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--fs-ink-500);
  cursor: pointer;
  white-space: nowrap;
  transition:
    color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    box-shadow var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.atabs__i:hover:not(.is-on) {
  color: var(--fs-ink-900);
  background: rgba(var(--fs-ink-900-rgb), 0.05);
}
.atabs__i.is-on {
  background: var(--fs-bg-surface);
  color: var(--fs-ink-900);
  font-weight: 600;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14), var(--fs-e1);
}
/* ==================== V7 入场微动效 ====================
   Tab 切换 120ms 交叉淡入（v-if 重建时重放；内容不位移）；卡片错峰由各子视图 .a-rise/.stagger 承担 */
.col-scroll > * { animation: tab-in 0.12s ease both; }
@keyframes tab-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
html[data-motion-allowed="false"] .anim,
html[data-motion-allowed="false"] .col-scroll > * {
  animation: none;
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .anim,
  html:not([data-motion="on"]) .col-scroll > * {
    animation: none;
  }
}
</style>
