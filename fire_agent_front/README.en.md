# FlameSentry · Smart Fire-Risk Early Warning & Multi-Agent Collaboration Platform — Frontend (fire_agent_front)

> **Current version**: v1.0.1 (including post-v1.0.1 iterations: frontend structure refactor / visual system v2 / 2D-3D map migration / knowledge-base original-file reading / security hardening & streaming reliability — see [10. Version History](#10-version-history))
> This repository is the frontend of "FlameSentry — Smart Fire-Risk Early Warning & Multi-Agent Collaboration Platform" (deployed name: **焰哨多Agent与可视化平台**), built with **Vue 3 + Vite + OpenLayers + Three.js + ECharts + Element Plus**.
> Backend: [fire_agent_back](https://gitee.com/WJLGraph/Fire_agent_back) (FastAPI + PostgreSQL/PostGIS + LangChain/LangGraph)
> The full system design document is `整体实现.md` in the backend repository.
> **Live demo**: https://wjl2004.ffuf.cn/ or https://8.156.67.47/login
> **Demo account**: test / 123456
> **GitHub**: https://github.com/wjl-cong/fire_agent (Stars welcome)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Page-by-Page Features](#4-page-by-page-features)
5. [Frontend API Modules ↔ Backend Endpoints](#5-frontend-api-modules--backend-endpoints)
6. [Requirements](#6-requirements)
7. [Quick Start](#7-quick-start)
8. [Build & Deployment](#8-build--deployment)
9. [FAQ](#9-faq)
10. [Version History](#10-version-history)

---

## 1. Overview

A front-end/back-end separated SPA with **8 page routes** covering the whole fire-risk workflow:

| Page | Route | Access | Capabilities |
| ---- | ----- | ------ | ------------ |
| Login / Register | `/login` | Public | JWT login, register-and-login, `?redirect=` return |
| Situation Dashboard | `/dashboard` | Auth | Historical fire points / predicted risk / prefecture boundaries / heatmap / clustering / draw & measure / export PNG + 4 charts; one-click 2D/3D switch (Three.js digital twin); left AI fire-image recognition rail (vision model + history + Markdown rendering + speech) |
| Smart Query | `/smart-query` | Auth | Natural language → intent parsing → summary / table / chart / map four-way linkage; query history persisted server-side (dedup by text); voice input auto-execute + summary playback |
| Knowledge Base | `/knowledge-base` | Auth | Document upload & management + RAG Q&A (streaming typewriter + non-streaming fallback) + citations + full-text reader + PDF inline preview / original download; voice question + answer playback |
| Agent Center | `/agent-center` | Auth | Multi-agent pipeline with SSE node-level progress + HITL approval (approve / edit / reject) + full task replay + capability panel; voice task submission + report playback |
| Report Center | `/report-center` | Auth | Report list / detail / type filter / model badge / export Markdown / HTML / print to PDF (soft delete); report speech playback |
| Profile | `/profile` | Auth | Sidebar avatar entry, change email / password |
| Admin | `/admin` | **admin only** | Overview / datasource / model access (4 providers + AMD 5 capability classes + Bailian free-tier catalog + quota snapshot) / agent parameters / logs / users |

**Highlights**:

- **Agent identity across the UI**: DataAgent pipeline status and VisionAgent rail on the dashboard, QueryAgent parse panel on smart query, RagAgent retrieval panel in the knowledge base, ReportAgent badge in the report center.
- **3D digital-twin dashboard**: `components/map/Map3D.vue` (Three.js) — extruded prefecture polygons + side light-sweep shader + bezier flight lines + screen-space clustered fire columns (40px greedy clustering mirrored to the 2D OpenLayers cluster behaviour).
- **SSE streaming + HITL**: `openTaskStream` consumes node-level progress over `fetch` with an `Authorization` header (auto fallback to task detail on disconnect; the first `report_snapshot` frame restores what the current run has already produced); report drafts require human approval before being finalized into the report center.
- **Unified HTTP kernel**: every request goes through `api/http.js` (auto Bearer, 401 logout redirect, envelope parsing, upload progress, stream reading).
- **Dual theme + visual system v2**: `gis-theme.css` tokens + `theme-v2.css`, `html.dark` toggle applied before first paint; `localStorage.fire_agent_theme_v2 = 'off'` rolls back to the legacy visual layer.
- **End-to-end voice**: `utils/speech.js` records PCM via Web Audio API and encodes WAV in the browser (ASR), and plays TTS audio blobs.
- **Graceful degradation**: dashboard falls back to local JSON when backend APIs fail; no blank screens.
- **Single source of risk levels**: 5-level fire-risk colours and copy live in `utils/riskLevel.js` and match the backend thresholds exactly.

---

## 2. Tech Stack

| Category | Technology | Version | Purpose |
| -------- | ---------- | ------- | ------- |
| Framework | Vue 3 (Composition API) | ^3.5.13 | All pages use `<script setup>` |
| Routing | Vue Router | ^4.5.0 | 8 routes + auth/admin guards |
| State | Pinia | ^3.0.1 | auth store + theme store (token / user / theme persisted) |
| UI kit | Element Plus | ^2.9.6 | Tables / pagination / upload / message / confirm (zh-CN + auto import) |
| Map engine | OpenLayers | ^10.4.0 | Tianditu basemap, clustering, heatmap, boundaries, draw/measure |
| 3D engine | Three.js | ^0.186.1 | Digital twin (extruded polygons / flight lines / clustered columns / CSS2D labels) |
| Geospatial | Turf.js | ^7.2.0 | Area / distance measurement |
| Charts | ECharts | ^5.6.0 | 4 dashboard charts + smart-query result charts (GIS dark theme) |
| Heatmap | webgl-heatmap | ^0.2.3 | Fire-point density heatmap |
| Build | Vite | ^6.1.0 | Dev server + `/api` and `/tianditu` proxies |
| Utilities | file-saver / moment | ^2.0.5 / ^2.30.1 | Map export, time formatting |
| Quality | ESLint 9 + oxlint | dev | `npm run lint` runs both |

---

## 3. Project Structure

```
fire_agent_front/
├── vite.config.js                  ← /api proxy → http://localhost:8000;
│                                     /tianditu proxy with referer stripped (avoids 403);
│                                     Element Plus auto import; @ alias → src
├── .env.example                    ← VITE_TIANDITU_KEY / VITE_AMAP_KEY
├── package.json                    ← dependencies and scripts
└── src/
    ├── main.js                     ← Pinia / Router / Element Plus zh-CN; OL canvas willReadFrequently patch; theme applied early
    ├── App.vue
    ├── router/
    │   ├── index.js                ← 8 routes + global guards (auth + admin)
    │   └── navItems.js             ← sidebar nav definitions (adminOnly filter, icons rendered by AppIcon)
    ├── layout/MainLayout.vue       ← 72px sidebar (icon + 11px label), collapse, theme switch, avatar → profile
    ├── stores/
    │   ├── auth.js                 ← token / user in localStorage; login / register / logout / updateUser
    │   └── theme.js                ← html.dark + html.theme-v2; localStorage persistence
    ├── api/
    │   ├── http.js                 ← HTTP kernel: authFetch / parseJson / get / post / put / del /
    │   │                              postFormJson / postFormWithProgress / postStream
    │   ├── auth.js                 ← PUT /auth/me, PUT /auth/me/password (login/register handled by stores/auth.js)
    │   ├── dashboard.js            ← history fires / predicted risks
    │   ├── query.js                ← query execution + history
    │   ├── rag.js                  ← documents / Q&A / Q&A history
    │   ├── agent.js                ← task CRUD / resume / SSE stream subscription (fetch + Authorization) / capabilities & status
    │   ├── report.js               ← report list / detail / delete / export
    │   ├── admin.js                ← status / config / logs / model catalogs / quota / tests / users
    │   └── vision.js               ← fire-image recognition / image stream / TTS / ASR
    ├── composables/
    │   ├── useTaskStream.js        ← Agent SSE subscription (report_snapshot / step / report_think / think_reset / report_delta / approval / report / error + 180ms batched flush + 4s detail polling fallback while running)
    │   ├── useRiskAnalytics.js     ← risk scoring / levels / prefecture list / predicted GeoJSON / chart sources
    │   ├── useRequest.js           ← loading / error wrapper
    │   ├── useResizeObserver.js    ← chart container resize observer
    │   ├── useCountUp.js           ← number roll-up animation
    │   └── useThemeTokens.js       ← read theme CSS variables in JS
    ├── components/
    │   ├── base/                   ← AppIcon / AppBadge / AppEmpty / AppIconButton / AppPanel /
    │   │                              AppSectionTitle / AppSegmentedControl
    │   ├── common/                 ← HistoryPanel / MarkdownView / SpeakButton / VoiceInputButton
    │   ├── chart/                  ← EChart wrapper / ChartFullscreenDialog
    │   ├── map/
    │   │   ├── Map2D.vue           ← OpenLayers 2D map (Tianditu basemap / cluster / heatmap / boundaries / highlight)
    │   │   └── Map3D.vue           ← Three.js digital twin
    │   ├── clock.vue
    │   └── SystemCapabilities.vue  ← capability panel (GET /agent/capabilities)
    ├── utils/
    │   ├── speech.js               ← PCM → 16-bit WAV (ASR) + TTS playback (480-char truncation)
    │   ├── markdown.js             ← safe Markdown rendering (HTML escaped)
    │   ├── riskLevel.js            ← 5-level risk colours / copy (matches backend)
    │   ├── config.js               ← API_V1 and constants
    │   ├── themeTokens.js / llmProviders.js / reportMeta.js
    │   ├── map3dGeo.js / map3dMaterial.js / map3dTheme.js
    │   ├── cityCenter.js / parseGeoData.js / setPointStyle.js / timeWeather.js
    │   └── draw.js / computed.js / downLoad.js
    ├── style/
    │   ├── common.css
    │   ├── gis-theme.css           ← light/dark CSS variable tokens (html.dark)
    │   ├── theme-v2.css            ← visual system v2 (headers / cards / buttons / tables / hairlines / square badges)
    │   └── markdown.css
    ├── views/
    │   ├── login/index.vue
    │   ├── dashboard/              ← index + 8 sub-components (AnimNumber, ClusterDrawer, DashboardTopBar,
    │   │                              FireWarningBar, MapOverlays, MapToolbar, RailFilterPanel, VisionRail)
    │   ├── smart-query/            ← index + 5 sub-components (QueryHistoryRail, QueryInputPanel,
    │   │                              QueryParsePanel, QueryResultMap, QueryResultPanel)
    │   ├── knowledge-base/         ← index + 6 sub-components (KbAnswerPanel, KbDocReader, KbDocsPanel,
    │   │                              KbQaInput, KbReferenceList, KbRetrievalPanel)
    │   ├── agent-center/           ← index + 6 sub-components (AgentPipeline, AgentReportView, AgentStreamView,
    │   │                              ApprovalPanel, TaskFormCard, TaskHistoryList)
    │   ├── report-center/          ← index + ReportListPanel + ReportDetailPanel
    │   ├── admin/                  ← index + AdminOverview, AdminDatasource, AdminModel,
    │   │                              AdminModelAliyun, AdminModelAmd, AdminModelLongcat, AdminModelOllama,
    │   │                              AdminAgent, AdminLogs, AdminUsers
    │   ├── chart/                  ← 4 dashboard charts
    │   └── profile/index.vue
    └── assets/                     ← local fallback data (Yunnan_fire.json / Yunnan_border.json /
                                        predict_2025_2026_daily.json / predict_2025_2026_month.json)
```

### 3.1 Layering conventions

- `views/*` only orchestrates; complex blocks are split into sibling sub-components. **No single file exceeds 800 lines after the refactor.**
- All backend calls go through `api/*`; pages never call `fetch` directly. `api/http.js` is the only HTTP kernel.
- Reusable pure computation lives in `composables/` (e.g. `useTaskStream`, `useRiskAnalytics`) and never holds map instances.
- Visual tokens come from `gis-theme.css` / `theme-v2.css`; no hard-coded colours in components.

### 3.2 Legacy file cleanup

The following leftover files from earlier versions (untracked in git, referenced by no page) were removed on 2026-11-01; the `unplugin-vue-components` `Map3D` naming-conflict warning is gone with them:

- `src/components/map.vue` (replaced by `src/components/map/Map2D.vue`)
- `src/components/Map3D.vue` (replaced by `src/components/map/Map3D.vue`)
- `src/utils/authFetch.js` (inlined into `src/api/http.js`)
- `src/utils/echartsGisTheme.js` (replaced by `RISK_COLORS` in `utils/riskLevel.js`)

---

## 4. Page-by-Page Features

### 4.1 Login / Register (`/login`)

- Two modes with validation (username ≥ 2 chars, password ≥ 6 chars, confirmed password).
- Successful login/register stores the JWT in `localStorage.fire_agent_token` and returns to `?redirect=`.
- No sidebar on this route (BlankLayout); dark glass card UI.

### 4.2 Situation Dashboard (`/dashboard`)

- **Data flow**: `Promise.all` for historical fire points (max 5000) / daily predictions / monthly predictions; any failure falls back to local JSON.
- **2D map** (`components/map/Map2D.vue`): Tianditu basemap, clustering (distance 40, `ClusterDrawer` on click), webgl heatmap, 16 prefecture boundaries, polygon/line draw + Turf measurement, PNG export.
- **3D digital twin** (`components/map/Map3D.vue`): extruded prefecture polygons + light-sweep shader + bezier flight lines + screen-space clustered columns (40px greedy clustering mirrored to the 2D cluster) + ExtrudeGeometry base pads; light/dark theme; entry dive, hover lift, `city-click` highlighting the 2D layer.
- **Fire-risk warning** (`FireWarningBar.vue` + `composables/useRiskAnalytics.js`): overall score, 5-level rating, prefecture risk list and dynamic summary from `Final_Fire_Index` (daily) or `Risk_Score` (monthly).
- **Charts** (`views/chart/`): historical risk-level distribution / fire frequency / predicted warning share / predicted distribution, with fullscreen view.
- **Top bar** (`DashboardTopBar.vue`): live clock, AMap weather, daily/monthly switch, DataAgent pipeline status.
- **Left AI fire-image rail** (`VisionRail.vue`, collapsible 34px ↔ 310px): drag-and-drop photo → vision model → Markdown result (verdict / scene / severity / actions) → speech playback; history replay via authenticated image stream; single-item delete.

### 4.3 Smart Query (`/smart-query`)

- Natural-language input (textarea, Ctrl+Enter, 4 examples) + voice input (record → ASR → auto execute).
- **QueryAgent parse panel** (`QueryParsePanel.vue`): intent (history / predict / summary), structured parameter chips, parser badge (`llm` / `keyword`), explanation.
- **Four-way result linkage**: summary card (speech), dynamic-column table, chart (bar / line / pie), map (`QueryResultMap.vue` with risk-level colours and auto-fit).
- **History rail** (`QueryHistoryRail.vue`): collapse/expand, server persistence (dedup by text), per-user isolation, pagination, single delete, parser label, full-result replay.

### 4.4 Knowledge Base (`/knowledge-base`)

- **Documents panel** (`KbDocsPanel.vue`): drag/click upload (PDF / TXT / MD), byte-level progress, status badges, delete, prompt category.
- **Q&A** (`KbQaInput.vue` / `KbAnswerPanel.vue`): example questions, voice question (auto submit after ASR), answer card with LLM / keyword badge + speech playback.
- **Retrieval panel** (`KbRetrievalPanel.vue`): matched documents / chunks / method (hybrid / keyword + rerank).
- **Citations** (`KbReferenceList.vue`): relevance score + expandable full text.
- **Document reader** (`KbDocReader.vue`): `GET /rag/documents/{id}/content` (chunks concatenated) in a paper-style overlay; PDF inline preview via `GET /rag/documents/{id}/file` with original download.
- **Streaming Q&A**: prefers `POST /rag/ask/stream` (SSE typewriter, citations appended at the end), falls back to the non-streaming endpoint.

### 4.5 Agent Center (`/agent-center`)

- Task input (`TaskFormCard.vue`, Ctrl+Enter + examples) + voice input (auto execute after ASR).
- **Agent status bar**: 6 agents (including Reviewer) from `GET /agent/status`.
- **Pipeline** (`AgentPipeline.vue`): parse task → query data → analyze GIS → retrieve knowledge → generate report → quality review → human approval, with completed / running / pending states. The 7th step (human approval) can be hidden for legacy tasks; the backend graph actually has 8 nodes (including the UI-less `join`).
- **SSE progress** (`composables/useTaskStream.js`): `openTaskStream` subscribes to `GET /agent/tasks/{id}/stream` over `fetch` with `Authorization: Bearer` (the token never goes into the query string), streaming node progress and `report_delta` (typewriter, 180ms batched flush); the first `report_snapshot` frame restores the current run's report/thinking, and a broken stream falls back to `GET /agent/tasks/{id}`.
- **HITL approval** (`ApprovalPanel.vue`): the task pauses after the draft report is generated; approve / approve-edited / reject-with-comment; only after resume is the report finalized into the report center.
- **Capability panel** (`SystemCapabilities.vue`): `GET /agent/capabilities` (LLM / checkpointer / orchestration / data / RAG / memory / MCP / observability / evaluation / degradation).
- **Execution summary** (`AgentStreamView.vue`) + Markdown report (`AgentReportView.vue`, speech) + ReportAgent badge; when the pipeline is collapsed the report card fills the remaining height (`flex: 1`) and scrolls internally.
- **Task history** (`TaskHistoryList.vue`): server-persisted, click to replay, single delete; replay chain: local cache → `GET /agent/tasks/{id}` with persisted steps (`agent_task_steps`) and linked report.

### 4.6 Report Center (`/report-center`)

- **List panel** (`ReportListPanel.vue`): type filter (all / daily / weekly / monthly / special) + pagination + type badges / tags / summary + single delete.
- **Model badge**: `llm_model` first (e.g. qwen-max), fallback to provider name (Alibaba Bailian / AMD GPU Cloud / LongCat / Ollama).
- **Soft delete**: a user delete hides the report only for that user (admins still see it); an admin delete is a global soft delete.
- **Detail** (`ReportDetailPanel.vue`): Markdown rendering + speech (summary + body) / export Markdown / export HTML / print to PDF / delete.
- ReportAgent badge marks agent-generated reports.

### 4.7 Admin (`/admin`, admin only)

| Tab | Features |
| --- | -------- |
| Overview | Version, database status, LLM availability, 5 agent cards |
| Datasource | Masked database URL + connection test |
| Model access | Four provider blocks (Bailian / AMD GPU Cloud / LongCat / Ollama): provider switch, masked API key (`sk-***xxx`), model selection, save writes `.env` and hot-reloads, real LLM invoke test; **Bailian free-tier catalog** (5 tabs: LLM / vision / omni / speech / embedding, live availability, ordered free-first → longer validity → current → verified, one-click "Use"); **AMD 4-class catalog** (LLM / vision / speech / OCR, live tokenfactory crawl, free / limited-free / paid tiers); **LongCat catalog**; **Bailian quota snapshot** (5 categories + account quota table) |
| Agent params | Orchestration temperature / report temperature / max agents |
| Logs | 200-entry ring buffer (agent tasks / config changes / user management / connection tests), 30s polling |
| Users | User list, role change (self-change blocked), delete user (self-delete blocked) |

### 4.8 Profile (`/profile`)

- Reachable from the sidebar avatar; update email (`PUT /auth/me`) and password (`PUT /auth/me/password`, old-password check, confirmed new password).

---

## 5. Frontend API Modules ↔ Backend Endpoints

> All paths are prefixed with `/api/v1`. `api/http.js` attaches `Authorization: Bearer <token>`; every business endpoint requires auth except `GET /`, `GET /health`, `POST /auth/login`, `POST /auth/register` and `GET /dashboard/summary` (aggregate counts only); `scripts/check_auth_coverage.py` enforces an explicit auth declaration for all 62 backend routes.
>
> JWTs use HS256 with `exp = iat + 15h` and a sliding session: authenticated responses may carry `X-Token-Refresh` (exposed via CORS `expose_headers`), and the client absorbs it only within a 10-minute activity window, so just 15 consecutive idle hours force a re-login. The `tv` claim is compared with `users.token_version`, so a password change or deactivation revokes old tokens (a token without `tv` counts as 0).

| Frontend module | Function | Method & endpoint |
| --------------- | -------- | ----------------- |
| `stores/auth.js` | `login` / `register` | `POST /auth/login`, `POST /auth/register` |
| `api/auth.js` | `updateMe` / `changePassword` | `PUT /auth/me`, `PUT /auth/me/password` |
| `api/dashboard.js` | `fetchHistoryFires` / `fetchPredictRisks` | `GET /dashboard/history-fires`, `GET /dashboard/predict-risks` |
| `api/query.js` | `execute` | `POST /query/execute` |
| `api/query.js` | history CRUD | `GET /query/history`, `GET /query/history/{id}`, `DELETE /query/history`, `DELETE /query/history/{id}` |
| `api/rag.js` | documents | `GET /rag/documents`, `POST /rag/documents` (FormData), `DELETE /rag/documents/{id}`, `GET /rag/documents/{id}/content` |
| `api/rag.js` | Q&A | `POST /rag/ask`, `POST /rag/ask/stream` (SSE) |
| `api/rag.js` | Q&A history | `GET /rag/history`, `GET /rag/history/{id}`, `DELETE /rag/history`, `DELETE /rag/history/{id}` |
| `views/knowledge-base/KbDocReader.vue` | original file | `GET /rag/documents/{id}/file` (authenticated URL built in the component) |
| `api/agent.js` | status / capabilities | `GET /agent/status`, `GET /agent/capabilities` |
| `api/agent.js` | tasks | `POST /agent/tasks`, `GET /agent/tasks`, `GET /agent/tasks/{id}`, `DELETE /agent/tasks/{id}` |
| `api/agent.js` | `resumeTask` | `POST /agent/tasks/{id}/resume` (approve / edit / reject) |
| `api/agent.js` | `openTaskStream` | `GET /agent/tasks/{id}/stream` (SSE, `fetch` + `Authorization` header) |
| `api/report.js` | list / detail / delete | `GET /reports/list`, `GET /reports/{id}`, `DELETE /reports/{id}` |
| `api/report.js` | export | `GET /reports/export/{id}?format=md\|html` |
| `api/admin.js` | status / config / logs | `GET /admin/status`, `GET /admin/config`, `POST /admin/config`, `GET /admin/logs?limit=100` |
| `api/admin.js` | catalogs / quota | `GET /admin/llm/models?provider=aliyun\|amd\|ollama\|longcat`, `GET /admin/bailian/quota` |
| `api/admin.js` | tests / users | `POST /admin/test/db`, `POST /admin/test/llm`, `GET /admin/users`, `PUT /admin/users/{id}/role`, `DELETE /admin/users/{id}` |
| `api/vision.js` | recognition | `POST /vision/analyze`, `GET /vision/history`, `DELETE /vision/history/{id}`, `GET /vision/image/{id}` |
| `api/vision.js` | audio | `POST /vision/audio/speech`, `POST /vision/audio/transcriptions` |

**Two streaming channels**:

- Agent progress uses `fetch + ReadableStream` (`api/agent.js#openTaskStream` with an `Authorization` header) instead of `EventSource`: the native API cannot send custom headers, and a token in the query string would leak into Nginx access logs.
- RAG Q&A also uses `fetch + ReadableStream` (`api/http.js#postStream`) because the question must be POSTed with query / top_k.

---

## 6. Requirements

| Component | Requirement |
| --------- | ----------- |
| Node.js | **18+** (20 LTS recommended) |
| npm | 9+ (bundled with Node) |
| Backend | `fire_agent_back` running at `http://localhost:8000` |
| Browser | Modern Chrome / Edge (voice requires a secure context) |

---

## 7. Quick Start

### 7.1 Start the backend first

```bash
cd fire_agent_back
conda activate fire_agent_back
uvicorn app.main:app --reload --port 8000
```

See the backend README for details: https://gitee.com/WJLGraph/Fire_agent_back

Backend `.env` (see the backend repository's `.env.example`): `ENV` (development | production), `JWT_SECRET` (empty in the template; generate with `python -c "import secrets;print(secrets.token_urlsafe(48))"`), `ADMIN_INIT_PASSWORD` (empty), `CORS_ORIGINS` (JSON array).

### 7.2 Start the frontend

```bash
cd fire_agent_front
npm install
npm run dev
```

Open **http://localhost:5173**.

- Default admin: `admin / 123456` (seeded on first backend start).
- Unauthenticated users are redirected to `/login`.
- Env vars (`.env.example`): `VITE_TIANDITU_KEY`, `VITE_AMAP_KEY`.

### 7.3 Proxy configuration

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
        proxy.on('proxyReq', req => delete req.getHeaders().referer)   // strip referer to avoid Tianditu 403
      },
    },
  },
}
```

If the backend runs on another port, change the `/api` target and restart `npm run dev`.

### 7.4 Accounts and permissions

| Account | Role | Accessible pages |
| ------- | ---- | ---------------- |
| admin | admin | All 8 pages (including Admin) |
| registered | user | 7 pages (Admin excluded) |

---

## 8. Build & Deployment

```bash
npm run build        # production build → dist/
npm run preview      # preview the build locally
npm run lint         # oxlint + eslint
```

`base: './'` is set in `vite.config.js`, so the build works under any sub-path. `dist/` is ignored by `.gitignore` and does not travel with git; server deployments (e.g. BT panel) must rebuild inside the frontend directory on the server. Nginx example:

```nginx
server {
    listen 80;
    root /path/to/fire_agent_front/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;   # SPA fallback
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_buffering off;                # SSE must not be buffered
        proxy_read_timeout 3600s;
    }
}
```

> SSE endpoints (`/agent/tasks/{id}/stream`, `/rag/ask/stream`) require unbuffered proxying; otherwise progress arrives in one burst.

---

## 9. FAQ

| Problem | Solution |
| ------- | -------- |
| Blank page / no data | Ensure the backend is up (`http://localhost:8000/health` returns ok); check DevTools; hard refresh |
| Voice input does nothing | Grant microphone permission; use Chrome/Edge over `localhost` or HTTPS (`getUserMedia` requires a secure context) |
| Speech playback fails | The backend needs a Bailian `LLM_API_KEY` (TTS primary path is Bailian, with AMD OmniVoice fallback); check backend TTS logs |
| Redirected back to login | Check backend `JWT_SECRET` (production requires `ENV=production` and a random `JWT_SECRET` of at least 32 bytes; empty, weak or public placeholder values abort startup); clear `localStorage` (`fire_agent_token` / `fire_agent_user`) and sign in again |
| Basemap missing | Replace `VITE_TIANDITU_KEY`; in dev ensure the `/tianditu` proxy works (referer is stripped) |
| UI suddenly looks legacy | Check `localStorage.fire_agent_theme_v2`; set to `on` or remove it and refresh to restore v2 visuals |
| Port in use | `npm run dev -- --port 5174`, and update backend `CORS_ORIGINS` |
| Slow npm install | `npm config set registry https://registry.npmmirror.com` |
| PDF yields no text | The backend's four-layer extraction (pdfplumber → pypdf → PyMuPDF → OCR) may have failed; check logs and `OCR_PROVIDER` |

---

## 10. Version History

### Post-v1.0.1 iterations (current code state)

**Structural refactor**

- Unified data layer: `api/http.js` kernel (`authFetch` / `parseJson` / `get·post·put·del` / `postFormWithProgress` / `postStream`); `utils/authFetch.js` inlined and removed; new `api/auth.js`, `api/dashboard.js`, `api/query.js`, `api/rag.js`, `api/agent.js`, `api/report.js`, `api/admin.js`, `api/vision.js`.
- `components/` layering: `base/` (AppIcon / AppBadge / AppEmpty / AppIconButton / AppPanel / AppSectionTitle / AppSegmentedControl), `common/` (HistoryPanel / MarkdownView / SpeakButton / VoiceInputButton), `chart/`, `map/`.
- Map migration: `components/map.vue` → `components/map/Map2D.vue`, `components/Map3D.vue` → `components/map/Map3D.vue`.
- `views/` split into sub-components: dashboard 8, smart query 5, knowledge base 6, agent center 6, report center 2, admin 10; **no file exceeds 800 lines**.
- `composables/`: `useTaskStream` (SSE), `useRiskAnalytics` (risk scoring / predicted GeoJSON), `useRequest`, `useResizeObserver`, `useCountUp`, `useThemeTokens`.
- Navigation extracted to `router/navItems.js` (adminOnly filter + inline SVG icons).

**Visual system v2 / v0**

- New `src/style/theme-v2.css`: headers, cards, buttons, tables, hairlines, square badges, sunken surfaces; activated by `html.theme-v2`, rollback via `localStorage.fire_agent_theme_v2 = 'off'`.
- Sidebar 48px → 72px (icon + 11px label); emoji/character buttons replaced with 20px linear SVG; metal gradients / glows / bounce removed; active state reduced to a 2px solid bar.
- Admin, Agent Center, Knowledge Base, Report Center and Profile rebuilt against the v0 prototype.

**Feature increments**

- Knowledge base: full document text `GET /rag/documents/{id}/content`, PDF inline preview + original download `GET /rag/documents/{id}/file`, upload byte progress.
- Lists: pagination and compact single-line layout for query history / Q&A history / report list.
- Admin: four provider blocks (Bailian / AMD / LongCat / Ollama); AMD four capability classes (LLM / vision / speech / OCR) with one-click switching and chain annotations.

**Security hardening**

- SSE and auth: Agent progress moved to `fetch` + `Authorization` (`openTaskStream`) so the token never appears in the query string; JWTs now use a 15-hour sliding session (`X-Token-Refresh`), where only 15 consecutive idle hours require a re-login.
- Uploads: size + extension + magic-byte validation in the backend.
- Secrets and logs: `JWT_SECRET` startup self-check (production rejects empty / <32-byte / publicly known placeholder values); keys and tokens are redacted from logs and error messages.
- Frontend: admin console links bind `:href` only for https URLs (blocks `javascript:`); dashboard data fetching goes through `authFetch` (a raw `fetch` previously made a 401 look like "local fallback data" forever).
- Production (`ENV=production`) disables `/docs` and `/redoc`.

### v1.0.1

- **Agent Center**: v1.0.1 used `EventSource` for node-level progress (fallback to task detail on disconnect; later hardening switched to `fetch` + `Authorization`); HITL approval gate (draft pauses → approve / edit / reject → resume finalizes the report); server-persisted task history with full replay; `report_delta` streaming report rendering; capability panel.
- **3D dashboard**: Three.js digital twin — extruded polygons + light-sweep shader + bezier flight lines + rotating rings + rising light columns + CSS2D labels; screen-space clustered fire columns (40px greedy clustering mirrored from the 2D OL cluster, 120ms wheel debounce, base columns keep all 16 prefectures visible); ExtrudeGeometry base pads close boundary cracks; light/dark themes; entry dive, hover lift, `city-click`.
- **Dual theme system**: `stores/theme.js` + `style/gis-theme.css` tokens + `utils/themeTokens.js`.
- **End-to-end voice**: `utils/speech.js` (Web Audio PCM→WAV ASR + TTS playback) wired into the dashboard AI rail, smart query, knowledge base, agent center and report center.
- **Report Center**: type filter + badges, model badge (`llm_model` first, provider fallback), user soft delete / admin soft delete.
- **Knowledge Base**: `/rag/ask/stream` streaming Q&A with non-streaming fallback.
- **Smart Query**: server-persisted query history (dedup by text).
- **Admin**: AMD `tokenfactory` live catalog, Bailian free-tier catalog (5 classes) + quota snapshot, config save writes `.env` and hot-reloads, masked API keys, 30s log polling.
- **Profile**: new `/profile` route.
- Backend same version: SSE orchestration, HITL interrupt/resume, rerank, MCP weather tool, PostgresStore memory, Langfuse observability, golden-set regression, Docker delivery.

### v1.0.0

Initial release: login/register / 2D dashboard / smart query / knowledge-base RAG / basic agent center / report center / basic admin.

---

*Developer: wjl (19136220923@163.com) · Frontend: https://gitee.com/WJLGraph/Fire_agent_front · Backend: https://gitee.com/WJLGraph/Fire_agent_back*
</content>
