<script setup>
/**
 * 系统管理 · 模型接入 · 阿里云（百炼）区块
 *
 * 阶段 4f：从 AdminModel.vue 按提供商区块拆分。
 * configForm 为父组件传入的 reactive 对象，本组件直接读写其属性（与原单文件实现等价）。
 * 模板 / 类名 / 逻辑逐字迁移，未做任何改写。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { updateConfig, fetchLlmModels, fetchBailianQuota as fetchBailianQuotaApi } from '@/api/admin'

const props = defineProps({
  configForm: { type: Object, required: true },
})
const emit = defineEmits(['refresh-status', 'save'])

// ====== 百炼模型列表 ======
const modelList = ref(null) // { fetch_ok, available_count, current_model, categories, models, key_info }
const loadingModels = ref(false)
const modelCategory = ref('text') // 分类 Tab：text/vision/multimodal/audio/embedding

const categoryTabs = [
  { key: 'text', label: '大语言模型' },
  { key: 'vision', label: '视觉模型' },
  { key: 'multimodal', label: '全模态模型' },
  { key: 'audio', label: '语音模型' },
  { key: 'embedding', label: '向量模型' },
]

// 当前分类下的模型（免费在前、有效期长在前，后端已排好序）
const filteredModels = computed(() => {
  if (!modelList.value) return []
  return modelList.value.models.filter(m => m.category === modelCategory.value)
})

// 各分类数量徽标
const categoryCount = (key) => {
  if (!modelList.value) return 0
  return modelList.value.models.filter(m => m.category === key).length
}

// 模型列表展开/收起（避免占位过大）
const modelListVisible = ref(false)

// 服务端下发的控制台链接只认 https；出现 javascript:/data: 等 scheme 时不绑 href，
// 链接渲染成不可点的文字，避免管理员一次误点就执行脚本。
const safeConsoleHref = (u) => (/^https:\/\/\S+$/i.test(String(u || '')) ? u : undefined)

const fetchFreeModels = async () => {
  loadingModels.value = true
  try {
    const json = await fetchLlmModels('aliyun')
    if (json.code === 200) {
      modelList.value = json.data
      modelListVisible.value = true
      if (!json.data.fetch_ok) {
        if (json.data.key_info?.directory_ok) {
          ElMessage.warning('已解析官方免费额度目录，但 /models 校验失败（请检查 API Key），可用性标记仅供参考')
        } else {
          ElMessage.warning('官方目录与 /models 均拉取失败，展示内置免费额度目录（未经可用性校验）')
        }
      } else {
        ElMessage.success(`已获取 ${json.data.available_count} 个可用模型（免费额度目录 ${json.data.key_info.free_count} 个）`)
      }
    } else {
      ElMessage.error('获取模型列表失败')
    }
  } catch {
    ElMessage.error('获取模型列表失败')
  } finally {
    loadingModels.value = false
  }
}

// 一键切换模型：写 .env 热生效，无需重启
// text→Chat / embedding→Embedding / vision·multimodal→视觉 / audio→ASR·TTS（按 usage）
const applyModel = async (mid, category = 'text', usage = '') => {
  let field, label, extra = null
  if (category === 'embedding') {
    field = 'embedding_model'; label = 'Embedding'
  } else if (category === 'vision' || category === 'multimodal') {
    field = 'vision_model'; label = '视觉识别'
    extra = { vision_provider: 'aliyun' } // 视觉切回百炼
  } else if (category === 'audio') {
    if (usage === 'tts') { field = 'tts_model'; label = '语音合成'; extra = { tts_provider: 'aliyun' } } // TTS 切回百炼（避免 AMD 槽位残留）
    else { field = 'asr_model'; label = '语音识别' }
  } else {
    field = 'llm_model'; label = 'Chat'
  }
  try {
    const json = await updateConfig({ active_provider: 'aliyun', [field]: mid, ...(extra || {}) })
    if (json.code === 200) {
      if (props.configForm[field] !== undefined) props.configForm[field] = mid
      // extra 携带的提供商切换（vision_provider / tts_provider 切回百炼）同步回表单
      if (extra) {
        for (const [k, v] of Object.entries(extra)) {
          if (props.configForm[k] !== undefined) props.configForm[k] = v
        }
      }
      if (modelList.value) {
        modelList.value.models = modelList.value.models.map(m => {
          // 同用途的模型互斥更新"当前"标记
          const sameSlot = (m.category === category) && (m.category !== 'audio' || m.usage === usage)
          return sameSlot ? { ...m, is_current: m.id === mid } : m
        })
        if (modelList.value.key_info) modelList.value.key_info[field] = mid
      }
      ElMessage.success(`已切换${label}模型：${mid}（已写入 .env 并热生效）`)
      emit('refresh-status')
    } else {
      ElMessage.error('切换失败')
    }
  } catch {
    ElMessage.error('切换失败')
  }
}

// ====== 百炼账号免费额度（静态内置快照） ======
const bailianQuota = ref(null) // { ok, rows, counts, total, snapshot_date }
const loadingBailianQuota = ref(false)

// 加载账号免费额度（静态数据，剩余量/过期时间/状态）
const fetchBailianQuota = async () => {
  loadingBailianQuota.value = true
  try {
    const json = await fetchBailianQuotaApi()
    if (json.data?.ok) {
      bailianQuota.value = json.data
      quotaVisible.value = true
      ElMessage.success(`已加载 ${json.data.total} 条账号免费额度（快照 ${json.data.snapshot_date}）`)
    } else {
      bailianQuota.value = json.data || { ok: false, rows: [] }
      ElMessage.warning('加载失败')
    }
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loadingBailianQuota.value = false
  }
}

// 过期时间临近提醒（30 天内标橙）
const isExpiringSoon = (expire) => {
  if (!expire) return false
  const t = new Date(expire.replace(/-/g, '/')).getTime()
  if (Number.isNaN(t)) return false
  return t - Date.now() < 30 * 86400 * 1000
}

// ====== 额度快照：展开/收起、分类 Tab、用途映射、按过期时间排序 ======
const quotaVisible = ref(false)
const quotaCategory = ref('all')

const quotaTabs = [
  { key: 'all', label: '全部' },
  { key: 'text', label: '语言模型' },
  { key: 'vision', label: '视觉模型' },
  { key: 'multimodal', label: '全模态' },
  { key: 'audio', label: '语音模型' },
  { key: 'embedding', label: '向量模型' },
]

const quotaTabCount = (key) => {
  if (!bailianQuota.value?.ok) return 0
  return key === 'all'
    ? bailianQuota.value.rows.length
    : bailianQuota.value.rows.filter(r => r.category === key).length
}

// 用途映射：「使用」按钮写入哪个配置槽；null = 系统暂不支持（按钮禁用）
const quotaUsage = (row) => {
  const m = row.model || ''
  if (row.category === 'text') {
    return { field: 'llm_model', usage: 'chat', label: '对话模型' }
  }
  if (row.category === 'embedding') {
    return m.includes('rerank')
      ? null
      : { field: 'embedding_model', usage: 'embedding', label: '向量模型' }
  }
  if (row.category === 'audio') {
    if (/tts|sambert|cosyvoice/i.test(m)) return { field: 'tts_model', usage: 'tts', label: '语音合成 (TTS)' }
    if (/asr|paraformer|fun-asr/i.test(m)) return { field: 'asr_model', usage: 'asr', label: '语音识别 (ASR)' }
  }
  return null
}

// 说明列：用途去向或暂不支持原因
const quotaRemark = (row) => {
  const u = quotaUsage(row)
  if (u) return `点击使用 → 设为${u.label}`
  if (row.category === 'embedding') return '重排序模型，系统暂不支持'
  return '生图 / 视频生成模型，系统暂不支持'
}

// 当前使用标记（与配置槽比对）
const quotaIsCurrent = (row) => {
  const u = quotaUsage(row)
  return !!u && props.configForm[u.field] === row.model
}

// 排序：谁先过期谁在前面（2099 永久额度排最后）
const filteredQuotaRows = computed(() => {
  if (!bailianQuota.value?.ok) return []
  let rows = [...bailianQuota.value.rows]
  if (quotaCategory.value !== 'all') rows = rows.filter(r => r.category === quotaCategory.value)
  const t = (s) => {
    const v = new Date(String(s || '').replace(/-/g, '/')).getTime()
    return Number.isNaN(v) ? 8.64e15 : v
  }
  return rows.sort((a, b) => t(a.expire) - t(b.expire) || a.model.localeCompare(b.model))
})

// 当前行高亮（两张列表共用）
const rowCls = ({ row }) => (row.is_current || quotaIsCurrent(row) ? 'is-cur' : '')
</script>

<template>
  <!-- 配置卡片 -->
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">阿里云（百炼）配置</span>
      <span class="amk-bdg amk-bdg--accent">对话 · 向量 · 视觉 · 语音</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" title="保存本卡配置到后端 .env 并热生效" @click="$emit('save')">保存配置</button>
      <span class="amk-hd__d amk-mono">DASHSCOPE / COMPATIBLE-MODE</span>
    </div>
    <div class="amk-bd">
      <div class="amk-fgrid">
        <div class="amk-fi">
          <label>LLM API Key</label>
          <el-input v-model="configForm.llm_api_key" type="password" show-password placeholder="sk-..." />
        </div>
        <div class="amk-fi">
          <label>API Base URL</label>
          <el-input v-model="configForm.llm_api_base" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
        </div>
        <div class="amk-fi">
          <label>Chat 模型</label>
          <el-input v-model="configForm.llm_model" placeholder="qwen-plus" />
        </div>
        <div class="amk-fi">
          <label>Embedding 模型</label>
          <el-input v-model="configForm.embedding_model" placeholder="text-embedding-v3" />
        </div>
      </div>
    </div>
  </div>

  <!-- 百炼模型列表 -->
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">百炼模型</span>
      <span v-if="modelList" class="amk-bdg amk-bdg--ok">{{ modelList.available_count }} 个可用</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" :disabled="loadingModels" @click="fetchFreeModels">
        <el-icon :class="{ 'is-loading': loadingModels }"><Refresh /></el-icon>
        {{ loadingModels ? '获取中…' : '获取模型列表' }}
      </button>
      <button v-if="modelList" class="amk-btn" @click="modelListVisible = !modelListVisible">
        {{ modelListVisible ? '收起' : '展开' }}
      </button>
    </div>
    <div class="amk-bd">
      <div class="amk-note">
        根据已保存的阿里云密钥调用百炼 <code>GET /compatible-mode/v1/models</code> 获取真实可用模型，
        同时实时解析官方计费文档的免费额度目录（官方新增 / 调整自动跟随），
        按<b>大语言 / 视觉 / 全模态 / 语音 / 向量</b>五大类展示；点击「使用」立即切换并热生效，无需重启。
      </div>

      <template v-if="modelListVisible && modelList">
        <!-- 密钥使用概况 -->
        <div v-if="modelList.key_info" class="key-info">
          <div class="key-info__row">
            <div class="ki-item">
              <span class="ki-label">提供商</span>
              <span class="ki-value">{{ modelList.key_info.provider_name }}</span>
            </div>
            <div class="ki-item">
              <span class="ki-label">API Key</span>
              <span class="ki-value amk-mono">{{ modelList.key_info.api_key_configured ? modelList.key_info.api_key_masked : '未配置' }}</span>
            </div>
            <div class="ki-item">
              <span class="ki-label">Chat 模型</span>
              <span class="ki-value amk-mono">{{ modelList.current_model || '-' }}</span>
            </div>
            <div class="ki-item">
              <span class="ki-label">Embedding</span>
              <span class="ki-value amk-mono">{{ modelList.key_info.embedding_model || '-' }}</span>
            </div>
            <div class="ki-item">
              <span class="ki-label">视觉识别</span>
              <span class="ki-value amk-mono">{{ modelList.key_info.vision_model || '-' }}（{{ modelList.key_info.vision_provider === 'amd' ? 'AMD' : '百炼' }}）</span>
            </div>
            <div class="ki-item">
              <span class="ki-label">语音识别 / 合成</span>
              <span class="ki-value amk-mono">{{ modelList.key_info.asr_model || '-' }} / {{ modelList.key_info.tts_model || '-' }}</span>
            </div>
            <div class="ki-item">
              <span class="ki-label">可用模型</span>
              <span class="ki-value">{{ modelList.available_count }} 个（免费额度 {{ modelList.key_info.free_count }}）</span>
            </div>
          </div>
          <div class="key-info__links">
            <span class="ki-note">{{ modelList.key_info.quota_note }}</span>
            <div class="ki-btns">
              <a class="amk-btn" :href="safeConsoleHref(modelList.key_info.console_urls.usage)" target="_blank" rel="noopener">用量与额度明细</a>
              <a class="amk-btn amk-btn--primary" :href="safeConsoleHref(modelList.key_info.console_urls.aliyun_benefit)" target="_blank" rel="noopener">我的高校权益</a>
            </div>
          </div>
        </div>

        <div
          v-if="!modelList.fetch_ok && !modelList.key_info?.directory_ok"
          class="amk-note amk-note--warn"
        >
          <b>官方目录与 /models 接口均拉取失败</b>，下表为内置免费额度目录（未经可用性校验）
        </div>

        <!-- 分类分段器 -->
        <div class="amk-seg">
          <button
            v-for="tab in categoryTabs"
            :key="tab.key"
            class="amk-seg__i"
            :class="{ 'is-on': modelCategory === tab.key }"
            @click="modelCategory = tab.key"
          >
            {{ tab.label }}
            <span class="amk-seg__n">{{ categoryCount(tab.key) }}</span>
          </button>
        </div>

        <div class="amk-tbl">
          <el-table :data="filteredModels" size="small" max-height="380" :row-class-name="rowCls">
            <el-table-column prop="id" label="模型 ID" min-width="160">
              <template #default="{ row }">
                <span v-if="row.is_current" class="amk-bdg amk-bdg--accent" style="margin-right: 6px">当前</span>
                <span class="amk-mono" style="font-size: 11.5px">{{ row.id }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="130" />
            <el-table-column label="免费额度" width="110" align="center">
              <template #default="{ row }">
                <span v-if="row.is_free" class="amk-bdg amk-bdg--warn">{{ row.free_quota }}</span>
                <span v-else class="ki-dim">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="validity" label="有效期" width="100" align="center" />
            <el-table-column label="校验" width="80" align="center">
              <template #default="{ row }">
                <el-tooltip :content="row.verified ? '已通过 /models 接口校验，当前 Key 可调用' : '未在 /models 返回中（可能下线或 Key 无权限）'">
                  <span class="amk-bdg" :class="{ 'amk-bdg--ok': row.verified }">
                    {{ row.verified ? '已验证' : '未验证' }}
                  </span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="desc" label="说明" min-width="170" show-overflow-tooltip />
            <el-table-column label="操作" width="90" fixed="right" align="center">
              <template #default="{ row }">
                <button
                  class="amk-btn amk-btn--primary"
                  :disabled="row.is_current"
                  @click="applyModel(row.id, row.category, row.usage)"
                >
                  {{ row.is_current ? '使用中' : '使用' }}
                </button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <div v-else-if="modelList" class="amk-empty">
        <span class="amk-empty__t">目录已收起 · 点击「展开」查看已获取的模型列表</span>
      </div>

      <div v-else class="amk-empty">
        <span class="amk-empty__t">尚未获取模型列表 · 点击右上角按钮拉取百炼真实可用模型</span>
        <button class="amk-btn" :disabled="loadingModels" @click="fetchFreeModels">立即获取</button>
      </div>
    </div>
  </div>

  <!-- 百炼账号免费额度（静态内置快照） -->
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">账号免费额度（控制台快照）</span>
      <span v-if="bailianQuota && bailianQuota.ok" class="amk-bdg">{{ bailianQuota.total }} 条</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" :disabled="loadingBailianQuota" @click="fetchBailianQuota">
        <el-icon :class="{ 'is-loading': loadingBailianQuota }"><Refresh /></el-icon>
        {{ bailianQuota ? '刷新额度' : '加载额度' }}
      </button>
      <button v-if="bailianQuota && bailianQuota.ok" class="amk-btn" @click="quotaVisible = !quotaVisible">
        {{ quotaVisible ? '收起' : '展开' }}
      </button>
    </div>
    <div class="amk-bd">
      <div class="amk-note">
        <template v-if="bailianQuota && bailianQuota.ok">
          语言 {{ bailianQuota.counts.text }} · 视觉 {{ bailianQuota.counts.vision }} ·
          全模态 {{ bailianQuota.counts.multimodal }} · 向量 {{ bailianQuota.counts.embedding }} ·
          语音 {{ bailianQuota.counts.audio }}，共 {{ bailianQuota.total }} 条（快照 {{ bailianQuota.snapshot_date }}）。
        </template>
        「剩余量 / 过期时间 / 状态」为阿里云账号级数据（控制台无公开 API），已内置为静态快照；
        表格<b>按过期时间升序</b>（谁先过期谁在前面，2099 永久额度排最后）；
        「使用」可将模型设为对应用途并写入 .env 热生效；生图 / 视频生成、重排序类暂不支持，按钮置灰。
      </div>

      <template v-if="quotaVisible && bailianQuota && bailianQuota.ok">
        <!-- 分类分段器 -->
        <div class="amk-seg">
          <button
            v-for="tab in quotaTabs"
            :key="tab.key"
            class="amk-seg__i"
            :class="{ 'is-on': quotaCategory === tab.key }"
            @click="quotaCategory = tab.key"
          >
            {{ tab.label }}
            <span class="amk-seg__n">{{ quotaTabCount(tab.key) }}</span>
          </button>
        </div>

        <div class="amk-tbl">
          <el-table :data="filteredQuotaRows" size="small" max-height="380" :row-class-name="rowCls">
            <el-table-column prop="model" label="模型 Code" min-width="210" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="quotaIsCurrent(row)" class="amk-bdg amk-bdg--accent" style="margin-right: 6px">当前</span>
                <span class="amk-mono" style="font-size: 11.5px">{{ row.model }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="category" label="类别" width="100" align="center">
              <template #default="{ row }">
                <span
                  class="amk-bdg"
                  :class="{ text: 'amk-bdg--accent', vision: 'amk-bdg--warn', multimodal: 'amk-bdg--ok', embedding: 'amk-bdg--danger', audio: '' }[row.category] || ''"
                >
                  {{ { text: '语言', vision: '视觉', multimodal: '全模态', embedding: '向量', audio: '语音' }[row.category] }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="quota" label="免费额度剩余量" min-width="170" align="center">
              <template #default="{ row }">
                <span class="amk-mono" style="font-size: 11.5px">{{ row.quota }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="expire" label="过期时间" width="120" align="center">
              <template #default="{ row }">
                <span class="amk-mono" :class="{ 'ki-expiring': isExpiringSoon(row.expire) }" style="font-size: 11.5px">
                  {{ row.expire }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90" align="center">
              <template #default="{ row }">
                <span class="amk-bdg" :class="row.status && row.status.includes('过期') ? '' : 'amk-bdg--ok'">
                  {{ row.status || '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">
                <span style="font-size: 12px; color: var(--fs-ink-500)">{{ quotaRemark(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right" align="center">
              <template #default="{ row }">
                <el-tooltip
                  :disabled="!!quotaUsage(row)"
                  content="该模型类型系统暂不支持（生图/视频/重排序），无法设为当前使用"
                  placement="top"
                >
                  <span>
                    <button
                      class="amk-btn amk-btn--primary"
                      :disabled="!quotaUsage(row) || quotaIsCurrent(row)"
                      @click="applyModel(row.model, row.category, quotaUsage(row)?.usage || '')"
                    >
                      {{ quotaIsCurrent(row) ? '使用中' : '使用' }}
                    </button>
                  </span>
                </el-tooltip>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* ---- 密钥使用概况（sunken 内嵌面板） ---- */
.key-info {
  padding: 12px 14px;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-sm, 6px);
  animation: ki-in 0.4s var(--fs-ease-out) both;
}
@keyframes ki-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.key-info__row { display: flex; flex-wrap: wrap; gap: 10px 26px; }
.ki-item { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.ki-label {
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--fs-ink-500);
  transition: color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.ki-item:hover .ki-label { color: var(--fs-ink-700); }
.ki-value {
  font-size: 12px;
  color: var(--fs-ink-900);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  user-select: all; /* 掩码 Key 与模型名整段选中，一次复制不必手动圈选 */
}
.ki-dim { color: var(--fs-ink-400); }
.ki-expiring {
  color: var(--fs-warning);
  font-weight: 700;
  letter-spacing: 0.02em;
}
.key-info__links {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--fs-hairline);
  flex-wrap: wrap;
}
.ki-note { font-size: 11px; line-height: 1.6; letter-spacing: 0.01em; color: var(--fs-ink-500); flex: 1; min-width: 260px; }
.ki-btns { display: flex; gap: 8px; }
html[data-motion-allowed="false"] .key-info { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .key-info { animation: none; }
}
</style>
