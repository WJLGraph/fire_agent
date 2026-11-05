<script setup>
/**
 * 系统管理 · 模型接入 · AMD GPU Cloud 区块（含 Qwen3.8-Flash 时间窗口）
 *
 * 阶段 4f：从 AdminModel.vue 按提供商区块拆分。
 * configForm 为父组件传入的 reactive 对象，本组件直接读写其属性（与原单文件实现等价）。
 * 模板 / 类名 / 逻辑逐字迁移，未做任何改写。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { updateConfig, fetchLlmModels } from '@/api/admin'

const props = defineProps({
  configForm: { type: Object, required: true },
})
const emit = defineEmits(['refresh-status', 'save'])

// ====== Qwen3.8 可用性状态 ======
const qwen3_8Status = computed(() => {
  const start = props.configForm.qwen3_8_flash_start
  const end = props.configForm.qwen3_8_flash_end
  if (!start || !end) return { text: '未配置时间窗口（默认可用）', cls: 'gray' }
  try {
    const now = new Date()
    const s = new Date(start.replace(' ', 'T'))
    const e = new Date(end.replace(' ', 'T'))
    if (now >= s && now <= e) return { text: '可用', cls: 'ok' }
    if (now < s) return { text: '尚未到可用时间', cls: 'warn' }
    return { text: '已过期', cls: 'fail' }
  } catch {
    return { text: '时间格式错误', cls: 'fail' }
  }
})

// ====== AMD GPU Cloud 模型列表（动态获取 + 计费层级） ======
const amdModelList = ref(null) // { fetch_ok, available_count, current_model, models, key_info }
const loadingAmdModels = ref(false)
const amdCategory = ref('text') // 分类 Tab：text/vision/speech/ocr

// 能力类型 Tab（与官方 tokenfactory 徽标一致：LLM/VLM/TTS/OCR）
const amdCategoryTabs = [
  { key: 'text', label: '大语言模型' },
  { key: 'vision', label: '视觉模型' },
  { key: 'speech', label: '语音合成' },
  { key: 'ocr', label: '文档识别' },
]
// 四类均已接入系统调用链路，可一键切换：
// text→对话 / vision→视觉识别 / speech→语音播报 / ocr→知识库文档识别
const appliableCategories = ['text', 'vision', 'speech', 'ocr']

// 各能力类型切换后走哪条系统链路的说明（表格「说明」列前缀 / tooltip）
const categoryChainHint = {
  text: '系统对话/报告生成',
  vision: '火情图片识别（多模态可兼作对话）',
  speech: '报告语音播报',
  ocr: '知识库扫描件文档识别',
}

// 当前分类下的 AMD 模型（后端已按 免费优先 排好序）
const filteredAmdModels = computed(() => {
  if (!amdModelList.value) return []
  return amdModelList.value.models.filter(m => m.category === amdCategory.value)
})

// 时间窗口状态徽标 class
const qwenCls = computed(() => ({
  ok: 'amk-bdg--ok',
  warn: 'amk-bdg--warn',
  fail: 'amk-bdg--danger',
  gray: '',
}[qwen3_8Status.value.cls] || ''))

// 当前行高亮（模型列表）
const rowCls = ({ row }) => (row.is_current ? 'is-cur' : '')

// 各分类数量徽标
const amdCategoryCount = (key) => {
  if (!amdModelList.value) return 0
  return amdModelList.value.models.filter(m => m.category === key).length
}

const fetchAmdModels = async () => {
  loadingAmdModels.value = true
  try {
    const json = await fetchLlmModels('amd')
    if (json.code === 200) {
      amdModelList.value = json.data
      if (!json.data.fetch_ok) {
        if (json.data.key_info?.directory_ok) {
          ElMessage.warning('已获取 AMD 官方模型目录，但 /models 校验失败（请检查 API Key），可用性标记仅供参考')
        } else {
          ElMessage.warning('AMD 官方目录与 /models 均拉取失败，请检查网络与 API Key')
        }
      } else {
        ElMessage.success(`已获取 ${json.data.available_count} 个可用模型`)
      }
    } else {
      ElMessage.error('获取 AMD 模型列表失败')
    }
  } catch {
    ElMessage.error('获取 AMD 模型列表失败')
  } finally {
    loadingAmdModels.value = false
  }
}

// AMD 计费层级标签（free=免费 / limited_free=限时免费 / paid=付费专属实例）
const tierTag = (tier) => ({
  free: { text: '免费', type: 'success' },
  limited_free: { text: '限时免费', type: 'warning' },
  paid: { text: '付费', type: 'danger' },
}[tier] || { text: '未知', type: 'info' })

// 一键切换 AMD 模型（写 .env 热生效，无需重启）：
// text→AMD_MODEL；vision→vision_provider='amd'+VISION_MODEL；
// speech→tts_provider='amd'+TTS_MODEL（语音播报走 AMD）；
// ocr→ocr_provider='amd'+OCR_MODEL（知识库扫描件识别走 AMD MinerU）
const applyAmdModel = async (mid, category = 'text') => {
  const chain = categoryChainHint[category] || '系统调用'
  let payload
  if (category === 'vision') {
    payload = { active_provider: 'amd', vision_provider: 'amd', vision_model: mid }
  } else if (category === 'speech') {
    payload = { tts_provider: 'amd', tts_model: mid }
  } else if (category === 'ocr') {
    payload = { ocr_provider: 'amd', ocr_model: mid }
  } else {
    payload = { active_provider: 'amd', amd_model: mid }
  }
  try {
    const json = await updateConfig(payload)
    if (json.code === 200) {
      // 同步本地表单与列表概况，避免下次打开时回显旧值
      const form = props.configForm
      if (category === 'vision') {
        form.vision_provider = 'amd'; form.vision_model = mid
      } else if (category === 'speech') {
        form.tts_provider = 'amd'; form.tts_model = mid
      } else if (category === 'ocr') {
        form.ocr_provider = 'amd'; form.ocr_model = mid
      } else {
        form.amd_model = mid
      }
      if (amdModelList.value?.key_info) {
        const ki = amdModelList.value.key_info
        if (category === 'vision') { ki.vision_provider = 'amd'; ki.vision_model = mid }
        else if (category === 'speech') { ki.tts_provider = 'amd'; ki.tts_model = mid }
        else if (category === 'ocr') { ki.ocr_provider = 'amd'; ki.ocr_model = mid }
        else ki.current_model = mid
      }
      if (amdModelList.value) {
        amdModelList.value.models = amdModelList.value.models.map(m => {
          // 同分类的模型互斥更新"当前"标记
          const sameSlot = m.category === category
          return sameSlot ? { ...m, is_current: m.id === mid } : m
        })
      }
      ElMessage.success(`已切换${chain}模型：${mid}（已写入 .env 并热生效）`)
      emit('refresh-status')
    } else {
      ElMessage.error('切换失败')
    }
  } catch {
    ElMessage.error('切换失败')
  }
}
</script>

<template>
  <!-- 配置卡片 -->
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">AMD GPU Cloud 配置</span>
      <span class="amk-bdg amk-bdg--accent">对话 · 视觉 · 播报 · OCR 四链路</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" title="保存本卡配置到后端 .env 并热生效" @click="$emit('save')">保存配置</button>
      <span class="amk-hd__d amk-mono">RADEON V1</span>
    </div>
    <div class="amk-bd">
      <div class="amk-fgrid">
        <div class="amk-fi">
          <label>AMD API Key</label>
          <el-input v-model="configForm.amd_api_key" type="password" show-password placeholder="rc-..." />
        </div>
        <div class="amk-fi">
          <label>API Base URL</label>
          <el-input v-model="configForm.amd_api_base" placeholder="https://developer.amd.com.cn/radeon/v1" />
        </div>
        <div class="amk-fi">
          <label>当前 AMD 模型</label>
          <el-input v-model="configForm.amd_model" placeholder="DeepSeek-V4-Flash" />
        </div>
        <div class="amk-fi">
          <label>Embedding 模型</label>
          <el-input v-model="configForm.embedding_model" placeholder="text-embedding-v3" />
        </div>
      </div>
    </div>
  </div>

  <!-- AMD 模型列表（动态获取 + 计费层级） -->
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">AMD GPU Cloud 模型列表</span>
      <span v-if="amdModelList" class="amk-bdg amk-bdg--ok">{{ amdModelList.available_count }} 个可用</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" :disabled="loadingAmdModels" @click="fetchAmdModels">
        <el-icon :class="{ 'is-loading': loadingAmdModels }"><Refresh /></el-icon>
        {{ loadingAmdModels ? '获取中…' : '获取模型列表' }}
      </button>
    </div>
    <div class="amk-bd">
      <div class="amk-note">
        实时抓取 AMD 官方 <code>tokenfactory</code> 模型目录（Public Free + Dedicated），
        按<b>免费 / 限时免费 / 付费</b>三类计费标注，并调用 <code>GET /radeon/v1/models</code> 校验 Key 可用性；
        四类能力均已接入系统链路，点击「使用」立即写入 .env 热生效，无需重启。
        <div class="amk-map">
          <span class="amk-map__i"><span class="amk-map__k">大语言</span><span class="amk-map__a">→</span><span class="amk-map__v">系统对话与报告生成</span></span>
          <span class="amk-map__i"><span class="amk-map__k">视觉</span><span class="amk-map__a">→</span><span class="amk-map__v">火情图片识别（VLM 多模态，可兼作对话）</span></span>
          <span class="amk-map__i"><span class="amk-map__k">语音合成</span><span class="amk-map__a">→</span><span class="amk-map__v">报告语音播报</span></span>
          <span class="amk-map__i"><span class="amk-map__k">文档识别（MinerU）</span><span class="amk-map__a">→</span><span class="amk-map__v">知识库扫描件 OCR</span></span>
        </div>
      </div>

      <div
        v-if="amdModelList && !amdModelList.fetch_ok && !amdModelList.key_info?.directory_ok"
        class="amk-note amk-note--warn"
      >
        <b>AMD 官方目录与 /models 接口均拉取失败</b>，请检查网络 / API Key
      </div>

      <template v-if="amdModelList">
        <!-- AMD 分类分段器 -->
        <div class="amk-seg">
          <button
            v-for="tab in amdCategoryTabs"
            :key="tab.key"
            class="amk-seg__i"
            :class="{ 'is-on': amdCategory === tab.key }"
            @click="amdCategory = tab.key"
          >
            {{ tab.label }}
            <span class="amk-seg__n">{{ amdCategoryCount(tab.key) }}</span>
          </button>
        </div>

        <!-- 视觉模型多模态提示：VLM 同时具备文本能力，可直接设为对话模型 -->
        <div v-if="amdCategory === 'vision'" class="amk-note">
          视觉模型均为<b>多模态 VLM</b>：除火情图片识别外，同样具备文本对话与报告生成能力，
          可直接点「设为对话」写入 <code>AMD_MODEL</code>（可与视觉链路的模型相同，一次调用两用）。
        </div>

        <div class="amk-tbl">
          <el-table :data="filteredAmdModels" size="small" max-height="380" :row-class-name="rowCls">
            <el-table-column prop="id" label="模型 ID" min-width="200">
              <template #default="{ row }">
                <span v-if="row.is_current" class="amk-bdg amk-bdg--accent" style="margin-right: 6px">当前</span>
                <span v-if="row.also_text" class="amk-bdg amk-bdg--ok" style="margin-right: 6px" title="多模态 VLM，可兼作对话模型">多模态</span>
                <span class="amk-mono" style="font-size: 11.5px">{{ row.id }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="150" />
            <el-table-column label="计费" width="100" align="center">
              <template #default="{ row }">
                <span
                  class="amk-bdg"
                  :class="{ free: 'amk-bdg--ok', limited_free: 'amk-bdg--warn', paid: 'amk-bdg--danger' }[row.tier] || ''"
                >{{ tierTag(row.tier).text }}</span>
              </template>
            </el-table-column>
            <el-table-column label="校验" width="80" align="center">
              <template #default="{ row }">
                <el-tooltip :content="row.verified ? '已通过 /models 接口校验，当前 Key 可调用' : '未在 /models 返回中（可能需要专属实例部署或已下线）'">
                  <span class="amk-bdg" :class="{ 'amk-bdg--ok': row.verified }">
                    {{ row.verified ? '已验证' : '未验证' }}
                  </span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="desc" label="说明" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span :title="row.capability_label ? `能力类型：${row.capability_label}` : ''">{{ row.desc }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right" align="center">
              <template #default="{ row }">
                <el-tooltip
                  :disabled="true"
                  :content="`切换后${categoryChainHint[row.category] || '系统调用'}立即使用该模型（写 .env 热生效）`"
                  placement="top"
                >
                  <span>
                    <button
                      class="amk-btn amk-btn--primary"
                      :disabled="row.is_current || !appliableCategories.includes(row.category)"
                      @click="applyAmdModel(row.id, row.category)"
                    >
                      {{ row.is_current ? '使用中' : '使用' }}
                    </button>
                  </span>
                </el-tooltip>
                <button
                  v-if="row.also_text"
                  class="amk-btn"
                  style="margin-left: 6px"
                  :disabled="amdModelList?.key_info?.current_model === row.id"
                  title="多模态 VLM：设为系统对话 / 报告生成模型（写 AMD_MODEL 热生效）"
                  @click="applyAmdModel(row.id, 'text')"
                >
                  {{ amdModelList?.key_info?.current_model === row.id ? '对话使用中' : '设为对话' }}
                </button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <div v-else class="amk-empty">
        <span class="amk-empty__t">尚未获取模型列表 · 点击右上角按钮实时抓取官方目录</span>
        <button class="amk-btn" :disabled="loadingAmdModels" @click="fetchAmdModels">立即获取</button>
      </div>
    </div>
  </div>

  <!-- Qwen3.8-Flash 系列时间窗口 -->
  <div v-if="(configForm.amd_model || '').toLowerCase().includes('qwen3.8-flash')" class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">Qwen3.8-Flash-Next 可用时间窗口</span>
      <span class="amk-sp"></span>
      <span class="amk-bdg" :class="qwenCls">{{ qwen3_8Status.text }}</span>
    </div>
    <div class="amk-bd">
      <div class="amk-fgrid">
        <div class="amk-fi">
          <label>起始时间</label>
          <el-input v-model="configForm.qwen3_8_flash_start" placeholder="2026-01-01 00:00:00" />
        </div>
        <div class="amk-fi">
          <label>结束时间</label>
          <el-input v-model="configForm.qwen3_8_flash_end" placeholder="2026-12-31 23:59:59" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 样式全部收敛至 AdminModel.vue 的共享 amk kit（unscoped），本组件无局部样式 */
</style>
