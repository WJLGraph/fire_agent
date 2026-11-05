# 焰哨 FlameSentry · 前端展示层重构规划

> 版本：v1.1（主体已实施，转历史存档）
> 范围：`fire_agent_front` 展示层（views / components / layout / style / api / stores）
> 硬约束：**现有功能完全不受影响** —— 不删减业务能力、不改变接口调用结果、不破坏现有交互逻辑
> 说明：阶段 0/3/4/5 已完成并合入 master，阶段 6 部分完成；本文保留重构前的基线与规划原文便于回溯。其中「SSE token 走 query」等基线描述已被后续安全加固取代——现状为 `fetch + Authorization` 请求头订阅、15 小时滑动会话、仅 5 个公开端点。当前事实以 `README.md` / `整体实现.md` 为准。

---

## 0. 阅读约定与脱敏声明

- 本文涉及的所有配置、环境变量、第三方服务 Key，**一律只做占位说明**，不记录、不引用、不输出任何真实值。
- 文中出现的路径均为仓库相对路径（`fire_agent_front/...`、`fire_agent_back/...`）。
- 行号引用基于当前 `master` 工作区快照，仅用于定位问题，实施时以实际代码为准。

---

## 1. 现状梳理与主要问题（重构前基线）

### 1.1 技术栈现状

**前端** `fire_agent_front`

| 维度 | 现状 |
|---|---|
| 框架 | Vue 3.5（`<script setup>` 组合式 API 为主，少量 Options 残留） |
| 构建 | Vite 6，`base: './'`，`@` → `src` 别名 |
| 路由 | vue-router 4，`createWebHistory`，8 条扁平路由 |
| 状态 | Pinia 3，**仅 2 个 store**：`auth`（69 行）、`theme`（44 行） |
| UI 库 | Element Plus 2.9（全量注册 + 中文语言包） |
| 组件解析 | `unplugin-auto-import` + `unplugin-vue-components`（ElementPlusResolver）—— 模板中 `<el-*>` **无需 import** |
| 地图 | OpenLayers 10（2D）+ Three.js 0.186（3D）+ Turf 7（量测）+ 天地图 XYZ 瓦片 |
| 图表 | ECharts 5.6（**裸用，无封装**） |
| 样式 | 原生 CSS/SCSS + 全局 CSS 变量主题（`gis-theme.css`） |
| 其他 | `file-saver`（地图导出）、`moment`、`webgl-heatmap` |
| 外部脚本 | `index.html` 中通过 CDN 引入 ol 4.6.5 / FileSaver / 阿里 iconfont（**与 npm 依赖的 ol 10 并存，属历史遗留**） |
| 质量工具 | ESLint 9 + oxlint（`npm run lint`），**无单测、无 e2e** |

**后端** `fire_agent_back`

| 维度 | 现状 |
|---|---|
| 框架 | FastAPI + SQLAlchemy + Alembic，Postgres 可选 |
| 分层 | `api/v1/routes` → `services` → `repositories` → `models`；`schemas` 做 DTO |
| 多智能体 | `agents/`（orchestrator / data / gis / rag / report）+ `workflows/agent_workflow.py`（LangGraph） |
| 统一响应 | `{ code, message, data }`，`code === 200` 为成功 |
| 鉴权 | JWT Bearer；**重构前基线**中 SSE 端点因 `EventSource` 不能带 Header，token 走 query 参数（现状已改为 `Authorization` 请求头） |

### 1.2 接口契约清单（重构前基线：前端实际调用）

统一前缀：`/api/v1`（由 `utils/config.js` 从 `import.meta.env.VITE_API_BASE` 读取，开发/生产均走同源代理）。

| 模块 | 方法 | 端点 | 前端调用位置 |
|---|---|---|---|
| 认证 | POST | `/auth/login` `/auth/register` | `stores/auth.js` |
| 认证 | PUT | `/auth/me` `/auth/me/password` | `views/profile/index.vue`（**裸 fetch**） |
| 大屏 | GET | `/dashboard/history-fires` `/predict-risks` | `api/dashboard.js` |
| 大屏 | GET | `/dashboard/summary` | **已定义未使用** |
| 智能查询 | POST | `/query/execute` | `views/smart-query/index.vue` |
| 智能查询 | GET/DELETE | `/query/history`、`/query/history/{id}` | 同上 |
| 知识库 | POST | `/rag/ask`、`/rag/ask/stream`（流式） | `views/knowledge-base/index.vue` |
| 知识库 | GET/POST/DELETE | `/rag/documents`、`/rag/documents/{id}` | 同上 |
| 知识库 | GET/DELETE | `/rag/history`、`/rag/history/{id}` | 同上 |
| Agent | POST | `/agent/tasks` | `views/agent-center/index.vue` |
| Agent | GET/DELETE | `/agent/tasks`、`/agent/tasks/{id}` | 同上 |
| Agent | POST | `/agent/tasks/{id}/resume`（HITL 审批） | 同上 |
| Agent | GET | `/agent/tasks/{id}/stream`（**SSE**，基线用 `?token=`，现状走请求头） | 同上 |
| Agent | GET | `/agent/status`、`/agent/capabilities` | 同上 / `components/SystemCapabilities.vue` |
| 报告 | GET | `/reports/list`、`/reports/{id}`、`/reports/export/{id}?format=` | `views/report-center/index.vue` |
| 报告 | DELETE | `/reports/{id}` | 同上；`agent-center` 也调 `/reports/{id}` |
| 视觉/语音 | POST | `/vision/analyze`（图片火情识别） | `views/dashboard/index.vue` |
| 视觉/语音 | GET/DELETE | `/vision/history`、`/vision/history/{id}`、`/vision/image/{id}` | 同上 |
| 视觉/语音 | POST | `/vision/audio/speech`（TTS）、`/vision/audio/transcriptions`（ASR） | `utils/speech.js` |
| 系统管理 | GET/POST | `/admin/config` | `views/admin/index.vue`（**自带本地 authFetch**） |
| 系统管理 | GET | `/admin/status` `/admin/logs` `/admin/users` `/admin/llm/models` `/admin/bailian/quota` | 同上 |
| 系统管理 | POST | `/admin/test/db` `/admin/test/llm` | 同上 |
| 系统管理 | PUT/DELETE | `/admin/users/{id}/role` `/admin/users/{id}` | 同上 |

> **结论**：后端契约清晰、稳定。**本次重构不触碰后端任何一行代码，也不改变以上任何一处 URL、Method、请求体与响应解析逻辑。**

### 1.3 前端目录现状与规模

```
src/  共 16,894 行（.vue/.js/.css）
├─ api/          46 行    只有 dashboard.js
├─ components/ 1,986 行    Map3D(970) SystemCapabilities(528) map(394) clock(94)
├─ layout/      265 行    MainLayout.vue（唯一布局）
├─ router/      102 行    扁平路由表 + beforeEach 守卫
├─ stores/      113 行    auth / theme
├─ style/       832 行    common.css(reset) + gis-theme.css(主题令牌)
├─ utils/       939 行    authFetch / markdown / riskLevel / parseGeoData / speech / ...
└─ views/    12,569 行    dashboard(2309) admin(2085) agent-center(1909)
                          smart-query(1422) knowledge-base(1361) report-center(970)
                          chart/*(1899) login(312) profile(302)
```

**规模失衡信号**：`views/` 占 74%，单文件最大 2,309 行；`components/` 只有 4 个组件且 3 个是"大块头"（地图/3D/能力卡），**没有一层通用 UI 组件**。

### 1.4 页面 / 路由 / 导航现状

| 路由 | 视图 | 根类名 | 主要内容 |
|---|---|---|---|
| `/login` | login | `.login-shell` | 登录/注册切换、表单校验 |
| `/dashboard` | dashboard | `.gis-shell` | 顶栏（标题+天气+时钟+检索+预警）／左：AI 火情识别栏／中：地图(2D/3D)／右：4 图 + 图层/标绘/量测/热力工具栏／底部聚合抽屉 |
| `/smart-query` | smart-query | `.query-shell` | 自然语言查询 + 摘要/表格/图表/地图 四 Tab + 历史 |
| `/knowledge-base` | knowledge-base | `.kb-shell` | 文档管理 + RAG 问答（支持流式）+ 历史 |
| `/agent-center` | agent-center | `.agent-shell` | 发起任务 + 执行链路 + 报告流渲染 + HITL 审批 + 任务历史 |
| `/report-center` | report-center | `.report-shell` | 报告列表 + Markdown 详情 + 导出 md/html + 打印 |
| `/profile` | profile | `.profile-shell` | 资料（邮箱）+ 改密 |
| `/admin` | admin | `.admin-shell` | 6 个 Tab：概览/数据源/模型/Agent 参数/日志/用户（管理员可见） |

导航：`MainLayout.vue` 内**硬编码数组** `allNavItems`（6 项 + admin 过滤），48px 图标侧栏，含主题切换 / 头像跳转 / 退出。

### 1.5 主要问题清单（按严重度）

#### P0 — 结构性问题

**P0-1 页面级巨型组件，职责边界消失**
- `dashboard/index.vue` 2,309 行（script 797 行、template 380 行、style 1,132 行）；`admin` 2,085 行（template 单块 769 行、6 个 Tab 全在一个文件）；`agent-center` 1,909 行。
- 单文件内同时承担：数据获取、业务计算、地图控制、图表配置、DOM 样式、交互状态。**改一处需通读全文**。

**P0-2 图表逻辑四份复制粘贴**
- `views/chart/` 下 4 个文件共 1,899 行，逐行比对后**结构完全一致**：
  `isMaximized / chartRef / maxChartRef / chartInstance / maxChartInstance / initChart / initMaxChart / toggleMaximize / handleResize / currentPage / pageSize / isLoading / paginatedData / handleCurrentChange / handleSizeChange / Teleport 全屏弹窗 / window resize 监听 / 主题 watch 重建`
- 差异仅在：数据源（本地 JSON vs props）、ECharts option、表格列。
- 证据：4 个文件中 `isMaximized` 各 6–7 处、`maxChartInstance` 各 6–11 处、`handleCurrentChange` 各 2 处、`el-pagination` 各 1 处。
- `smart-query/index.vue` 还独立写了**第 5 份** `echarts.init` + resize 监听（第 340 / 453 行）。

**P0-3 三个页面各自重写"历史列表"**
- `agent-center` / `knowledge-base` / `smart-query` 都实现了 `loadHistory` + `deleteHistory`，其中两个还有 `clearHistory`。
- 三份逻辑相似但细节有差异（排序、时间格式化、空态文案、删除确认方式），**已出现行为不一致**。

#### P1 — 一致性与复用问题

**P1-1 没有通用组件层，卡片/面板/徽标/空态被反复重写**
- 每个页面自造一套前缀：`gis-*`（54 处类）、`agent-*`、`kb-*`、`qa-*`、`query-*`、`report-*`、`admin-*`、`profile-*`、`login-*`。
- `panel-card` 只在 `agent-center` 里有（scoped），其余页面各自另起炉灶。
- `views/chart/*.vue` 是**组件却放在 `views/` 下**，且被 dashboard 以相对路径 `../chart/xxx.vue` 引用。

**P1-2 HTTP 层三套实现并存**
- `utils/authFetch.js`（标准版，带 401 跳登录）
- `views/admin/index.vue:20` **内联重写的 authFetch**（逻辑重复但少了 `parseJson` 约定）
- `views/profile/index.vue:30,75` **裸 `fetch`**（手动拼 Authorization，401 不跳转）
- 结果：401 处理行为在三个页面不一致。

**P1-3 API 调用散落在视图中，无统一 service 层**
- `api/` 目录只有 1 个文件 46 行；其余 7 个页面各自定义 `const API_BASE = \`${API_V1}/xxx\`` 并内联 fetch。
- 例外：`views/dashboard/index.vue` 里视觉识别相关 4 个请求也是内联的（第 613–697 行）。

**P1-4 样式：令牌体系已建立，但落地率不足**
- `style/gis-theme.css` 已定义完整令牌（`--gis-bg-* / --gis-glass-* / --gis-accent* / --gis-radius-* / --gis-space-* / --gis-text*`），质量很高。
- 但页面内**硬编码色值泛滥**：`admin` 114 处 hex + 35 处 rgba、`agent-center` 102 + 33、`smart-query` 78 + 30、`knowledge-base` 66 + 27、`report-center` 50 + 10、`dashboard` 57 + 38。
- 深色/浅色切换靠 `html.dark`，但硬编码值不跟随主题，切换后必然出现"局部不换肤"。

**P1-5 Markdown 渲染样式孤立**
- `renderMarkdown`（`utils/markdown.js`）被 3 个页面使用，但 `.markdown-body` 的样式**只写在 `report-center/index.vue:867-950`**（约 15 条 `:deep()` 规则）。
- `agent-center`、`dashboard` 使用 `markdown-body` 类名却拿不到样式 → 渲染表现与报告中心不一致。

**P1-6 命名与归属不一致**
- `components/map.vue`、`components/clock.vue` 小写文件名，与 `Map3D.vue` / `SystemCapabilities.vue` 混用。
- `utils/computed.js` 命名易与 Vue `computed` 混淆（实为 Turf 量测工具）。
- `utils/echartsGisTheme.js` 已从 `riskLevel.js` re-export，属过渡态文件。

#### P2 — 可维护性与工程化

**P2-1 零测试**：无单测、无 e2e、无可视化回归基线 → 重构缺少安全网（见第 6、7 节应对）。
**P2-2 `App.vue` 与 `main.js` 重复 import** `style/common.css`（无害但冗余）。
**P2-3 登录页嵌在 `MainLayout` 内**：`/login` 渲染时左侧 48px 导航与主题/退出按钮仍然可见（当前行为，重构需显式处理，见 4.1）。
**P2-4 历史遗留 CDN 脚本**：`index.html` 引入 ol 4.6.5 与 FileSaver，而 npm 已有 ol 10 / file-saver；同时 `index.html` 里内联 `<style>` 隐藏 OL 控件。
**P2-5 死代码**：`api/dashboard.js` 的 `fetchDashboardSummary` 未被引用；`common.css` 中的 reset 与 Element Plus 部分重叠。
**P2-6 配置合规（需你单独确认）**：源码中存在两处第三方服务 Key 的**硬编码兜底字面量**（`components/map.vue:143`、`views/dashboard/index.vue:530`，值已脱敏不在本文记录）。建议后续收敛到统一配置模块并以占位符表示；**此改动会改变"环境变量缺失时"的运行时行为，默认不在本次重构范围内**，需单独确认后再动。

---

## 2. 重构目标与原则

### 2.1 目标（可度量）

| 目标 | 度量口径 |
|---|---|
| G1 消除重复 | 图表全屏/分页/resize 逻辑 5 份 → 1 份；历史列表 3 份 → 1 份；HTTP 层 3 套 → 1 套 |
| G2 降低单文件复杂度 | 无 `.vue` 文件 > 800 行 —— ✅ **验收时已达成**（最大 756 行）；后续功能迭代后 `agent-center/index.vue` 回升至约 1,845 行，G2 需重新评估 |
| G3 建立通用组件层 | ≥ 8 个通用组件被 ≥ 2 个页面复用 |
| G4 样式令牌化 | 页面内硬编码 hex/rgba 数量下降 ≥ 80%，且浅色/深色切换无遗留不换肤元素 |
| G5 统一 API 层 | 所有请求经 `api/*`，视图中不出现裸 `fetch` / 内联 `API_BASE` |

### 2.2 原则（不可违背）

1. **行为等价（Behavior Equivalence）**：重构前后，相同输入产生相同 DOM 结构、相同网络请求、相同视觉呈现。任何"顺手优化"若会改变表现，一律不做或单独提出。
2. **渐进式（Incremental）**：按阶段推进，每阶段结束都是**可运行、可提交、可部署**的状态。不做"大爆炸式"重写。
3. **可回滚（Reversible）**：
   - 每阶段一个独立分支 + 一个 PR/commit；
   - 新结构以**新增文件**为主，旧文件在阶段验收通过后才删除；
   - 关键页面保留"新旧切换开关"（见 6.3）。
4. **契约冻结**：URL、Method、请求参数、响应解析、`localStorage` 键名（`fire_agent_token` / `fire_agent_user` / `fire_agent_theme`）、路由 path 与 name、**全部保持不变**。
5. **先立新、后拆旧**：先沉淀通用组件与 hooks，再让页面接入，最后才删旧代码。
6. **不动后端**：本次不涉及 `fire_agent_back` 任何文件。
7. **不改配置读取方式**：`import.meta.env.*` 的读取方式与 `.env*` 文件结构保持原样。

### 2.3 非目标（明确排除）

- 不改后端接口、不改数据模型、不改数据库。
- ~~不做视觉风格的重新设计（沿用现有 `gis-theme.css` 令牌与配色）~~ —— **已作废**：视觉重做单列为独立轨道，见 **§10 前端展示效果重做规划**。本章（阶段 0–6）仍只做结构收敛、表现不变。
- 不引入新重型依赖（不引入 Tailwind、不引入 Pinia 之外的状态库、不替换 ECharts 封装库）。
- 不重写地图内核（`map.vue` / `Map3D.vue` 本轮只做"接口收敛与目录归位"，不改渲染逻辑）。
- 不做响应式/移动端适配（当前为桌面指挥端定位，如需另行规划）。

---

## 3. 目标目录结构与职责划分

```
src/
├─ api/                          # 唯一 HTTP 出口（契约冻结层）
│  ├─ http.js                    # 请求内核：baseURL/鉴权/401/错误规范化（由 utils/authFetch 演进）
│  ├─ auth.js                    # /auth/*
│  ├─ dashboard.js               # /dashboard/*（保留并补全）
│  ├─ query.js                   # /query/*
│  ├─ rag.js                     # /rag/*（含流式 fetch reader）
│  ├─ agent.js                   # /agent/*（含 SSE URL 构造）
│  ├─ report.js                  # /reports/*
│  ├─ vision.js                  # /vision/*（图片识别 + TTS/ASR）
│  └─ admin.js                   # /admin/*
│
├─ components/                   # 通用组件层（可被 ≥2 页面复用；不依赖具体业务）
│  ├─ base/                      # 原子级
│  │  ├─ AppPanel.vue            # 面板/卡片容器（原 panel-card / 各页 card 的统一）
│  │  ├─ AppSectionTitle.vue     # 面板标题（含 title-en / 计数徽标 slot）
│  │  ├─ AppBadge.vue            # 状态徽标（LLM/模板/角色/等级标签）
│  │  ├─ AppEmpty.vue            # 空态
│  │  ├─ AppIconButton.vue       # 图标按钮（统一 hover/focus/active/disabled）
│  │  └─ AppSegmentedControl.vue # 分段切换（原 gis-seg / atab / query tab 统一）
│  ├─ chart/
│  │  ├─ EChart.vue              # ★ ECharts 容器：init/dispose/resize/主题重建
│  │  └─ ChartFullscreenDialog.vue # ★ 全屏图表弹窗 + 分页表格（4 图共用）
│  ├─ common/
│  │  ├─ HistoryPanel.vue        # ★ 历史列表（加载/删除/清空/空态，3 页共用）
│  │  ├─ VoiceInputButton.vue    # 语音输入（ASR，3 页共用）
│  │  ├─ SpeakButton.vue         # 语音播报（TTS，5 页共用）
│  │  └─ MarkdownView.vue        # ★ Markdown 渲染 + 统一样式（3 页共用）
│  └─ map/
│     ├─ Map2D.vue               # 原 components/map.vue（归位，逻辑不变）
│     └─ Map3D.vue               # 原 components/Map3D.vue（归位，逻辑不变）
│
├─ composables/                  # 组合式函数（跨页面复用逻辑）
│  ├─ useThemeTokens.js          # 主题 token 响应式取值（含 ECharts 重建）
│  ├─ useRequest.js              # loading/error/竞态序号 统一封装
│  ├─ useResizeObserver.js       # 容器尺寸监听（替代 window.resize）
│  └─ useSpeech.js               # TTS/ASR 状态封装
│
├─ layout/
│  ├─ MainLayout.vue             # 主布局（导航/主题/用户/退出，结构不变）
│  └─ BlankLayout.vue            # 空白布局（供 /login 使用，见 4.1 决策项）
│
├─ router/
│  ├─ index.js                   # 路由实例 + 守卫（行为不变）
│  └─ navItems.js                # 导航配置外置（数据驱动，内容与顺序不变）
│
├─ stores/                       # auth / theme（保持不变，仅可微调）
├─ style/
│  ├─ common.css                 # reset（保留）
│  ├─ gis-theme.css              # ★ 主题令牌（保留并"只增不减"）
│  ├─ tokens.css                 # 语义令牌别名层（新增，可选）
│  └─ markdown.css               # ★ 从 report-center 抽出的全局 Markdown 样式
├─ utils/                        # 纯函数工具（保持不变，仅内部整理）
└─ views/
   ├─ dashboard/
   │  ├─ index.vue               # 编排层（目标 < 300 行）
   │  └─ components/             # DashboardTopBar / FireWarningBar / VisionRail / MapToolbar / ClusterDrawer
   ├─ admin/
   │  ├─ index.vue               # 编排层 + Tab 切换
   │  └─ components/             # OverviewTab / DataSourceTab / ModelTab / AgentParamTab / LogsTab / UsersTab
   ├─ agent-center/
   │  ├─ index.vue
   │  └─ components/             # TaskFormCard / PipelineFlow / ReportStream / ApprovalPanel
   ├─ smart-query/ index.vue + components/
   ├─ knowledge-base/ index.vue + components/
   ├─ report-center/ index.vue + components/
   ├─ login/ index.vue
   └─ profile/ index.vue
```

**职责划分原则**

| 层 | 职责 | 禁止 |
|---|---|---|
| `api/*` | 唯一发请求的地方；负责 URL 拼接、鉴权头、错误规范化 | 不含业务判断、不含 UI 状态 |
| `stores/*` | 跨页面共享状态（auth / theme） | 不膨胀为页面私有状态的垃圾桶 |
| `composables/*` | 无渲染的可复用逻辑 | 不直接操作具体业务 API |
| `components/*` | 无业务耦合的展示组件 | 不 import `api/*`（除 `components/map` 等特例需评审） |
| `views/*/index.vue` | 页面编排：组合子组件 + 注入数据 | 不写大段样式、不写超过 300 行的业务逻辑 |
| `views/*/components/*` | 该页面私有的子组件 | 不被其他页面引用（否则提升到 `components/`） |

---

## 4. 统一方案

### 4.1 页面导航与布局

- **保留** `MainLayout.vue` 的视觉与交互（48px 侧栏、图标+`title` 提示、主题切换、头像、退出）。
- 导航项从组件内硬编码数组 → `router/navItems.js` 导出（**内容、顺序、iconfont 类名、`adminOnly` 过滤逻辑逐项保持一致**）。
- **决策项（需你确认）**：`/login` 目前渲染在 `MainLayout` 内，登录页仍能看到左侧导航与退出按钮。
  - 方案 A（**推荐，默认采纳**）：新增 `BlankLayout.vue`，`/login` 走空白布局，其余不变。→ **会改变登录页视觉**（左侧栏消失）。
  - 方案 B：保持现状完全不动。
  - 因涉及"是否改变表现"，**默认执行方案 B**，除非你明确选择 A。
- 新增页面级 `<router-view>` 过渡**不在本轮范围**（避免引入动效改变感知）。

### 4.2 通用组件规范

统一命名前缀 `App*`（与 Element Plus 的 `el-` 区分），统一约定：

- **Props**：全部显式声明 `type` 与 `default`。
- **样式**：只使用 `--gis-*` 令牌；组件内**不出现** hex / rgba 字面量（确需语义色时引用 `--gis-*` 或 `riskLevel.js` 常量）。
- **状态**：必须覆盖 `default / hover / focus-visible / active / disabled`，列表类另需 `loading / empty / error`。
- **事件**：以 `update:*` + 语义事件命名，禁止透传 DOM 事件名造成歧义。
- **无障碍**：可点击元素带 `title`，纯装饰层加 `aria-hidden="true"`（现有 `gis-grid-layer` / `agent-vignette` 已如此，保持）。

**EChart.vue 契约（P0-2 的统一出口）**

```
props:  option(Object, required), loading(Boolean), height(String)
emits:  ready(instance), click(params)
行为：   挂载 init → dispose 前重建 → 主题 mode 变化时 setOption
        → ResizeObserver 监听容器 → onUnmounted dispose
约束：   ★ option 的计算逻辑仍在各图内（保持原有图表配置一字不改），
          仅"容器/生命周期/主题响应/resize"被抽走
```

**ChartFullscreenDialog.vue 契约**

```
props:  modelValue(全屏开关), title, columns(表格列), rows(表格数据), option
行为：   Teleport to body + 全屏图表 + 分页表格（page/pageSize/loading 内置）
约束：   ★ 现有 4 图的分页默认值（pageSize=20）、加载态、关闭按钮位置保持原样
```

### 4.3 样式规范

1. **令牌唯一来源**：`style/gis-theme.css` 的 `--gis-*` 全量保留，**只增不减**；新增令牌命名沿用现有语义（`--gis-accent-soft` 这类）。
2. **硬编码清零**：组件/页面内 hex 与 rgba 逐步替换为令牌；确属"语义色"（火险五色、成功/警告/危险）的，统一从 `utils/riskLevel.js` 或新增 `style/semantic.css` 取，禁止就地写死。
3. **Markdown 样式全局化**：把 `report-center/index.vue:867-950` 的 `.markdown-body :deep(...)` 规则整体迁入 `style/markdown.css`，并在 `main.js` 全局引入 → 使 agent-center / dashboard 的 Markdown 与报告中心一致。
   - ⚠️ 注意：这会让 agent-center 与 dashboard 的 Markdown **样式发生变化（从无样式到有样式）**。属"修复既有不一致"，若你要求严格像素级不变，请告知，我将改为"仅报告中心保留"的保守方案。
4. **页面私有样式**：随组件下沉到 `views/*/components/*.vue` 的 `<style scoped>`；`index.vue` 只保留布局骨架样式。
5. **命名**：BEM 化的小写连字符（沿用现有 `gis-*` 风格），禁止再新增 `qa-` / `vrd-` / `fw-` 这类页面私有缩写前缀（旧的在拆分时随组件一并重命名或保留在私有组件内）。

### 4.4 API 层与状态

- `api/http.js` 作为唯一内核，**完整继承** `utils/authFetch.js` 现有行为：附加 `Authorization: Bearer`、401 → `auth.logout()` + 跳 `/login`（带 `redirect`）、`parseJson` 的 `code !== 200` 抛错规则。
- `views/admin/index.vue` 的内联 authFetch 与 `views/profile/index.vue` 的裸 fetch **统一接入** `api/*`。
  - ⚠️ profile 接入后会新增 401 跳转行为（原为不跳转）。这是**修复既有不一致**，如要求严格等价请告知。
- 流式请求（`rag/ask/stream`）与 SSE（`agent/tasks/{id}/stream`）保持读取循环不变，仅把 URL 构造搬进 `api/*`。（现状：SSE 已由安全加固改为 `fetch + Authorization` 请求头，见 `docs/安全加固方案.md` §2.5）
- Pinia store 维持现状（auth / theme），**不新增全局 store**；页面私有状态留在页面/composable 内。

---

## 5. 分阶段迁移步骤

> 每个阶段 = 一个分支 + 一次验收 + 一次提交。任一阶段验收不通过即回退，不进入下一阶段。
> 分支命名建议：`refactor/stage-N-<简述>`

### 阶段 0：安全网与地基（无表现变化）✅ **已完成** `cda43d5`

> 实际完成内容：`docs/refactor-baseline/network.md`（网络基线）+ `build-baseline.txt`（构建基线）；新增 3 个 composable 与 `style/markdown.css`，均未被引用。
> 注：截图基线（第 1 项）因本机无浏览器自动化环境暂缺，改用「构建基线 + 网络基线 + 逐人工验收」替代。

**范围**
1. 建立基线：本地启动前端 + 后端，对 8 个页面逐页截图（浅色/深色各一套），存 `docs/refactor-baseline/`，作为视觉回归对照。
2. 记录网络基线：用浏览器 DevTools 导出各页面请求清单（URL/Method/状态码/响应结构），存 `docs/refactor-baseline/network.md`。
3. 新增 `composables/useThemeTokens.js`、`composables/useResizeObserver.js`（纯新增，无人引用）。
4. 新增 `style/markdown.css`（内容从 report-center 复制，暂不引入 main.js）。

**验收**：`npm run lint` 通过；`npm run build` 产物与基线一致（无新增文件被打包引用）；页面表现零变化。

---

### 阶段 1：API 层收敛（无表现变化，除 401 一致性）

**范围**
1. 新增 `api/http.js`（由 `utils/authFetch.js` 演进，**保留原文件与导出**以免误伤）。
2. 新增 `api/{auth,dashboard,query,rag,agent,report,vision,admin}.js`，逐个搬运现有 URL 与参数构造。
3. 改造 7 个视图：删除内联 `API_BASE` 与 fetch，改为 import `api/*`。
4. 删除 `views/admin/index.vue` 内联 authFetch；`views/profile/index.vue` 裸 fetch 改走 `api/auth.js`。

**顺序**：`dashboard` → `report-center` → `knowledge-base` → `smart-query` → `agent-center` → `admin` → `profile`（由易到难）。

**验收**：逐页比对网络面板 —— **URL、Method、请求体、响应解析结果与基线完全一致**；`utils/authFetch.js` 暂留不删。

---

### 阶段 2：通用组件沉淀（新增文件，旧代码不动）

**范围**
1. `components/base/`：`AppPanel` / `AppSectionTitle` / `AppBadge` / `AppEmpty` / `AppIconButton` / `AppSegmentedControl`。
2. `components/chart/`：`EChart.vue` + `ChartFullscreenDialog.vue`。
3. `components/common/`：`MarkdownView.vue` / `HistoryPanel.vue` / `VoiceInputButton.vue` / `SpeakButton.vue`。
4. `components/map/`：`Map2D.vue`（原 `components/map.vue` 重命名归位）、`Map3D.vue` 移入。

**验收**：组件独立可用（可临时挂一个 demo 路由验证，验证后删除）；`npm run build` 通过；**现有页面此时仍用旧代码，表现零变化**。

---

### 阶段 3：图表层接入（P0-2 收口，风险最高）✅ **已完成** `d7fc126`

> 按计划顺序逐个接入逐个验证，净减 **926 行**（+208 / −1134）。四个图的 `option` 计算内容逐字保留。
>
> **落地偏差（均为必要的等价性修正）**
> 1. `proportionFireRiskWarnings` / `distributionFireRiskWarning` 原用 `chartTokens()` **无参调用**（非响应式），其重绘依赖 `watch(searchDate/viewMode)` + `watch(theme.mode)`。改为 computed 后必须显式写 `chartTokens(theme.mode)` 建立响应式依赖，否则主题切换后图表颜色不刷新。
> 2. 原靠 `watch` + `requestAnimationFrame` 双帧补.layout 的写法，改由 `EChart` 内的 `ResizeObserver` 接管（`scheduleMaxChartLayout` 删除）。
> 3. `ChartFullscreenDialog` 增加**列插槽转发**（`col.slot`），否则置信度/火险等级的 `el-tag` 渲染无法迁移；`EChart` 增加 `height=""` 语义（不写内联高度），保证 smart-query 图表容器的 flex 布局与原 DOM 完全一致。
> 4. 全屏表格容器由原 `#fff`/`#ebeef5` 硬编码白底改为 `--gis-*` 令牌 —— **这是一处预期内的表现变更**（原实现在深色模式下全屏表格仍是白底黑字，属既有不一致），已在阶段 3 顺带消除。

**范围**
1. `views/chart/` 4 个文件**不动目录**（避免路径引用风险），改为内部接入 `EChart` + `ChartFullscreenDialog`：
   - 删除各自的 init/dispose/resize/主题 watch/分页/全屏模板；
   - **完整保留**各自的 `option` 计算逻辑与表格列定义。
2. `smart-query/index.vue` 的图表同样接入 `EChart`（删除其第 340 行 init 与第 453 行 resize 监听）。

**顺序**：`historicalFireFrequency`（最简单）→ `historicalFireHazardLevel` → `proportionFireRiskWarnings` → `distributionFireRiskWarning` → `smart-query`。**逐个接入、逐个验证**。

**验收**：4 图 + 全屏弹窗 + 分页 + 主题切换重建，逐项对照基线截图；`smart-query` 图表 Tab 表现一致。
> 静态验收已通过：`src` 内 `echarts.init` 归零（仅剩注释提及）、四个图 props 契约（`fireData` / `searchDate` / `viewMode` / `predictData`）与 dashboard 调用点完全未变、`npm run build` 通过。**运行时验收（全屏弹窗 / 翻页 / 主题切换重建）需人工过一遍。**

---

### 阶段 4：页面拆分 ✅ **已完成并合入 master（验收时 G2 达成：无 `.vue` > 800 行）**

> **已落地**（8 次提交：`74e7017` / `9c2e4b7` / `62fb364` / `d82a106` / `277d96c` / `4276fb8` / `917318e` / `9534eda`，均已在 `master`）
> - **admin**（`74e7017`）：2,046 行 → 外壳 287 + 6 个子组件（Overview/Datasource/Model/Agent/Logs/Users）。
> - **agent-center**（`9c2e4b7`）：1,895 行 → 父 854 + 7 个受控子组件（TaskFormCard/TaskHistoryList/AgentPipeline/AgentStepTrace/AgentStreamView/AgentReportView/ApprovalPanel）。
> - **dashboard**（`62fb364`）：2,304 行 → 父 1,013 + 5 个子组件（DashboardTopBar/FireWarningBar/VisionRail/MapToolbar/ClusterDrawer）。
>
> **dashboard 落地要点**
> - 父组件只保留「数据编排 + OpenLayers 实例生命周期」；地图工具全部受控，子组件只渲染 + 上抛事件，
>   **OL 实例不跨组件传递**（这是避免实例生命周期被破坏的关键）。
> - `VisionRail` 是唯一完全自包含的区块：`vision*` 状态与识别请求整体迁入，
>   `onMounted` 拉历史、`onUnmounted` 调 `cleanupSpeech`，与父原生命周期同点。
> - 天气（`amapKey` + `fethLocation`）随顶栏下沉，**读取方式未改动**。
> - 守恒校验：26 个函数 1:1（仅 `handleResetView` 为内联三元提取为函数的预期新增）；
>   `class` / `:class` / `:style` **三项完全一致**；CSS 124 个类名零丢失、括号平衡。
>
> **阶段 4d–4h：G2 收官（剩余 4 个超标文件全部压到 800 行以内）**
> - **smart-query**（`d82a106`）：1,396 → 父 434 + 5 子组件（QueryHistoryRail / QueryInputPanel / QueryParsePanel / QueryResultPanel / QueryResultMap）。
>   OL 地图实例整体下沉到 `QueryResultMap`，原「点击地图 Tab → `nextTick(renderMap())`」改为「Tab 挂载即渲染」，等价。
> - **knowledge-base**（`277d96c`）：1,347 → 父 407 + 5 子组件（KbDocsPanel / KbQaInput / KbAnswerPanel / KbRetrievalPanel / KbReferenceList）。
>   流式打字机与终态结果合并进 `KbAnswerPanel`，条件与原来两个独立 `v-if` 完全一致。
> - **AdminModel**（`4276fb8`）：1,270 → 父 292 + 4 子组件（Aliyun / Amd / Ollama / Longcat），按提供商区块切。
>   `configForm` 仍以 props 传入并由子组件直写属性，与原单文件实现等价。
> - **report-center**（`917318e`）：964 → 父 311 + 2 子组件（ReportListPanel / ReportDetailPanel），
>   类型与 Provider 标签映射提取为 `utils/reportMeta.js`（消掉列表/详情两处重复）。
> - **agent-center**（`9534eda`）：854 → 756，SSE 订阅整段搬入 `composables/useTaskStream.js`（状态与回调经 `ctx` 注入）。
> - **dashboard**（`9534eda`）：1,013 → 740，`fireWarning` / `processedPredictData` / `cityRiskData` / `predictDataForChart`
>   搬入 `composables/useRiskAnalytics.js`，州市中心坐标搬入 `utils/cityCenter.js`。
> - **Map3D**（`9534eda`）：971 → 737，投影/几何/聚合搬入 `utils/map3dGeo.js`，两个 shader 与 `disposeGroup`
>   搬入 `utils/map3dMaterial.js`，双主题配色搬入 `utils/map3dTheme.js`；**渲染内核逻辑一字未改**（符合 2.3 非目标）。
>
> **G2 验收时状态**：`src` 下最大 `.vue` = `agent-center/index.vue` 756 行，当时全项目 0 个文件 > 800 行；后续功能迭代该文件已增至约 1,845 行，需重新拆分。

> **CSS 拆分手法（可复用）**：`<style scoped>` 近似扁平时可写脚本按「类名 → 归属组件」自动切分，配合
> 函数守恒 / class 守恒 / 类名覆盖 + 括号平衡三项校验，比手工搬运可靠得多。
> 两个必须注意的点：
> 1. `@media` / `@keyframes` **必须整块分发**（`@keyframes` 按动画名归属，`@media` 按块内类名归属并可多份）。
>    否则会抽出缩进子规则、留下孤儿 `}`，构建直接 `postcss Unexpected }`。
> 2. dashboard 用的是 **scss（含嵌套）**，需按花括号计数切顶层块，不能按行首缩进切。

**范围与顺序**
1. **dashboard**（2,309 行）：
   - `DashboardTopBar.vue`（顶栏：标题/天气/时钟/数据模式/检索）
   - `FireWarningBar.vue`（火险预警摘要 + 州市详情）
   - `VisionRail.vue`（AI 火情识别侧栏，含上传/历史/播报）
   - `MapToolbar.vue`（图层/标绘/量测/热力/导出）
   - `ClusterDrawer.vue`（聚合点详情抽屉）
   - `index.vue` 保留编排 + 数据计算（`processedPredictData` / `cityRiskData` / `displayFireData` / `fireWarning`）
2. **admin**（2,085 行）：6 个 Tab → 6 个子组件。
3. **agent-center**（1,909 行）：`TaskFormCard` / `PipelineFlow` / `ReportStream` / `ApprovalPanel`。

**约束**：拆分是**纯搬运**——模板、类名、样式、事件处理函数逐字迁移；禁止在拆分过程中"顺手改样式/改逻辑"。

**验收**：三页逐区域截图比对；所有交互（地图工具、标绘、量测、热力、导出 PNG、SSE 流式、HITL 审批、Tab 切换）逐项回归。

---

### 阶段 5：样式令牌化与收尾 ✅ **已完成并合入 master**

> **已落地**
> - **令牌化 G4**：`<style>` 段硬编码色值 **720 → 60 处**（下降 **91.7%**，目标 ≥80%）。
> - **关键决策（零回归）**：新增语义令牌的取值**逐一等于替换前的硬编码值**，且 `:root`（浅色）
>   与 `html.dark` 同值 —— 因此替换后两种主题下的表现**完全不变**。
>   这批令牌是当前视觉的"快照"，**§10 视觉轨道重做配色时只需改 `gis-theme.css`，不必再碰 30 个页面文件**。
> - 新增令牌：`--gis-surface-1/2/3`、`--gis-ink{,-muted,-subtle,-dim,-strong,-deep}`、
>   `--gis-brand{,-light,-lighter}`、`--gis-risk-1..5`（与 `riskLevel.js` 的 `RISK_COLORS` 严格一致），
>   以及配套 `*-rgb` 三元组（供 `rgba(var(--x-rgb), 0.08)` 带透明度复用）。
> - **替换严格限定在 `<style>` 段内**：`<script>` 中的 ECharts option / OpenLayers 热力图色值是 canvas
>   配置，不可用 CSS 变量；`components/map/*`（地图 canvas 配色体系独立）排除在外。
> - 刻意保留 60 处：`#f87171` / `#fbbf24` 等 EP 状态色派生、`#fff` / `#000`、一次性装饰色
>   （语义多义，强行映射反而易误伤）。
>
> **收尾项**
> - `utils/authFetch.js` 实现内联进 `api/http.js` 后删除 → HTTP 出口真正唯一。
> - `utils/echartsGisTheme.js` 删除：两图改为直接 `import { RISK_COLORS } from '@/utils/riskLevel'`
>   （火险五级色仍唯一来自 `riskLevel.js`，符合 R7 白名单）。
> - 删除无引用的 `api/dashboard.js#fetchDashboardSummary`。
> - `style/markdown.css` 接入 `main.js`（D2：Markdown 样式全局化）。
> - 删除 `App.vue` 中与 `main.js` 重复的 `common.css` import。
> - 导航配置外置为 `router/navItems.js`（`path/label/icon/adminOnly` 契约逐字不变）。
> - `providerName` **三份重复**（TaskHistoryList / AgentStepTrace / SystemCapabilities）
>   提取为 `utils/llmProviders.js`。

**范围**
1. 页面内硬编码 hex/rgba → 令牌替换（按 G4 目标 ≥80%）。
2. `style/markdown.css` 接入 `main.js`（见 4.3 第 3 条决策项）。
3. 清理：`utils/authFetch.js`（确认无引用后删除）、`utils/echartsGisTheme.js`（若仅剩 re-export 则删除并改引用）、`App.vue` 重复 import、`fetchDashboardSummary`（确认无用后删除或保留待用）。
4. `router/navItems.js` 外置导航配置。
5. 补齐组件状态（hover/focus/active/disabled/loading/empty/error）。

**验收**：浅色/深色双主题逐页走查无遗留不换肤元素；`npm run lint` + `npm run build` 通过。

---

### 阶段 6（可选）🟡 **部分完成**

| 项 | 状态 | 说明 |
|---|---|---|
| 引入 `ResizeObserver` 替代 `window.resize` | ✅ 已完成 | smart-query 地图容器改用 `useResizeObserver`（精确到容器；`v-if` 晚挂载由内置 `watch` 兜住，不支持时降级 `window.resize`）。`src` 内 `window.addEventListener('resize')` 已清零 |
| 登录页 `BlankLayout` 切换 | ⏸ 未做 | 属**视觉/布局表现**改动，归入 §10 视觉轨道一并处理 |
| 第三方 Key 硬编码兜底收敛 | ⏸ 未做 | 会改变"环境变量缺失时"的运行时行为，规划已明确**排除出本轮**，需单独拍板 |
| `index.html` 历史 CDN 脚本清理 | ⏸ 未做 | 规划 6.2 明确"**本轮不动**"，避免破坏仍依赖全局 `ol` / `saveAs` 的代码路径 |

---

## 6. 风险点、兼容性考虑与回退策略

### 6.1 风险登记册

| # | 风险 | 影响 | 概率 | 应对 |
|---|---|---|---|---|
| R1 | 拆分 dashboard 时丢失地图/标绘/量测/热力的实例引用（`map`、`drawSource`、`measureSource`、`heatMapLayerInst` 为模块级 `let`） | 地图交互失效 | 高 | 拆分时**严禁**把这些变量搬进子组件各自作用域；统一留在 `index.vue` 或收敛为 `useMapTools` composable，通过 props/emit 传递。先拆无地图依赖的 `FireWarningBar` / `ClusterDrawer` 试水 |
| R2 | ECharts option 在容器复用/dispose 时序下出现空白图 | 图表不渲染 | 中 | `EChart.vue` 内 `dispose` + `init` 顺序严格对齐现有 `initChart`；接入后立即单图验证 |
| R3 | 主题切换后图表未重建 | 深浅切换后图表配色错乱 | 中 | 复用现有 `watch(() => theme.mode)` 机制，迁移到 `EChart.vue` 内部；四图逐一验证 |
| R4 | SSE（agent）与流式（rag）被"统一封装"破坏 | 实时进度/打字机失效 | 中 | **只搬 URL 构造，不改读取循环**；阶段 1 明确排除对这两个调用的改造 |
| R5 | Element Plus 自动导入（`unplugin-vue-components`）在新组件中失效 | 组件未渲染 | 低 | 新组件统一放在 `src/components/` 下（已被 resolver 扫描）；不在 `node_modules` 或 ignored 路径建组件 |
| R6 | 样式作用域（`scoped` + `:deep()`）在拆分后变化，导致 Element Plus 覆盖样式失效 | 控件外观变化 | 中 | 拆分时连同 `:deep()` 规则一起搬；搬完立即比对控件截图 |
| R7 | 硬编码色值替换时误替换"语义色"（火险五色） | 风险等级配色错乱 | 中 | 火险五色只允许来自 `utils/riskLevel.js`；替换前先 grep 出所有 `RISK_COLORS` 相关用法作为白名单 |
| R8 | `localStorage` 键或路由 path/name 被无意修改 | 登录态丢失、书签失效 | 低 | 契约冻结清单（6.4）逐项 grep 校验 |
| R9 | 无自动化测试兜底 | 回归漏测 | 高 | 阶段 0 建立截图 + 网络双基线；每阶段按第 7 节清单人工逐项勾选 |
| R10 | 仓库当前 `git status` 干净但无分支保护 | 误推 master | 低 | 全程在 `refactor/stage-N-*` 分支，仅在阶段验收通过后合并 |

### 6.2 兼容性考虑

- **浏览器**：维持现状目标（Chromium 现代版 + `backdrop-filter`）；不引入需要 polyfill 的新 API（`ResizeObserver` 若使用需确认目标浏览器支持，否则保留 `window.resize`）。
- **Element Plus 2.9**：不升级大版本；不引入 Tailwind 等会与 EP 变量冲突的方案。
- **Vite 6 / Vue 3.5**：不升级；`vite.config.js` 的 `base: './'`、dev proxy（`/api`、`/tianditu`）**保持不变**。
- **构建产物**：`base: './'` + `createWebHistory` 的组合已在线上运行，**路由创建方式不得改动**（否则部署路径会变）。
- **CDN 依赖**：`index.html` 的 ol 4.6.5 / FileSaver / iconfont 本轮**不动**（P2-4 移出范围），避免破坏可能仍在依赖全局 `ol` / `saveAs` 的代码路径。
- **`index.html` 内联 `<style>`**（隐藏 `.ol-attribution` / `.ol-zoom`）：保留。
- **环境变量**：`.env.development` / `.env.production` / `.env.example` 与其读取方式（`import.meta.env.VITE_*`）**完全不变**。

### 6.3 回退策略

1. **分支级回退**：每阶段一个分支；验收不通过 → 丢弃该分支，`git checkout master` 即完全复原。
2. **文件级回退**：阶段 2（组件沉淀）之后的所有改造，都是"新文件 + 旧文件切换引用"，可通过改一行 import 回退。
3. **开关级回退**：对 dashboard / admin / agent-center 三个高风险页面，保留旧文件副本（如 `views/dashboard/index.legacy.vue`）并在路由处加一行注释化的切换开关，直到阶段 4 验收通过后随分支合并一并删除。
4. **构建级回退**：保留阶段 0 的 `dist/` 基线产物副本，紧急情况下可直接回滚部署。

### 6.4 契约冻结清单（每阶段结束 grep 校验）

- [ ] 路由 `path` 与 `name`：`/login /dashboard /smart-query /knowledge-base /agent-center /report-center /profile /admin`
- [ ] `localStorage` 键：`fire_agent_token`、`fire_agent_user`、`fire_agent_theme`
- [ ] 主题机制：`html.dark` class 增删（`stores/theme.js` 的 `applyTheme`）
- [ ] 请求前缀：`VITE_API_BASE` → `/api/v1`
- [ ] 401 处理：`auth.logout()` + 跳 `/login?redirect=`
- [ ] 成功判定：`json.code === 200`
- [ ] SSE：`GET /api/v1/agent/tasks/{id}/stream`（重构前基线为 `?token=`；现状已改为 `Authorization` 请求头）
- [ ] 导航项：`icon-ditu01 / icon-jingweidu / icon-023tuceng / icon-duobianxing / icon-relitu / icon-radio-on`

---

## 7. 验收清单（逐项确认功能与原有表现一致）

> 使用方式：每阶段结束后执行，全部勾选方可进入下一阶段。
> 前置条件：后端已启动、前端 dev 可访问、`docs/refactor-baseline/` 基线已就位。

### 7.0 通用门禁（每阶段必过）

- [ ] `npm run lint` 无 error
- [ ] `npm run build` 成功，无新增警告/错误
- [ ] 浏览器 Console 无新增 error / warning
- [ ] Network 面板：请求 URL、Method、状态码、响应体结构与基线一致（**阶段 1 尤其严格**）
- [ ] 浅色 / 深色双主题下，页面截图与基线的差异项均已逐条说明并判定可接受

### 7.1 登录 / 注册（`/login`）

- [ ] 登录成功 → 跳 `/dashboard`；带 `?redirect=` 时跳回原路径
- [ ] 注册成功 → 自动登录并跳转
- [ ] 校验：用户名 ≥2、密码 ≥6、两次密码一致、空值提示
- [ ] 密码眼睛按钮显示/隐藏；回车提交
- [ ] 未登录访问任意页面 → 重定向 `/login`（含 redirect 参数）
- [ ] 非管理员访问 `/admin` → 提示"需要管理员权限"并跳 `/dashboard`
- [ ] 退出登录后 `localStorage` 三项被正确清理

### 7.2 作战大屏（`/dashboard`）

- [ ] 顶栏：主/副标题、实时时钟、天气（定位成功/失败两态）、DataAgent 管线状态三态（`同步数据中… / 后端数据 / 本地降级`）
- [ ] 数据模式切换：历史火点 ↔ 预测火险；预测态下逐日/逐月切换
- [ ] 日期选择器禁用范围正确（历史 2021–2025 / 预测 2025–2026）；州市下拉来自边界 GeoJSON
- [ ] 检索：定位州市 + 按日期筛选，地图与图表同步刷新
- [ ] 火险预警：摘要条颜色/图标/文案正确；展开详情后州市卡片（等级标签、描述、措施）正确
- [ ] 地图 2D / 3D 切换正常；3D 州市点击回调正常
- [ ] 地图工具：图层显隐、标绘（点/线/面）、量测（距离/面积）、清空标绘、热力图分析、导出 PNG
- [ ] 聚合点点击 → 抽屉打开，火点详情表格数据与导出正确
- [ ] 鼠标坐标显示；底图（天地图）加载正常
- [ ] AI 火情识别侧栏：展开/折叠、上传、识别、历史加载、历史删除、图片回显、语音播报、Markdown 渲染
- [ ] 4 个图表：小图数据/配色正确；全屏按钮 → 弹窗图表 + 分页表格；分页切换与每页条数；关闭后小图 resize 正常
- [ ] 主题切换后：页面配色 + 4 个图表配色同步更新

### 7.3 智能查询（`/smart-query`）

- [ ] 自然语言执行 → 摘要 / 表格 / 图表 / 地图 四个 Tab 内容正确
- [ ] 解析过程展示（intent / params / method = llm|keyword）标签正确
- [ ] 图表 Tab：ECharts 渲染 + resize；地图 Tab：OpenLayers 渲染 + 边界
- [ ] 历史：加载、点击回填、单条删除、清空全部
- [ ] 语音输入（录音 → 识别 → 自动执行）
- [ ] 示例问句点击填入；加载态与空态

### 7.4 知识库（`/knowledge-base`）

- [ ] 文档列表加载 / 上传 / 删除；上传中 loading
- [ ] 问答：非流式与流式两条路径结果一致（流式打字机正常、可中断）
- [ ] 引用来源展示；`llm_used` 标识
- [ ] 历史：加载、回填、单条删除、清空
- [ ] 语音输入 + 语音播报

### 7.5 Agent 协作中心（`/agent-center`）

- [ ] 发起任务（含 Ctrl+Enter、示例标签点击）；执行中 loading
- [ ] SSE 实时链路：步骤状态（pending/running/completed/skipped/failed）与图标正确
- [ ] 报告流式渲染（`report_delta` 打字机 + 终态以 DB 为准 + 轮次递增清缓冲）
- [ ] HITL 审批：`awaiting_approval` 时展示草稿与评审意见；approve / edit / reject 三种动作
- [ ] 报告 Markdown 渲染与样式
- [ ] 任务历史：列表、状态文案、LLM/模型/模板徽标、点击加载、删除
- [ ] Agent 状态与系统能力卡片数据正确
- [ ] 语音输入任务

### 7.6 报告中心（`/report-center`）

- [ ] 列表分页（page / page_size）+ 类型筛选（全部/日报/周报/月报/专项）
- [ ] 详情加载（含 404 错误态）与快速切换的竞态防护（`detailSeq`）
- [ ] Markdown 渲染完整：标题/段落/列表/引用/代码块/表格/链接
- [ ] 导出 Markdown、导出 HTML、打印预览（新窗口）
- [ ] 删除确认与刷新

### 7.7 个人中心（`/profile`）

- [ ] 资料展示（用户名/角色/邮箱/创建时间）与邮箱保存（同步更新 store）
- [ ] 修改密码：旧密码校验、两次一致、成功/失败提示
- [ ] 角色标签（管理员/普通用户）与时间格式化

### 7.8 系统管理（`/admin`，管理员）

- [ ] 6 个 Tab 切换与数据加载：概览 / 数据源 / 模型 / Agent 参数 / 日志 / 用户
- [ ] 概览：系统状态（DB / LLM 连通性）
- [ ] 数据源：配置读取与保存（**保存后不回显/不落库任何密钥明文**）
- [ ] 模型：三家模型列表拉取、分类计数、应用模型、额度查询与"即将过期"标记
- [ ] Agent 参数：温度 / max_agents / 审批开关保存
- [ ] 连通性测试：测试数据库 / 测试 LLM
- [ ] 日志列表（limit=100）与等级样式
- [ ] 用户管理：列表、改角色、删除（含二次确认）
- [ ] 非管理员不可见该导航项

### 7.9 全局

- [ ] 侧栏 6+1 项导航：图标、激活态、`title` 提示、管理员可见性
- [ ] 主题切换按钮图标与 `<html>` class 同步；刷新后保持
- [ ] 头像首字母与跳转 `/profile`；退出登录跳 `/login`
- [ ] 浏览器刷新任意路由（History 模式 + Nginx 配置）不 404
- [ ] 窗口缩放时所有图表与地图自适应

---

## 8. 待你确认的决策项（确认后才开工）

| # | 决策点 | 默认方案 | 备注 |
|---|---|---|---|
| D1 | `/login` 是否改用 `BlankLayout`（登录页将不再显示左侧导航） | **方案 B：保持现状** | 涉及表现变化，需你明确选择 |
| D2 | Markdown 样式是否全局化（agent-center / dashboard 的 Markdown 渲染将新增样式） | **全局化** | 属修复既有不一致，若要求像素级不变请说明 |
| D3 | `views/profile` 接入统一 HTTP 层后新增 401 自动跳转 | **接入** | 同上，属修复既有不一致 |
| D4 | 是否执行阶段 6（登录布局 / Key 硬编码收敛 / CDN 清理 / ResizeObserver） | **暂不执行** | 每项单独确认 |
| D5 | 每阶段是否要求我提供"改前/改后"对照截图 | **提供（阶段 0、3、4）** | 会增加耗时但最稳妥 |

---

## 9. 附：本轮明确不做的事

- 不动 `fire_agent_back` 任何代码
- 不改任何接口 URL / Method / 参数 / 响应结构
- 不改 `.env*` 与其读取方式（不在文档中记录任何真实配置值）
- 不升级 Vue / Vite / Element Plus / ECharts / OpenLayers 版本
- 不引入新的第三方 UI 框架或图表库
- ~~不做视觉风格重新设计（沿用现有令牌体系）~~ —— 已作废，视觉重做见 §10（独立轨道，不污染阶段 0–6 的行为等价约束）

---

## 10. 前端展示效果重做规划（Visual Overhaul · 独立轨道）

> 本章**推翻现有全部视觉表现**，按"高端 / 简约 / 克制"重新建立设计体系。
> 它与 §2–§9 的结构重构是两条互不干扰的轨道：**结构轨道改代码组织、表现不变；视觉轨道改表现、功能与交互不变。**

### 10.0 生效范围与保护契约

| 类别 | 内容 |
|---|---|
| **本轨道可改** | 配色、字体、字号/字重、间距、圆角、阴影与发光、图标、面板材质、动效、图表主题、空/加载/错误态、排版节奏、信息密度 |
| **本轨道不可改（保护契约）** | 路由 path 与 name、导航信息架构（6+1 项及其顺序）、`localStorage` 三键（`fire_agent_token` / `fire_agent_user` / `fire_agent_theme`）、`<html class="dark">` 切换机制、接口 URL/Method/参数/响应解析、Element Plus 组件选型与交互语义、地图与 3D 渲染逻辑及图层、SSE/流式行为、导出与打印的文件内容结构 |
| **原则豁免** | §2.2 原则 1 中"相同视觉呈现"在本轨道内**不适用**；但 DOM 结构（除视觉必需的包裹层）、网络请求、业务状态机必须等价 |
| **分支策略** | 独立分支 `design/vN-*`，与 `refactor/stage-N-*` 并行；任一 V 步可单独回退而不影响结构轨道 |

### 10.1 Design Read（设计判读与五档标定）

```yaml
Design Read:
  artifact: 桌面端 GIS + 多 Agent 指挥平台（1 张作战大屏 + 5 个业务页 + 登录页）
  audience: 森林防火值班/指挥人员（高频、长时间注视）+ 技术评审/作品展示
  visual-language: Editorial-Minimal × Modern Tool —— 保留 Linear 的克制与发丝线，
                   但材质换成"纸感/石英"，强调色换成"火语义"，去掉冷紫与玻璃拟态
  mode: Redesign · Overhaul（视觉层） / Preserve（信息架构与交互流程）
  visual-variance: 4        # 内部指挥工具，需要稳定识别，不宜花哨
  motion-intensity: 3       # 微交互为主；仅首屏与报告流允许 0.8–1.2s 从容动画
  information-density: 8    # 高密度，靠排版与发丝线降噪，不靠留白稀释信息
  asset-dependence: 2       # 无品牌 VI/logo 资产，用字标 + 火语义色，不用 Emoji
  brand-fidelity: 3         # 自有项目，本次即建立新视觉识别
```

**四个定位问题的答案**：

| 问题 | 结论 |
|---|---|
| 叙事角色 | 大屏 = "数据主角"（地图是主角，UI 让位）；业务页 = "工具"（效率优先）；报告 = "阅读"（编辑感） |
| 观看距离 | 大屏 3–5m（投影/墙屏）→ 字号与线宽上调；业务页 0.5m → 正常密度 |
| 视觉温度 | Quiet + 轻微 Authoritative（沉稳、可信；不暖不闹，也不赛博冷） |
| 容量检查 | 当前大屏"四图并排 + 玻璃 + 光晕"信息过载 → 必须减图、减装饰，靠分层与留白解决 |

### 10.2 现状视觉诊断（推翻清单）

| # | 现状（代码定位） | 为什么不行 | 处理 |
|---|---|---|---|
| V-1 | 主强调色冷紫 `#5e6ad2`（`gis-theme.css:56`） | 与"火险/焰哨"语义无关，是 AI/工具站模板的收敛色 | 换 **ember 火烬橙红**，语义化 |
| V-2 | metal 金属渐变、metal-sheen 扫光、metal-edge 顶边亮线（`:76-82`） | 装饰层压过信息层；多渐变叠加=廉价质感 | **全删**，改实色 + 1px 发丝线 |
| V-3 | glow / glow-strong / line-glow / text-glow 四套发光（`:67-73`） | 发光=低端"科技感"；投影环境发虚 | **全删**，阴影只留 3 级 |
| V-4 | glassmorphism + `backdrop-filter: blur(14px) saturate(150%)`（`:35-48`） | 大屏低配机器掉帧；多层半透明导致对比度失控 | 改 90%+ 实色分层 |
| V-5 | halo-a/b/c 三光晕 + atmo-bg + 48px 网格底纹（`:84-88,109`） | 背景装饰噪音；与地图瓦片打架 | **全删**，canvas 纯色 |
| V-6 | 侧栏 48px 纯图标、无文字（`MainLayout.vue:99-137`） | 6 个图标靠猜，学习成本高 | 改 **72px（图标+11px 文字）**，可折叠 |
| V-7 | Emoji/字符当按钮：`☀ ☾ ⏻`（`MainLayout.vue:69-75`） | 字符即图标是明显的偷懒，跨平台字形不一致 | 换 **20px 线性 SVG 图标** |
| V-8 | 导航激活态 = 左侧 2px 渐变条 + 发光 + 金属渐变（`:166-175`） | 三重强调叠加 | 只保留 **1 项**：左侧 2px 实色条（或底色二选一） |
| V-9 | 头像/主按钮用金属渐变 + `transform: scale(1.08)` hover（`:209-227`） | 弹跳式缩放廉价 | 改静态语义色 + 120ms 微位移 |
| V-10 | 页面私有前缀 `gis-/agent-/kb-/qa-/report-/admin-/profile-/login-` | 8 套视觉方言，同一控件 8 种长相 | 统一 `--fs-*` 令牌 + 通用组件 |
| V-11 | 图表沿用 ECharts 默认蓝紫 + 渐变填充 + 阴影 | 非数据元素过多，数据-墨比低 | 顶刊级细线低饱和，见 §10.7 |
| V-12 | 大屏顶栏渐变 + 强投影、四图同时竞争注意力 | 主次不分 | 顶栏纯色 + 1px 底边；四图收为**两块 tab** |

### 10.3 新视觉体系（Design System Declaration）

**设计锚点**：Editorial Minimal（原研哉 / Apple HIG 的克制与留白）× Modern Tool（Linear / Vercel 的发丝线与单一强调）× 少量"火"语义色。**不是** cyber 霓虹，**不是** 玻璃拟态，**不是** 渐变发光。

#### 10.3.1 色彩

| 令牌 | 浅色「石英 Quartz」 | 深色「夜航 Nightwatch」 | 用途 |
|---|---|---|---|
| `--fs-bg-canvas` | `#F4F4F2`（暖纸白，去蓝调） | `#101214` | 页面底 |
| `--fs-bg-surface` | `#FFFFFF` | `#171A1D` | 卡片/面板/顶栏 |
| `--fs-bg-sunken` | `#EDEDEA` | `#0B0C0E` | 表头/代码块/输入轨道/草稿区 |
| `--fs-ink-900` | `#17181A` | `#E8E9EA` | 主文字/标题 |
| `--fs-ink-700` | `#3D4045` | `#B6B9BD` | 正文 |
| `--fs-ink-500` | `#6E7178` | `#878B90` | 次要/轴标签 |
| `--fs-ink-400` | `#9A9DA3` | `#5F646A` | 占位/禁用 |
| `--fs-hairline` | `rgba(23,24,26,.10)` | `rgba(232,233,234,.10)` | 默认分隔 |
| `--fs-hairline-strong` | `rgba(23,24,26,.18)` | `rgba(232,233,234,.18)` | 容器外框/hover 边 |
| `--fs-accent` | `#A8451F`（ember 火烬） | `#E07A4A`（同色相提亮） | 主操作/激活/关键数值 |
| `--fs-accent-soft` | `rgba(168,69,31,.10)` | `rgba(224,122,74,.14)` | 选中底/标签底 |
| `--fs-on-accent` | `#FFFFFF` | `#17181A` | 强调底上的文字 |

**强调色用量纪律**：一屏之内实心强调色 ≤ 1 处（主按钮或激活项），其余用 hairline / ink / soft 底表达层级。

**火险语义四级**（双主题各自一套，语义不变、明度适配）：

| 等级 | 浅色 | 深色 |
|---|---|---|
| 低 | `#5F8577`（sage） | `#7FA896` |
| 中 | `#B38A3C`（ochre） | `#C9A24E` |
| 高 | `#C0572B`（ember） | `#E0713F` |
| 极高 | `#8E2F2A`（oxide） | `#C4483F` |

**状态色**：success `#4F7A63` / warning `#B38A3C` / danger `#8E2F2A` / info `#5F7C8A`（浅色；深色同比例提亮）。
**数据色板**：主序列 ember→ochre→sage 三色 + 中性 `#6E7A8A`，**同图 ≤ 4 色**；顺序数据用单色明度阶梯。

#### 10.3.2 字体

```css
--fs-font-sans: "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei", system-ui, sans-serif;
--fs-font-serif: "Songti SC", "Noto Serif SC", "SimSun", Georgia, serif;   /* 报告正文/引言 */
--fs-font-mono: "IBM Plex Mono", "JetBrains Mono", ui-monospace, Menlo, monospace; /* 数字/坐标/代码/时间 */
```

- **默认不加载中文 Web 字体**（内网/离线可用优先，避免 3–5MB 字体包）；中文走系统栈。
- 数字、坐标、时间、代码统一 `tabular-nums` + mono，指挥端读数对齐是关键差异化。
- **报告正文改宋体**（`--fs-font-serif`）：把"AI 生成的 Markdown"变成"可读的文档"，这是本轮最重要的差异化决策之一。
- 可选（作品展示态，默认关）：Latin 显示字 `Instrument Sans`（Google Fonts，仅 Latin 子集 ~15KB）。**不使用** Inter / Roboto / Arial / Fraunces 作为显示字体。

**字号节奏**（桌面 1440+）：

| 层级 | 浅色/常规 | 大屏（3–5m 观看） |
|---|---|---|
| Display / KPI | — | `clamp(40px, 3.2vw, 64px)`，600 字重，mono tabular |
| H1 页标题 | 28 / 36，600 | 32 / 40 |
| H2 分区 | 20 / 28，500 | 22 / 28 |
| H3 卡片标题 | 16 / 24，500 | 18 / 24 |
| Body | 14 / 22（业务页）、15 / 26（阅读页） | 15 |
| Meta / 轴标签 | 12 / 18，500，`letter-spacing .04em` | 13 |
| 字重 | 只用 400 / 500 / 600 三档（KPI 可用 600） | 禁止 700+ 堆砌 |

#### 10.3.3 间距、圆角、阴影、边框

| 项 | 规范 |
|---|---|
| 间距基准 | 4px；尺度 `4 / 8 / 12 / 16 / 20 / 24 / 32 / 48 / 64`；页面外边距 24；卡片内边距 16–20；栅格 gutter 16（12 栏） |
| 圆角 | `--fs-r-xs 3`（标签）/ `sm 6`（控件）/ `md 10`（卡片面板）/ `lg 14`（对话框）/ `pill 999`（浮动工具条）。**上限 14**，杜绝"圆润 SaaS 感" |
| 阴影 | 只 3 级：`e1 0 1px 2px rgba(16,18,20,.06)`、`e2 0 2px 8px rgba(16,18,20,.08)`、`e3 0 8px 28px rgba(16,18,20,.12)`（仅 drawer/dialog）。**禁止**彩色发光、`text-shadow`、外发光模拟选中、`box-shadow` 当描边 |
| 边框 | 1px hairline 为默认分隔；分区优先用"间距 + 顶部 1px section rule"，**禁止卡片套卡片** |
| 图标 | 统一 20px 线性 SVG（stroke 1.5，round cap）；现存 iconfont 保留但逐步替换；**禁止 Emoji / 字符当图标** |

### 10.4 壳层与布局

| 区域 | 现状 | 新方案 |
|---|---|---|
| 侧栏 | 48px 纯图标 + 金属字 + 发光 | **72px**（20px 图标 + 11px 文字），可折叠至 48；品牌区 56px 用字标「焰哨 FlameSentry」（字重 600，无发光）；底部改为 32px 头像 + 昵称/角色 + 图标操作行（主题切换 / 退出） |
| 业务页容器 | 各页自造 `*-shell` | 统一 `max-width: 1440px` 居中 + 左右 24 gutter；大屏页全屏铺满 |
| 页头 | 每页自造 header 卡片（渐变/投影） | 统一 **64px 页头条**：左侧 H1 + 副标题，右侧操作区；仅底部 1px hairline，无背景块 |
| 大屏三栏 | 340 / 1fr / 340 玻璃浮层 | 保留比例（**不改交互**），但 rail 改为与 canvas 同色系实色 + **仅内侧 1px** 分隔线，去掉模糊与外发光 |
| 大屏工具条 | 分散在地图四角 | 底部居中**浮动工具条**（高 32，radius pill，surface + e2），图层/量测/下载收纳其中 |

### 10.5 组件视觉规范

| 组件 | 视觉规范 |
|---|---|
| `AppPanel` | surface + 1px hairline + radius 10；标题 12px/500 + `letter-spacing .04em`，标题下 12px 间距；**禁止左侧色条**、**禁止渐变顶边**、**禁止嵌套面板** |
| 表格 | 无外框；仅行间 1px hairline；表头 12px + sunken 底；行高 40；hover 用 surface 微亮（不用色染）；数字列右对齐 + tabular-nums；斑马纹关闭 |
| 按钮 | 高度 32（密集）/36（常规），radius 6；默认 secondary（hairline + surface），primary 每屏 ≤1；按下 `scale(.98)` 120ms；**禁止渐变底与发光** |
| Badge / Tag | radius 3，10px 字号，语义色 10% 底 + 同色文字；**不用纯色块** |
| 空态 | 细线占位框 + 一句说明 + 一个操作（不插 Emoji、不放大插画） |
| 加载态 | 骨架块（sunken + 1.2s shimmer）或 20px 细环 spinner；**禁止全屏遮罩 loading**（首屏除外） |
| Toast | 右上浮层，surface + e2 + hairline；图标 + 语义色文字，**不加左侧色条** |
| 输入框 | 高 32；hairline 边；focus 时边框转 `--fs-accent` + 1px，**不加发光环** |
| Dialog / Drawer | radius 14，e3，遮罩 `rgba(16,18,20,.45)`；进入 240ms `cubic-bezier(.22,1,.36,1)` |

### 10.6 页面级展示重做（逐页）

| 页面 | 关键改动 | 明确不动 |
|---|---|---|
| **登录 `/login`** | 全屏两栏：左 58% 视觉面（低饱和等高线/火点热力纹理 + 字标 + 一句价值主张），右 42% 表单卡（24px 标题 → 输入 → 主按钮，无阴影堆叠）。建议 **D1 改为 BlankLayout**，登录时不再显示侧栏 | 接口、校验、错误提示文案、redirect 逻辑 |
| **作战大屏 `/dashboard`** | ①顶栏 64px，只留字标/时间/天气/**3 个 KPI**（火点数、高风险州市、预警等级），其余入 rail；②地图成为唯一主角，去容器发光与边框；③右侧四图收为**两块 tab**（历史 / 预测），单图高 180；④左侧火情识别改为**任务抽屉**（默认 36px 图标按钮，展开 360px）；⑤KPI 用 `clamp` 大字 + count-up 800ms | 地图图层/交互/量测/下载、聚合抽屉字段、主题切换、SSE 无关 |
| **智能查询 `/smart-query`** | Hero 化查询区（居中标题 + 大输入框 + 示例 chips）；结果三 tab（摘要/表格/图表·地图）；解析过程用**细线流程条**展示 intent/params | 查询逻辑、历史列表行为、图表 option 数据、地图要素 |
| **知识库 `/knowledge-base`** | 左：细线文档列表 + 拖放上传区；右：对话流——用户消息右对齐 surface 气泡（r10），AI 回答**无气泡、直接正文排版**（编辑感），引用来源用 12px 脚注 + 上标序号；语音按钮改 SVG | 上传/删除/流式解析/历史行为 |
| **Agent 中心 `/agent-center`** | 三栏 360 / 1fr / 380；流水线改**竖向细线时间轴**（24px 圆点 + 1px 连接线，状态用语义色描边而非填充发光）；报告流打字机 16–24ms/字 + 1px 光标；审批区用"文档审阅"视觉（sunken 草稿底 + 顶部分组操作） | 6 步节点定义、SSE 事件解析、审批三动作、历史去重逻辑 |
| **报告中心 `/report-center`** | 列表→阅读双栏；阅读态"纸张化"：宋体正文 + 行高 1.9 + 段距 1em + 标题细线下划；工具条（导出/打印/删除）吸顶 64px；Markdown 表格改**顶刊三线表**（表头下 1px + 表底 1px，无竖线） | 列表分页、详情竞态处理、导出/打印文件内容 |
| **个人中心 `/profile`** | 单列 720 居中卡片组，两个分区（资料 / 密码），操作右对齐 | 字段、校验、401 行为 |
| **系统管理 `/admin`** | 密集表单栅格（label 88px 右对齐 + 输入）；分区用 1px 顶边 + 12px 小标题；模型列表表格 + 徽标；状态灯 6px 圆点（无发光）；**去掉全部金属渐变按钮** | 6 个 Tab 结构、所有配置字段与保存逻辑、403 分支 |

### 10.7 图表视觉规范（顶刊级）

- **删**：背景网格（或仅保留 y 轴 1px `rgba(...,.06)` 虚线）、3D、渐变填充、图形阴影、legend 冗余图标、图表容器外框。
- **用**：线宽 1.5（主）/1（次）；面积填充 ≤12% 透明；柱圆角 ≤2；legend 改 8px 方点；轴标签 12px ink-500。
- Tooltip：surface + e2 + 1px hairline，radius 6，12px 字，无位移动画。
- 地图底图降饱和（`filter: saturate(.75) contrast(1.02)`），让数据层跳出来；火险等级严格取 §10.3 语义四级。
- **数据-墨比纪律**：每张图上线前必须删掉 ≥1 项非数据元素，并在验收中说明删了什么。
- 主题切换：沿用 `chartTokens()` 实时取 CSS 变量重建，取值源从 `--gis-*` 切到 `--fs-*`。

### 10.8 动效与"呼吸感"法则

| 类别 | 时长 | 曲线 |
|---|---|---|
| 微交互（hover/按下/切换） | 120–200ms | `cubic-bezier(.22,1,.36,1)` |
| 面板 / 抽屉 / 下拉 | 240–320ms | 同上；退出 `cubic-bezier(.4,0,1,1)` |
| 页面级入场 / 数字动画 | **800–1200ms，从容收尾** | ease-out |
| 火点脉冲（唯一允许的循环动效，可关闭） | ≤1.2s 慢呼吸 | ease-in-out |

**呼吸感 B1–B6（沿用你既定的审美红线）**：

1. **每屏一个焦点**——大屏焦点是地图，业务页焦点是主内容区。
2. **密疏交替**——地图/表格（密）之后必须有留白段（疏），不连续堆叠动效区块。
3. **空屏喘息位**——大屏保留 24–32px 纯呼吸区，不填满。
4. **连续动效不超过 2 组**，之后必须静默一段。
5. **快而急一律禁止**——页面级动画 0.8–1.2s；禁止 <100ms 的"急停"。
6. **禁止整页同时运动**——入场用 60–80ms  stagger 分组推进。

- 动效只服务于**状态变化**与**首次入场**，不做装饰性循环。
- `@media (prefers-reduced-motion: reduce)`：位移/缩放降级为 opacity 或直接关闭。

### 10.9 令牌迁移映射（旧 → 新）

| 旧令牌 | 新令牌 / 处理 |
|---|---|
| `--gis-accent*` (冷紫 `#5e6ad2`) | `--fs-accent*`（ember，**语义变更**） |
| `--gis-glass` / `glass-2` / `glass-solid` / `glass-border` / `glass-blur` / `glass-saturate` | **删除** → `--fs-bg-surface` |
| `--gis-glow` / `glow-strong` / `line-glow` / `text-glow` | **删除** → `--fs-shadow-e1..e3` |
| `--gis-metal-accent` / `sheen` / `edge` / `text` | **删除** |
| `--gis-halo-a/b/c` / `--gis-atmo-bg` / `--gis-grid` | **删除**（canvas 纯色，无底纹） |
| `--gis-bg-deep` / `bg-panel` / `bg-panel-2` / `bg-header` | `--fs-bg-canvas` / `surface` / `sunken` / `surface` |
| `--gis-text` / `text-muted` | `--fs-ink-900` / `--fs-ink-500` |
| `--gis-border` / `border-strong` | `--fs-hairline` / `--fs-hairline-strong` |
| `--gis-radius-*` / `--gis-space-*` | `--fs-r-*` / `--fs-space-*`（尺度重排为 4 基准） |
| `--el-*`（Element Plus 全套） | 全量重映射到新体系（重点：`--el-color-primary` → `--fs-accent`） |

**落地方式**：新增 `style/theme-v2.css` 定义 `--fs-*`；`gis-theme.css` 暂留为**兼容层**（旧变量映射到新变量）；开关 `html.theme-v2`（默认关，逐页开启），全部页面切完后删除兼容层。

### 10.10 实施顺序（V 轨道）

| 步骤 | 范围 | 产物 |
|---|---|---|
| **V0** | **视觉原型（先确认方向）**：单页 HTML，含大屏 / Agent 中心 / 报告中心 三张关键屏 + 组件样例 + Tweaks 面板（亮暗 / 强调色 / 密度 / 圆角 / 动效开关） | `docs/design/visual-v0.html` ✅ **已完成并确认（2026-11-01）** |
| **V1** | 令牌与内核：`theme-v2.css` + EP `--el-*` 重映射 + 字体/圆角/阴影/间距；`html.theme-v2` 开关 | 令牌层 ✅ **已完成** `f242b13` |
| **V2** | 壳层：侧栏 72 / 页头条 / 按钮·表格·徽标·空态·Toast·输入框 视觉 | 壳层 + 基础组件换肤 ✅ **已完成** `8042d3c` |
| **V3** | 大屏：地图去装饰、rail 重排、KPI 排版、四图收两块、图表顶刊化 | 大屏换肤 ✅ **已完成** `2e32108` |
| **V4** | 业务页：smart-query → knowledge-base → agent-center → report-center → profile → admin | 业务页换肤 ✅ **已完成** `80e373d` |
| **V5** | 登录页 + 图标 SVG 化 + 动效收尾 + 对比度/性能/打印验收 | 收尾 ✅ **已完成** `cd651ca` |

> **V1–V5 已全部合入 master 并推送 Gitee（9534eda..cd651ca，70 文件 +2654/−1780）。**
> 回退开关：`localStorage.setItem('fire_agent_theme_v2','off')` 后刷新，即整站回到 `gis-theme.css` 旧视觉。

每步一个分支 `design/vN-*`，独立可回退；全程保持接口、路由、交互等价。

### 10.11 视觉验收清单

- [ ] 令牌：页面内 `#hex` / `rgba()` 硬编码 grep 为 0；`--gis-*` 引用为 0（兼容层除外）
- [ ] 主题：亮/暗切换后无残留不换肤元素；正文对比度 ≥4.5:1，次要文字 ≥3:1，图表轴标签 ≥3:1
- [ ] 组件：按钮 hover / focus / active / disabled / loading 五态齐全，且无一使用发光
- [ ] 表格 / 空态 / 加载态 / Toast 符合 §10.5
- [ ] 性能：移除 `backdrop-filter` 与多光晕后，中低配机器大屏帧率 ≥50fps；`prefers-reduced-motion` 生效
- [ ] 打印与导出：报告 HTML 导出与打印预览仍可读（新 Markdown 样式需同步进导出模板）
- [ ] 功能不回退：§7 全部清单仍通过（视觉轨道不得破坏功能）
- [ ] 反模式清零：无冷紫玻璃、无霓虹发光、无 Emoji 图标、无金属渐变、无左侧装饰色条
- [ ] 主观自评：哲学一致性 / 层级 / 工艺 / 功能必要性 / 原创性 五维均 ≥7/10

### 10.12 风险与应对

| 风险 | 应对 |
|---|---|
| Element Plus 内部样式覆盖不全（`--el-*` 遗漏） | 逐组件走查 + 兜底 reset；V1 结束做一轮全组件巡检 |
| 中文 Web 字体体积 | **不引入中文 Web 字体**，仅系统栈 + 本地宋体栈 |
| Map3D 材质与新色板冲突 | 3D 只调整环境色/线框色，不改几何与性能预算 |
| 大屏低配性能（瓦片 + ECharts 仍重） | 图表 tab 懒加载 + 移除模糊；必要时降低瓦片饱和滤镜成本 |
| 导出/打印样式与页面不一致 | Markdown 新样式同步进导出 HTML 模板，并纳入 V4 验收 |
| 视觉改动面大、返工成本高 | **必须 V0 原型确认后再落地**；用 `html.theme-v2` 开关逐页灰度 |

### 10.13 待你确认的视觉决策项

| # | 决策点 | 状态 |
|---|---|---|
| D6 | 主强调色由冷紫改 **ember 火烬橙红** | ✅ 已采用并落地 |
| D7 | 报告正文改**宋体**（"纸张化"阅读态） | ✅ 已采用并落地（`--fs-font-serif`，markdown.css） |
| D8 | 侧栏 48 → **72px（图标+文字）**，Emoji 按钮换 SVG 图标 | ✅ 已采用并落地（AppIcon + 72px，可折叠 48） |
| D9 | 大屏右侧四图收为**两块 tab**（同屏图数 4 → 2） | ✅ 已采用并落地（历史 / 预测 tab） |
| D10 | 登录页改用 BlankLayout（去掉左侧导航） | ✅ 已采用并落地（`is-blank` 分支） |
| D11 | 是否加载外部字体（Instrument Sans / IBM Plex Mono） | ✅ **不加载**（离线优先，走系统栈） |

- 不在未确认前修改登录页布局与第三方 Key 处理逻辑

### 10.14 收尾遗留（V6 可选）

| # | 事项 | 说明 |
|---|---|---|
| R1 | **零运行时冒烟** | 本机无 puppeteer/playwright，V1–V5 全部改动只做了编译 + 进包校验，需人工过一遍：大屏地图标绘/量测/热力/导出/3D 切换、四图 tab、Agent SSE 与审批、报告宋体与三线表、深浅主题切换、登录两栏 |
| R2 | 删 `gis-theme.css` 兼容层 | 全站 `.vue` 已 0 处 `--gis-` 引用，但 `gis-theme.css` 仍含全局元素规则（scrollbar / EP 兜底），删除前需逐项确认 theme-v2 已覆盖 |
| R3 | `utils/riskLevel.js` 的 `SUMMARY_MAP.icon` 仍存 Emoji 字符串 | 渲染处已改为语义色圆点（FireWarningBar），字典里的 `icon` 字段已成死数据，可清 |
| R4 | 图标 SVG 化未全量 | `DashboardTopBar` 的天气图标、`MapToolbar` 的工具图标仍用 iconfont（外部 CDN 字体），可继续换 AppIcon |
| R5 | 动效收尾（§10.8） | 页面级入场 stagger、KPI count-up、火点脉冲尚未接入，本轮只做了令牌与静态视觉 |
| R6 | 打印 / 导出样式同步 | 报告导出 HTML 模板需同步宋体与三线表样式 |
