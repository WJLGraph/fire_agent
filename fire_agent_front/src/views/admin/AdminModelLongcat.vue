<script setup>
/**
 * 系统管理 · 模型接入 · LongCat 区块（官方静态目录 + /models 校验，仅 LLM）
 *
 * 阶段 4f：从 AdminModel.vue 按提供商区块拆分。
 * configForm 为父组件传入的 reactive 对象，本组件直接读写其属性（与原单文件实现等价）。
 * 展示层走 AdminModel.vue 注入的共享 amk kit（v0 卡片 / 发丝输入 / sunken 注脚）。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { updateConfig, fetchLlmModels } from '@/api/admin'

const props = defineProps({
  configForm: { type: Object, required: true },
})
const emit = defineEmits(['refresh-status', 'save'])

// ====== LongCat 模型列表（官方静态目录，仅 LLM） ======
const longcatModelList = ref(null) // { fetch_ok, available_count, current_model, models, key_info }
const loadingLongcatModels = ref(false)

const fetchLongcatModels = async () => {
  loadingLongcatModels.value = true
  try {
    const json = await fetchLlmModels('longcat')
    if (json.code === 200) {
      longcatModelList.value = json.data
      if (!json.data.fetch_ok) {
        ElMessage.warning('已获取 LongCat 官方目录，但 /models 校验失败（请检查 API Key），可用性标记仅供参考')
      } else {
        ElMessage.success(`已获取 ${json.data.available_count} 个可用模型`)
      }
    } else {
      ElMessage.error('获取 LongCat 模型列表失败')
    }
  } catch {
    ElMessage.error('获取 LongCat 模型列表失败')
  } finally {
    loadingLongcatModels.value = false
  }
}

// 一键切换 LongCat 模型（仅 Chat 槽位）：写 .env 热生效
const applyLongcatModel = async (mid) => {
  try {
    const json = await updateConfig({ active_provider: 'longcat', longcat_model: mid })
    if (json.code === 200) {
      props.configForm.longcat_model = mid
      if (longcatModelList.value) {
        longcatModelList.value.models = longcatModelList.value.models.map(m => ({
          ...m, is_current: m.id === mid,
        }))
        if (longcatModelList.value.key_info) longcatModelList.value.key_info.current_model = mid
      }
      ElMessage.success(`已切换 Chat 模型：${mid}（已写入 .env 并热生效）`)
      emit('refresh-status')
    } else {
      ElMessage.error('切换失败')
    }
  } catch {
    ElMessage.error('切换失败')
  }
}

// 当前行高亮
const rowCls = ({ row }) => (row.is_current ? 'is-cur' : '')
</script>

<template>
  <!-- 配置卡片 -->
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">LongCat 配置</span>
      <span class="amk-bdg amk-bdg--accent">仅 LLM</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" title="保存本卡配置到后端 .env 并热生效" @click="$emit('save')">保存配置</button>
      <span class="amk-hd__d">Embedding 始终走阿里百炼，不受切换影响</span>
    </div>
    <div class="amk-bd">
      <div class="amk-fgrid">
        <div class="amk-fi">
          <label>LongCat API Key</label>
          <el-input v-model="configForm.longcat_api_key" type="password" show-password placeholder="ak-..." />
        </div>
        <div class="amk-fi">
          <label>API Base URL</label>
          <el-input v-model="configForm.longcat_api_base" placeholder="https://api.longcat.chat/openai" />
        </div>
        <div class="amk-fi">
          <label>Chat 模型</label>
          <el-input v-model="configForm.longcat_model" placeholder="LongCat-2.5-Preview" />
        </div>
      </div>
    </div>
  </div>

  <!-- LongCat 模型列表（官方目录 + /models 校验） -->
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">LongCat 模型列表</span>
      <span v-if="longcatModelList" class="amk-bdg amk-bdg--ok">{{ longcatModelList.available_count }} 个可用</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" :disabled="loadingLongcatModels" @click="fetchLongcatModels">
        <el-icon :class="{ 'is-loading': loadingLongcatModels }"><Refresh /></el-icon>
        {{ loadingLongcatModels ? '获取中…' : '获取模型列表' }}
      </button>
    </div>
    <div class="amk-bd">
      <div class="amk-note">
        调用 LongCat OpenAI 兼容 <code>GET /models</code> 校验当前 Key 可用性，
        按官方文档目录（<a href="https://longcat.chat/platform/docs/zh/" target="_blank">longcat.chat/platform/docs</a>）展示；
        点击「使用」立即切换并热生效，无需重启。LongCat 仅提供对话（LLM）模型，Embedding 不受切换影响。
      </div>

      <div v-if="longcatModelList && !longcatModelList.fetch_ok" class="amk-note amk-note--warn">
        <b>LongCat /models 接口校验失败</b>（请检查网络 / API Key），目录仅供展示
      </div>

      <template v-if="longcatModelList">
        <div class="amk-tbl">
          <el-table :data="longcatModelList.models" size="small" max-height="300" :row-class-name="rowCls">
            <el-table-column prop="id" label="模型 ID" min-width="200">
              <template #default="{ row }">
                <span v-if="row.is_current" class="amk-bdg amk-bdg--accent" style="margin-right: 6px">当前</span>
                <span class="amk-mono" style="font-size: 11.5px">{{ row.id }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="150" />
            <el-table-column label="校验" width="80" align="center">
              <template #default="{ row }">
                <el-tooltip :content="row.verified ? '已通过 /models 接口校验，当前 Key 可调用' : '未在 /models 返回中（可能已下线）'">
                  <span class="amk-bdg" :class="{ 'amk-bdg--ok': row.verified }">
                    {{ row.verified ? '已验证' : '未验证' }}
                  </span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="desc" label="说明" min-width="220" show-overflow-tooltip />
            <el-table-column label="操作" width="90" fixed="right" align="center">
              <template #default="{ row }">
                <button
                  class="amk-btn amk-btn--primary"
                  :disabled="row.is_current"
                  @click="applyLongcatModel(row.id)"
                >
                  {{ row.is_current ? '使用中' : '使用' }}
                </button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <div v-else class="amk-empty">
        <span class="amk-empty__t">尚未获取模型列表 · 点击右上角按钮拉取官方目录</span>
        <button class="amk-btn" :disabled="loadingLongcatModels" @click="fetchLongcatModels">立即获取</button>
      </div>
    </div>
  </div>
</template>
