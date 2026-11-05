# 网络请求基线（重构前）

> 用途：阶段 1（API 层收敛）验收时逐条比对 —— **URL、Method、请求体、响应解析结果必须与本表一致**。
> 记录时间：2026-10-31 · 基于 `master` 工作区源码静态提取
> 脱敏：本文只记录路径与参数结构，**不记录任何真实 Key / Token / 账号密码**。
> **存档说明**：本表是重构前的历史快照。后续变化：SSE 已改为 `fetch + Authorization` 请求头（`?token=` 仅保留给缓存旧 bundle 兜底）；会话改为 15 小时滑动续期；除 `/`、`/health`、`/auth/login`、`/auth/register`、`/dashboard/summary` 外全部接口需鉴权；报告流首帧补 `report_snapshot`。当前事实以 `README.md` / `整体实现.md` 为准。

## 通用约定

| 项 | 值 |
|---|---|
| 基址 | `import.meta.env.VITE_API_BASE`（dev/prod 均为 `/api`）→ `API_BASE`，`API_V1 = ${API_BASE}/v1` |
| 鉴权 | `Authorization: Bearer <token>`（取自 `localStorage.fire_agent_token`） |
| SSE 例外 | **重构前**：`EventSource` 无法带 Header → token 走 query：`?token=<urlencoded>`。**现状**：改为 `fetch + ReadableStream`，走 `Authorization: Bearer` |
| 成功判定 | `json.code === 200`，业务数据在 `json.data` |
| 401 行为 | `utils/authFetch.js`：`auth.logout()` + 跳 `/login?redirect=<当前 fullPath>` |

## 端点清单（前端当前实际调用）

### auth — `views/profile/index.vue`（裸 fetch）、`stores/auth.js`

| Method | 路径 | 请求体 | 现状 |
|---|---|---|---|
| POST | `/api/v1/auth/login` | `{username, password}` | stores/auth.js |
| POST | `/api/v1/auth/register` | `{username, password, email}` | stores/auth.js |
| PUT | `/api/v1/auth/me` | `{email}` | profile（裸 fetch，手动拼 Header） |
| PUT | `/api/v1/auth/me/password` | `{old_password, new_password, confirm_password}` | profile（裸 fetch） |

### dashboard — `api/dashboard.js`

| Method | 路径 | 参数 |
|---|---|---|
| GET | `/api/v1/dashboard/history-fires` | `start_date, end_date, city, confidence, page, page_size` |
| GET | `/api/v1/dashboard/predict-risks` | `year, month, day, view_mode, city` |
| GET | `/api/v1/dashboard/summary` | `start_date, end_date`（**已定义未使用**） |

> 该模块使用独立 `request()`：拼 URLSearchParams（跳过 `undefined/null/''`）→ `!res.ok` 抛 `HTTP xxx` → `json.code !== 200` 抛 `json.message` → 返回 `json.data`。

### query — `views/smart-query/index.vue`

| Method | 路径 | 请求体/参数 |
|---|---|---|
| POST | `/api/v1/query/execute` | `{query}` |
| GET | `/api/v1/query/history` | — |
| GET | `/api/v1/query/history/{id}` | — |
| DELETE | `/api/v1/query/history` | — |
| DELETE | `/api/v1/query/history/{id}` | — |

### rag — `views/knowledge-base/index.vue`

| Method | 路径 | 请求体 |
|---|---|---|
| POST | `/api/v1/rag/ask` | `{query, top_k}` |
| POST | `/api/v1/rag/ask/stream` | `{query, top_k}`（**fetch + reader 流式，非 EventSource**） |
| GET | `/api/v1/rag/documents` | — |
| POST | `/api/v1/rag/documents` | `FormData{file, category}` |
| DELETE | `/api/v1/rag/documents/{id}` | — |
| GET | `/api/v1/rag/history` | — |
| GET | `/api/v1/rag/history/{id}` | — |
| DELETE | `/api/v1/rag/history` | — |
| DELETE | `/api/v1/rag/history/{id}` | — |

### agent — `views/agent-center/index.vue`、`components/SystemCapabilities.vue`

| Method | 路径 | 请求体/参数 |
|---|---|---|
| POST | `/api/v1/agent/tasks` | `{query}` |
| GET | `/api/v1/agent/tasks` | — |
| GET | `/api/v1/agent/tasks/{id}` | — |
| DELETE | `/api/v1/agent/tasks/{id}` | — |
| POST | `/api/v1/agent/tasks/{id}/resume` | `{action: approve\|edit\|reject, content, comment}` |
| GET | `/api/v1/agent/tasks/{id}/stream` | 重构前：`?token=`，**SSE / EventSource**；现状：`Authorization` 请求头 + fetch 流，首帧 `report_snapshot` |
| GET | `/api/v1/agent/status` | — |
| GET | `/api/v1/agent/capabilities` | — |

### reports — `views/report-center/index.vue`、`views/agent-center/index.vue`

| Method | 路径 | 参数 |
|---|---|---|
| GET | `/api/v1/reports/list` | `page, page_size, report_type` |
| GET | `/api/v1/reports/{id}` | — |
| DELETE | `/api/v1/reports/{id}` | — |
| GET | `/api/v1/reports/export/{id}` | `?format=md\|html` → **blob 下载 / 打印** |

### vision（媒体） — `views/dashboard/index.vue`、`utils/speech.js`

| Method | 路径 | 请求体 |
|---|---|---|
| POST | `/api/v1/vision/analyze` | `FormData`（图片） |
| GET | `/api/v1/vision/history` | — |
| GET | `/api/v1/vision/history/{id}` | — |
| DELETE | `/api/v1/vision/history/{id}` | — |
| GET | `/api/v1/vision/image/{id}` | — |
| POST | `/api/v1/vision/audio/speech` | TTS |
| POST | `/api/v1/vision/audio/transcriptions` | `FormData`（音频，ASR） |

### admin — `views/admin/index.vue`（内联 authFetch）

| Method | 路径 | 请求体 |
|---|---|---|
| GET | `/api/v1/admin/config` | — |
| POST | `/api/v1/admin/config` | 配置字段（**仅更新非空字段**） |
| GET | `/api/v1/admin/status` | — |
| GET | `/api/v1/admin/logs` | `?limit=100` |
| GET | `/api/v1/admin/users` | — |
| PUT | `/api/v1/admin/users/{id}/role` | `{role}` |
| DELETE | `/api/v1/admin/users/{id}` | — |
| GET | `/api/v1/admin/llm/models` | `?provider=amd\|longcat\|aliyun` |
| GET | `/api/v1/admin/bailian/quota` | — |
| POST | `/api/v1/admin/test/db` | — |
| POST | `/api/v1/admin/test/llm` | — |

## 本地资源（非网络，但属数据降级路径）

| 资源 | 用途 |
|---|---|
| `assets/Yunnan_fire.json` | 历史火点（API 降级兜底） |
| `assets/Yunnan_border.json` | 州市行政边界 |
| `assets/predict_2025_2026_daily.json` / `_month.json` | 预测火险（API 降级兜底） |
| `assets/GTWR_Predicted_Risk_2025_2026.csv` | 预测风险原始表 |
| `assets/yunnan_terrain_normal.png` | 3D 地形贴图 |

## 基线快照说明

- **构建基线**：见 `build-baseline.txt`（`npm run build` 输出，含各 chunk 体积）。
- **视觉基线**：本环境无可用的无头浏览器截图能力，**未生成截图基线**。改为采用"代码级等价校验"：
  - 模板结构、class 名、样式规则在拆分/迁移时**逐字搬运**；
  - 每阶段通过 `npm run build` + 人工页面走查（按 `../frontend-refactor-plan.md` 第 7 节验收清单）确认；
  - 如需真正的像素级回归，建议在具备浏览器环境时补做。
