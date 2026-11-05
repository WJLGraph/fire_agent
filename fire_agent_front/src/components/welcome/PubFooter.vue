<script setup>
/**
 * 公开页组统一页脚：品牌 / 页组导航 / 真实数据口径行 / 版权
 * 口径与作战大屏/登录页一致：16 州市 · 5,411 历史火点 · 6 协作智能体
 */
const year = new Date().getFullYear()

const links = [
  { path: '/welcome', label: '总览' },
  { path: '/welcome/features', label: '能力详解' },
  { path: '/welcome/workflow', label: '工作流' },
  { path: '/welcome/technology', label: '技术与部署' },
  { path: '/welcome/about', label: '系统说明' },
]
</script>

<template>
  <footer class="pub-foot">
    <div class="pub-foot__inner">
      <div class="pub-foot__top">
        <div class="pub-foot__brand">
          <span class="pub-foot__cn">焰哨</span>
          <span class="qt-eyebrow">FLAMESENTRY</span>
        </div>
        <nav class="pub-foot__links" aria-label="页脚导航">
          <router-link v-for="l in links" :key="l.path" :to="l.path" class="qt-focus">{{ l.label }}</router-link>
          <router-link to="/login" class="qt-focus">登录平台</router-link>
        </nav>
      </div>

      <div class="pub-foot__ticks qt-ticks" aria-hidden="true"></div>

      <div class="pub-foot__meta">
        <span class="qt-eyebrow">16 州市 · 5,411 历史火点 · 6 协作智能体</span>
        <span class="qt-eyebrow">EPSG:4326 · WGS84</span>
        <span class="pub-foot__cp">© {{ year }} 焰哨多Agent与可视化平台</span>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.pub-foot {
  border-top: 1px solid var(--fs-hairline);
  background: var(--fs-bg-surface);
}
.pub-foot__inner {
  width: min(1200px, 100% - 48px);
  margin: 0 auto;
  padding: var(--fs-s8) 0 var(--fs-s6);
}
.pub-foot__top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fs-s4);
}
.pub-foot__brand { display: flex; align-items: baseline; gap: 10px; }
.pub-foot__cn {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--fs-ink-900);
}
.pub-foot__links {
  margin-left: auto;
  display: flex;
  flex-wrap: wrap;
  gap: var(--fs-s4);
}
.pub-foot__links a {
  position: relative;
  font-size: 12px;
  color: var(--fs-ink-500);
  text-decoration: none;
  transition: color var(--fs-dur-micro) var(--fs-ease);
}
.pub-foot__links a::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 1px;
  background: var(--fs-accent);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.22s var(--fs-ease);
}
.pub-foot__links a:hover { color: var(--fs-ink-900); }
.pub-foot__links a:hover::after, .pub-foot__links a:focus-visible::after { transform: scaleX(1); }

.pub-foot__ticks { margin: var(--fs-s5) 0 var(--fs-s4); }

.pub-foot__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--fs-s2) var(--fs-s6);
}
.pub-foot__cp { font-family: var(--fs-font-mono); font-size: 11px; color: var(--fs-ink-400); }

@media (max-width: 640px) {
  .pub-foot__inner { width: min(1200px, 100% - 32px); }
  .pub-foot__links { margin-left: 0; }
}
</style>
