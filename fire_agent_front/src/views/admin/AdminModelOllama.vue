<script setup>
/**
 * 系统管理 · 模型接入 · 本地 Ollama 区块（无需 API Key，Embedding 始终走阿里百炼）
 *
 * 阶段 4f：从 AdminModel.vue 按提供商区块拆分。
 * configForm 为父组件传入的 reactive 对象，本组件直接读写其属性（与原单文件实现等价）。
 * 展示层走 AdminModel.vue 注入的共享 amk kit（v0 卡片 / 发丝输入 / sunken 注脚）。
 */
defineProps({
  configForm: { type: Object, required: true },
})
defineEmits(['save'])
</script>

<template>
  <div class="amk-card">
    <div class="amk-hd">
      <span class="amk-hd__t">本地 Ollama 配置</span>
      <span class="amk-bdg">无需 API Key</span>
      <span class="amk-sp"></span>
      <button class="amk-btn" title="保存本卡配置到后端 .env 并热生效" @click="$emit('save')">保存配置</button>
      <span class="amk-hd__d">Embedding 始终走阿里百炼，不受切换影响</span>
    </div>
    <div class="amk-bd">
      <div class="amk-fgrid">
        <div class="amk-fi">
          <label>API Base URL</label>
          <el-input v-model="configForm.ollama_api_base" placeholder="http://localhost:11434/v1" />
        </div>
        <div class="amk-fi">
          <label>Chat 模型</label>
          <el-input v-model="configForm.ollama_model" placeholder="qwen2.5:7b" />
        </div>
      </div>
      <div class="amk-note">
        请先安装 Ollama 并拉取模型（如 <code>ollama pull qwen2.5:7b</code>）；
        Embedding 检索不受切换影响，始终使用阿里百炼 <code>text-embedding-v3</code>。
      </div>
    </div>
  </div>
</template>
