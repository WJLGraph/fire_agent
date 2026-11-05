<script setup>
/**
 * 系统管理 · 模型接入 Tab
 *
 * 阶段 4f：按「提供商区块」拆分为 4 个子组件（阿里云 / AMD / Ollama / LongCat），
 *          本文件只保留提供商切换、知识库参数、保存与连接测试（跨提供商的公共部分）。
 *
 * configForm 是父组件传入的 reactive 对象：
 *   - 「数据源」Tab 的 config 回填、本 Tab 的模型切换、保存配置均作用于同一份对象；
 *   - 子组件直接读写其属性（非整体替换），与原单文件实现完全等价。
 * 保存 / 切换模型后需要刷新 status 与 config，通过事件上抛给父组件（父持有 fetchStatus / fetchConfig）。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { updateConfig, testLlm as testLlmApi } from '@/api/admin'
import AdminModelAliyun from './AdminModelAliyun.vue'
import AdminModelAmd from './AdminModelAmd.vue'
import AdminModelOllama from './AdminModelOllama.vue'
import AdminModelLongcat from './AdminModelLongcat.vue'

const props = defineProps({
  configForm: { type: Object, required: true },
})

const emit = defineEmits(['refresh-status', 'refresh-config'])

// ====== 保存配置 ======
const saveConfig = async () => {
  const payload = {
    active_provider: props.configForm.active_provider,
    // 阿里云字段
    llm_api_key: props.configForm.llm_api_key.trim() || null,
    llm_api_base: props.configForm.llm_api_base.trim() || null,
    llm_model: props.configForm.llm_model.trim() || null,
    embedding_model: props.configForm.embedding_model.trim() || null,
    // AMD 字段
    amd_api_key: props.configForm.amd_api_key.trim() || null,
    amd_api_base: props.configForm.amd_api_base.trim() || null,
    amd_model: props.configForm.amd_model,
    qwen3_8_flash_start: props.configForm.qwen3_8_flash_start.trim() || null,
    qwen3_8_flash_end: props.configForm.qwen3_8_flash_end.trim() || null,
    // Ollama 字段
    ollama_api_base: props.configForm.ollama_api_base.trim() || null,
    ollama_model: props.configForm.ollama_model.trim() || null,
    longcat_api_key: props.configForm.longcat_api_key.trim() || null,
    longcat_api_base: props.configForm.longcat_api_base.trim() || null,
    longcat_model: props.configForm.longcat_model.trim() || null,
    // 知识库
    kb_chunk_size: Number(props.configForm.kb_chunk_size),
    kb_chunk_overlap: Number(props.configForm.kb_chunk_overlap),
    kb_top_k: Number(props.configForm.kb_top_k),
  }
  try {
    const json = await updateConfig(payload)
    if (json.code === 200) {
      ElMessage.success('模型/知识库配置已保存')
      emit('refresh-config')
      emit('refresh-status')
    } else {
      ElMessage.error('保存失败')
    }
  } catch {
    ElMessage.error('保存失败')
  }
}

// ====== 测试连接 ======
const testLlm = ref(null)
const testing = ref(false)

const testLlmConn = async () => {
  testing.value = true
  testLlm.value = null
  try {
    const res = await testLlmApi()
    const json = await res.json()
    testLlm.value = json.data
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="am">
    <!-- 提供商选择（v0 卡片头 + 分段器） -->
    <div class="amk-card">
      <div class="amk-hd">
        <span class="amk-hd__t">LLM 提供商</span>
        <span class="amk-hd__d">四类能力（对话 / 视觉 / 播报 / OCR）均可独立指定提供商</span>
        <span class="amk-sp"></span>
        <div class="amk-seg">
          <button class="amk-seg__i" :class="{ 'is-on': configForm.active_provider === 'aliyun' }" @click="configForm.active_provider = 'aliyun'">阿里云（百炼）</button>
          <button class="amk-seg__i" :class="{ 'is-on': configForm.active_provider === 'amd' }" @click="configForm.active_provider = 'amd'">AMD GPU Cloud</button>
          <button class="amk-seg__i" :class="{ 'is-on': configForm.active_provider === 'ollama' }" @click="configForm.active_provider = 'ollama'">本地 Ollama</button>
          <button class="amk-seg__i" :class="{ 'is-on': configForm.active_provider === 'longcat' }" @click="configForm.active_provider = 'longcat'">LongCat</button>
        </div>
      </div>
    </div>

    <!-- ===== 各提供商配置（按区块拆分，逻辑与表现不变；@save 直接写回后端 .env） ===== -->
    <AdminModelAliyun
      v-if="configForm.active_provider === 'aliyun'"
      :config-form="configForm"
      @save="saveConfig"
      @refresh-status="emit('refresh-status')"
    />
    <AdminModelAmd
      v-if="configForm.active_provider === 'amd'"
      :config-form="configForm"
      @save="saveConfig"
      @refresh-status="emit('refresh-status')"
    />
    <AdminModelOllama
      v-if="configForm.active_provider === 'ollama'"
      :config-form="configForm"
      @save="saveConfig"
    />
    <AdminModelLongcat
      v-if="configForm.active_provider === 'longcat'"
      :config-form="configForm"
      @save="saveConfig"
      @refresh-status="emit('refresh-status')"
    />

    <!-- 知识库参数（公共 · v0 pf-row 偏好行） -->
    <div class="kb-ans">
      <div class="kb-ans__hd">
        <span class="kb-ans__t">知识库参数</span>
        <span class="sq-panel__sp"></span>
        <button class="vbtn vbtn--ghost" :disabled="testing" @click="testLlmConn">
          测试{{ configForm.active_provider === 'amd' ? ' AMD' : (configForm.active_provider === 'ollama' ? ' Ollama' : (configForm.active_provider === 'longcat' ? ' LongCat' : '')) }}连接
        </button>
        <button class="vbtn vbtn--primary" @click="saveConfig">保存模型配置</button>
      </div>
      <div class="kb-ans__bd" style="padding:0">
        <div class="pf-row">
          <div class="pf-row__b">
            <span class="pf-row__t">切分大小</span>
            <span class="pf-row__d">文档入库时每个分片的目标长度（字符）</span>
          </div>
          <el-input-number v-model="configForm.kb_chunk_size" :min="100" :max="2000" :step="100" size="small" style="width: 120px" />
        </div>
        <div class="pf-row">
          <div class="pf-row__b">
            <span class="pf-row__t">切分重叠</span>
            <span class="pf-row__d">相邻分片的重叠字符数，保证跨片语义连续</span>
          </div>
          <el-input-number v-model="configForm.kb_chunk_overlap" :min="0" :max="200" :step="10" size="small" style="width: 120px" />
        </div>
        <div class="pf-row" style="border-bottom:none">
          <div class="pf-row__b">
            <span class="pf-row__t">Top-K 召回</span>
            <span class="pf-row__d">每次检索召回的知识库片段数</span>
          </div>
          <el-input-number v-model="configForm.kb_top_k" :min="1" :max="20" size="small" style="width: 120px" />
        </div>
      </div>
    </div>

    <!-- 连接测试结果（v0 徽标行） -->
    <div v-if="testLlm" class="am__result" :class="testLlm.ok ? 'ok' : 'fail'">
      <i></i>{{ testLlm.detail }}
    </div>
  </div>
</template>

<style scoped>
.am {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  flex-shrink: 0; /* 禁止纵向压缩（旧 min-height:100% 会触发整列卡片被压矮裁剪） */
}

/* ===== kb-ans 面板（v0 同构） ===== */
.kb-ans {
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
}
.kb-ans__hd {
  min-height: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.kb-ans__t {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--fs-ink-900);
}
.kb-ans__t::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 2px;
  background: var(--fs-accent);
  opacity: 0.7;
}
.kb-ans__bd { display: flex; flex-direction: column; }
.sq-panel__sp { flex: 1; }

/* v0 atabs 分段（提供商选择已迁移至 amk-seg，见下方共享 kit） */

/* v0 btn 同构 */
.vbtn {
  height: 26px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  letter-spacing: 0.01em;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.vbtn:hover:not(:disabled) { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.vbtn--ghost { background: transparent; box-shadow: none; }
.vbtn--ghost:hover:not(:disabled) { background: var(--fs-bg-sunken); box-shadow: none; }
.vbtn--primary {
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-weight: 600;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.vbtn--primary:hover:not(:disabled) {
  background: var(--fs-accent-hover);
  color: var(--fs-on-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
}
.vbtn:disabled { color: var(--fs-ink-400); cursor: not-allowed; }

/* ===== v0 pf-row 偏好行 ===== */
.pf-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.pf-row:hover { background: rgba(var(--fs-ink-900-rgb), 0.02); }
.pf-row__b { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.pf-row__t { font-size: 12px; font-weight: 500; letter-spacing: 0.01em; color: var(--fs-ink-900); }
.pf-row__d { font-size: 11px; line-height: 1.6; color: var(--fs-ink-400); }

/* 连接测试结果 */
.am__result {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  letter-spacing: 0.01em;
  padding: 9px 14px;
  border-radius: var(--fs-r-sm, 6px);
  animation: am-in 0.4s var(--fs-ease-out) both;
}
@keyframes am-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
html[data-motion-allowed="false"] .am__result { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .am__result { animation: none; }
}
.am__result i { width: 6px; height: 6px; border-radius: 50%; flex: none; }
.am__result.ok { color: var(--fs-success); background: color-mix(in srgb, var(--fs-success) 10%, transparent); }
.am__result.ok i { background: var(--fs-success); }
.am__result.fail { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 10%, transparent); }
.am__result.fail i { background: var(--fs-danger); }
</style>

<!-- ===== 模型接入共享 kit（unscoped：供四个提供商子组件复用，全部走 v0 令牌） ===== -->
<style>
/* ---- 卡片 ---- */
.amk-card {
  background: var(--fs-bg-surface);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
  flex-shrink: 0; /* overflow:hidden 的 flex 子项自动最小高度=0，必须禁止压缩，否则内容被裁 */
  min-width: 0;
}
.amk-hd {
  min-height: 42px;
  padding: 5px 14px;
  display: flex;
  align-items: center;
  flex-wrap: wrap; /* 空间不足时换行，不再横向溢出 */
  row-gap: 5px;
  column-gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.amk-hd__t {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--fs-ink-900);
  white-space: nowrap;
  flex: none;
}
.amk-hd__t::before {
  content: '';
  width: 2px;
  height: 11px;
  border-radius: 2px;
  background: var(--fs-accent);
  opacity: 0.7;
}
.amk-hd__d { font-size: 11px; letter-spacing: 0.02em; color: var(--fs-ink-400); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 0 1 auto; min-width: 0; }
.amk-sp { flex: 1; min-width: 4px; }
.amk-bd { padding: 14px; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.amk-mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; }

/* ---- 表单（2 列定栅格 + 发丝输入，替代散排 auto-fit） ---- */
.amk-fgrid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px; }
@media (max-width: 760px) { .amk-fgrid { grid-template-columns: 1fr; } }
.amk-fi { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.amk-fi > label {
  font-size: 11px;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
  transition: color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
/* 字段聚焦时标签升到主文字色，替代「找不到光标在哪」的错位感 */
.amk-fi:focus-within > label { color: var(--fs-ink-900); }
.amk-fi .el-input__wrapper {
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  border-radius: var(--fs-r-sm, 6px);
  padding: 0 10px;
  transition: box-shadow var(--fs-dur-micro) var(--fs-ease), background-color var(--fs-dur-micro) var(--fs-ease);
}
.amk-fi .el-input__wrapper:hover { box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.amk-fi .el-input__wrapper.is-focus { box-shadow: inset 0 0 0 1px var(--fs-accent); }
.amk-fi .el-input__inner {
  height: 30px;
  font-size: 12.5px;
  color: var(--fs-ink-900);
  caret-color: var(--fs-accent);
  font-family: var(--fs-font-mono);
  font-variant-numeric: tabular-nums;
}
.amk-fi .el-input__inner::placeholder { color: var(--fs-ink-400); }
.amk-fi .el-input__suffix { color: var(--fs-ink-400); transition: color var(--fs-dur-micro) var(--fs-ease); }
.amk-fi .el-input__wrapper:hover .el-input__suffix { color: var(--fs-ink-700); }

/* ---- 说明注脚（sunken 底，替代虚线大段文字） ---- */
.amk-note {
  padding: 10px 12px;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-sm, 6px);
  font-size: 11px;
  line-height: 1.75;
  color: var(--fs-ink-500);
}
.amk-note code {
  font-family: var(--fs-font-mono);
  font-size: 10.5px;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  color: var(--fs-accent);
}
.amk-note b { color: var(--fs-ink-700); font-weight: 600; }
.amk-note a { color: var(--fs-accent); transition: color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)); }
.amk-note a:hover { color: var(--fs-accent-hover); }
.amk-note--warn {
  border-left: 2px solid var(--fs-warning);
  background: color-mix(in srgb, var(--fs-warning) 9%, transparent);
  color: var(--fs-warning);
}
.amk-note--warn b { color: var(--fs-warning); }

/* ---- 链路映射 chips（一段文字 → 可扫读的键值对） ---- */
.amk-map { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 9px; }
.amk-map__i {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 20px;
  padding: 0 8px;
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  border-radius: var(--fs-r-xs, 3px);
  font-size: 10.5px;
  color: var(--fs-ink-500);
}
.amk-map__k { color: var(--fs-ink-900); font-weight: 600; }
.amk-map__a { color: var(--fs-ink-400); }
.amk-map__v { color: var(--fs-accent); }

/* ---- 能力分段器（模型分类 Tab，与 v0 atabs 同构） ---- */
.amk-seg {
  display: flex;
  gap: 2px;
  padding: 2px;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-md, 10px);
  width: fit-content;
  max-width: 100%;
  min-width: 0;
  flex: 0 1 auto;
  flex-wrap: wrap;
}
.amk-seg__i {
  height: 24px;
  padding: 0 10px;
  border: none;
  background: transparent;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--fs-ink-500);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  transition:
    color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    box-shadow var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.amk-seg__i:hover:not(.is-on) {
  color: var(--fs-ink-900);
  background: rgba(var(--fs-ink-900-rgb), 0.05);
}
.amk-seg__i.is-on {
  background: var(--fs-bg-surface);
  color: var(--fs-ink-900);
  font-weight: 600;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14), var(--fs-e1);
}
.amk-seg__n { font-size: 10px; font-family: var(--fs-font-mono); font-variant-numeric: tabular-nums; color: var(--fs-ink-400); }
.amk-seg__i.is-on .amk-seg__n { color: var(--fs-accent); }

/* ---- 徽标（v0 badge：18px 方角 sunken 底） ---- */
.amk-bdg {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 18px;
  padding: 0 6px;
  border-radius: var(--fs-r-xs, 3px);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  white-space: nowrap;
}
.amk-bdg--accent { color: var(--fs-accent); background: var(--fs-accent-soft); }
.amk-bdg--ok { color: var(--fs-success); background: color-mix(in srgb, var(--fs-success) 12%, transparent); }
.amk-bdg--warn { color: var(--fs-warning); background: color-mix(in srgb, var(--fs-warning) 14%, transparent); }
.amk-bdg--danger { color: var(--fs-danger); background: color-mix(in srgb, var(--fs-danger) 12%, transparent); }

/* ---- 按钮（v0 vbtn 同构，24px 表格级） ---- */
.amk-btn {
  height: 24px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--fs-ink-700);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  flex: none;
  transition:
    color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    box-shadow var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)),
    background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.amk-btn:hover:not(:disabled) {
  color: var(--fs-ink-900);
  box-shadow: inset 0 0 0 1px var(--fs-ink-400), var(--fs-e1);
}
.amk-btn:active:not(:disabled) { box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.amk-btn--primary {
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-weight: 600;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.amk-btn--primary:hover:not(:disabled) {
  background: var(--fs-accent-hover);
  color: var(--fs-on-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
}
.amk-btn--primary:active:not(:disabled) { box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15); }
.amk-btn:disabled { color: var(--fs-ink-400); background: var(--fs-bg-sunken); box-shadow: none; cursor: not-allowed; }
.amk-btn .is-loading { animation: amk-spin 0.9s linear infinite; }
@keyframes amk-spin { to { transform: rotate(360deg); } }
html[data-motion-allowed="false"] .amk-btn .is-loading { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .amk-btn .is-loading { animation: none; }
}

/* ---- 表格（去默认边框，sunken 表头 + 发丝行线 + 当前行点亮） ---- */
.amk-tbl { border-radius: var(--fs-r-sm, 6px); overflow: hidden; box-shadow: inset 0 0 0 1px var(--fs-hairline); min-width: 0; max-width: 100%; }
.amk-tbl .el-table {
  --el-table-border-color: var(--fs-hairline);
  --el-table-header-bg-color: var(--fs-bg-sunken);
  --el-table-header-text-color: var(--fs-ink-500);
  --el-table-text-color: var(--fs-ink-700);
  --el-table-row-hover-bg-color: color-mix(in srgb, var(--fs-accent) 5%, transparent);
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  font-size: 12px;
}
.amk-tbl .el-table th.el-table__cell {
  font-family: var(--fs-font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  background: var(--fs-bg-sunken);
  border-bottom: 1px solid var(--fs-hairline);
  padding: 7px 0;
}
.amk-tbl .el-table td.el-table__cell {
  padding: 7px 0;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease)), border-color var(--up-dur-fast, 120ms) var(--up-ease, var(--fs-ease));
}
.amk-tbl .el-table .cell { padding: 0 10px; line-height: 1.5; }
.amk-tbl tr.is-cur .el-table__cell { background: var(--fs-accent-soft) !important; }
.amk-tbl tr.is-cur td.el-table__cell { border-bottom-color: rgba(var(--fs-accent-rgb), 0.28); }
.amk-tbl .el-table__empty-block { background: transparent; }

/* ---- 空态 ---- */
.amk-empty { padding: 26px 0 24px; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.amk-empty__t { font-size: 12px; color: var(--fs-ink-400); }
</style>
