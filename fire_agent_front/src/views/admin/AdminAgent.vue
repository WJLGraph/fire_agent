<script setup>
/**
 * 系统管理 · Agent 参数 Tab — v0 kb-ans 面板 + pf-row 偏好行同构
 *
 * agentForm 是父组件传入的 reactive 对象（与「模型接入」Tab 的 fetchConfig 回填共用同一份）。
 */
import { ElMessage } from 'element-plus'
import { updateConfig } from '@/api/admin'

const props = defineProps({
  agentForm: { type: Object, required: true },
})

const emit = defineEmits(['refresh-config'])

// ====== 保存 Agent 参数 ======
const saveAgent = async () => {
  try {
    const json = await updateConfig({
      orchestrator_temperature: Number(props.agentForm.orchestrator_temperature),
      report_temperature: Number(props.agentForm.report_temperature),
      max_agents: Number(props.agentForm.max_agents),
    })
    if (json.code === 200) {
      ElMessage.success('Agent 参数已保存')
      emit('refresh-config')
    }
  } catch {
    ElMessage.error('保存失败')
  }
}
</script>

<template>
  <div class="aa">
    <!-- 编排参数（v0 pf-row 偏好行：左说明 + 右控件） -->
    <div class="kb-ans">
      <div class="kb-ans__hd">
        <span class="kb-ans__t">编排参数</span>
        <span class="sq-panel__sp"></span>
        <button class="vbtn vbtn--primary" @click="saveAgent">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h9l3 3v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M7 4v4h6"/></svg>
          保存参数
        </button>
      </div>
      <div class="kb-ans__bd" style="padding:0">
        <div class="pf-row">
          <div class="pf-row__b">
            <span class="pf-row__t">编排 Agent 温度</span>
            <span class="pf-row__d">任务拆解与路由的随机性（0-1，mono 数值实时显示）</span>
          </div>
          <div class="aa__slider">
            <el-slider v-model="agentForm.orchestrator_temperature" :min="0" :max="1" :step="0.1" style="width: 220px" />
            <span class="aa__val mono">{{ Number(agentForm.orchestrator_temperature || 0).toFixed(1) }}</span>
          </div>
        </div>
        <div class="pf-row">
          <div class="pf-row__b">
            <span class="pf-row__t">报告 Agent 温度</span>
            <span class="pf-row__d">报告正文生成的随机性（0-1）</span>
          </div>
          <div class="aa__slider">
            <el-slider v-model="agentForm.report_temperature" :min="0" :max="1" :step="0.1" style="width: 220px" />
            <span class="aa__val mono">{{ Number(agentForm.report_temperature || 0).toFixed(1) }}</span>
          </div>
        </div>
        <div class="pf-row">
          <div class="pf-row__b">
            <span class="pf-row__t">最大并行 Agent 数</span>
            <span class="pf-row__d">同时运行的子 Agent 上限（1-10）</span>
          </div>
          <el-input-number v-model="agentForm.max_agents" :min="1" :max="10" size="small" style="width: 110px" />
        </div>
        <div class="pf-row">
          <div class="pf-row__b">
            <span class="pf-row__t">报告人工审批（HITL）</span>
            <span class="pf-row__d">报告通过质量评审后，需人工审批（通过 / 编辑 / 驳回）才定稿归档</span>
          </div>
          <button class="tg" :class="{ 'is-on': agentForm.require_approval }" @click="agentForm.require_approval = !agentForm.require_approval"><i></i></button>
        </div>
        <div class="pf-row" style="border-bottom: none">
          <div class="pf-row__b">
            <span class="pf-row__t">全链路流式输出</span>
            <span class="pf-row__d">报告与 RAG 回答逐字流式推送（打字机效果）；关闭后回退整段返回</span>
          </div>
          <button class="tg" :class="{ 'is-on': agentForm.llm_stream_enabled }" @click="agentForm.llm_stream_enabled = !agentForm.llm_stream_enabled"><i></i></button>
        </div>
      </div>
    </div>

    <!-- Agent 图谱说明（v0 adm-log 终端同构） -->
    <div class="kb-ans">
      <div class="kb-ans__hd"><span class="kb-ans__t">Agent 图谱说明</span></div>
      <div class="aa__graph mono">
        <div><b>Orchestrator</b>（LangGraph 编排）→ 拆解任务（plan 驱动路由）→</div>
        <div class="aa__indent">├─ <b>DataAgent</b>：查数据库（历史火点/预测双源）→ <b>GisAgent</b>：空间分析</div>
        <div class="aa__indent">├─ <b>RagAgent</b>：知识库 RAG 检索（Adaptive + Rerank）</div>
        <div class="aa__indent">└─ 汇合 → <b>ReportAgent</b>：生成报告 → <b>Reviewer</b>：质量评审（不通过退回重写，最多 2 轮）</div>
        <div>→ 人工审批闸口（HITL，可配置）：通过 / 编辑 / 驳回 → 报告定稿归档</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.aa {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex-shrink: 0; /* 禁止纵向压缩（原 min-height:100% 会导致卡片被压矮、内容被裁） */
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
.mono { font-family: var(--fs-font-mono); letter-spacing: 0.02em; font-variant-numeric: tabular-nums; }

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
.vbtn svg { width: 12px; height: 12px; }
.vbtn:hover:not(:disabled) { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.vbtn--primary {
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-weight: 600;
  height: 28px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.vbtn--primary:hover:not(:disabled) {
  background: var(--fs-accent-hover);
  color: var(--fs-on-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), var(--fs-e1);
}

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
.aa__slider { display: flex; align-items: center; gap: 10px; }
.aa__val {
  flex: none;
  width: 30px;
  padding: 2px 0;
  font-size: 12px;
  color: var(--fs-ink-900);
  text-align: center;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-xs, 3px);
}

/* ===== v0 tg 迷你开关 ===== */
.tg {
  flex: none;
  width: 34px;
  height: 19px;
  border: none;
  border-radius: 999px;
  background: var(--fs-hairline-strong);
  position: relative;
  cursor: pointer;
  padding: 0;
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.tg:hover:not(.is-on) { background: var(--fs-ink-400); }
.tg i {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--fs-bg-surface);
  box-shadow: var(--fs-e1);
  transition: transform var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease);
}
.tg:hover i { box-shadow: var(--fs-e2); }
.tg.is-on { background: var(--fs-accent); }
.tg.is-on i { transform: translateX(15px); }

/* 图谱终端 */
.aa__graph {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 11px;
  line-height: 1.7;
  color: var(--fs-ink-700);
  background: var(--fs-bg-sunken);
}
.aa__graph b { color: var(--fs-accent); font-weight: 600; }
.aa__indent { padding-left: 1.5em; }

/* 两张面板错峰入场（基线=终态可见，受动效闸门管控） */
.aa > .kb-ans { animation: aa-in 0.4s var(--fs-ease-out) both; }
.aa > .kb-ans:nth-child(2) { animation-delay: 55ms; }
@keyframes aa-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
html[data-motion-allowed="false"] .aa > .kb-ans { animation: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .aa > .kb-ans { animation: none; }
}
</style>
