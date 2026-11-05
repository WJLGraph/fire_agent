<script setup>
/**
 * PubPager — 公开页组底部翻页带（总览 → 能力 → 工作流 → 技术 → 关于）
 *
 * - 路由表唯一事实源，所有链接均为站内真实路由，无死链
 * - 末页（关于）的「下一页」回总览，形成闭环
 * - 序号 NN / 05 + 细进度线（当前位置填充）；hover 箭头位移、线条展开
 * - 键盘可达（真链接 Tab + Enter）、aria-label 明确；移动端上下堆叠不依赖 hover
 */
import { computed } from 'vue'
import AppIcon from '@/components/base/AppIcon.vue'

const props = defineProps({
  /** 当前页在页组中的序号：0 总览 / 1 能力 / 2 工作流 / 3 技术 / 4 关于 */
  index: { type: Number, required: true },
})

const PAGES = [
  { path: '/welcome', label: '总览' },
  { path: '/welcome/features', label: '能力详解' },
  { path: '/welcome/workflow', label: '智能体与工作流' },
  { path: '/welcome/technology', label: '技术与部署' },
  { path: '/welcome/about', label: '系统说明' },
]

const prev = computed(() => (props.index > 0 ? PAGES[props.index - 1] : null))
const next = computed(() => (props.index < PAGES.length - 1 ? PAGES[props.index + 1] : PAGES[0]))
const no = (i) => String(((i % PAGES.length) + PAGES.length) % PAGES.length + 1).padStart(2, '0')
const prevNo = computed(() => no(props.index - 1))
const nextNo = computed(() => no(props.index + 1))
const progress = computed(() => `${((props.index + 1) / PAGES.length) * 100}%`)
</script>

<template>
  <nav class="ppager" aria-label="公开页翻页">
    <div class="ppager__in">
      <router-link
        v-if="prev"
        :to="prev.path"
        class="ppager__item is-prev qt-focus"
        :aria-label="`上一页：${prev.label}`"
      >
        <AppIcon name="chevron-right" :size="14" :rotate="180" class="ppager__arr is-l" />
        <span class="ppager__meta">
          <em class="qt-num ppager__no"><span class="ppager__no-a">{{ prevNo }} / 05</span><span class="ppager__no-b" aria-hidden="true">{{ prevNo }} / 05</span></em>
          <span class="ppager__lb">上一页 · {{ prev.label }}</span>
        </span>
      </router-link>
      <span v-else class="ppager__ghost" aria-hidden="true"></span>

      <span class="ppager__line" aria-hidden="true">
        <i class="ppager__line-fill" :style="{ width: progress }"></i>
      </span>

      <router-link
        :to="next.path"
        class="ppager__item is-next qt-focus"
        :aria-label="`下一页：${next.label}`"
      >
        <span class="ppager__meta">
          <em class="qt-num ppager__no"><span class="ppager__no-a">{{ nextNo }} / 05</span><span class="ppager__no-b" aria-hidden="true">{{ nextNo }} / 05</span></em>
          <span class="ppager__lb">下一页 · {{ next.label }}</span>
        </span>
        <AppIcon name="chevron-right" :size="14" class="ppager__arr" />
      </router-link>
    </div>
  </nav>
</template>

<style scoped>
.ppager {
  border-top: 1px solid var(--fs-hairline);
  background: var(--fs-bg-canvas);
}
.ppager__in {
  width: min(1120px, 100% - 48px);
  margin: 0 auto;
  padding: 18px 0;
  display: flex;
  align-items: center;
  gap: 20px;
}
.ppager__item {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  padding: 8px 10px;
  border-radius: var(--fs-r-sm);
  position: relative;
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
.ppager__item:hover { background: rgba(var(--fs-ink-900-rgb), 0.04); }
.ppager__item.is-prev { margin-right: auto; }
.ppager__item.is-next { margin-left: auto; text-align: right; }

.ppager__meta { display: flex; flex-direction: column; gap: 3px; }
.ppager__item.is-next .ppager__meta { align-items: flex-end; }
/* 序号遮罩切换：hover 时上层滑出、下层自下方滑入（160ms） */
.ppager__no {
  position: relative;
  display: block;
  height: 1.1em;
  overflow: hidden;
  font-style: normal;
}
.ppager__no-a,
.ppager__no-b {
  display: block;
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--fs-ink-400);
  line-height: 1.1em;
  transition: transform 0.16s var(--fs-ease);
}
.ppager__no-b { position: absolute; top: 100%; left: 0; right: 0; color: var(--fs-accent); }
.ppager__item:hover .ppager__no-a { transform: translateY(-100%); }
.ppager__item:hover .ppager__no-b { transform: translateY(-100%); }
.ppager__lb {
  font-size: 13px;
  font-weight: 600;
  color: var(--fs-ink-700);
  transition: color var(--fs-dur-micro) var(--fs-ease);
}
.ppager__item:hover .ppager__lb { color: var(--fs-ink-900); }

.ppager__arr {
  color: var(--fs-ink-400);
  transition: transform var(--fs-dur-micro) var(--fs-ease), color var(--fs-dur-micro) var(--fs-ease);
}
.ppager__item:hover .ppager__arr { color: var(--fs-accent); }
.ppager__item:hover .ppager__arr:not(.is-l) { transform: translateX(3px); }
.ppager__item:hover .ppager__arr.is-l { transform: rotate(180deg) translateX(3px); }

/* 细进度线：当前位置填充，hover 邻项时轻微展开 */
.ppager__line {
  position: relative;
  flex: 1;
  height: 1px;
  background: var(--fs-hairline);
  overflow: hidden;
}
.ppager__line-fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  background: linear-gradient(90deg, var(--fs-accent), var(--fs-risk-mid));
  opacity: 0.6;
  transition: width 0.4s var(--fs-ease);
}

.ppager__ghost { flex: 1; }

@media (max-width: 760px) {
  .ppager__in {
    width: min(1120px, 100% - 32px);
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    padding: 14px 0;
  }
  .ppager__item, .ppager__item.is-prev, .ppager__item.is-next { margin: 0; justify-content: space-between; width: 100%; }
  .ppager__item.is-next .ppager__meta { align-items: flex-start; }
  .ppager__line { order: -1; width: 100%; flex: none; height: 2px; }
  .ppager__ghost { display: none; }
}
</style>
