# 验收清单 · 公开站点审计 + 增强

> 状态：✅ 已全部验收通过，本文件为历史存档。审计后系统又经历了安全加固（SSE 改请求头鉴权、15 小时滑动会话、全端点鉴权收口），"SSE 与鉴权描述与代码一致"一条反映的是审计当时的状态。

> 逐项核对 `spec.md` 与代码事实；`[x]` 表示已用代码检索 / 构建 / headless 截图或断言证实。

## 阶段一 · 文案与技术事实一致

- [x] 五级火险名称（正常 / 注意 / 警告 / 高温 / 极度）与 `src/utils/riskLevel.js` 完全一致，无自造等级。
- [x] 技术栈版本口径与 `package.json` / `fire_agent_back/requirements.txt` 一致；页面不硬编码具体小版本号。
- [x] 大模型口径统一为 Qwen（`qwen-plus`），embedding 描述与 `app/core/config.py` 的 `EMBEDDING_MODEL` 一致；可切换项标注为「可切换」而非默认。
- [x] 数据库口径为 PostgreSQL + PostGIS（Docker Compose），不再出现 SQLite / MySQL 表述。
- [x] 智能体数量与名称（Orchestrator / DataAgent / GISAgent / RAGAgent / ReportAgent / Reviewer）与 `AGENT_REGISTRY` 一致。
- [x] 「七环节」与「8 节点（查询 ∥ 检索并行 + HITL）」口径不再自相矛盾；检索标注为「与查询并行、固定执行」，未再声称可按计划跳过。
- [x] 统计数字 16 / 5,411 / 6 可由后端 `dashboard.py` 计数口径与 MODIS 2021–2025 数据解释；页面注明「摘要口径」「示例」。
- [x] 空间基准 EPSG:4326、SSE、端口 8000/5173、鉴权与部署描述均与代码/配置一致。
- [x] 「计划/按需」未被写成「已实现/全量」；`GLM|SQLite|MySQL|2s 轮询|前端零密钥|无外部依赖|七节点|LIVE SITUATION|API 数据同步` 全站 0 命中。
- [x] 仅改文案与数据口径，未改主题 token、配色与布局结构。

## 阶段二 · 渐进增强

- [x] Bloom 仅桌面（>1024px）+ `motionAllowed=true` + WebGL2 启用；移动端 / off / import 失败直接渲染。
- [x] Bloom 只作用于 layer 1（光柱/脉冲环），加色合成叠回底图；板块与州界未被冲白，文字可读。
- [x] composer 半分辨率并在 resize 同步；卸载时 composer / pass / quad / 场景资源全量 dispose，`WEBGL_lose_context` 释放。
- [x] 火星粒子 GPU 单 pass（顶点着色器上升淡出），低核设备自动降至 3,000，移动端/off 不创建。
- [x] `uTime / uPointer / uProgress` uniform 生效：指针视差 ≤8px、滚动雾化 ≤6%、off 冻结。
- [x] View Transitions + `clip-path` 遮罩按页面序号区分前进/后退；不支持 / reduced-motion / `data-no-vt` 直接放行。
- [x] 所有持续动效接入 `html[data-motion-allowed]` 与 `prefers-reduced-motion` 降级；off 态地形回退静态等高线 SVG 可读。
- [x] 6 页 × 2 视口截图无横向溢出、无旧文案、H1 存在；关键区块（terrain / anet / vt）断言通过。

## 构建与交付

- [x] `npm run build` 通过（three 后处理进入独立动态 chunk）。
- [x] `node scripts/check-sfc-bindings.mjs` PASS。
- [x] `npx oxlint src/views/welcome src/views/login src/components/welcome src/composables src/router src/style` 0 error / 0 warning。
- [x] 帧率采样记录：welcome 36.2fps、terrainOn 52.2fps、terrainOff 60.0fps、technology 60.1fps、welcomeOff 60.1fps（headless Edge SwiftShader，1440×900）。
- [x] 截图存 `preview/audit-enhance/`，提交并推送 `origin master`，回报 commit hash。
