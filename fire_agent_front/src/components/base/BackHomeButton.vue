<script setup>
/**
 * 返回首页（门户 welcome）· 各页页头统一入口
 *
 * 侧栏导航不含门户页，登录后没有回到 welcome 的显式路径，这里补上：
 * 每个业务页页头（含作战大屏顶栏）最左侧放同一颗幽灵按钮，样式只在本组件维护一份。
 * 纯展示组件：只依赖 router-link，不参与任何业务状态。
 */
import AppIcon from './AppIcon.vue'
</script>

<template>
  <router-link
    to="/welcome"
    class="bhk"
    title="返回门户首页"
    aria-label="返回门户首页"
  >
    <AppIcon class="bhk__ic" name="home" :size="14" />
    <span class="bhk__t">返回首页</span>
  </router-link>
</template>

<style scoped>
.bhk {
  flex: none;
  height: 28px;
  padding: 0 10px 0 8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--fs-r-sm, 6px);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--fs-ink-500);
  background-color: transparent;
  box-shadow: inset 0 0 0 1px var(--fs-hairline);
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  transition:
    color var(--fs-dur-micro) var(--fs-ease),
    background-color var(--fs-dur-micro) var(--fs-ease),
    box-shadow var(--fs-dur-micro) var(--fs-ease),
    transform var(--fs-dur-micro) var(--fs-ease);
}
.bhk:hover {
  color: var(--fs-ink-900);
  background-color: var(--fs-bg-sunken);
  box-shadow: inset 0 0 0 1px var(--fs-hairline-strong);
}
.bhk:active { transform: translateY(0.5px); }
.bhk__ic {
  color: inherit;
  transition: transform var(--fs-dur-micro) var(--fs-ease);
}
/* 图标轻抬：与页头其它按钮的悬停反馈同拍，不做大位移 */
.bhk:hover .bhk__ic { transform: translateY(-1px); }
.bhk:focus-visible {
  outline: 2px solid var(--fs-accent);
  outline-offset: 1px;
}

/* 窄屏（页头空间紧张）只留图标，宽屏再补文字；阈值取 900px，常规桌面宽度都能看到「返回首页」 */
@media (max-width: 900px) {
  .bhk { padding: 0 7px; }
  .bhk__t { display: none; }
}

/* 动效三态闸门 */
html[data-motion-allowed="false"] .bhk:active,
html[data-motion-allowed="false"] .bhk:hover .bhk__ic { transform: none; }
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion="on"]) .bhk:active,
  html:not([data-motion="on"]) .bhk:hover .bhk__ic { transform: none; }
}
</style>
