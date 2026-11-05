# 任务清单 · 公开站点审计 + 增强

> 状态：✅ 全部任务完成，本文件为历史存档。

> 依赖 `spec.md`；批准后按顺序执行，每完成一项即更新状态。

## 阶段一 · 文案审计落地

- [x] T1 `technology.vue`：A1–A9 共 9 处文案/数据结构修正（架构层级、技术栈、部署、安全、FAQ、数据表、并行汇合注记）。
- [x] T2 `workflow.vue`：B1–B4（七环节、检索并行固定执行、SSE 兜底、思考留存）。
- [x] T3 `features.vue`：C1–C3（七环节、思考留存、空间基准）。
- [x] T4 `index.vue`：D1–D4（七环节注、SITUATION OVERVIEW、摘要口径、MODIS 2021–2025）。
- [x] T5 `about.vue`：E1–E2（七环节 ×2）。
- [x] T6 `login/index.vue`：F1（行政区划边界表述）。
- [x] T7 `AgentNetGL.vue`：G1–G2（注释口径、删除虚构 GIS→RAG 边，改为并行汇合 + DOM 注）。
- [x] T8 全局 grep 校验：`GLM|SQLite|2s 轮询|前端零密钥|无外部依赖|七节点` 仅剩合法注释。

## 阶段二 · 增强实现

- [x] T9 `TerrainGL.vue` E1：EffectComposer + 轻 Bloom（桌面 + motionAllowed + WebGL2），resize/dispose 完整。
- [x] T10 `TerrainGL.vue` E2：uTime/uPointer/uProgress uniform 与 ≤8px 指针视差、滚动雾化；off 冻结。
- [x] T11 `TerrainGL.vue` E3：8,000 点 GPU 火星粒子（低核设备降 3,000；移动端/off 不创建）。
- [x] T12 `router/index.js` + `qt.css` E4：VT clip-path 遮罩（前进/后退方向 + 320ms，降级守卫）。

## 验收与交付

- [x] T13 `npm run build` + `check-sfc-bindings.mjs` + `oxlint` 全绿。
- [x] T14 headless Edge 截图 6 页 × 2 视口 + 4 张关键区块 + 2 张 off → `preview/audit-enhance/`。
- [x] T15 帧率采样（/welcome、/welcome/technology，5s，on/off 对照）并记录。
- [x] T16 提交并推送 Gitee `origin master`，回报 commit hash、改动清单、截图与帧率。
