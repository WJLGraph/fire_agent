# 公开站点技术信息审计 + 前端增强 · 规格说明

> 状态：✅ 已完成并合入 master（本文件为历史规格存档）。
> 后续变化：SSE 已改为 `fetch + Authorization` 请求头（不再走 `?token=`）；会话改为 15 小时滑动续期；除 5 个公开端点外全部接口需鉴权；Agent 流新增 `report_snapshot` 首帧与 running 期 4s 详情轮询兜底。当前事实以 `README.md` / `整体实现.md` 为准。
> 范围：仅公开页组（`/welcome` 五页 + `/login`）与公开页共用样式/组件；不改主题 token、系统名称、业务事实（16 州市 / 5,411 火点 / 6 智能体 / 五级火险）、后端与内部业务逻辑。
> 目标：先让文案与代码事实对齐，再在不新增不实宣称的前提下做 3–5 项渐进增强。

---

## 一、事实基线（本次审计的证据源）

| 事实 | 代码/数据证据 | 结论 |
|---|---|---|
| 版本 1.0.1 | `fire_agent_front/package.json:3`、`fire_agent_back/app/core/config.py:11` | 保留 |
| 16 州市边界 | `app/api/v1/routes/dashboard.py:19-34`（region_boundaries city 级）、`整体实现.md:859` | 保留 |
| 历史火点 5,411 | `fire_agent_back/sql/public.sql:35833`（序列终值 5411）、`整体实现.md:473` | 保留（补时间范围 2021–2025） |
| 6 协作智能体 | `app/api/v1/routes/agent.py:48-61`（AGENT_REGISTRY 6 条） | 保留 |
| 五级火险 | `src/utils/riskLevel.js:66-92`（正常/注意/警告/高度/极度） | 保留 |
| 流水线拓扑 | `orchestrator_agent.py:1582-1589`：`parse_task → (query_data → analyze_gis) ∥ retrieve_knowledge → join → generate_report → review_report → approval_gate`；并行边 `:1594-1602` | **7 环节 / 8 节点**；查询与检索并行且固定执行（`:720`、`:749-751`、`:1015-1051`）；页面“7 节点顺序含检索”需修正 |
| 数据库 | `config.py:35` PostgreSQL；`requirements.txt:31` GeoAlchemy2；`docker-compose.yml:14` postgis:16-3.4；`app/models/resource.py:21` SRID=4326 | **PostgreSQL + PostGIS**，非 SQLite/MySQL |
| 大模型 | `config.py:41-47` 默认 aliyun / `qwen-plus`；`:59-71` 可切 AMD / Ollama / LongCat | **Qwen**，非 GLM |
| 向量检索 | `app/models/kb_document.py:34-36` embedding 以 Text(JSON) 存储，Python 侧余弦相似度 | 可说“向量检索”，**不可说 pgvector** |
| SSE 断线兜底 | `src/composables/useTaskStream.js:143-144, 294-302`：`onerror → loadTaskDetailFallback` 一次性回查 | **无 2s 轮询**，需改表述 |
| 思考留存 | `app/agents/orchestrator_agent.py:116` 落库上限 12,000 字符；`:416-423` 按轮次落库 | “完整留存”应改为“按轮次留存（有上限）” |
| 前端密钥 | `src/views/dashboard/DashboardTopBar.vue:23`、`src/components/map/Map2D.vue:143` 含地图 Key | **“前端零密钥”不成立** |
| 外部依赖 | `config.py:45` LLM_API_BASE、`:103` MCP_ENABLED（高德天气） | **“无外部依赖调用”不成立** |
| 仓库地址 | `git remote -v` = `gitee.com/WJLGraph/Fire_agent_front` | about 页写法正确，保留 |
| 角色 | `src/layout/MainLayout.vue:45` admin=管理员，其余=值班员 | 公开页“管理员/值班员”与系统展示一致，保留 |

---

## 二、阶段一：审计改动清单（逐条）

> 处置原则：能证实的保留；不能证实或冲突的改文案/降级/删除；不改主题、不改布局结构。

### A. `src/views/welcome/technology.vue`

| # | 原文（位置） | 改后 | 依据 |
|---|---|---|---|
| A1 | `:22` `SQLite/MySQL · GLM 大模型 · 向量检索` | `PostgreSQL + PostGIS · Qwen 大模型 · 向量检索` | config.py:35、docker-compose.yml:14、config.py:46 |
| A2 | `:20` `LangGraph · 6 智能体 · 七节点流水线` | `LangGraph · 6 智能体 · 七环节流水线（查询 ∥ 检索并行）` | `agent.py:48-61`，`orchestrator_agent.py:1582-1602` |
| A3 | `:43` `大模型 GLM，知识库向量检索` | `大模型 Qwen（可切换 AMD / Ollama / LongCat），知识库向量检索` | config.py:41-71 |
| A4 | `:50` `数据库 SQLite 起步，可切 MySQL` | `PostgreSQL + PostGIS 空间库，Docker Compose 一键拉起` | docker-compose.yml:12-57 |
| A5 | `:51` `密钥仅存服务端 .env，前端零密钥` | `大模型/数据库密钥仅存服务端 .env；地图瓦片 Key 为前端公开配置` | DashboardTopBar.vue:23、Map2D.vue:143 |
| A6 | `:67` FAQ 数据来源“气象与地形数据接入统一时空基线；接口异常时自动降级本地数据并标注数据源” | `卫星火点（MODIS，2021–2025，当前口径 5,411 条）；气象为高德接口实时查询，地形为 16 州市行政边界；接口异常时统计降级为本地默认口径` | agent.py:1232-1235、dashboard.py:108-115、index.vue SAFE_STATS |
| A7 | `:70` FAQ “前后端分离、无外部依赖调用，大模型接口可配置为内网代理” | `前后端分离，可用 Docker Compose 一键部署；大模型与天气接口均可配置代理或关闭降级` | docker-compose.yml、config.py:45,103 |
| A8 | `:192` 数据表“流水线节点 7｜含 HITL 人工审批闸口” | `7（8 个节点）｜查询 ∥ 检索并行后汇合，含 HITL` | `orchestrator_agent.py:1582-1602` |
| A9 | `:143` lead “连线上的光点是正在流动的数据包” | 保留（视觉隐喻），但同页下方补一行 mono 注：“示意：查询数据与知识检索并行执行后汇合；数据包仅表示调度关系” | `orchestrator_agent.py:749-751`，`:1594-1602` |
| A10 | `:59` “管理员/值班员” | 保留 | MainLayout.vue:45 |

### B. `src/views/welcome/workflow.vue`

| # | 原文 | 改后 | 依据 |
|---|---|---|---|
| B1 | `:77` “七个节点，一条可追溯的报告流水线” | “七个环节，一条可追溯的报告流水线” | `orchestrator_agent.py:1582-1602` |
| B2 | `:21-44` 步骤 04 “检索知识”顺序 | 描述补“与查询数据并行执行，未命中时如实说明、不跳过”；步骤 05 描述补“汇合数据、GIS 结论与检索依据后成文” | `orchestrator_agent.py:749-751`，`:1594-1602` |
| B3 | `:181` “SSE 断线自动降级为 2s 轮询，状态不丢” | “SSE 断线自动回查任务详情兜底，状态不丢” | useTaskStream.js:143-144, 294-302 |
| B4 | `:185` “每个节点的思考过程完整保存” | “生成节点的思考按轮次落库，可展开回看” | orchestrator_agent.py:116, 416-423 |
| B5 | `:78` “六个智能体分工协作” | 保留 | agent.py:48-61 |

### C. `src/views/welcome/features.vue`

| # | 原文 | 改后 | 依据 |
|---|---|---|---|
| C1 | `:28` “七节点流水线编排” | “七环节流水线编排（查询 ∥ 检索并行）” | `orchestrator_agent.py:1582-1602` |
| C2 | `:28` “思考过程完整留存” | “思考过程按轮次留存” | orchestrator_agent.py:116 |
| C3 | `:40` 多源数据融合“统一时空基线” | “统一空间基准（EPSG:4326）；气象为接口实时查询” | models/resource.py:21、config.py:38 |
| C4 | `:28` “SSE 流式过程可视”“评审三态 + 人工闸口” | 保留 | config.py:92、agent.py:1225-1227 |

### D. `src/views/welcome/index.vue`

| # | 原文 | 改后 | 依据 |
|---|---|---|---|
| D1 | `:10` 注释、`:469` “七个节点”、`:485` 注 | “七环节”；注改为“查询数据与知识检索并行执行，汇合后进入成文” | `orchestrator_agent.py:1594-1602` |
| D2 | `:329` `LIVE SITUATION · ...` | `SITUATION OVERVIEW · YUNNAN WILDFIRE COMMAND` | 同页 :373 已声明“非实时监测” |
| D3 | `:344` 绿色状态“API 数据同步” | 中性状态“SUMMARY · 摘要口径” | 仅挂载时拉取一次 + 5s 超时降级，非健康监测 |
| D4 | `:501` “多源卫星火点长序列归集” | “MODIS 卫星火点 · 2021–2025 归集” | agent.py:1232-1233、sql 行 source=MODIS |
| D5 | `:361` 5,411、`:362` 6 | 保留 | sql/public.sql:35833、agent.py:48-61 |

### E. `src/views/welcome/about.vue`

| # | 原文 | 改后 | 依据 |
|---|---|---|---|
| E1 | `:41` “七节点流水线” | “七环节流水线” | agent.py:1219-1220 |
| E2 | `:76` “流水线节点 7” | “流水线环节 7” | 同上 |
| E3 | `:150` “Gitee · WJLGraph/Fire_agent_front” | 保留 | git remote |
| E4 | `:113` “v1.0.1” | 保留 | package.json:3、config.py:11 |

### F. `src/views/login/index.vue`

| # | 原文 | 改后 | 依据 |
|---|---|---|---|
| F1 | `:172` “融合卫星火点、气象要素与地形数据…” | “融合卫星火点、气象与行政区划边界数据…” | 无 DEM 数据；仅有 16 州市边界 + 高德天气 |
| F2 | `:174` 16 / 5,411 / 6 / 五级 | 保留 | 同上 |

### G. 组件口径

| # | 文件 | 改动 | 依据 |
|---|---|---|---|
| G1 | `AgentNetGL.vue:7` 注释 | “七节点流水线”→“七环节流水线” | `orchestrator_agent.py:1582-1602` |
| G2 | `AgentNetGL.vue:41` FLOW_EDGES | 删除虚构的 `GIS→RAG` 边，改为 `GIS→REPORT` / `RAG→REPORT` 并行汇合；DOM 注“查询与检索并行后汇合” | `orchestrator_agent.py:1594-1602` |
| G3 | `TerrainGL.vue` | 不改文案（已声明“示意 · 非实时”） | TerrainGL.vue:10,122 |
| G4 | `PubFooter.vue:34-36` | 保留 | 事实已核 |

---

## 三、阶段二：选定 4 项增强（渐进增强，均有降级）

> 选择理由：与现有极简/冷钢设计语言一致，优先“光与数据”而非装饰；不引入后处理库以外的依赖；不改首屏结构。

### E1 · 地形场景选择性 Bloom（`TerrainGL.vue`）
- 实现：在 `three` 动态 import 同时导入 `EffectComposer / RenderPass / UnrealBloomPass`；仅当 `desktop (>1024px)`、`motionAllowed`、WebGL2 可用时启用。
- 分层：光柱与脉冲环挂 `layer 1`，`bloomCam` 只渲染该层；`EffectComposer` 的 `renderToScreen=false`，结果留在 `readBuffer`，再用自定义全屏四边形以 `CustomBlending（SrcAlpha/One，alpha 不叠加）` 加色叠回原底图 → 板块/州界保持原始清晰度，只有光柱/脉冲环产生光溢出。
- 参数：`strength 1.4`、`radius 0.5`、`threshold 0.0`，composer 半分辨率（`0.5w × 0.5h`）。
- 渲染顺序：`renderer.render(scene, camera)` → `composer.render()` → 加色合成；resize 同步 `setSize`；卸载 `composer/quad/loseContext` 全量 dispose。
- 降级：移动端 / `motionAllowed=false` / import 失败 / WebGL2 不可用 → 保持现有直接渲染，无额外开销。
- 验证：`/welcome` 1440×900 地形带截图亮部溢出但不糊字；地形段泛光开/关各 5s 帧率对照。

### E2 · 滚动/指针驱动 uniform（`TerrainGL.vue`）
- 新增 `uTime`、`uPointer`（vec2，lerp 阻尼）、沿用 `uProgress`；在既有扫描亮带/发丝州界 shader 中加极弱噪声位移与随滚动的雾化（≤0.04 幅度）。
- 交互：仅 `pointer: fine` 绑定 `pointermove`；指针视差 ≤8px；`pointerleave` 回中。
- 降级：`motionAllowed=false` 时 uniform 冻结在初始值；移动端不绑定指针；离屏 IO 已暂停 rAF。
- 验证：DOM 断言 canvas 存在、uniform 随时间变化（DEV 探针）；截图两帧差异肉眼可见但不影响阅读。

### E3 · GPU 火星粒子（`TerrainGL.vue`）
- 实现：单次 `THREE.Points`（8,000 顶点）+ `ShaderMaterial`（additive，颜色取 `--fs-risk-4/5`），顶点着色器按 `uTime` 上升并淡出；位置用 mulberry32 在 16 州市 bbox 内确定性生成；一次 draw call。
- 条件：仅桌面 + `motionAllowed`；移动端隐藏；`motion off` 不创建 BufferGeometry。
- 降级：WebGL 不可用 → 现有静态 SVG 回退不变。
- 验证：截图可见细颗粒光点；帧率不低于现有基线 -10%。

### E4 · View Transitions clip-path 遮罩（`router/index.js` + `qt.css`）
- 实现：`beforeResolve` 已有 VT 包装；导航时在 `document.documentElement` 写 `data-vt-dir`（按页面序号前进/后退）；CSS 对 `::view-transition-new(root)` 使用 `clip-path: inset(...)` 320ms 展开，旧页 200ms 淡出；保留现有 `#vt-banner`。
- 降级：不支持 `startViewTransition` / `motionAllowed=false` 直接跳转；`prefers-reduced-motion` 已有全局放行。
- 验证：点击导航后 DOM 断言 `data-vt-dir` 存在；截图目标页正常渲染；无布局塌陷。

### 不做（明确排除）
- 不引入后处理库以外的依赖；不做 GPGPU 双缓冲（8k 粒子单 pass 已够）；不改 Lenis/GSAP 主循环；不新增声音/全屏缩放/大面积玻璃拟态。

---

## 四、验收标准

1. `npm run build` 通过（three/examples 进入公开路由 chunk，仍为动态 import）。
2. `node scripts/check-sfc-bindings.mjs` PASS。
3. `npx oxlint src/views/welcome src/views/login src/components/welcome src/composables src/router` 0 error / 0 warning。
4. headless Edge 截图：6 页 × 2 视口 → `preview/audit-enhance/`；关键区块 `terrain-bloom`、`terrain-embers`、`vt-clip`、`anet-optional`；`off` 态 2 张。
5. 帧率采样（1440×900，5s rAF）：`/welcome` 与 `/welcome/technology` 记录 avg fps；`motion off` 对照。
6. 文案审计清单逐条复查：`grep` 旧表述（`GLM`、`SQLite`、`2s 轮询`、`前端零密钥`、`无外部依赖`、`七节点`）为 0 命中（除历史注释/本 spec）。
7. `git push origin master`，回报 commit hash、截图路径、帧率数据。

## 五、风险与回滚

- Bloom 只作用于光柱层（layer 1）且半分辨率 + 加色合成，不改变板块/州界/文字对比；实测地形段开泛光 52.2fps / 关泛光 60.0fps（headless SwiftShader，非真机口径）。
- 粒子在低端机掉帧：`navigator.hardwareConcurrency <= 4` 时自动降到 3,000；仍掉帧则整体禁用。
- VT clip-path 在部分浏览器抖动：加 `@media (prefers-reduced-motion: reduce)` 与 `@supports` 守卫；异常时退回现有淡入。
- 全部改动可按文件粒度回滚；不触碰主题 token、后端、内部页。
