# 焰哨 FlameSentry · 智慧火险预警与多智能体协作平台 —— 后端（fire_agent_back）

> **当前版本**：v1.0.1（含 v1.0.1 后续迭代：LongCat 接入 / AMD GPU Cloud 四类能力 / 知识库文档全文与原件 / 启动自愈 / AgentGauntlet 红队 / 安全加固与流式可靠性，详见 [13. 版本记录](#13-版本记录)）
> 本项目是「焰哨 FlameSentry · 智慧火险预警与多智能体协作平台」（现实使用名：**焰哨多Agent与可视化平台**）的后端部分，基于 **FastAPI + PostgreSQL/PostGIS + LangChain/LangGraph** 构建。
> 配套前端：[fire_agent_front](https://gitee.com/WJLGraph/Fire_agent_front)（Vue 3 + Vite + OpenLayers + Three.js）
> **在线演示**：https://wjl2004.ffuf.cn/　or　https://8.156.67.47/login
> **演示账户**：test / 123456
> **GitHub 仓库**：https://github.com/wjl-cong/fire_agent（欢迎 Star）

---

## 目录

1. [项目简介与总体架构](#1-项目简介与总体架构)
2. [技术栈](#2-技术栈)
3. [项目结构](#3-项目结构)
4. [数据模型](#4-数据模型)
5. [API 总览](#5-api-总览)
6. [Agent 编排](#6-agent-编排)
7. [LLM 接入与降级](#7-llm-接入与降级)
8. [RAG 流水线](#8-rag-流水线)
9. [记忆 · 工具 · 观测 · 评估 · 红队](#9-记忆--工具--观测--评估--红队)
10. [启动与配置](#10-启动与配置)
11. [Docker 部署](#11-docker-部署)
12. [常见问题](#12-常见问题)
13. [版本记录](#13-版本记录)

---

## 1. 项目简介与总体架构

后端为智能体驱动的火险分析服务：接收自然语言任务 → LangGraph 多智能体编排（数据查询 / GIS 分析 / 知识检索 / 报告生成 / 报告评审 / 人工审批）→ 报告落库；同时提供大屏数据、智能查询、知识库 RAG、视觉识别与语音合成 / 转写、系统管理等 API。

```
┌──────────────────────────────────────────────────────────────┐
│                        Vue 3 前端（SPA）                      │
│   大屏 / 智能查询 / 知识库 / Agent 中心 / 报告中心 / 系统管理   │
└───────────────┬──────────────────────────┬───────────────────┘
                │ REST（JSON 信封）          │ SSE（fetch 流 + Authorization 头）
┌───────────────▼──────────────────────────▼───────────────────┐
│                     FastAPI（/api/v1）                        │
│  dashboard │ query │ rag │ agent │ reports │ admin │ auth │ vision │
├──────────────────────────────────────────────────────────────┤
│  services：data / query / rag                                  │
│  agents  ：orchestrator（LangGraph 8 节点）                    │
│  core    ：llm / llm_invoker / reranker / memory_store /      │
│            mcp_client / observability / amd_directory         │
├──────────────────────────────────────────────────────────────┤
│  PostgreSQL + PostGIS（业务表 13 张 / 向量 pgvector）           │
│  文件存储（知识库原件 KB_UPLOAD_DIR）/ 识别图片                  │
└──────────────────────────────────────────────────────────────┘
        │                    │                    │
   阿里百炼 DashScope    AMD GPU Cloud        Ollama / LongCat
   （LLM/Embedding/      （text/vision/         （本地或第三方
     Vision/ASR/TTS）      speech/ocr）           兼容 OpenAI 协议）
```

**核心能力**：

- **多智能体编排**：LangGraph `StateGraph` 8 节点，含并行 fan-out/join、反思重试、报告评审循环与 HITL 中断恢复；
- **流式交付**：Agent 任务 SSE 节点级进度 + 报告增量；RAG 问答 SSE 打字机；
- **四提供商 LLM**：统一 `llm_invoker` 重试 / 熔断 / 链式降级 / 规则兜底；
- **AMD 四类能力**：大语言 / 视觉 / 语音合成 / 文档识别，管理端可一键切换；
- **知识库**：四层 PDF 提取 + 中文切分 + 混合检索 + 重排 + Adaptive RAG + 文档全文与原件接口；
- **可观测与质量**：Langfuse 链路追踪、golden set 回归评估、AgentGauntlet 红队故障注入。

---

## 2. 技术栈

| 类别 | 依赖 | 版本 | 用途 |
| ---- | ---- | ---- | ---- |
| Web 框架 | FastAPI | 0.115.0 | 路由 / 依赖注入 / 自动文档 |
| ASGI | uvicorn | — | 生产运行 |
| ORM | SQLAlchemy | 2.0.35 | 模型与会话 |
| 空间扩展 | GeoAlchemy2 | 0.15.1 | PostGIS 几何字段 |
| 数据库 | PostgreSQL + PostGIS | 16 / 3.x | 业务数据与空间数据 |
| 向量 | pgvector | 0.3.6 | 知识库分片向量 |
| 驱动 | psycopg[binary] | 3.3.6 | PostgreSQL 连接 |
| 编排 | langgraph | 0.2.64 | StateGraph / interrupt / checkpointer |
| LLM 框架 | langchain | 0.3.17 | Prompt / 工具 / 回调 |
| OpenAI 兼容 | langchain-openai | 0.3.0 | AMD / LongCat / Ollama |
| 百炼 SDK | dashscope | 1.27.7 | 百炼 LLM / Embedding / ASR / TTS |
| 检查点 | langgraph-checkpoint-postgres | 2.0.15 | PostgresSaver（降级 MemorySaver） |
| PDF 提取 | pdfplumber / pypdf / PyMuPDF | — | 三层文本提取 |
| OCR | rapidocr-onnxruntime | — | 本地 OCR 兜底 |
| 观测 | langfuse | 4.15.4 | LLM 链路追踪 |
| MCP | mcp / langchain-mcp-adapters | 2.2.0 / 0.2.0 | 高德天气工具（stdio） |
| 测试 | pytest | 9.1.1 | 回归评估 |

> `requirements.txt` 环境同步于 2026-10-02；AgentGauntlet 为本地评测包，不列入部署依赖。

---

## 3. 项目结构

```
fire_agent_back/
├── app/
│   ├── main.py                     ← lifespan：create_all → 幂等补列 → 种子 admin/123456 →
│   │                                  启动自愈（running 任务置 failed + 清理僵尸步骤）；CORS；8 路由挂载
│   ├── core/
│   │   ├── config.py               ← 全部配置项（VERSION = "1.0.1"）、REPORT_FOOTER
│   │   ├── database.py             ← Engine / SessionLocal / get_db
│   │   ├── security.py             ← JWT 签发与校验、密码哈希
│   │   ├── llm.py                  ← get_llm / get_embedding / get_vision_llm /
│   │   │                              transcribe_audio / synthesize_speech / amd_ocr_pdf
│   │   ├── llm_invoker.py          ← 重试（1s/2s/4s）×3、熔断（3 次/60s）、Provider 链降级、审计
│   │   ├── reranker.py             ← qwen3-rerank，失败降级 RRF
│   │   ├── memory_store.py         ← PostgresStore 偏好记忆（降级禁用）
│   │   ├── mcp_client.py           ← MCP 懒加载 + get_weather_for_city
│   │   ├── observability.py        ← Langfuse CallbackHandler
│   │   └── amd_directory.py        ← AMD tokenfactory 实时目录抓取
│   ├── api/v1/routes/
│   │   ├── dashboard.py            ← 大屏数据
│   │   ├── query.py                ← 智能查询
│   │   ├── rag.py                  ← 知识库
│   │   ├── agent.py                ← Agent 任务 / SSE / 能力 / 状态
│   │   ├── report.py               ← 报告中心
│   │   ├── admin.py                ← 系统管理（内置模型目录与额度快照）
│   │   ├── auth.py                 ← 注册 / 登录 / 个人信息
│   │   └── media.py                ← 视觉识别 / 语音（挂载前缀 /api/v1/vision）
│   ├── agents/
│   │   ├── orchestrator_agent.py   ← LangGraph 编排（8 节点 + 兜底节点 + 图构建）
│   │   ├── data_agent.py           ← DataAgent：数据查询节点
│   │   ├── gis_agent.py            ← GisAgent：空间分析节点
│   │   ├── rag_agent.py            ← RagAgent：知识检索节点
│   │   └── report_agent.py         ← ReportAgent：报告生成 / 评审
│   ├── services/
│   │   ├── data_service.py         ← 大屏数据查询（封装 FireRepository）
│   │   ├── query_service.py        ← 意图解析（llm / keyword）与执行器
│   │   └── rag_service.py          ← 文档上传 / 提取 / 切分 / 检索 / 重排 / 生成
│   ├── models/                     ← 13 张业务表
│   ├── schemas/                    ← Pydantic（admin / agent / common / dashboard / query / rag / report / user）
│   ├── repositories/               ← fire_repository / report_repository
│   └── utils/                      ← 通用工具
├── mcp_server/weather_server.py    ← FastMCP stdio：高德 geo → adcode → weather
├── scripts/
│   ├── init_db.py                  ← 建表 + 种子
│   ├── import_fire_points.py / import_predict_risks.py / import_region_boundaries.py
│   ├── run_all_imports.py
│   ├── eval_regression.py          ← golden set 回归评估
│   └── golden_set.json             ← 评估用例
├── migrations/                     ← SQL 迁移脚本
├── sql/public.sql                  ← 初始化 SQL
├── docker-compose.yml              ← db / backend / frontend（+ 可选 langfuse profile）
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 4. 数据模型

共 **13 张业务表**：

| # | 表 | 说明 |
| - | -- | ---- |
| 1 | `users` | 用户（username / email / password_hash / role：admin \| user） |
| 2 | `fire_points` | 历史火点（经纬度 / 亮度 / 置信度 / 时间 / 省份州市县） |
| 3 | `fire_risks` | 预测火险（Year / Month / Day / City / Final_Fire_Index / Pred_Fire_Count / Risk_Score / Pred_Fire_Risk） |
| 4 | `regions` | 行政区划边界（PostGIS Geometry，州市 / 县） |
| 5 | `resources` | 应急资源（队伍 / 物资 / 位置） |
| 6 | `agent_tasks` | Agent 任务（status / query / parsed_intent / report_id / llm_provider / llm_model / llm_tokens / llm_degraded / user_id / 时间） |
| 7 | `agent_task_steps` | 任务步骤（step_name / status / input_payload / output_payload / 时间，按 `(task_id, step_name)` 增量落库；output 含 summary / thinking / thinking_rounds / review_status 等） |
| 8 | `analysis_reports` | 报告（report_type / title / content / summary / llm_provider / llm_model / llm_tokens / llm_degraded / user_id / 软删标记） |
| 9 | `kb_documents` | 知识库文档（filename / file_type / file_path / category / chunk_count / user_id） |
| 10 | `kb_chunks` | 文档分片（content / embedding / 序号） |
| 11 | `query_history` | 查询历史（query / result JSON / 同用户同文本去重） |
| 12 | `rag_history` | 问答历史（query / answer / sources / result JSON） |
| 13 | `vision_history` | 火情识别记录（图片路径 / 结果 Markdown / 时间） |

---

## 5. API 总览

统一前缀 `/api/v1`；**除 `/`、`/health`、`/auth/login`、`/auth/register`、`/dashboard/summary` 外均需 `Authorization: Bearer <JWT>`**。`/dashboard/summary` 是唯一刻意匿名的业务端点（登录页/门户未登录时要展示真实统计，只回聚合计数，不含逐条数据）；鉴权口径由 `scripts/check_auth_coverage.py` 静态校验，62 条路由必须逐条显式声明，新增端点漏声明会直接失败。

### 5.1 大屏数据（`/dashboard`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/dashboard/history-fires` | 历史火点（支持 limit / 时间 / 区域过滤，默认上限 5000） |
| GET | `/dashboard/predict-risks` | 预测火险（逐日 / 逐月，按 Year-Month-Day 过滤） |
| GET | `/dashboard/summary` | 数据汇总统计 |

### 5.2 智能查询（`/query`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/query/parse` | 仅解析意图，不执行查询 |
| POST | `/query/execute` | 解析 + 执行 + 落库（同用户同文本去重） |
| GET | `/query/history` | 查询历史（按用户隔离） |
| GET | `/query/history/{history_id}` | 历史详情（回显完整 result） |
| DELETE | `/query/history` | 清空历史 |
| DELETE | `/query/history/{history_id}` | 删除单条 |

### 5.3 知识库（`/rag`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/rag/ask` | RAG 问答（Adaptive，落库） |
| POST | `/rag/ask/stream` | RAG 流式问答（SSE：`meta` → `delta` → `done`，半截不落库） |
| GET | `/rag/history` | 问答历史 |
| GET | `/rag/history/{history_id}` | 问答详情 |
| DELETE | `/rag/history` | 清空 |
| DELETE | `/rag/history/{history_id}` | 删除单条 |
| POST | `/rag/documents` | 上传文档（FormData：file + category） |
| GET | `/rag/documents` | 文档列表（含 file_type / chunk_count） |
| GET | `/rag/documents/{doc_id}/content` | 文档全文（分片拼接，仅本人 / admin） |
| GET | `/rag/documents/{doc_id}/file` | 文档原件（FileResponse，RFC 5987 中文名，inline） |
| DELETE | `/rag/documents/{doc_id}` | 删除文档（级联分片） |

### 5.4 Agent 协作（`/agent`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/agent/tasks` | 任务列表（用户隔离 / admin 全量，limit 50，附报告模型与 `progress`/`elapsed_seconds`/`total_tokens`） |
| GET | `/agent/tasks/{task_id}` | 任务详情（steps + report + llm_used + 审计 + `elapsed_seconds` / `total_tokens`，无值时为 `null`） |
| DELETE | `/agent/tasks/{task_id}` | 删除任务（级联步骤） |
| POST | `/agent/tasks` | 创建任务（立即返回 task_id，后台执行） |
| POST | `/agent/tasks/{task_id}/resume` | 审批恢复（approve / edit / reject）；闸口未就绪 / 重复提交返回 **409 + 语义化 code**：`approval_not_ready` / `already_resumed` / `approval_busy` / `task_finished` / `checkpoint_unavailable`（checkpoint 降级 MemorySaver 时拒绝）/ `task_busy`（同任务恢复并发锁） |
| GET | `/agent/tasks/{task_id}/stream` | SSE（`Authorization` 头鉴权，**token 不进 URL**）：`report_snapshot`（重连首帧，补齐本轮已产出正文/思考）/ `step` / `report_think`（带 `run`）/ `think_reset`（复读截断）/ `approval` / `report_delta` / `report` / `error` |
| GET | `/agent/capabilities` | 系统能力清单（真实运行态） |
| GET | `/agent/status` | 6 个 Agent 状态（含 Reviewer） |

### 5.5 报告中心（`/reports`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/reports/list` | 报告列表（page / page_size / report_type） |
| GET | `/reports/{report_id}` | 报告详情 |
| POST | `/reports/generate` | 直接生成报告（不经过 Agent 编排） |
| DELETE | `/reports/{report_id}` | 删除（用户软删 / 管理员全局软删） |
| GET | `/reports/export/{report_id}` | 导出（`format=md\|html`） |

### 5.6 系统管理（`/admin`，仅 admin）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/admin/config` | 配置读取（API Key 脱敏 `key[:3] + "****" + key[-3:]`） |
| POST | `/admin/config` | 配置保存（写 `.env` + `setattr` 热生效，跳过脱敏值） |
| POST | `/admin/test/db` | 数据库连接测试 |
| POST | `/admin/test/llm` | LLM 真实 invoke 测试 |
| GET | `/admin/llm/models?provider=` | 模型目录（`aliyun\|amd\|ollama\|longcat`） |
| GET | `/admin/bailian/quota` | 百炼免费额度快照 |
| GET | `/admin/status` | 系统状态（DB / LLM / 模型 / 6 个 Agent） |
| GET | `/admin/logs?limit=` | 系统日志（环形缓冲 200） |
| GET | `/admin/users` | 用户列表 |
| PUT | `/admin/users/{user_id}/role` | 修改角色（防自改） |
| DELETE | `/admin/users/{user_id}` | 删除用户（防自删） |

### 5.7 认证（`/auth`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/auth/register` | 注册即登录 |
| POST | `/auth/login` | 登录，返回 `access_token` + `user` |
| GET | `/auth/me` | 当前用户 |
| PUT | `/auth/me` | 修改邮箱 |
| PUT | `/auth/me/password` | 修改密码（旧密码校验，改密后吊销旧 token） |

- **15 小时滑动会话**：`exp = iat + 15h`；每个已认证请求的响应会带 `X-Token-Refresh`（CORS `expose_headers` 暴露），前端在确有用户活动时替换本地 token —— 连续 15 小时无操作才需重登，期间有操作即重新计时；
- **吊销**：`users.token_version`（token 内 `tv`）不匹配即失效；无 `tv` 的旧 token 视为 0，部署不强制全员掉线。

### 5.8 视觉与语音（`/vision`）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/vision/analyze` | 火情图片识别（视觉模型，落库） |
| GET | `/vision/history` | 识别历史 |
| GET | `/vision/history/{rec_id}` | 识别记录 |
| DELETE | `/vision/history/{rec_id}` | 删除记录 |
| GET | `/vision/image/{rec_id}` | 识别图片（鉴权二进制流） |
| POST | `/vision/audio/transcriptions` | 语音转写（ASR，wav 上传） |
| POST | `/vision/audio/speech` | 语音合成（TTS，返回音频二进制） |

### 5.9 服务信息

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/` | 服务信息（名称 / 版本 / 文档地址；生产 `ENV=production` 时 `/docs`、`/redoc` 关闭） |
| GET | `/health` | 健康检查 |

---

## 6. Agent 编排

### 6.1 图结构

```
                    ┌─────────────┐
                    │ parse_task  │  意图解析 → TaskPlan（子任务清单）
                    └──────┬──────┘
              ┌────────────┴────────────┐
              ▼                         ▼
      ┌──────────────┐         ┌────────────────────┐
      │  query_data  │         │ retrieve_knowledge │
      └──────┬───────┘         └─────────┬──────────┘
             ▼                           │
      ┌──────────────┐                   │
      │ analyze_gis  │                   │
      └──────┬───────┘                   │
             └────────────┬──────────────┘
                          ▼
                     ┌─────────┐
                     │  join   │  合并并行分支
                     └────┬────┘
                          ▼
                 ┌─────────────────┐
                 │ generate_report │  评审意见注入 / 天气 / 偏好 / 流式增量
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  review_report  │  低温度评审 + 硬护栏，≤2 轮
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  approval_gate  │  interrupt() 人工审批
                 └────────┬────────┘
                          ▼
                         END
```

- **8 个节点**：`parse_task`、`query_data`、`analyze_gis`、`retrieve_knowledge`、`join`、`generate_report`、`review_report`、`approval_gate`（前端流水线按 7 步展示：任务解析 / 数据查询 / GIS 分析 / 知识检索 / 报告生成 / 质量评审 / 人工审核——`join` 为无 UI 的汇聚节点；待审批 6/7、定稿 7/7）。
- **并行**：`query_data → analyze_gis` 与 `retrieve_knowledge` fan-out，`join` 汇聚；plan 未包含 GIS 时 `analyze_gis` 为 no-op。
- **反思**：`parse_task` 可产出 `QueryRetryPlan`，最多 2 轮改写重查。
- **评审三态**：`review_report` 使用低温度 LLM + 硬护栏（≥800 字、必备章节、真实数据），
  - `passed`：评审成功且未发现问题 → 进审批；
  - `returned`：评审给出具体问题 → 退回重写，**最多 2 轮**，达上限转人工（`forced`，`review_status=degraded`）；
  - `degraded`：评审自身失败（LLM 异常 / 解析失败 / 判不通过却无具体问题）→ **不退回**，报告直接进人工审核（`review_status=degraded` + `degraded_reason`，步骤不置 failed）。
  - 评审结论写入步骤 output 的 `review_status` 字段，前端按三态着色（退回红、降级警告色）。
- **两轮思考**：`generate_report` 流式输出内置复读检测（逐字 + bigram 近似簇 × 频次 + 后缀块），思考命中复读/超限 → 截断到句子边界（`think_reset` 帧通知前端丢弃重复尾巴）→ **立即发起第二轮**（run+1，提示词注入截断摘要并禁止复述；预算第一轮 6k/150s、第二轮 12k/180s），最多 2 轮；思考按 `thinking_rounds` 分轮落库。
- **HITL**：`approval_gate` 通过 `langgraph.types.interrupt()` 暂停，`resume` 三动作：
  - `approve`：草稿直接定稿；
  - `edit`：以编辑稿（`content`）定稿；
  - `reject`：携带 `comment` 重新生成。
  - `resume` 前置校验失败返回 409 + 语义化 `detail.code`（见 §5.4），闸口未挂起时不再静默放行。
- **兜底**：无 LLM 时使用 `_make_fallback_nodes` 模板节点（评审直接通过），保证任务可完成。

### 6.2 任务状态机

```
running → awaiting_approval → running → completed
                                   └──→ failed
```

- 任务创建后立即返回 `task_id`，后台 `_spawn_task` 执行；`_bg_tasks` 持有引用防 GC。
- 每次节点状态变化通过 `_upsert_step_row` 按 `(task_id, step_name)` 增量落库（running 预写 + 终态覆盖）。
- `resume` 仅任务所有者 / admin 可调用，且必须处于 `awaiting_approval`。

### 6.3 SSE 事件协议

| 事件 `type` | 字段 | 说明 |
| ----------- | ---- | ---- |
| `report_snapshot` | `run` / `report` / `think` | **连接建立首帧**：当前轮次已产出的正文与思考副本（切页/刷新回来不丢已上屏内容；无产出时不发） |
| `step` | `step.step` / `step.status` / `step.output` | 节点开始（running 预写行）/ 结束（completed / failed / skipped） |
| `report_think` | `run` / `text` | 思考过程增量（`run` 为生成轮次，重写/第二轮递增） |
| `think_reset` | `run` / `text` | 复读截断：前端把该轮实时思考替换为 `text`（截断版），随后 run+1 开新轮 |
| `report_delta` | `run` / `text` | 报告增量（打字机） |
| `approval` | `data` | 进入待审批，附任务详情（含草稿全文） |
| `report` | `data` | 终态完整报告（含 steps） |
| `error` | `message` | 执行错误 / 看门狗超时 |

- 开连即回放历史步骤，并补一帧 `report_snapshot`（后端按任务+轮次在进程内保留增量副本，终态丢弃；因此流式途中切页/刷新回来不会丢已上屏内容）；
- 鉴权走 `Authorization` 请求头（前端用 fetch 流而非 `EventSource`；token 放查询参数会落进 Nginx access log）；
- 结束前等待 0.6s 以冲刷 `report_delta`；
- 单连接最长 `_SSE_MAX_SECONDS = 1800` 秒，停滞看门狗 `_SSE_STALL_SECONDS = 600` 秒；
- 响应头 `X-Accel-Buffering: no` 避免 Nginx 缓冲。
- 前端消费：增量经 180ms 非响应式缓冲批量 flush（防长任务 O(n²) 重渲染）；`step` 事件即时处理；running 期间另有 4s 详情轮询兜底（SSE 丢事件时从 DB 恢复步骤与状态）。

---

## 7. LLM 接入与降级

### 7.1 四提供商

| 提供商 | 配置 | 默认模型 | 说明 |
| ------ | ---- | -------- | ---- |
| 阿里百炼 | `LLM_API_KEY` / `LLM_API_BASE` | `qwen-plus` | LLM + Embedding + Vision + ASR + TTS 主路 |
| AMD GPU Cloud | `AMD_API_KEY` / `AMD_API_BASE` | `DeepSeek-V4-Flash` | OpenAI 兼容；四类能力目录 |
| Ollama | `OLLAMA_API_BASE` | `qwen2.5:7b` | 本地部署 |
| LongCat | `LONGCAT_API_KEY` / `LONGCAT_API_BASE` | `LongCat-2.5-Preview` | OpenAI 兼容；静态目录 + `/models` 校验 |

`ACTIVE_LLM_PROVIDER=aliyun|amd|ollama|longcat` 决定主提供商。

### 7.2 统一调用层 `llm_invoker`

- **重试**：指数退避 1s / 2s / 4s，最多 3 次；
- **熔断**：连续 3 次失败进入 60s 冷却（`_Breaker`，`breaker_status()` 对外暴露）；
- **降级链**：激活提供商优先，其余按 `aliyun → amd → ollama → longcat` 顺序尝试；
- **规则兜底**：全部失败时走关键词 / 模板逻辑，任务不失败；
- **审计**：每次调用返回 `provider` / `model` / `tokens` / `degraded`，写入任务与报告。
- 对外接口：`invoke_llm`、`invoke_structured`、`stream_llm`。

### 7.3 能力路由

| 能力 | 配置项 | 可选值 | 默认 | 降级策略 |
| ---- | ------ | ------ | ---- | -------- |
| 视觉识别 | `VISION_PROVIDER` / `VISION_MODEL` | `aliyun` / `amd` | `aliyun` / `qwen-vl-plus` | 按 `VISION_PROVIDER` 路由（模型名需与所选提供商匹配） |
| 语音转写 | `ASR_MODEL` | — | `qwen3-asr-flash` | 百炼 data URI 上传 |
| 语音合成 | `TTS_PROVIDER` / `TTS_MODEL` | `aliyun` / `amd` | `aliyun` / `qwen3-tts-flash` | 百炼失败自动 AMD OmniVoice `/audio/speech`（返回 wav） |
| 文档 OCR | `OCR_PROVIDER` / `OCR_MODEL` | `local` / `amd` | `local` / `MinerU2.5-Pro` | AMD 优先，失败降级本地 RapidOCR |

### 7.4 管理端模型目录

- **百炼**：内置 `BAILIAN_FREE_MODELS`（5 大类 30+ 模型）+ 实时免费目录校验，`MODEL_CATEGORIES` / `BAILIAN_CONSOLE_URLS`；排序规则「免费优先 → 有效期长 → 当前使用 → 已验证」；
- **AMD**：`app/core/amd_directory.py` 实时抓取 `developer.amd.com.cn` tokenfactory（bootstrap POST + templates GET + 逐卡 detail），能力 key `text/vision/speech/ocr`；tier 映射：`dedicated` / 无 badge → `paid`，`limited` → `limited_free`，`free` → `free`；无缓存，失败返回空列表；
- **LongCat**：`LONGCAT_MODELS` 静态目录（`LongCat-2.5-Preview`、`LongCat-2.0`）+ `/models` 校验；
- **Ollama**：仅 `/models` 列举。
- 一键切换：`POST /admin/config` 写入 `.env` 并 `setattr` 热生效，无需重启。

---

## 8. RAG 流水线

```
上传 → 提取 → 切分 → 向量化 → 入库
                          │
提问 → Adaptive 分类 ──────┼── 混合检索（向量 + 关键词）
      （simple/complex）    │        └→ qwen3-rerank（失败降级 RRF）
                          │
                          └→ Prompt（引用编号）→ LLM → 答案 + 来源
```

- **四层 PDF 提取**（`_extract_pdf`）：pdfplumber → pypdf → PyMuPDF（fitz）→ OCR；乱码 / 扫描件自动判定；
  - `OCR_PROVIDER=amd` 时优先 `amd_ocr_pdf`（逐页 PNG → `/ocr` → Markdown，模型 `MinerU2.5-Pro`）；
  - 失败再降级本地 `_ocr_pdf`（RapidOCR）。
- **切分**：`_chunk_text` 中文友好，chunk 500 / overlap 50（`KB_CHUNK_SIZE` / `KB_CHUNK_OVERLAP`）。
- **检索**：`retrieve()` 返回 `items` / `matched_chunks` / `method`（`hybrid` / `keyword` / `none`，可带 `+rerank`）/ `reranked` / `keywords` / `vector_enabled`；`top_k` 默认 5。
- **重排**：`qwen3-rerank`（`RERANK_ENABLED` / `RERANK_MODEL`），失败降级 RRF。
- **Adaptive RAG**：`_classify_query_complexity` 判定 `simple` / `complex`；complex 最多 3 轮 LLM 改写重查。
- **生成**：`_rag_prompt` 要求引用来源编号；`answer` 非流式、`answer_stream` 流式。
- **流式协议**：`meta`（来源 / 检索方法）→ `delta`（增量）→ `done`（收尾）；半截内容不落库（线程桥接 `asyncio.Queue`）。
- **文档阅读**：
  - `GET /documents/{id}/content`：按分片顺序拼接全文；
  - `GET /documents/{id}/file`：`FileResponse` + RFC 5987 中文文件名，`inline` 供前端内嵌预览。

---

## 9. 记忆 · 工具 · 观测 · 评估 · 红队

| 能力 | 实现 | 降级 |
| ---- | ---- | ---- |
| 偏好记忆 | `app/core/memory_store.py`，`PostgresStore`，namespace `("prefs", "user-{id}")`，key=`analysis`；`_PrefExtract` 抽取 cities / period；任务完成后沉淀，ReportAgent 注入 | 创建失败置 `_store_disabled`，不影响主流程 |
| 检查点 | `PostgresSaver`（`langgraph-checkpoint-postgres`） | 失败降级 `MemorySaver` |
| MCP 工具 | `app/core/mcp_client.py` 懒加载 `MultiServerMCPClient`（stdio `mcp_server.weather_server`）；`get_weather_for_city` 失败返回空串 | 无 MCP 时报告不注入天气 |
| 观测 | `app/core/observability.py`：`build_callback_config(task_id, thread_id)` → Langfuse `CallbackHandler` | 未启用 / 无密钥返回 `None` |
| 评估 | `scripts/golden_set.json` + `scripts/eval_regression.py`；`GET /agent/capabilities` 读取 golden cases 数量 | 无 LLM 时跳过 |
| 红队 | `GAUNTLET_CHAOS` / `GAUNTLET_FAULTS_PATH` / `GAUNTLET_SEED` / `GAUNTLET_SYS_CANARY`；`_chaos_wrap` 故障注入，`_guard_canary_output` 输出金丝雀拦截 | 默认全关，生产无影响 |

---

## 10. 启动与配置

### 10.1 启动流程（lifespan）

1. `Base.metadata.create_all` 建表；
2. **幂等补列**：`kb_documents.user_id`、`analysis_reports.user_id / llm_provider / llm_model / llm_tokens / llm_degraded`、`agent_tasks.user_id`、`query_history.result`、`rag_history.result`；
3. 种子管理员 `admin / 123456`（已存在则跳过）；
4. **启动自愈**：
   - `running` 任务统一标记 `failed`（提示「服务重启导致任务中断，请重新发起任务」）；
   - 清理僵尸 `running` 步骤行；
   - `awaiting_approval` 任务保留，可继续审批；
5. 挂载 8 个路由；CORS 默认允许 `5173` / `4173`。

> **运行期孤儿清扫**：首次派发任务 worker 时启动守护线程（每进程一次，启动宽限 45s、每 30s 扫描）——`running/pending` 且进程内无对应 worker 的任务（`uvicorn --reload` 热重启遗留）判 `failed` 并将 running 步骤行置 `skipped`，前端可从历史重试。

### 10.2 本地启动

```bash
cd fire_agent_back
conda create -n fire_agent_back python=3.11 -y
conda activate fire_agent_back
pip install -r requirements.txt

# 准备 .env（参考 .env.example）
python scripts/init_db.py            # 建表 + 种子（或依赖 lifespan 自动建表）
python scripts/run_all_imports.py    # 导入火点 / 预测 / 边界（可选）

uvicorn app.main:app --reload --port 8000
```

访问：
- Swagger：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 10.3 环境变量（默认值取自 `app/core/config.py`）

| 变量 | 默认 | 说明 |
| ---- | ---- | ---- |
| `VERSION` | `1.0.1` | 服务版本 |
| `ENV` | `development` | `development` / `production`；生产会关闭 `/docs`、`/redoc` 并启用密钥自检 |
| `JWT_SECRET` | 空（示例留空） | **必须自备随机值**：`python -c "import secrets;print(secrets.token_urlsafe(48))"`；生产环境拒绝空 / <32 字节 / 仓库公开过的占位值，直接拒启 |
| `ADMIN_INIT_PASSWORD` | 空 | 首次建库种子管理员口令；**生产为空则拒绝启动**，开发环境为空回退 `123456`（仅本地） |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:4173"]` | JSON 数组，需含前端实际来源（SSE 与 Cookie 同源） |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/fire_agent` | PostGIS 库 |
| `AMAP_KEY` | 空 | 高德天气 / MCP |
| `ACTIVE_LLM_PROVIDER` | `aliyun` | `aliyun` / `amd` / `ollama` / `longcat` |
| `LLM_API_KEY` / `LLM_API_BASE` | 空 / 百炼默认 | 百炼 |
| `LLM_MODEL` | `qwen-plus` | 主 LLM |
| `EMBEDDING_MODEL` | `qwen3.7-text-embedding-flash` | 恒定百炼 |
| `VISION_PROVIDER` / `VISION_MODEL` | `aliyun` / `qwen-vl-plus` | 视觉识别 |
| `ASR_MODEL` | `qwen3-asr-flash` | 语音转写 |
| `TTS_PROVIDER` / `TTS_MODEL` | `aliyun` / `qwen3-tts-flash` | 语音合成 |
| `OCR_PROVIDER` / `OCR_MODEL` | `local` / `MinerU2.5-Pro` | 文档 OCR（`local` / `amd`） |
| `AMD_API_KEY` / `AMD_API_BASE` / `AMD_MODEL` | 空 / `https://developer.amd.com.cn/radeon/v1` / `DeepSeek-V4-Flash` | AMD GPU Cloud |
| `OLLAMA_API_BASE` / `OLLAMA_MODEL` | `http://localhost:11434/v1` / `qwen2.5:7b` | Ollama |
| `LONGCAT_API_KEY` / `LONGCAT_API_BASE` / `LONGCAT_MODEL` | 空 / `https://api.longcat.chat/openai` / `LongCat-2.5-Preview` | LongCat |
| `QWEN3_8_*` | — | qwen3-8 时间窗开关 |
| `KB_UPLOAD_DIR` | `data/knowledge_base` | 知识库原件目录 |
| `KB_CHUNK_SIZE` / `KB_CHUNK_OVERLAP` | `500` / `50` | 切分 |
| `KB_TOP_K` | `5` | 召回数 |
| `RERANK_ENABLED` / `RERANK_MODEL` | 开 / `qwen3-rerank` | 重排 |
| `AGENT_REQUIRE_APPROVAL` | 开 | HITL 审批开关 |
| `LLM_STREAM_ENABLED` | 开 | 报告流式增量 |
| `PREFERENCES_ENABLED` | 开 | 偏好记忆 |
| `MCP_ENABLED` | 开 | MCP 天气工具 |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | 空 | Langfuse |
| `GAUNTLET_CHAOS` / `GAUNTLET_FAULTS_PATH` / `GAUNTLET_SEED` / `GAUNTLET_SYS_CANARY` | `False` / 空 / `42` / 空 | AgentGauntlet 红队 |
| `REPORT_FOOTER` | 含系统名 / 开发者 / 邮箱 / 仓库 / 演示 / GitHub | 报告页脚 |

> `.env.example` 覆盖核心项；`LONGCAT_*`、`OCR_*`、`GAUNTLET_*` 以上表为代码默认值为准，可直接在 `.env` 追加。

---

## 11. Docker 部署

```bash
# 全栈（db + backend + frontend）
docker compose up -d --build

# 附带 Langfuse（可选 profile）
docker compose --profile langfuse up -d --build
```

- `db`：PostGIS 镜像，持久化卷；
- `backend`：`Dockerfile` 构建，依赖 `db` 健康检查，挂载 `data/`；
- `frontend`：构建产物由 Nginx 托管，`/api` 反代 backend；
- 生产部署务必在 `.env` 设置 `ENV=production` 并配置随机 `JWT_SECRET`（两者要同一次改完再重启，否则会拒启或让现有会话全部失效）、`ADMIN_INIT_PASSWORD`、数据库口令与 `CORS_ORIGINS` 白名单；SSE 需关闭代理缓冲。

---

## 12. 常见问题

| 问题 | 解决方案 |
| ---- | -------- |
| 启动报 `relation does not exist` | 执行 `python scripts/init_db.py`；lifespan 会自动 `create_all` 并补列 |
| PostGIS 扩展缺失 | `CREATE EXTENSION postgis;` 后重跑迁移 / `sql/public.sql` |
| LLM 全部失败 | 检查 `ACTIVE_LLM_PROVIDER` 与对应 Key；`/admin/test/llm` 真实 invoke；查看熔断状态 |
| Agent 任务一直 running | 重启后会被自愈标记 failed；检查后台异常日志与 `agent_task_steps` |
| 审批后无反应 | 任务须处于 `awaiting_approval`；`edit` 必须带 `content`，`reject` 必须带 `comment`；闸口未就绪 / 重复提交返回 409 + `detail.code`（`approval_not_ready` / `already_resumed` / `approval_busy` / `task_finished` / `checkpoint_unavailable` / `task_busy`），按提示重试或刷新 |
| 评审显示「评审未完成 · 转人工确认」 | 评审 LLM 异常 / 解析失败 / 未给出具体问题时按 `review_status=degraded` 降级：不退回重写，报告直接转人工审核定稿 |
| SSE 无进度 | Nginx 关闭 `proxy_buffering`，`proxy_read_timeout` 调大；确认请求带 `Authorization` 头（**不要再把 token 拼进 URL**）；断线重连会先收到 `report_snapshot` 补齐本轮已有内容 |
| 知识库上传后无文本 | 查看四层提取日志；扫描件需配置 `OCR_PROVIDER=amd` 或本地 RapidOCR 依赖 |
| 语音播报 402 / 欠费 | 百炼欠费会透传 code + message；可切 `TTS_PROVIDER=amd` |
| 报告为空 / 被评审打回 | 评审护栏要求 ≥800 字、必备章节、真实数据；最多 2 轮后强制放行 |
| CORS 报错 | 在 `CORS_ORIGINS` 中加入前端地址（默认 5173 / 4173） |

---

## 13. 版本记录

### 安全加固与流式可靠性（v1.0.1 后续迭代）

**安全加固**

- **授权收口**：全部 62 条路由逐条显式声明鉴权口径，`scripts/check_auth_coverage.py` 与 OpenAPI 操作数交叉校验；仅 `/`、`/health`、`/auth/login`、`/auth/register`、`/dashboard/summary` 匿名（后者只回聚合计数）
- **15 小时滑动会话**：`X-Token-Refresh` 静默续期，连续 15h 无操作才重登；`users.token_version` 支持改密/停用后吊销
- **密钥自检**：`ENV=production` 拒绝空 / <32 字节 / 仓库公开过的占位 `JWT_SECRET`；`ADMIN_INIT_PASSWORD` 生产缺失拒启；生产关闭 `/docs`、`/redoc`
- **上传三重校验**（大小 / 扩展名 / magic bytes）；**日志与错误信息脱敏**（API Key、token）

**流式可靠性**

- 报告流式通道按「任务 + 生成轮次」保留进程内增量副本，新连接首帧补 `report_snapshot`：流式途中切页/刷新不再丢已上屏正文与思考；终态丢弃副本，任务数 / 字符量双上限兜底

### v1.0.1 后续迭代（当前代码状态）

**LLM 与能力扩展**

- 新增 **LongCat** 提供商：`LONGCAT_API_KEY` / `LONGCAT_API_BASE` / `LONGCAT_MODEL`，`llm_invoker` 降级链扩为四提供商；管理端静态目录 + `/models` 校验
- **AMD GPU Cloud 四类能力**：目录抓取支持 `text` / `vision` / `speech` / `ocr`，tier 区分免费 / 限额免费 / 付费
- 新增 `TTS_PROVIDER`（百炼失败自动 AMD OmniVoice `/audio/speech`）、`OCR_PROVIDER`（AMD `MinerU2.5-Pro` → 本地 RapidOCR）
- `TTS` 错误透传（欠费 code + message）

**知识库**

- `GET /rag/documents/{id}/content`：分片拼接文档全文
- `GET /rag/documents/{id}/file`：原件 `FileResponse` + RFC 5987 中文文件名，支持内嵌预览与下载
- 文档列表补充 `file_type` / `chunk_count`

**稳定性**

- 启动自愈：`running` 任务置 `failed`、清理僵尸 `running` 步骤、保留 `awaiting_approval`
- 幂等补列扩展到 `agent_tasks.user_id`、`query_history.result`、`rag_history.result` 等

**质量与红队**

- AgentGauntlet 配置项与注入包装（`_chaos_wrap` / `_guard_canary_output`）
- golden set 回归评估与 `/agent/capabilities` 真实运行态

### v1.0.1

- **Agent 编排**：LangGraph 8 节点、并行 fan-out/join、反思重试、评审循环、HITL `interrupt` / `resume`
- **流式**：任务 SSE 节点级进度 + `report_delta`；RAG `ask/stream`
- **LLM 治理**：`llm_invoker` 重试 / 熔断 / Provider 链降级 / 审计；AMD 提供商接入
- **RAG**：四层 PDF 提取、混合检索、`qwen3-rerank`、Adaptive RAG、问答历史
- **能力增强**：PostgresStore 偏好记忆、MCP 高德天气、Langfuse 观测、golden set 评估
- **运维**：Docker Compose 全栈、启动补列与种子、CORS 白名单

### v1.0.0

初版：大屏数据、智能查询、知识库 RAG、Agent 基础编排、报告中心、系统管理、JWT 认证、视觉识别。

---

*开发者：wjl（19136220923@163.com） · 后端源码：https://gitee.com/WJLGraph/fire_agent_back · 前端源码：https://gitee.com/WJLGraph/Fire_agent_front*
