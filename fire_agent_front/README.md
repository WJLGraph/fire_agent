# 焰哨 FlameSentry · 智慧火险预警与多智能体协作平台 —— 前端（fire_agent_front）

> **当前版本**：v1.0.1（含 v1.0.1 后续迭代：前端工程结构重构 / 视觉体系 v2 / 2D-3D 地图迁移 / 知识库原件阅读 / 安全加固与流式可靠性，详见 [10. 版本记录](#10-版本记录)）
> 本项目是「焰哨 FlameSentry · 智慧火险预警与多智能体协作平台」（现实使用名：**焰哨多Agent与可视化平台**）的前端部分，基于 **Vue 3 + Vite + OpenLayers + Three.js + ECharts + Element Plus** 构建。
> 配套后端：[fire_agent_back](https://gitee.com/WJLGraph/Fire_agent_back)（FastAPI + PostgreSQL/PostGIS + LangChain/LangGraph）
> 完整的系统设计文档见后端仓库《整体实现.md》。
> **在线演示**：https://wjl2004.ffuf.cn/　or　https://8.156.67.47/login
> **演示账户**：test / 123456
> **GitHub 仓库**：https://github.com/wjl-cong/fire_agent（欢迎 Star）

---

## 目录

1. [项目简介](#1-项目简介)
2. [技术栈](#2-技术栈)
3. [项目结构](#3-项目结构)
4. [页面功能详解](#4-页面功能详解)
5. [前端 API 模块与后端端点对照](#5-前端-api-模块与后端端点对照)
6. [环境要求](#6-环境要求)
7. [快速启动](#7-快速启动)
8. [构建与部署](#8-构建与部署)
9. [常见问题](#9-常见问题)
10. [版本记录](#10-版本记录)

---

## 1. 项目简介

前端为**前后端分离架构**的 SPA 应用，共 8 个页面路由，覆盖火险治理全流程：

| 页面           | 路由                | 权限     | 核心能力 |
| -------------- | ------------------- | -------- | -------- |
| 登录 / 注册    | `/login`            | 公开     | JWT 登录、注册即登录、`?redirect=` 回跳 |
| 作战大屏       | `/dashboard`        | 登录     | 历史火点 / 预测火险 / 州市边界 / 热力图 / 聚合 / 绘制量测 / 导出 PNG + 4 图表；2D / 3D 地图一键切换（Three.js 数字孪生）；左侧 AI 火情识别侧栏（视觉模型识别 + 历史回看 + Markdown 渲染 + 语音播报） |
| 智能查询       | `/smart-query`      | 登录     | 自然语言 → 意图解析 → 摘要 / 表格 / 图表 / 地图四维联动；查询历史后端持久化（同文本去重）；语音输入自动查询 + 摘要播报 |
| 知识库         | `/knowledge-base`   | 登录     | 文档上传管理 + RAG 问答（流式打字机 + 非流式兜底）+ 引用来源 + 文档全文阅读 + PDF 原件内嵌预览 / 下载；语音提问 + 回答播报 |
| Agent 协作中心 | `/agent-center`     | 登录     | 多 Agent 流水线（7 步，含「人工审核通过」HITL）SSE 节点级流式进度 + 深度思考面板（多轮 thinking_rounds、思考与草稿同显）+ HITL 人工审批（通过 / 编辑 / 驳回）+ 质量评审三态展示 + 任务历史完整回放 + 系统能力面板；语音下发任务 + 报告播报 |
| 报告中心       | `/report-center`    | 登录     | 报告列表 / 详情 / 类型筛选 / 模型名徽标 / 导出 Markdown / HTML / 打印 PDF（删除为软删）；报告语音播报 |
| 个人中心       | `/profile`          | 登录     | 侧栏头像入口，修改邮箱 / 修改密码 |
| 系统管理       | `/admin`            | 仅 admin | 系统总览 / 数据源 / 模型接入（四提供商 + AMD 四类能力 + 百炼免费额度目录 + 额度快照）/ Agent 参数 / 日志 / 用户管理 |

**设计特色**：

- **Agent 风味贯穿全系统**：大屏展示 DataAgent 数据管线状态与 VisionAgent 火情识别侧栏、查询页展示 QueryAgent 解析过程、知识库展示 RagAgent 检索过程、报告中心标识 ReportAgent 生成来源；
- **3D 数字孪生大屏**：`components/map/Map3D.vue`（Three.js）——州市面片挤出 + 侧面扫光 shader + 贝塞尔飞线 + 火点屏幕空间聚类柱（40px 贪心聚类，与 2D OpenLayers Cluster 缩放行为镜像联动），与 2D 地图一键切换；
- **SSE 流式 Agent + HITL 人机协同**：`openTaskStream` 以 `fetch` + `Authorization` 请求头消费节点级流式进度（断线自动降级拉详情，重连首帧 `report_snapshot` 补齐本轮已产出内容），报告草稿经人工「通过 / 编辑 / 驳回」审批后才定稿落报告中心；
- **统一 HTTP 内核**：全站请求收敛到 `api/http.js`（自动 Bearer、401 登出跳转、错误信封解析、上传进度、流式读取），业务页面不再直接写 `fetch`；
- **明暗双主题 + 视觉体系 v2**：`gis-theme.css` token + `theme-v2.css` 视觉层，`html.dark` 切换，首屏提前应用避免闪烁；可通过 `localStorage.fire_agent_theme_v2 = 'off'` 回退旧视觉；
- **全链路语音交互**：`utils/speech.js` 统一封装录音（Web Audio API 采集 PCM → 纯前端编码 WAV）与播报（TTS 音频流播放），五个 AI 页面支持语音输入自动执行、结果一键播报；
- **降级兜底**：大屏后端 API 失败自动降级本地 JSON，核心页面永不白屏；
- **等级同源**：5 级火险颜色 / 文案统一由 `utils/riskLevel.js` 管理，与后端分档完全一致。

---

## 2. 技术栈

| 类别        | 技术                     | 版本      | 用途 |
| ----------- | ------------------------ | --------- | ---- |
| 框架        | Vue 3（Composition API） | ^3.5.13   | 全部页面使用 `<script setup>` |
| 路由        | Vue Router               | ^4.5.0    | 14 条路由记录 + 登录 / 管理员守卫 |
| 状态管理    | Pinia                    | ^3.0.1    | auth store + theme store（token / user / 主题持久化） |
| UI 组件库   | Element Plus             | ^2.9.6    | 表格 / 分页 / 上传 / 消息 / 确认框（中文语言包 + 自动按需导入） |
| 地图引擎    | OpenLayers               | ^10.4.0   | 天地图底图、火点聚合、热力图、边界、绘制量测 |
| 3D 引擎     | Three.js                 | ^0.186.1  | 数字孪生大屏（挤出面片 / 飞线 / 聚类柱 / CSS2D 标签） |
| 空间计算    | Turf.js                  | ^7.2.0    | 绘制面积 / 距离量测 |
| 图表        | ECharts                  | ^5.6.0    | 大屏 4 图表 + 智能查询结果图表（GIS 暗色主题） |
| 热力渲染    | webgl-heatmap            | ^0.2.3    | 火点密度热力图 |
| 构建工具    | Vite                     | ^6.1.0    | dev server + `/api`、`/tianditu` 双代理 |
| 辅助库      | file-saver / moment      | ^2.0.5 / ^2.30.1 | 地图导出、时间处理 |
| 代码质量    | ESLint 9 + oxlint        | dev       | 双 lint（`npm run lint`） |

---

## 3. 项目结构

```
fire_agent_front/
├── vite.config.js                  ← /api 代理到 http://localhost:8000；
│                                       /tianditu 代理天地图并剔除 referer（规避 403）；
│                                       Element Plus 自动导入，@ 别名指向 src
├── .env.example                    ← VITE_TIANDITU_KEY / VITE_AMAP_KEY
├── package.json                    ← 依赖与脚本（dev / build / preview / lint:oxlint / lint:eslint / lint）
└── src/
    ├── main.js                     ← 入口：注册 Pinia / Router / Element Plus 中文包；
    │                                  OpenLayers Canvas willReadFrequently patch；首屏提前应用主题
    ├── App.vue                     ← 轻量路由容器
    ├── router/
    │   ├── index.js                ← 14 条路由记录 + 全局守卫（登录鉴权 + admin 权限）
    │   └── navItems.js             ← 侧栏导航定义（含 adminOnly 过滤，图标名由 AppIcon 渲染）
    ├── layout/MainLayout.vue       ← 主框架：72px 侧栏（图标 + 11px 文字）+ 折叠 + 主题切换 + 头像进个人中心
    ├── stores/
    │   ├── auth.js                 ← 认证状态（token / user → localStorage，login / register / logout / updateUser）
    │   └── theme.js                ← 主题状态（html.dark + html.theme-v2，localStorage 持久化）
    ├── api/                        ← 统一数据层（页面不直接写 fetch）
    │   ├── http.js                 ← HTTP 内核：authFetch / parseJson / get / post / put / del /
    │   │                              postFormJson / postFormWithProgress / postStream
    │   ├── auth.js                 ← PUT /auth/me、PUT /auth/me/password（登录注册由 stores/auth.js 负责）
    │   ├── dashboard.js            ← 大屏历史火点 / 预测火险
    │   ├── query.js                ← 智能查询执行 + 查询历史
    │   ├── rag.js                  ← 文档管理 / 问答 / 问答历史
    │   ├── agent.js                ← 任务 CRUD / 审批恢复 / SSE 流订阅（fetch + Authorization） / 能力与状态
    │   ├── report.js               ← 报告列表 / 详情 / 删除 / 导出
    │   ├── admin.js                ← 系统状态 / 配置 / 日志 / 模型目录 / 额度 / 测试 / 用户
    │   └── vision.js               ← 火情识别 / 图片流 / TTS / ASR
    ├── composables/
    │   ├── useTaskStream.js        ← Agent SSE 订阅（report_snapshot / step / report_think / think_reset / report_delta / approval / report / error + 180ms 增量缓冲批量 flush + 运行期 4s 详情轮询兜底）
    │   ├── useRiskAnalytics.js     ← 火险预警评分 / 等级 / 州市列表 / 预测 GeoJSON / 图表数据源
    │   ├── useRequest.js           ← 请求 loading / error 封装
    │   ├── useResizeObserver.js    ← 图表容器尺寸监听
    │   ├── useCountUp.js           ← 数字滚动动画
    │   └── useThemeTokens.js       ← JS 侧读取主题 CSS 变量
    ├── components/
    │   ├── base/                   ← AppIcon / AppBadge / AppEmpty / AppIconButton / AppPanel /
    │   │                              AppSectionTitle / AppSegmentedControl
    │   ├── common/                 ← HistoryPanel / MarkdownView / SpeakButton / VoiceInputButton
    │   ├── chart/                  ← EChart 封装 / ChartFullscreenDialog
    │   ├── map/
    │   │   ├── Map2D.vue           ← OpenLayers 2D 核心地图（天地图底图 / 聚合 / 热力 / 边界 / 高亮图层）
    │   │   └── Map3D.vue           ← Three.js 数字孪生（挤出面片 / 扫光 / 飞线 / 聚类柱 / CSS2D 标签）
    │   ├── clock.vue               ← 实时时钟
    │   └── SystemCapabilities.vue  ← 系统能力面板（GET /agent/capabilities）
    ├── utils/
    │   ├── speech.js               ← 语音：录音 PCM → 16bit WAV（ASR）+ TTS 播报（480 字截断）
    │   ├── markdown.js             ← Markdown 安全渲染（HTML 转义）
    │   ├── riskLevel.js            ← 5 级火险颜色 / 文案（与后端分档一致）
    │   ├── config.js               ← API_V1 等常量
    │   ├── themeTokens.js          ← 主题 token 读取
    │   ├── llmProviders.js         ← 提供商展示名 / 徽标映射
    │   ├── reportMeta.js           ← 报告类型 / 状态元数据
    │   ├── map3dGeo.js / map3dMaterial.js / map3dTheme.js ← 3D 几何、材质、主题
    │   ├── cityCenter.js / parseGeoData.js / setPointStyle.js / timeWeather.js
    │   ├── draw.js / computed.js / downLoad.js
    │   └── …
    ├── style/
    │   ├── common.css              ← 全局基础样式
    │   ├── gis-theme.css           ← 明暗双主题 CSS 变量 token（html.dark 切换）
    │   ├── theme-v2.css            ← 视觉体系 v2（页头 / 卡片 / 按钮 / 表格 / 发丝线 / 方角徽标）
    │   └── markdown.css            ← Markdown 正文排版
    ├── views/
    │   ├── login/index.vue                     ← 登录 / 注册双模式
    │   ├── dashboard/                          ← 作战大屏（index + 8 个子组件）
    │   │   ├── index.vue
    │   │   ├── AnimNumber.vue                  ← 数字滚动
    │   │   ├── ClusterDrawer.vue               ← 聚合点详情抽屉
    │   │   ├── DashboardTopBar.vue             ← 顶栏（时钟 / 天气 / 视图切换 / 数据管线状态）
    │   │   ├── FireWarningBar.vue              ← 火险预警条（评分 / 等级 / 摘要）
    │   │   ├── MapOverlays.vue                 ← 地图浮层（图例 / 工具）
    │   │   ├── MapToolbar.vue                  ← 底图 / 图层 / 量测 / 导出
    │   │   ├── RailFilterPanel.vue             ← 左栏筛选（州市 / 日期 / 数据类型）
    │   │   └── VisionRail.vue                 ← AI 火情识别侧栏
    │   ├── smart-query/                        ← 智能查询（index + 5 个子组件）
    │   │   ├── index.vue
    │   │   ├── QueryHistoryRail.vue
    │   │   ├── QueryInputPanel.vue
    │   │   ├── QueryParsePanel.vue
    │   │   ├── QueryResultMap.vue
    │   │   └── QueryResultPanel.vue
    │   ├── knowledge-base/                     ← 知识库（index + 6 个子组件）
    │   │   ├── index.vue
    │   │   ├── KbAnswerPanel.vue
    │   │   ├── KbDocReader.vue                 ← 文档全文 / PDF 原件内嵌预览浮层
    │   │   ├── KbDocsPanel.vue
    │   │   ├── KbQaInput.vue
    │   │   ├── KbReferenceList.vue
    │   │   └── KbRetrievalPanel.vue
    │   ├── agent-center/                       ← Agent 协作中心（index + 7 个子组件）
    │   │   ├── index.vue
    │   │   ├── AgentPipeline.vue
    │   │   ├── AgentReportView.vue
    │   │   ├── AgentStreamView.vue
    │   │   ├── ApprovalPanel.vue
    │   │   ├── TaskFormCard.vue
    │   │   └── TaskHistoryList.vue
    │   ├── report-center/                      ← 报告中心
    │   │   ├── index.vue
    │   │   ├── ReportDetailPanel.vue
    │   │   └── ReportListPanel.vue
    │   ├── admin/                              ← 系统管理
    │   │   ├── index.vue                       ← 外壳 + 6 Tab
    │   │   ├── AdminOverview.vue
    │   │   ├── AdminDatasource.vue
    │   │   ├── AdminModel.vue                  ← 模型接入外壳（四提供商）
    │   │   ├── AdminModelAliyun.vue            ← 百炼模型目录 + 免费额度
    │   │   ├── AdminModelAmd.vue               ← AMD 四类能力模型目录
    │   │   ├── AdminModelLongcat.vue           ← LongCat 模型目录
    │   │   ├── AdminModelOllama.vue            ← Ollama 本地模型
    │   │   ├── AdminAgent.vue
    │   │   ├── AdminLogs.vue
    │   │   └── AdminUsers.vue
    │   ├── chart/                              ← 大屏 4 图表
    │   │   ├── historicalFireHazardLevel.vue   ← 历史火险等级分布
    │   │   ├── historicalFireFrequency.vue     ← 历史火点频次
    │   │   ├── proportionFireRiskWarnings.vue   ← 预测火险预警占比
    │   │   └── distributionFireRiskWarning.vue  ← 预测火险分布
    │   └── profile/index.vue                   ← 个人中心
    └── assets/                     ← 本地兜底数据：Yunnan_fire.json / Yunnan_border.json /
                                        predict_2025_2026_daily.json / predict_2025_2026_month.json
```

### 3.1 分层约定

- `views/*` 只做页面编排，复杂区块拆成同目录子组件；重构后**无单文件超过 800 行**。
- 所有后端请求经 `api/*`，页面不直接调用 `fetch`；`api/http.js` 是唯一 HTTP 内核。
- 跨页面复用的纯计算逻辑放 `composables/`（如 `useTaskStream`、`useRiskAnalytics`），不持有地图实例。
- 视觉 token 只从 `gis-theme.css` / `theme-v2.css` 取，不在组件里写死颜色。

### 3.2 历史遗留文件清理

以下早期残留文件（git 未跟踪、无任何页面引用）已于 2026-11-01 统一删除，`unplugin-vue-components` 的 `Map3D` 命名冲突警告随之消除：

- `src/components/map.vue`（已被 `src/components/map/Map2D.vue` 取代）
- `src/components/Map3D.vue`（已被 `src/components/map/Map3D.vue` 取代）
- `src/utils/authFetch.js`（已内联进 `src/api/http.js`）
- `src/utils/echartsGisTheme.js`（已被 `utils/riskLevel.js` 的 `RISK_COLORS` 取代）

---

## 4. 页面功能详解

### 4.1 登录 / 注册页（`/login`）

- 登录 / 注册双模式一键切换，表单校验（用户名 ≥2 字符、密码 ≥6 位、两次密码一致）
- 登录 / 注册成功后自动登录（JWT 存 `localStorage.fire_agent_token`），按 `?redirect=` 回跳原页面
- 登录页不渲染侧栏（BlankLayout），深色玻璃拟态卡片 UI

### 4.2 作战大屏（`/dashboard`）

- **数据流**：`Promise.all` 并发请求历史火点（5000 条上限）/ 逐日预测 / 逐月预测，任一失败自动降级本地 JSON
- **2D 地图**（`components/map/Map2D.vue`，OpenLayers）：天地图底图、火点聚合（Cluster distance=40，点击弹出 `ClusterDrawer` 详情）、webgl 热力图、16 州市边界、多边形 / 线绘制 + Turf.js 量测、导出 PNG
- **3D 数字孪生地图**（`components/map/Map3D.vue`，Three.js）：州市面片挤出 + 侧面扫光 shader + 贝塞尔飞线 + 火点屏幕空间聚类柱（40px 贪心聚类，与 2D 行为镜像联动）+ ExtrudeGeometry 实心基座垫块；明暗双主题、入场俯冲、悬停抬升、`city-click` 高亮 2D 图层；顶栏 2D / 3D 一键切换
- **火险预警**（`FireWarningBar.vue` + `composables/useRiskAnalytics.js`）：基于 `Final_Fire_Index`（逐日）或 `Risk_Score`（逐月）计算整体评分、5 级等级、州市风险列表与动态摘要
- **图表**（ECharts，`views/chart/`）：历史火险等级分布 / 历史火点频次 / 预测火险预警占比 / 预测火险分布；支持全屏查看
- **顶栏**（`DashboardTopBar.vue`）：实时时钟、高德天气、逐日 / 逐月视图切换、DataAgent 数据管线状态
- **左侧 AI 火情识别侧栏**（`VisionRail.vue`，可折叠 34px ↔ 310px）：拖拽上传火场照片 → 视觉模型识别 → 结果 Markdown 渲染（火情判定 / 场景描述 / 严重程度 / 处置建议）→ 语音播报；识别历史点击回看（鉴权图片流），单条删除

### 4.3 智能查询（`/smart-query`）

- 自然语言输入（textarea + Ctrl+Enter + 4 个示例标签）+ 语音输入（录音 → ASR → 自动执行查询）
- **QueryAgent 解析面板**（`QueryParsePanel.vue`）：意图（历史 / 预测 / 摘要）/ 结构化参数 chips / 解析方式徽标（`llm` / `keyword`）/ 解析说明
- **四维结果联动**：摘要卡片（语音播报）/ 表格（动态列 el-table）/ 图表（柱 · 折 · 饼）/ 地图（`QueryResultMap.vue`，GeoJSON 风险分档配色 + 自适应缩放）
- **查询历史侧栏**（`QueryHistoryRail.vue`）：展开 / 折叠、落库后端（同文本自动去重）、按用户隔离、分页、单条删除、解析方式标注、点击回显完整结果

### 4.4 知识库 RAG（`/knowledge-base`）

- **左侧文档面板**（`KbDocsPanel.vue`，折叠式）：拖拽 / 点击上传（PDF / TXT / MD），上传进度条、状态徽标、单条删除、提示词分类
- **右侧问答区**（`KbQaInput.vue` / `KbAnswerPanel.vue`）：示例问题、语音提问（识别完成自动提交）、回答卡片（LLM / 关键词徽标 + 语音播报）
- **检索过程**（`KbRetrievalPanel.vue`）：命中文档 / 分片数 / 检索方式（hybrid / keyword + rerank）展示
- **引用来源**（`KbReferenceList.vue`）：相关性分数 + 点击展开全文
- **文档阅读**（`KbDocReader.vue`）：`GET /rag/documents/{id}/content` 分片拼接全文，纸张式阅读浮层；PDF 走 `GET /rag/documents/{id}/file` 内嵌预览并提供下载原件
- **流式问答**：优先 `POST /rag/ask/stream`（SSE 打字机增量渲染，来源引用随流结束附上），失败 / 不支持自动回退非流式接口兜底

### 4.5 Agent 协作中心（`/agent-center`）

- 任务输入（`TaskFormCard.vue`，textarea + Ctrl+Enter + 示例任务）+ 语音输入（识别完成自动执行任务）
- **Agent 系统状态条**：`GET /agent/status` 6 个 Agent 就绪状态点（含 Reviewer）
- **流水线可视化**（`AgentPipeline.vue`）：拆解任务 → 查询数据 → 分析 GIS → 检索知识 → 生成报告 → 质量评审 → 人工审核通过，步骤逐个点亮（completed 绿 / running 黄脉冲 / pending 灰）；兼容旧任务时第 7 步（人工审核）可按需隐藏；实际后端图为 8 节点（含无 UI 的 `join`）
- **SSE 节点级流式进度**（`composables/useTaskStream.js`）：`openTaskStream` 以 `fetch` + `Authorization: Bearer` 订阅 `GET /agent/tasks/{id}/stream`（token 不进查询参数），实时接收节点进度与 `report_delta` 报告增量（打字机渲染，180ms 批量 flush）；连接首帧 `report_snapshot` 补齐本轮已产出正文 / 思考，流中断自动降级拉取任务详情兜底
- **HITL 人工审批**（`ApprovalPanel.vue`）：报告草稿生成后任务暂停（报告暂不落报告中心），右列审批卡展示草稿，支持**通过并定稿 / 以编辑稿定稿 / 驳回重写（附意见）**，审批后任务继续、报告定稿落报告中心
- **系统能力面板**（`SystemCapabilities.vue`，右列）：展示 `GET /agent/capabilities` 能力清单（LLM / 检查点 / 编排 / 数据 / RAG / 记忆 / MCP / 观测 / 评估 / 降级）
- **执行过程摘要**（`AgentStreamView.vue`）+ Markdown 报告渲染（`AgentReportView.vue`，语音播报）+ ReportAgent 徽标；流水线收起时分析报告卡铺满剩余高度（`flex: 1`，正文自身滚动）
- **任务历史侧栏**（`TaskHistoryList.vue`）：落库后端、点击回放、单条删除；回放链路：本地缓存 → `GET /agent/tasks/{task_id}` 拉取持久化步骤（`agent_task_steps`）与关联报告 → 完整还原

### 4.6 报告中心（`/report-center`）

- 左侧列表面板（`ReportListPanel.vue`，折叠式）：类型筛选（全部 / 日报 / 周报 / 月报 / 专项）+ 分页 + 类型徽标 / 标签 / 摘要 + 单条删除
- **模型名徽标**：列表与详情展示生成模型——`llm_model` 优先（如 qwen-max），无模型名回退供应商名「阿里百炼 / AMD GPU Cloud / LongCat / Ollama」
- **删除为软删**：用户自删仅对自己隐藏（管理员仍可见），管理员删除为全局软删
- 右侧详情（`ReportDetailPanel.vue`）：Markdown 正文渲染 + 语音播报（摘要 + 正文）/ 导出 Markdown / 导出 HTML / 打印另存 PDF / 删除
- ReportAgent 徽标标识 Agent 自动生成的报告

### 4.7 系统管理（`/admin`，仅管理员）

| Tab        | 功能 |
| ---------- | ---- |
| 系统总览   | 版本、数据库状态、LLM 可用性、6 Agent 状态卡片（空值兜底） |
| 数据源     | 数据库地址（脱敏）+ 连接测试 |
| 模型接入   | 四提供商区块（阿里百炼 / AMD GPU Cloud / LongCat / Ollama）：提供商切换、API Key（脱敏 `sk-***xxx`）、模型选择、保存即写 .env 热生效、LLM 真实 invoke 测试；**百炼免费额度目录**（5 大类 Tab：大语言 / 视觉 / 全模态 / 语音 / 向量，实时校验可用性，按「免费优先 → 有效期长 → 当前使用 → 已验证」排序，一键「使用」切换）；**AMD 四类能力目录**（大语言 / 视觉 / 语音合成 / 文档识别，实时抓取 tokenfactory，标注免费 / 限额免费 / 付费）；**LongCat 模型目录**；**百炼额度快照**（5 类 + 账号配额表：剩余量 / 过期时间 / 状态） |
| Agent 参数 | 编排温度 / 报告温度 / 最大 Agent 数 |
| 系统日志   | 环形缓冲 200 条（Agent 任务 / 配置变更 / 用户管理 / 连接测试），30s 轮询自动刷新 |
| 用户管理   | 用户列表、角色修改（防自改）、删除用户（防自删） |

### 4.8 个人中心（`/profile`）

- 侧栏用户头像进入，支持修改邮箱（`PUT /auth/me`）与修改密码（`PUT /auth/me/password`，旧密码校验、两次新密码一致校验）

---

## 5. 前端 API 模块与后端端点对照

> 全部路径前缀 `/api/v1`。`api/http.js` 统一附加 `Authorization: Bearer <token>`；除 `GET /`、`GET /health`、`POST /auth/login`、`POST /auth/register`、`GET /dashboard/summary`（只回聚合计数）外，所有业务接口都要求登录，后端 62 条路由的鉴权口径由 `scripts/check_auth_coverage.py` 逐条校验。
>
> JWT 为 HS256、`exp = iat + 15h` 的滑动会话：已认证响应可能带 `X-Token-Refresh`（CORS `expose_headers` 暴露），前端只在确有用户活动（10 分钟窗口）时吸收并替换本地 token，因此只有连续 15 小时无操作才需重新登录；token 内 `tv` 声明与 `users.token_version` 比对，改密 / 停用后旧 token 立即失效（无 `tv` 的旧 token 视为 0）。

| 前端模块 | 函数 | 方法与端点 |
| -------- | ---- | ---------- |
| `stores/auth.js` | `login` / `register` | `POST /auth/login`、`POST /auth/register` |
| `api/auth.js` | `updateMe` / `changePassword` | `PUT /auth/me`、`PUT /auth/me/password` |
| `api/dashboard.js` | `fetchHistoryFires` / `fetchPredictRisks` | `GET /dashboard/history-fires`、`GET /dashboard/predict-risks` |
| `api/query.js` | `execute` | `POST /query/execute` |
| `api/query.js` | `fetchHistory` / `fetchHistoryDetail` / `clearHistory` / `deleteHistoryItem` | `GET /query/history`、`GET /query/history/{id}`、`DELETE /query/history`、`DELETE /query/history/{id}` |
| `api/rag.js` | `fetchDocuments` / `uploadDocument` / `deleteDocument` | `GET /rag/documents`、`POST /rag/documents`（FormData）、`DELETE /rag/documents/{id}` |
| `api/rag.js` | `fetchDocumentContent` | `GET /rag/documents/{id}/content` |
| `api/rag.js` | `ask` / `askStream` | `POST /rag/ask`、`POST /rag/ask/stream`（SSE） |
| `api/rag.js` | `fetchHistory` / `fetchHistoryDetail` / `clearHistory` / `deleteHistoryItem` | `GET /rag/history`、`GET /rag/history/{id}`、`DELETE /rag/history`、`DELETE /rag/history/{id}` |
| `views/knowledge-base/KbDocReader.vue` | 原件预览 / 下载 | `GET /rag/documents/{id}/file`（直接构造鉴权 URL） |
| `api/agent.js` | `fetchStatus` / `fetchCapabilities` | `GET /agent/status`、`GET /agent/capabilities` |
| `api/agent.js` | `createTask` / `fetchTasks` / `fetchTaskDetail` / `deleteTask` | `POST /agent/tasks`、`GET /agent/tasks`、`GET /agent/tasks/{id}`、`DELETE /agent/tasks/{id}` |
| `api/agent.js` | `resumeTask` | `POST /agent/tasks/{id}/resume`（approve / edit / reject） |
| `api/agent.js` | `openTaskStream` | `GET /agent/tasks/{id}/stream`（SSE，`fetch` + `Authorization` 请求头） |
| `api/report.js` | `fetchList` / `fetchDetail` / `remove` | `GET /reports/list`、`GET /reports/{id}`、`DELETE /reports/{id}` |
| `api/report.js` | `exportRaw` / `buildExportUrl` | `GET /reports/export/{id}?format=md\|html` |
| `api/admin.js` | `fetchStatus` / `fetchConfig` / `updateConfig` | `GET /admin/status`、`GET /admin/config`、`POST /admin/config` |
| `api/admin.js` | `fetchLogs` / `fetchLlmModels` / `fetchBailianQuota` | `GET /admin/logs?limit=100`、`GET /admin/llm/models?provider=aliyun\|amd\|ollama\|longcat`、`GET /admin/bailian/quota` |
| `api/admin.js` | `testDatabase` / `testLlm` | `POST /admin/test/db`、`POST /admin/test/llm` |
| `api/admin.js` | `fetchUsersRaw` / `changeRoleRaw` / `removeUserRaw` | `GET /admin/users`、`PUT /admin/users/{id}/role`、`DELETE /admin/users/{id}` |
| `api/vision.js` | `analyze` / `fetchHistory` / `deleteHistory` / `fetchImageRaw` | `POST /vision/analyze`、`GET /vision/history`、`DELETE /vision/history/{id}`、`GET /vision/image/{id}` |
| `api/vision.js` | `textToSpeechRaw` / `transcribe` | `POST /vision/audio/speech`、`POST /vision/audio/transcriptions` |

**两套流式通道**：

- Agent 进度用 `fetch + ReadableStream`（`api/agent.js#openTaskStream`，`Authorization` 请求头）：不采用 `EventSource` 是因为它无法携带自定义请求头，而 token 放查询参数会落进 Nginx access log；
- RAG 问答同样用 `fetch + ReadableStream`（`api/http.js#postStream`），因为问答需要 POST 提交 query / top_k。

---

## 6. 环境要求

| 组件     | 要求 |
| -------- | ---- |
| Node.js  | **18+**（推荐 20 LTS） |
| npm      | 9+（随 Node 附带） |
| 后端服务 | `fire_agent_back` 运行于 `http://localhost:8000` |
| 浏览器   | Chrome / Edge 现代浏览器（语音能力需安全上下文） |

---

## 7. 快速启动

### 7.1 启动后端（前置条件）

```bash
cd fire_agent_back
conda activate fire_agent_back          # 或你的 Python 环境
uvicorn app.main:app --reload --port 8000
```

后端详细启动步骤见后端仓库 README：https://gitee.com/WJLGraph/Fire_agent_back

后端 `.env` 见后端仓库 `.env.example`：`ENV`（development | production）、`JWT_SECRET`（示例留空，用 `python -c "import secrets;print(secrets.token_urlsafe(48))"` 生成）、`ADMIN_INIT_PASSWORD`（留空）、`CORS_ORIGINS`（JSON 数组）。

### 7.2 启动前端

```bash
cd fire_agent_front
npm install          # 首次安装依赖
npm run dev          # 启动开发服务器
```

启动成功后访问：**http://localhost:5173**

- 默认管理员账号：`admin / 123456`（由后端首次启动时种子创建）
- 未登录会自动跳转到 `/login`
- 前端环境变量见 `.env.example`：`VITE_TIANDITU_KEY`（天地图 Key）、`VITE_AMAP_KEY`（高德 Key）

### 7.3 代理配置说明

开发环境由 Vite 代理解决跨域（`vite.config.js`）：

```js
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
    '/tianditu': {
      target: 'http://t0.tianditu.com',
      changeOrigin: true,
      rewrite: p => p.replace(/^\/tianditu/, ''),
      configure: proxy => {
        proxy.on('proxyReq', req => delete req.getHeaders().referer)   // 剔除 referer，规避天地图 403
      },
    },
  },
}
```

若后端不在 8000 端口，修改 `/api` 的 `target` 后重启 `npm run dev`。

### 7.4 账号与权限

| 账号     | 角色  | 可访问页面 |
| -------- | ----- | ---------- |
| admin    | admin | 全部 8 页（含系统管理） |
| 注册账号 | user  | 除系统管理外的 7 页 |

---

## 8. 构建与部署

```bash
npm run build        # 生产构建，输出 dist/
npm run preview      # 本地预览构建产物
npm run lint         # oxlint + eslint 双检查
```

`vite.config.js` 中 `base: './'`，构建产物可直接放在任意子路径。`dist/` 已被 `.gitignore` 忽略、不随 git 同步，宝塔等服务器部署需在服务器上的前端目录重新构建。Nginx 部署示例：

```nginx
server {
    listen 80;
    root /path/to/fire_agent_front/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;   # SPA 路由回退
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_buffering off;                # SSE 流式不缓冲
        proxy_read_timeout 3600s;
    }
}
```

> SSE（`/agent/tasks/{id}/stream`、`/rag/ask/stream`）要求关闭代理缓冲，否则进度会一次性到达。

---

## 9. 常见问题

| 问题 | 解决方案 |
| ---- | -------- |
| 页面空白 / 数据不显示 | 确认后端已启动（http://localhost:8000/health 返回 ok）；查看浏览器控制台；Ctrl+Shift+R 强刷 |
| 语音输入无反应 | 确认麦克风权限已授予；使用 Chrome / Edge 且页面经 `localhost` 或 HTTPS 访问（`getUserMedia` 需安全上下文） |
| 语音播报失败 | 后端需配置百炼 `LLM_API_KEY`（TTS 主路走百炼，失败自动兜底 AMD OmniVoice）；查看后端 TTS 报错 |
| 登录后跳回登录页 | 检查后端 `JWT_SECRET`（生产要求显式 `ENV=production` 且 `JWT_SECRET` ≥32 字节随机值，空 / 弱 / 公开占位值会启动失败）；清除 `localStorage`（`fire_agent_token` / `fire_agent_user`）后重新登录 |
| 地图底图不显示 | 天地图 Key 失效则更换 `VITE_TIANDITU_KEY`；开发环境下确认 `/tianditu` 代理生效（已剔除 referer） |
| 界面风格突变 / 旧版样式 | 检查 `localStorage.fire_agent_theme_v2` 是否为 `off`；置为 `on` 或删除后刷新即恢复 v2 视觉 |
| 端口被占用 | `npm run dev -- --port 5174`，同时修改后端 `CORS_ORIGINS` |
| npm install 缓慢 | `npm config set registry https://registry.npmmirror.com` |
| 上传 PDF 无文本 | 后端四层提取（pdfplumber → pypdf → PyMuPDF → OCR）可能全部失败，查看后端日志与 `OCR_PROVIDER` 配置 |

---

## 10. 版本记录

### v1.0.1 后续迭代（当前代码状态）

**工程结构重构**

- `api/` 数据层统一：新增 `api/http.js` 内核（`authFetch` / `parseJson` / `get·post·put·del` / `postFormWithProgress` / `postStream`），`utils/authFetch.js` 内联后删除；新增 `api/auth.js`、`api/dashboard.js`、`api/query.js`、`api/rag.js`、`api/agent.js`、`api/report.js`、`api/admin.js`、`api/vision.js`
- `components/` 分层：`base/`（AppIcon / AppBadge / AppEmpty / AppIconButton / AppPanel / AppSectionTitle / AppSegmentedControl）、`common/`（HistoryPanel / MarkdownView / SpeakButton / VoiceInputButton）、`chart/`、`map/`
- 地图组件迁移：`components/map.vue` → `components/map/Map2D.vue`，`components/Map3D.vue` → `components/map/Map3D.vue`
- `views/` 子组件化：大屏 8 个、智能查询 5 个、知识库 6 个、Agent 中心 6 个、报告中心 2 个、系统管理 10 个；重构后无单文件超过 800 行
- `composables/` 抽取：`useTaskStream`（SSE）、`useRiskAnalytics`（火险评分 / 预测 GeoJSON）、`useRequest`、`useResizeObserver`、`useCountUp`、`useThemeTokens`
- 导航外置：`router/navItems.js`（adminOnly 过滤 + 内联 SVG 图标）

**视觉体系 v2 / v0**

- 新增 `src/style/theme-v2.css`：页头、卡片、按钮、表格、发丝线、方角徽标、sunken 底；`html.theme-v2` 生效，`localStorage.fire_agent_theme_v2 = 'off'` 可回退旧视觉
- 侧栏 48px → 72px（图标 + 11px 文字），Emoji / 字符按钮改为 20px 线性 SVG，去掉金属渐变 / 发光 / 弹跳，激活态仅保留 2px 实色条
- 系统管理、Agent 中心、知识库、报告中心、个人中心按 v0 原型重做外壳与卡片体系

**功能增量**

- 知识库：文档全文 `GET /rag/documents/{id}/content`、PDF 原件内嵌预览与下载 `GET /rag/documents/{id}/file`、上传字节进度条
- 列表体验：智能查询历史 / 问答历史 / 报告列表分页与单行紧凑布局
- 系统管理：四提供商区块（阿里百炼 / AMD / LongCat / Ollama）、AMD 四类能力模型一键切换（大语言 / 视觉 / 语音合成 / 文档识别）、链路标注

**安全加固**

- SSE 与鉴权：Agent 进度改 `fetch` + `Authorization` 头（`openTaskStream`），token 不进查询参数；JWT 改 15 小时滑动会话（`X-Token-Refresh`），连续 15 小时无操作才需重登
- 上传校验：后端对上传文件做大小 + 扩展名 + magic bytes 三重校验
- 密钥与日志：`JWT_SECRET` 启动自检（生产拒绝空 / <32 字节 / 仓库公开占位值），日志与错误信息对 key / token 脱敏
- 前端：管理端外链 `:href` 仅放行 https 协议（防 `javascript:`）；大屏取数改走 `authFetch`（修复 401 后恒显示"本地降级数据"）
- 生产环境（`ENV=production`）关闭 `/docs`、`/redoc`

### v1.0.1

- **Agent 协作中心**：v1.0.1 当时用 `EventSource` 消费 SSE 节点级进度（断线降级拉任务详情；后续安全加固已改为 `fetch` + `Authorization` 头订阅）；HITL 审批卡点（报告草稿暂停 → 通过 / 编辑 / 驳回 → resume 后定稿落报告中心）；任务历史后端持久化 + 完整回放；`report_delta` 流式报告渲染；系统能力面板
- **首页 3D 地图**：Three.js 数字孪生——州市面片挤出 + 侧面扫光 shader + 贝塞尔飞线 + 旋转光环 + 上升光柱 + CSS2D 标签；火点屏幕空间聚类柱（40px 贪心聚类镜像 2D OL Cluster，滚轮 120ms 防抖重建，0 火点州市保留基柱 16 区域全覆盖）；ExtrudeGeometry 实心基座垫块填死边界裂缝；明暗双主题；入场俯冲 2.2s、悬停抬升、`city-click`
- **明暗主题系统**：`stores/theme.js` + `style/gis-theme.css` token + `utils/themeTokens.js` 全页面自动适配
- **全链路语音**：`utils/speech.js`（Web Audio PCM→WAV ASR + TTS 播报）接入大屏 AI 识别 / 智能查询 / 知识库 / Agent 中心 / 报告中心
- **报告中心**：类型筛选 + 类型徽标、模型名徽标（`llm_model` 优先，回退供应商名）、用户自删 / 管理员软删
- **知识库**：`/rag/ask/stream` 流式问答 + 非流式兜底
- **智能查询**：查询历史后端持久化（同文本去重）
- **系统管理**：AMD `tokenfactory` 实时模型目录、百炼免费额度目录（5 类）+ 配额快照、配置保存写 .env 热生效、API Key 脱敏、系统日志 30s 轮询
- **个人中心**：新增 `/profile`（侧栏头像入口，改邮箱 / 改密码）
- 配套后端同版本升级：SSE 流式编排、HITL interrupt/resume、Rerank 精排、MCP 天气工具、PostgresStore 记忆、Langfuse 可观测、golden set 评估回归、Docker 交付

### v1.0.0

初版功能：登录注册 / 2D 作战大屏 / 智能查询 / 知识库 RAG / Agent 协作中心基础版 / 报告中心 / 系统管理基础版。

---

*开发者：wjl（19136220923@163.com） · 前端源码：https://gitee.com/WJLGraph/Fire_agent_front · 后端源码：https://gitee.com/WJLGraph/Fire_agent_back*
