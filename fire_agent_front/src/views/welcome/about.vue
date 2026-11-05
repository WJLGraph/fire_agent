<script setup>
/**
 * /welcome/about — 系统说明（公开）
 * 使命定位一段、三条设计原则、项目时间线、开发者与联系方式；保持留白，不堆字。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import PubPage from '@/components/welcome/PubPage.vue'
import { motionAllowed } from '@/composables/useMotionPreference'

/* 时间线滚动激活：节点进入视口逐个点亮（off 时全部静态呈现） */
const tlRef = ref(null)
const litSet = ref(new Set())
let tlIO = null
onMounted(() => {
  if (!motionAllowed.value || !('IntersectionObserver' in window)) {
    litSet.value = new Set(timeline.map((_, i) => i)) // off：全部点亮态静态呈现
    return
  }
  const items = Array.from(tlRef.value?.querySelectorAll('.tl__item') ?? [])
  tlIO = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return
      const idx = Number(en.target.dataset.tlIdx)
      litSet.value = new Set([...litSet.value, idx])
      tlIO.unobserve(en.target)
    })
  }, { threshold: 0.4 })
  items.forEach((el) => tlIO.observe(el))
})
onBeforeUnmount(() => { tlIO?.disconnect(); tlIO = null })

const principles = [
  { k: '数据先于界面', v: '所有读数都可溯源到真实数据口径；界面服务于读数，不反过来。' },
  { k: '人做最后把关', v: '智能体负责生成与核查，发布永远经过人工审批闸口。' },
  { k: '值班场景优先', v: '长时间盯屏的暗色护眼、低对比噪声、状态一眼可辨。' },
]

const timeline = [
  { t: '一期', d: '数据接入与作战大屏：火点上图、五级口径、双模式切换' },
  { t: '二期', d: '智能查询与知识库：自然语言问数、文档 RAG 问答' },
  { t: '三期', d: 'Agent 协作中心：七环节流水线、评审三态、审批归档' },
]
</script>

<template>
  <PubPage
    eyebrow="ABOUT · 系统说明"
    title="焰哨是什么"
    lead="焰哨（FlameSentry）是面向云南省森林火险的智能研判与值班协同平台：用数据看清风险，用智能体写好报告，人做最后把关。"
    :page-index="4"
  >
    <!-- 使命定位 -->
    <section class="pg-sec">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">01</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">MISSION · 使命</p>
            <h2 class="pg-head__title pg-h2">让火险研判不再熬夜翻图</h2>
            <!-- 大号引文式排版：视觉锚点 -->
            <blockquote class="mission__quote rv">
              用数据看清风险，用智能体写好报告，<br />人做最后把关。
            </blockquote>
            <p class="pg-head__lead mission__lead">
              <span class="mission__main">云南省 16 个州市的森林防火值班，长期依赖人工读图与经验汇总。</span>
              <span class="mission__sub">焰哨把卫星火点、气象与州市边界数据接上多智能体流水线，从研判到简报归档自动完成，值班员只在关键节点把关。</span>
            </p>
          </div>
          <span class="pg-head__meta">EST. 2025</span>
        </div>
        <!-- 横向数据带 + 右侧注解（替代四张同质卡） -->
        <div class="kv-band rv">
          <div class="kv-b__item"><b class="qt-num">16</b><span class="pg-cap">州市覆盖</span></div>
          <div class="kv-b__item"><b class="qt-num">5,411</b><span class="pg-cap">历史火点</span></div>
          <div class="kv-b__item"><b class="qt-num">6</b><span class="pg-cap">协作智能体</span></div>
          <div class="kv-b__item"><b class="qt-num">7</b><span class="pg-cap">流水线环节</span></div>
          <span class="kv-b__note pg-cap">口径与作战大屏、公开页读数带一致</span>
        </div>
      </div>
    </section>

    <!-- 设计原则 -->
    <section class="pg-sec pg-sec--sunken">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">02</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">PRINCIPLES · 原则</p>
            <h2 class="pg-head__title pg-h2">三条设计原则</h2>
          </div>
        </div>
        <div class="principles" data-stagger>
          <div v-for="(p, i) in principles" :key="p.k" class="principle rv-item">
            <span class="qt-num principle__no">{{ String(i + 1).padStart(2, '0') }}</span>
            <div>
              <h3 class="pg-h3">{{ p.k }}</h3>
              <p class="pg-cap">{{ p.v }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 时间线 -->
    <section class="pg-sec">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">03</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">TIMELINE · 阶段</p>
            <h2 class="pg-head__title pg-h2">项目阶段</h2>
          </div>
          <span class="pg-head__meta">v1.0.1</span>
        </div>
        <!-- 纵向时间线：竖线随滚动生长，节点进入视口逐个点亮 -->
        <ol ref="tlRef" class="tl" :class="{ 'tl--lit': litSet.size === timeline.length }">
          <li
            v-for="(t, i) in timeline"
            :key="t.t"
            class="tl__item rv"
            :data-tl-idx="i"
            :data-rv-delay="String(i * 0.08)"
            :class="{ 'is-lit': litSet.has(i) }"
          >
            <i class="tl__dot" aria-hidden="true"></i>
            <span class="tl__t qt-eyebrow">{{ t.t }}</span>
            <p class="pg-body">{{ t.d }}</p>
          </li>
        </ol>
      </div>
    </section>

    <!-- 开发者 -->
    <section class="pg-sec qsec--last">
      <div class="pg-wrap">
        <div class="pg-head">
          <span class="pg-head__no">04</span>
          <div class="pg-head__main">
            <p class="pg-head__eyebrow">DEVELOPER · 开发者</p>
            <h2 class="pg-head__title pg-h2">开发者信息</h2>
          </div>
        </div>
        <div class="dev pg-card">
          <div class="dev__row">
            <span class="pg-cap dev__k">作者</span>
            <span class="pg-body">wjl</span>
          </div>
          <div class="dev__row">
            <span class="pg-cap dev__k">仓库</span>
            <span class="pg-body">Gitee · WJLGraph/Fire_agent_front</span>
          </div>
          <div class="dev__row">
            <span class="pg-cap dev__k">联系</span>
            <span class="pg-body">项目页面留言或仓库 Issue</span>
          </div>
        </div>
      </div>
    </section>
  </PubPage>
</template>

<style scoped>
.pg-sec--sunken { background: var(--fs-bg-sunken); }

/* 使命段：Editorial 透明度层次（主句墨色 / 辅句灰阶），宽行高呼吸感 */
.mission__quote {
  margin: 28px 0 8px;
  padding-left: 20px;
  border-left: 3px solid var(--fs-accent);
  font-size: 21px;
  font-weight: 500;
  line-height: 1.8;
  color: var(--fs-ink-900);
  letter-spacing: 0.01em;
}
.mission__lead { max-width: 620px; }
.mission__main {
  display: block;
  font-size: 17px;
  line-height: 2;
  color: var(--fs-ink-900);
}
.mission__sub {
  display: block;
  margin-top: 10px;
  font-size: 14px;
  line-height: 2;
  color: var(--fs-ink-500);
}

/* 横向数据带 + 右侧注解 */
.kv-band {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px 36px;
  padding: 22px 0;
  border-top: 1px solid var(--fs-hairline-strong);
  border-bottom: 1px solid var(--fs-hairline);
}
.kv-b__item { display: flex; flex-direction: column; gap: 6px; }
.kv-b__item b {
  font-size: 32px;
  font-weight: 600;
  color: var(--fs-ink-900);
  font-variant-numeric: tabular-nums;
  transition: color var(--fs-dur-micro) var(--fs-ease);
}
.kv-b__item:hover b { color: var(--fs-accent); }
.kv-b__note { margin-left: auto; max-width: 220px; }

.principles { display: flex; flex-direction: column; gap: 20px; }
.principle { display: flex; gap: 20px; align-items: flex-start; }
.principle__no {
  font-size: 13px;
  letter-spacing: 0.14em;
  color: var(--fs-accent);
  padding-top: 3px;
  transition: transform 0.3s var(--fs-ease);
}
.principle p { margin: 6px 0 0; transition: color var(--fs-dur-micro) var(--fs-ease); }
/* hover：序号右移（与总览页痛点卡同一动作语言），说明文字提亮一档 */
.principle:hover .principle__no { transform: translateX(3px); }
.principle:hover p { color: var(--fs-ink-700); }

/* 纵向时间线：竖线生长 + 节点点亮（滚动激活；off 时节点全亮） */
.tl {
  list-style: none;
  margin: 0;
  padding: 0 0 0 28px;
  position: relative;
  display: flex;
  flex-direction: column;
  max-width: 680px;
}
.tl::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 14px;
  bottom: 14px;
  width: 1px;
  background: var(--fs-hairline-strong);
}
.tl__item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px 0;
}
.tl__item + .tl__item { border-top: 1px solid var(--fs-hairline); }
.tl__dot {
  position: absolute;
  left: -28px;
  top: 27px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--fs-bg-canvas);
  border: 1px solid var(--fs-hairline-strong);
  transition: border-color 0.3s var(--fs-ease), box-shadow 0.3s var(--fs-ease), background 0.3s var(--fs-ease);
}
.tl__item.is-lit .tl__dot {
  background: var(--fs-accent);
  border-color: var(--fs-accent);
  box-shadow: 0 0 0 4px rgba(var(--fs-accent-rgb), 0.14);
}
.tl__t { color: var(--fs-ink-400); transition: color 0.3s var(--fs-ease); }
.tl__item.is-lit .tl__t { color: var(--fs-accent); }
/* 悬停让未点亮节点先「预备」：只描边转强调色，不改已点亮项的语义 */
.tl__item:hover:not(.is-lit) .tl__dot { border-color: var(--fs-accent); }
.tl__item p { margin: 0; }

.dev { padding: 0; overflow: hidden; }
.dev__row {
  display: flex;
  gap: 24px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--fs-hairline);
  transition: background-color var(--fs-dur-micro) var(--fs-ease);
}
/* Notion 式行 hover：只变背景，零位移（与内部页列表同一纪律） */
.dev__row:hover { background: var(--fs-bg-sunken); }
.dev__row:last-child { border-bottom: none; }
.dev__k { width: 72px; flex: none; }
.dev__row .pg-body { margin: 0; }

@media (max-width: 900px) {
  .kv-b__note { margin-left: 0; max-width: none; }
  .mission__quote { font-size: 18px; }
}
</style>
