<script setup>
/**
 * Agent 协作中心 · 人工审批卡（HITL，v0 review 卡同构）
 *
 * 头部（编辑图标 + 标题 + 轮次徽标 + 闸口状态徽标）+ 评审意见注记 + 模式切换 + 提交。
 * 草稿全文与编辑器已移至中列「分析报告」区域（全宽可读），本卡只承载审批操作：
 * 通过 → 左侧报告区预览草稿；修订后通过 → 左侧切换为大编辑器；驳回 → 在此填写意见。
 * 审批模式与内容由父组件持有（handleResume 提交时要读取），这里以 v-model 形式受控。
 *
 * 闸口三态（由 approvalStep 步骤行状态推导，防止"闸口未触发却假装提交成功"）：
 *   - 待闸口触发（无审批行 / 行非 awaiting）：全部按钮禁用，提示等待；
 *   - 待人工决策（行 status=awaiting）：可提交，提交后 approving 锁覆盖到终态；
 *   - 已定稿（行 completed 且 action=approve/edit）：只读结果态，不可再点。
 */
import { computed } from 'vue'

const props = defineProps({
  /** approval 步骤行（含 output.draft_report / output.review / output.revisions / output.action） */
  approvalStep: { type: Object, default: null },
  /** 评审意见 { issues: [] } */
  approvalReview: { type: Object, default: () => ({}) },
  /** 提交中的 loading 态（覆盖接口提交 → 任务终态确认，期间重复点击被吞掉） */
  approving: { type: Boolean, default: false },
  /** approve | edit | reject */
  mode: { type: String, default: 'approve' },
  comment: { type: String, default: '' },
})

const emit = defineEmits([
  'update:mode',
  'update:editContent',
  'update:comment',
  'submit',
])

// ====== 闸口状态推导（步骤行是唯一事实源） ======
const stepStatus = computed(() => (props.approvalStep && props.approvalStep.status) || '')
const stepAction = computed(() => (props.approvalStep && props.approvalStep.output && props.approvalStep.output.action) || '')
/** 已定稿：审批行 completed 且决策为通过/编辑通过（驳回重写中间态不算定稿） */
const finalized = computed(() => stepStatus.value === 'completed' && (stepAction.value === 'approve' || stepAction.value === 'edit'))
/** 闸口已触发、等待人工决策：仅此时允许提交 */
const ready = computed(() => stepStatus.value === 'awaiting')
const badgeText = computed(() => (finalized.value ? '已定稿' : (ready.value ? '待人工决策' : '待闸口触发')))
const finalizedText = computed(() => (stepAction.value === 'edit' ? '已以编辑稿定稿' : '已通过并定稿'))

// 按模式切换的提示文案（草稿/编辑都在左侧报告区）
const modeNote = (m) => ({
  approve: '报告草稿已在左侧「分析报告」区域全文展示，确认无误后点击通过。',
  edit: '已切换为编辑态：在左侧「分析报告」区域直接修改全文，完成后回到这里提交。',
  reject: '请在下方填写驳回意见，报告将按意见重写（这是唯一的自动重写入口）。',
}[m] || '')
</script>

<template>
  <section class="ap" :class="{ 'is-ready': ready, 'is-done': finalized }">
    <div class="ap__hd">
      <svg class="ap__ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m13.2 3.8 3 3L8 15H5v-3z"/><path d="m11.6 5.4 3 3"/></svg>
      <span class="ap__t">草稿审阅</span>
      <span class="ap__sp"></span>
      <span
        v-if="approvalStep?.output?.revisions > 0"
        class="ap__round"
      >第 {{ approvalStep.output.revisions }} 轮修订</span>
      <span class="ap__badge" :class="{ 'is-ready': ready, 'is-done': finalized }">{{ badgeText }}</span>
    </div>

    <!-- 已定稿：只读结果态（回看历史任务时不再可点） -->
    <div v-if="finalized" class="ap__bd">
      <p class="ap__note">{{ finalizedText }}，最终报告见左侧「分析报告」区域。</p>
      <div v-if="approvalReview.issues && approvalReview.issues.length" class="ap__review">
        <span class="ap__review-label">评审意见：</span>{{ approvalReview.issues.join('；') }}
      </div>
    </div>

    <!-- 待定稿：待闸口触发时全部禁用；待人工决策时可提交 -->
    <div v-else class="ap__bd">
      <p class="ap__note">{{ ready ? modeNote(mode) : '审批闸口尚未触发：报告仍在生成/评审中，请等待「人工审核」节点进入待审核状态后再提交。' }}</p>

      <div v-if="approvalReview.issues && approvalReview.issues.length" class="ap__review">
        <span class="ap__review-label">评审意见：</span>{{ approvalReview.issues.join('；') }}
      </div>

      <div class="ap__mode">
        <button
          class="ap__mbtn"
          :class="{ 'is-on': mode === 'approve' }"
          :disabled="!ready"
          @click="ready && emit('update:mode', 'approve')"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m4.5 10.4 3.6 3.6 7.4-8"/></svg>
          通过
        </button>
        <button
          class="ap__mbtn"
          :class="{ 'is-on': mode === 'edit' }"
          :disabled="!ready"
          @click="ready && emit('update:mode', 'edit')"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m13.2 3.8 3 3L8 15H5v-3z"/><path d="m11.6 5.4 3 3"/></svg>
          修订后通过
        </button>
        <button
          class="ap__mbtn ap__mbtn--danger"
          :class="{ 'is-on': mode === 'reject' }"
          :disabled="!ready"
          @click="ready && emit('update:mode', 'reject')"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5.5 5.5 9 9M14.5 5.5l-9 9"/></svg>
          驳回
        </button>
      </div>

      <el-input
        v-if="mode === 'reject'"
        :model-value="comment"
        type="textarea"
        :rows="3"
        class="ap__edit"
        :disabled="!ready"
        placeholder="请填写驳回意见（将作为重写要求，例如：补充玉溪市数据、巡防建议要具体到路段）"
        @update:model-value="emit('update:comment', $event)"
      />

      <div class="ap__ops">
        <button
          class="ap__submit"
          :disabled="approving || !ready"
          :title="!ready ? '等待审批闸口触发' : ''"
          @click="ready && !approving && emit('submit', mode)"
        >
          {{ approving ? '提交中…' : (mode === 'reject' ? '提交驳回' : (mode === 'edit' ? '以编辑稿定稿' : '通过并定稿')) }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* v0 review 卡：sunken 沉底 + 发丝环（区别于普通 surface 卡，文档审阅语义） */
.ap {
  position: relative; /* 呼吸环 ::after 的定位基准（缺失时以视口为基准） */
  flex-shrink: 0;
  background: var(--fs-bg-sunken);
  border-radius: var(--fs-r-md, 10px);
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  overflow: hidden;
  transition: box-shadow var(--fs-dur-panel, 0.28s) var(--fs-ease);
}
/* 闸口可用：整卡左沿 2px 强调导轨，明确「此处需要人工决策」 */
.ap::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--fs-hairline-strong);
  transform: scaleX(1);
  transform-origin: top center;
  transition: background var(--fs-dur-micro) var(--fs-ease);
}
.ap__hd {
  min-height: 40px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--fs-hairline);
}
.ap__ic { width: 14px; height: 14px; color: var(--fs-accent); flex-shrink: 0; }
.ap__t { font-size: 12px; font-weight: 600; letter-spacing: 0.04em; color: var(--fs-ink-700); }
.ap__sp { flex: 1; }
.ap__round {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: color-mix(in srgb, var(--fs-warning) 12%, transparent);
  color: var(--fs-warning);
  font-size: 10px;
  white-space: nowrap;
}
.ap__badge {
  height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  border-radius: var(--fs-r-xs, 3px);
  background: var(--fs-bg-sunken);
  color: var(--fs-ink-500);
  font-size: 11px;
  white-space: nowrap;
}
.ap__badge.is-ready { background: var(--fs-accent-soft); color: var(--fs-accent); }
.ap__badge.is-done {
  background: color-mix(in srgb, var(--fs-success) 12%, transparent);
  color: var(--fs-success);
}
/* 闸口三态导轨：待触发=灰 / 待决策=accent / 已定稿=success */
.ap.is-ready::before { background: var(--fs-accent); }
.ap.is-done::before { background: var(--fs-success); }
.ap.is-ready { box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
.ap.is-done { box-shadow: inset 0 0 0 1px var(--fs-hairline); }
/* 闸口未触发时的禁用态（模式钮与输入框统一置灰） */
.ap__mbtn:disabled { opacity: 0.5; cursor: not-allowed; }
.ap__mbtn:disabled:hover { color: var(--fs-ink-500); box-shadow: inset 0 0 0 1px var(--fs-hairline-strong); }
.ap__mbtn--danger:disabled:hover { color: var(--fs-danger); }

.ap__bd {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 提示注记（v0 review__note 同构） */
.ap__note {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--fs-ink-500);
}

/* 评审意见（warning 软底注记 + 左沿刻线，读作「模型给你的话」） */
.ap__review {
  font-size: 11px;
  line-height: 1.7;
  color: var(--fs-warning);
  background: color-mix(in srgb, var(--fs-warning) 8%, transparent);
  border-radius: var(--fs-r-sm, 6px);
  box-shadow: inset 2px 0 0 var(--fs-warning);
  padding: 8px 10px 8px 12px;
}
.ap__review-label { font-weight: 600; }

/* 模式按钮组（v0 review__ops 三钮同构：通过 primary 语义 / 修订 default / 驳回 danger） */
.ap__mode {
  display: flex;
  gap: 8px;
  padding-top: 4px;
  flex-wrap: wrap;
}
.ap__mbtn {
  position: relative;
  height: 28px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  color: var(--fs-ink-500);
  background: var(--fs-bg-surface);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fs-dur-micro) var(--fs-ease), box-shadow var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.ap__mbtn svg { width: 12px; height: 12px; transition: transform var(--fs-dur-micro) var(--fs-ease); }
.ap__mbtn:hover:not(:disabled) { color: var(--fs-ink-900); box-shadow: inset 0 0 0 1px var(--fs-ink-400); }
.ap__mbtn:hover:not(:disabled) svg { transform: scale(1.08); }
.ap__mbtn:active:not(:disabled) { transform: translateY(0.5px); }
.ap__mbtn.is-on {
  color: var(--fs-accent);
  font-weight: 600;
  box-shadow: inset 0 0 0 1px var(--fs-accent), inset 0 1px 0 rgba(255, 255, 255, 0.14);
}
.ap__mbtn--danger { color: var(--fs-danger); }
.ap__mbtn--danger:hover:not(:disabled) { color: var(--fs-danger); box-shadow: inset 0 0 0 1px var(--fs-danger); }
.ap__mbtn--danger.is-on {
  color: var(--fs-danger);
  box-shadow: inset 0 0 0 1px var(--fs-danger), inset 0 1px 0 rgba(255, 255, 255, 0.14);
}

/* 提交行（v0 btn--primary 同构，右对齐） */
.ap__ops {
  display: flex;
  justify-content: flex-end;
}
.ap__submit {
  position: relative;
  overflow: hidden;
  height: 28px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  border-radius: var(--fs-r-sm, 6px);
  background: var(--fs-accent);
  color: var(--fs-on-accent);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
  transition: background var(--fs-dur-micro) var(--fs-ease), transform var(--fs-dur-micro) var(--fs-ease);
}
.ap__submit::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.22) 50%, transparent 62%);
  transform: translateX(-130%);
}
.ap__submit:hover:not(:disabled) { background: var(--fs-accent-hover); }
.ap__submit:hover:not(:disabled)::after { animation: ap-sheen 0.62s var(--up-ease, ease-out); }
@keyframes ap-sheen {
  to { transform: translateX(130%); }
}
.ap__submit:active:not(:disabled) { transform: translateY(0.5px); }
.ap__submit:disabled { opacity: 0.6; cursor: not-allowed; }
/* ==================== V7 入场微动效：审批卡出现时淡入 + 边框呼吸两次（不持续闪） ==================== */
.ap { animation: ap-in 0.45s var(--fs-ease-out) both; }
@keyframes ap-in {
  0% { opacity: 0; transform: translateY(8px); }
  100% { opacity: 1; transform: none; }
}
.ap::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  box-shadow: 0 0 0 0 rgba(var(--fs-accent-rgb), 0);
  animation: ap-breathe 1.6s var(--fs-ease) 0.45s 2 both;
}
@keyframes ap-breathe {
  0%, 100% { box-shadow: 0 0 0 0 rgba(var(--fs-accent-rgb), 0); }
  50% { box-shadow: 0 0 0 3px rgba(var(--fs-accent-rgb), 0.14); }
}
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .ap,
  html:not([data-motion="on"]) .ap::after,
  html:not([data-motion="on"]) .ap__submit::after { animation: none; }
}
html[data-motion-allowed="false"] .ap,
html[data-motion-allowed="false"] .ap::after,
html[data-motion-allowed="false"] .ap__submit::after { animation: none; }
</style>
