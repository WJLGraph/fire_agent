# FlameSentry · Smart Fire-Risk Early Warning & Multi-Agent Collaboration Platform — Backend (fire_agent_back)

> **Current version**: v1.0.1 (including post-v1.0.1 iterations: LongCat integration / AMD GPU Cloud four capability classes / knowledge-base full text & original files / startup self-healing / AgentGauntlet red teaming / security hardening & streaming reliability — see [13. Version History](#13-version-history))
> This repository is the backend of "FlameSentry — Smart Fire-Risk Early Warning & Multi-Agent Collaboration Platform" (deployed name: **焰哨多Agent与可视化平台**), built with **FastAPI + PostgreSQL/PostGIS + LangChain/LangGraph**.
> Frontend: [fire_agent_front](https://gitee.com/WJLGraph/Fire_agent_front) (Vue 3 + Vite + OpenLayers + Three.js)
> **Live demo**: https://wjl2004.ffuf.cn/ or https://8.156.67.47/login
> **Demo account**: test / 123456
> **GitHub**: https://github.com/wjl-cong/fire_agent (Stars welcome)

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Data Model](#4-data-model)
5. [API Reference](#5-api-reference)
6. [Agent Orchestration](#6-agent-orchestration)
7. [LLM Access & Degradation](#7-llm-access--degradation)
8. [RAG Pipeline](#8-rag-pipeline)
9. [Memory · Tools · Observability · Evaluation · Red Teaming](#9-memory--tools--observability--evaluation--red-teaming)
10. [Startup & Configuration](#10-startup--configuration)
11. [Docker Deployment](#11-docker-deployment)
12. [FAQ](#12-faq)
13. [Version History](#13-version-history)

---

## 1. Overview & Architecture

An agent-driven fire-risk analysis service: it accepts natural-language tasks → LangGraph multi-agent orchestration (data query / GIS analysis / knowledge retrieval / report generation / report review / human approval) → persists reports. It also serves dashboard data, smart query, knowledge-base RAG, vision recognition, speech synthesis/transcription and administration APIs.

```
┌──────────────────────────────────────────────────────────────┐
│                    Vue 3 frontend (SPA)                      │
│  Dashboard / Query / Knowledge Base / Agent / Reports / Admin │
└───────────────┬──────────────────────────┬───────────────────┘
                │ REST (JSON envelope)      │ SSE (fetch stream + Authorization header)
┌───────────────▼──────────────────────────▼───────────────────┐
│                     FastAPI (/api/v1)                        │
│ dashboard │ query │ rag │ agent │ reports │ admin │ auth │ vision │
├──────────────────────────────────────────────────────────────┤
│ services : data / query / rag                                 │
│ agents   : orchestrator (LangGraph, 8 nodes)                 │
│ core     : llm / llm_invoker / reranker / memory_store /     │
│            mcp_client / observability / amd_directory        │
├──────────────────────────────────────────────────────────────┤
│ PostgreSQL + PostGIS (13 business tables / pgvector)          │
│ File storage (KB_UPLOAD_DIR originals) / recognition images   │
└──────────────────────────────────────────────────────────────┘
        │                    │                    │
   Alibaba Bailian      AMD GPU Cloud        Ollama / LongCat
   (LLM/Embedding/      (text/vision/         (local or third-party
    Vision/ASR/TTS)      speech/ocr)            OpenAI-compatible)
```

**Core capabilities**:

- **Multi-agent orchestration**: LangGraph `StateGraph` with 8 nodes, parallel fan-out/join, reflection retries, report review loop and HITL interrupt/resume.
- **Streaming delivery**: agent task SSE node-level progress + report deltas; RAG Q&A SSE typewriter.
- **Four LLM providers**: unified `llm_invoker` with retry / circuit breaker / provider-chain fallback / rule-based fallback.
- **AMD four capability classes**: LLM / vision / speech / OCR, switchable from the admin UI.
- **Knowledge base**: four-layer PDF extraction + Chinese-aware chunking + hybrid retrieval + rerank + Adaptive RAG + full-text and original-file endpoints.
- **Observability & quality**: Langfuse tracing, golden-set regression evaluation, AgentGauntlet chaos injection.

---

## 2. Tech Stack

| Category | Dependency | Version | Purpose |
| -------- | ---------- | ------- | ------- |
| Web framework | FastAPI | 0.115.0 | Routing / DI / docs |
| ASGI | uvicorn | — | Runtime |
| ORM | SQLAlchemy | 2.0.35 | Models & sessions |
| Spatial | GeoAlchemy2 | 0.15.1 | PostGIS geometry fields |
| Database | PostgreSQL + PostGIS | 16 / 3.x | Business & spatial data |
| Vector | pgvector | 0.3.6 | KB chunk embeddings |
| Driver | psycopg[binary] | 3.3.6 | PostgreSQL connection |
| Orchestration | langgraph | 0.2.64 | StateGraph / interrupt / checkpointer |
| LLM framework | langchain | 0.3.17 | Prompts / tools / callbacks |
| OpenAI compatible | langchain-openai | 0.3.0 | AMD / LongCat / Ollama |
| Bailian SDK | dashscope | 1.27.7 | Bailian LLM / Embedding / ASR / TTS |
| Checkpoint | langgraph-checkpoint-postgres | 2.0.15 | PostgresSaver (falls back to MemorySaver) |
| PDF | pdfplumber / pypdf / PyMuPDF | — | Three extraction layers |
| OCR | rapidocr-onnxruntime | — | Local OCR fallback |
| Observability | langfuse | 4.15.4 | LLM tracing |
| MCP | mcp / langchain-mcp-adapters | 2.2.0 / 0.2.0 | AMap weather tool (stdio) |
| Testing | pytest | 9.1.1 | Regression evaluation |

> `requirements.txt` was synced on 2026-10-02; AgentGauntlet is a local evaluation package and is not a deployment dependency.

---

## 3. Project Structure

```
fire_agent_back/
├── app/
│   ├── main.py                     ← lifespan: create_all → idempotent column patching → seed admin/123456 →
│   │                                  startup self-healing (running → failed + zombie step cleanup); CORS; 8 routers
│   ├── core/
│   │   ├── config.py               ← all settings (VERSION = "1.0.1"), REPORT_FOOTER
│   │   ├── database.py             ← Engine / SessionLocal / get_db
│   │   ├── security.py             ← JWT sign/verify, password hashing
│   │   ├── llm.py                  ← get_llm / get_embedding / get_vision_llm /
│   │   │                              transcribe_audio / synthesize_speech / amd_ocr_pdf
│   │   ├── llm_invoker.py          ← retry (1s/2s/4s) ×3, breaker (3 failures/60s), provider chain, audit
│   │   ├── reranker.py             ← qwen3-rerank with RRF fallback
│   │   ├── memory_store.py         ← PostgresStore preference memory (disabled on failure)
│   │   ├── mcp_client.py           ← lazy MCP + get_weather_for_city
│   │   ├── observability.py        ← Langfuse CallbackHandler
│   │   └── amd_directory.py        ← live AMD tokenfactory catalog crawler
│   ├── api/v1/routes/
│   │   ├── dashboard.py
│   │   ├── query.py
│   │   ├── rag.py
│   │   ├── agent.py                ← tasks / SSE / capabilities / status
│   │   ├── report.py
│   │   ├── admin.py                ← built-in model catalogs & quota snapshots
│   │   ├── auth.py
│   │   └── media.py                ← vision / speech (mounted at /api/v1/vision)
│   ├── agents/
│   │   ├── orchestrator_agent.py   ← LangGraph orchestration (8 nodes + fallback nodes + graph builder)
│   │   ├── data_agent.py           ← DataAgent: data-query node
│   │   ├── gis_agent.py            ← GisAgent: GIS analysis node
│   │   ├── rag_agent.py            ← RagAgent: knowledge retrieval node
│   │   └── report_agent.py         ← ReportAgent: report generation / review
│   ├── services/
│   │   ├── data_service.py         ← dashboard data queries (wraps FireRepository)
│   │   ├── query_service.py        ← intent parsing (llm / keyword) + executors
│   │   └── rag_service.py          ← upload / extract / chunk / retrieve / rerank / generate
│   ├── models/                     ← 13 business tables
│   ├── schemas/                    ← Pydantic (admin / agent / common / dashboard / query / rag / report / user)
│   ├── repositories/               ← fire_repository / report_repository
│   └── utils/
├── mcp_server/weather_server.py    ← FastMCP stdio: AMap geo → adcode → weather
├── scripts/
│   ├── init_db.py
│   ├── import_fire_points.py / import_predict_risks.py / import_region_boundaries.py
│   ├── run_all_imports.py
│   ├── eval_regression.py          ← golden-set regression evaluation
│   └── golden_set.json
├── migrations/                     ← SQL migrations
├── sql/public.sql
├── docker-compose.yml              ← db / backend / frontend (+ optional langfuse profile)
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 4. Data Model

**13 business tables**:

| # | Table | Description |
| - | ----- | ----------- |
| 1 | `users` | username / email / password_hash / role (admin \| user) |
| 2 | `fire_points` | Historical fire points (lat/lon, brightness, confidence, time, province/city/county) |
| 3 | `fire_risks` | Predicted risk (Year / Month / Day / City / Final_Fire_Index / Pred_Fire_Count / Risk_Score / Pred_Fire_Risk) |
| 4 | `regions` | Administrative boundaries (PostGIS geometry, prefecture / county) |
| 5 | `resources` | Emergency resources (teams / supplies / locations) |
| 6 | `agent_tasks` | status / query / parsed_intent / report_id / llm_provider / llm_model / llm_tokens / llm_degraded / user_id / timestamps |
| 7 | `agent_task_steps` | step_name / status / detail / timestamps; incremental upsert on `(task_id, step_name)` |
| 8 | `analysis_reports` | report_type / title / content / summary / llm_provider / llm_model / llm_tokens / llm_degraded / user_id / soft-delete flags |
| 9 | `kb_documents` | filename / file_type / file_path / category / chunk_count / user_id |
| 10 | `kb_chunks` | content / embedding / index |
| 11 | `query_history` | query / result JSON, deduplicated per user + text |
| 12 | `rag_history` | query / answer / sources / result JSON |
| 13 | `vision_history` | image path / Markdown result / timestamps |

---

## 5. API Reference

Base path `/api/v1`. **Every endpoint except `/`, `/health`, `/auth/login`, `/auth/register` and `/dashboard/summary` requires `Authorization: Bearer <JWT>`.** `/dashboard/summary` is the only deliberately anonymous business endpoint (the public portal and login page show real aggregate counters before sign-in; it returns aggregates only, never per-row data). Auth requirements are enforced statically by `scripts/check_auth_coverage.py`: all 62 routes must declare their policy explicitly, and a new undeclared endpoint fails the check.

### 5.1 Dashboard (`/dashboard`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/dashboard/history-fires` | Historical fire points (limit / time / area filters, default cap 5000) |
| GET | `/dashboard/predict-risks` | Predicted risk (daily / monthly, filtered by Year-Month-Day) |
| GET | `/dashboard/summary` | Aggregate statistics |

### 5.2 Smart Query (`/query`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/query/parse` | Parse only, does not execute |
| POST | `/query/execute` | Parse + execute + persist (dedup per user + text) |
| GET | `/query/history` | History (per-user isolation) |
| GET | `/query/history/{history_id}` | Detail (full result replay) |
| DELETE | `/query/history` | Clear history |
| DELETE | `/query/history/{history_id}` | Delete one entry |

### 5.3 Knowledge Base (`/rag`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/rag/ask` | RAG answer (Adaptive, persisted) |
| POST | `/rag/ask/stream` | Streaming RAG (SSE: `meta` → `delta` → `done`, partial answers not persisted) |
| GET | `/rag/history` | Q&A history |
| GET | `/rag/history/{history_id}` | Q&A detail |
| DELETE | `/rag/history` | Clear |
| DELETE | `/rag/history/{history_id}` | Delete one |
| POST | `/rag/documents` | Upload (FormData: file + category) |
| GET | `/rag/documents` | List (includes file_type / chunk_count) |
| GET | `/rag/documents/{doc_id}/content` | Full text (chunks concatenated, owner/admin only) |
| GET | `/rag/documents/{doc_id}/file` | Original file (FileResponse, RFC 5987 name, inline) |
| DELETE | `/rag/documents/{doc_id}` | Delete (cascades chunks) |

### 5.4 Agent (`/agent`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/agent/tasks` | Task list (owner isolation / admin all, limit 50, joins report model + `progress`/`elapsed_seconds`/`total_tokens`) |
| GET | `/agent/tasks/{task_id}` | Detail (steps + report + llm_used + audit + `elapsed_seconds` / `total_tokens`, `null` when unavailable) |
| DELETE | `/agent/tasks/{task_id}` | Delete task (cascades steps) |
| POST | `/agent/tasks` | Create task (returns task_id immediately, runs in background) |
| POST | `/agent/tasks/{task_id}/resume` | Approval resume (approve / edit / reject). Gate-not-ready / duplicate submits return **409 + semantic code**: `approval_not_ready` / `already_resumed` / `approval_busy` / `task_finished` / `checkpoint_unavailable` (refused when checkpoint degraded to MemorySaver) / `task_busy` (per-task resume lock) |
| GET | `/agent/tasks/{task_id}/stream` | SSE (auth via `Authorization` header, **token never in the URL**): `report_snapshot` (first frame on (re)connect, replays this round's text/thinking) / `step` / `report_think` (with `run`) / `think_reset` (loop truncation) / `approval` / `report_delta` / `report` / `error` |
| GET | `/agent/capabilities` | Capability manifest (real runtime state) |
| GET | `/agent/status` | Status of the 6 agents (including Reviewer) |

### 5.5 Reports (`/reports`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/reports/list` | List (page / page_size / report_type) |
| GET | `/reports/{report_id}` | Detail |
| POST | `/reports/generate` | Generate a report directly (bypasses agent orchestration) |
| DELETE | `/reports/{report_id}` | Delete (user soft delete / admin global soft delete) |
| GET | `/reports/export/{report_id}` | Export (`format=md\|html`) |

### 5.6 Admin (`/admin`, admin only)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/admin/config` | Read config (API keys masked as `key[:3] + "****" + key[-3:]`) |
| POST | `/admin/config` | Save config (writes `.env` + `setattr` hot reload, skips masked values) |
| POST | `/admin/test/db` | Database connection test |
| POST | `/admin/test/llm` | Real LLM invoke test |
| GET | `/admin/llm/models?provider=` | Model catalog (`aliyun\|amd\|ollama\|longcat`) |
| GET | `/admin/bailian/quota` | Bailian free-tier quota snapshot |
| GET | `/admin/status` | System status (DB / LLM / models / 6 agents) |
| GET | `/admin/logs?limit=` | Logs (200-entry ring buffer) |
| GET | `/admin/users` | User list |
| PUT | `/admin/users/{user_id}/role` | Change role (self-change blocked) |
| DELETE | `/admin/users/{user_id}` | Delete user (self-delete blocked) |

### 5.7 Auth (`/auth`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/auth/register` | Register and sign in |
| POST | `/auth/login` | Login, returns `access_token` + `user` |
| GET | `/auth/me` | Current user |
| PUT | `/auth/me` | Update email |
| PUT | `/auth/me/password` | Change password (old password verified; revokes old tokens) |

- **15-hour sliding session**: `exp = iat + 15h`; every authenticated response may carry `X-Token-Refresh` (exposed via CORS `expose_headers`) and the frontend replaces its token when there is real user activity — you only sign in again after 15 hours of inactivity;
- **Revocation**: `users.token_version` (the `tv` claim) must match; legacy tokens without `tv` count as 0, so deploying does not log everyone out.

### 5.8 Vision & Speech (`/vision`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/vision/analyze` | Fire-image recognition (vision model, persisted) |
| GET | `/vision/history` | Recognition history |
| GET | `/vision/history/{rec_id}` | One record |
| DELETE | `/vision/history/{rec_id}` | Delete record |
| GET | `/vision/image/{rec_id}` | Authenticated image binary |
| POST | `/vision/audio/transcriptions` | ASR (wav upload) |
| POST | `/vision/audio/speech` | TTS (returns audio binary) |

### 5.9 Service info

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/` | Service info (name / version / docs URL; `/docs` and `/redoc` are disabled when `ENV=production`) |
| GET | `/health` | Health check |

---

## 6. Agent Orchestration

### 6.1 Graph

```
                    ┌─────────────┐
                    │ parse_task  │  intent → TaskPlan (sub-task list)
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
                     │  join   │  merge parallel branches
                     └────┬────┘
                          ▼
                 ┌─────────────────┐
                 │ generate_report │  review notes / weather / preferences / stream deltas
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  review_report  │  low-temperature review + hard guards, ≤2 rounds
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  approval_gate  │  interrupt() human approval
                 └────────┬────────┘
                          ▼
                         END
```

- **8 nodes**: `parse_task`, `query_data`, `analyze_gis`, `retrieve_knowledge`, `join`, `generate_report`, `review_report`, `approval_gate`.
- **Parallel**: `query_data → analyze_gis` and `retrieve_knowledge` fan out, `join` merges; `analyze_gis` is a no-op when the plan has no GIS task.
- **Reflection**: `parse_task` may emit a `QueryRetryPlan`; at most 2 rewrite rounds.
- **Review (three states)**: `review_report` uses a low-temperature LLM plus hard guards (≥800 chars, required sections, real data):
  - `passed`: review succeeded with no issues → goes to approval;
  - `returned`: concrete issues found → rewrite, **at most 2 rounds**, then human review takes over (`forced`, `review_status=degraded`);
  - `degraded`: review itself failed (LLM error / parse failure / rejection without concrete issues) → **no rewrite**, report goes straight to human approval (`review_status=degraded` + `degraded_reason`, step not marked failed).
  - The verdict is persisted in step output as `review_status`; the frontend colors the three states accordingly.
- **Two-round thinking**: `generate_report` streaming embeds loop detection (exact + bigram near-duplicate clusters × frequency + suffix blocks). On loop/limit hit, thinking is truncated at a sentence boundary (`think_reset` frame tells the frontend to drop the repeated tail) and a **second round starts immediately** (run+1, prompt injects the truncated summary and forbids repetition; budget 6k/150s for round 1, 12k/180s for round 2), at most 2 rounds; thinking is persisted per round in `thinking_rounds`.
- **HITL**: `approval_gate` pauses via `langgraph.types.interrupt()`; `resume` supports three actions:
  - `approve`: finalize the draft as-is;
  - `edit`: finalize with edited `content`;
  - `reject`: regenerate with a `comment`.
- **Fallback**: `_make_fallback_nodes` template nodes run when no LLM is available (review auto-passes), so tasks still complete.

### 6.2 Task state machine

```
running → awaiting_approval → running → completed
                                   └──→ failed
```

- Task creation returns `task_id` immediately; `_spawn_task` runs in the background and `_bg_tasks` keeps a reference to prevent GC.
- Every node transition upserts `agent_task_steps` on `(task_id, step_name)` (running pre-write + terminal overwrite).
- `resume` is limited to the owner/admin and requires `awaiting_approval`.

### 6.3 SSE protocol

| Event `type` | Fields | Description |
| ------------ | ------ | ----------- |
| `report_snapshot` | `run` / `report` / `think` | **First frame on connect**: incremental copy of this round's report and thinking (so switching pages / refreshing mid-stream loses nothing; omitted when nothing produced yet) |
| `step` | `step.step` / `step.status` / `step.output` | Node start (pre-written running row) / end (completed / failed / skipped) |
| `report_think` | `run` / `text` | Thinking increments (`run` = generation round, increments on rewrite / second round) |
| `think_reset` | `run` / `text` | Loop truncation: frontend replaces this round's live thinking with `text`, next run+1 starts a new round |
| `report_delta` | `run` / `text` | Incremental report text |
| `approval` | `data` | Awaiting approval with the task detail (incl. draft) |
| `report` | `data` | Final full report (incl. steps) |
| `error` | `message` | Execution error |

- Historical steps are replayed on connect, followed by a `report_snapshot` frame (the backend keeps a per-task, per-round in-process copy of streamed text and drops it on terminal state);
- Auth uses the `Authorization` header (the frontend reads a fetch stream, not `EventSource`; a token in the query string would land in Nginx access logs);
- The stream waits 0.6s before closing to flush pending `report_delta`.
- Max connection lifetime `_SSE_MAX_SECONDS = 1800`.
- `X-Accel-Buffering: no` prevents Nginx buffering.

---

## 7. LLM Access & Degradation

### 7.1 Four providers

| Provider | Config | Default model | Notes |
| -------- | ------ | ------------- | ----- |
| Alibaba Bailian | `LLM_API_KEY` / `LLM_API_BASE` | `qwen-plus` | LLM + Embedding + Vision + ASR + TTS primary path |
| AMD GPU Cloud | `AMD_API_KEY` / `AMD_API_BASE` | `DeepSeek-V4-Flash` | OpenAI-compatible; four capability classes |
| Ollama | `OLLAMA_API_BASE` | `qwen2.5:7b` | Local deployment |
| LongCat | `LONGCAT_API_KEY` / `LONGCAT_API_BASE` | `LongCat-2.5-Preview` | OpenAI-compatible; static catalog + `/models` validation |

`ACTIVE_LLM_PROVIDER=aliyun|amd|ollama|longcat` selects the primary provider.

### 7.2 Unified `llm_invoker`

- **Retry**: exponential backoff 1s / 2s / 4s, up to 3 attempts.
- **Circuit breaker**: 3 consecutive failures → 60s cooldown (`_Breaker`, exposed via `breaker_status()`).
- **Fallback chain**: active provider first, then `aliyun → amd → ollama → longcat`.
- **Rule fallback**: keyword/template logic when all providers fail, so tasks never hard-fail.
- **Audit**: returns `provider` / `model` / `tokens` / `degraded`, persisted on tasks and reports.
- Public functions: `invoke_llm`, `invoke_structured`, `stream_llm`.

### 7.3 Capability routing

| Capability | Config | Values | Default | Degradation |
| ---------- | ------ | ------ | ------- | ----------- |
| Vision | `VISION_PROVIDER` / `VISION_MODEL` | `aliyun` / `amd` | `aliyun` / `qwen-vl-plus` | Routed by `VISION_PROVIDER` (model must match the selected provider) |
| ASR | `ASR_MODEL` | — | `qwen3-asr-flash` | Bailian data URI upload |
| TTS | `TTS_PROVIDER` / `TTS_MODEL` | `aliyun` / `amd` | `aliyun` / `qwen3-tts-flash` | Bailian failure auto-falls back to AMD OmniVoice `/audio/speech` (wav) |
| Document OCR | `OCR_PROVIDER` / `OCR_MODEL` | `local` / `amd` | `local` / `MinerU2.5-Pro` | AMD first, falls back to local RapidOCR |

### 7.4 Admin model catalogs

- **Bailian**: built-in `BAILIAN_FREE_MODELS` (5 categories, 30+ models) + live free-tier validation; `MODEL_CATEGORIES` / `BAILIAN_CONSOLE_URLS`; ordering free-first → longer validity → current → verified.
- **AMD**: `app/core/amd_directory.py` crawls `developer.amd.com.cn` tokenfactory live (bootstrap POST + templates GET + per-card detail); capability keys `text/vision/speech/ocr`; tier mapping `dedicated` / no badge → `paid`, `limited` → `limited_free`, `free` → `free`; no cache, empty list on failure.
- **LongCat**: static `LONGCAT_MODELS` (`LongCat-2.5-Preview`, `LongCat-2.0`) + `/models` validation.
- **Ollama**: `/models` listing only.
- One-click switch: `POST /admin/config` writes `.env` and hot-reloads via `setattr`, no restart needed.

---

## 8. RAG Pipeline

```
upload → extract → chunk → embed → persist
                          │
question → Adaptive classification ─┼── hybrid retrieval (vector + keyword)
           (simple/complex)          │        └→ qwen3-rerank (RRF fallback)
                                     │
                                     └→ prompt (numbered citations) → LLM → answer + sources
```

- **Four-layer PDF extraction** (`_extract_pdf`): pdfplumber → pypdf → PyMuPDF (fitz) → OCR; garbled or scanned pages detected automatically.
  - With `OCR_PROVIDER=amd`, `amd_ocr_pdf` runs first (page PNG → `/ocr` → Markdown, model `MinerU2.5-Pro`).
  - Falls back to local `_ocr_pdf` (RapidOCR).
- **Chunking**: Chinese-aware `_chunk_text`, size 500 / overlap 50 (`KB_CHUNK_SIZE` / `KB_CHUNK_OVERLAP`).
- **Retrieval**: `retrieve()` returns `items` / `matched_chunks` / `method` (`hybrid` / `keyword` / `none`, optionally `+rerank`) / `reranked` / `keywords` / `vector_enabled`; `top_k` defaults to 5.
- **Rerank**: `qwen3-rerank` (`RERANK_ENABLED` / `RERANK_MODEL`), falls back to RRF.
- **Adaptive RAG**: `_classify_query_complexity` labels `simple` / `complex`; complex queries get up to 3 LLM rewrite rounds.
- **Generation**: `_rag_prompt` requires numbered citations; `answer` is non-streaming and `answer_stream` is streaming.
- **Stream protocol**: `meta` (sources / retrieval method) → `delta` → `done`; partial answers are not persisted (thread bridged via `asyncio.Queue`).
- **Document reading**:
  - `GET /documents/{id}/content`: concatenates chunks in order.
  - `GET /documents/{id}/file`: `FileResponse` with RFC 5987 filename, `inline` for in-page preview.

---

## 9. Memory · Tools · Observability · Evaluation · Red Teaming

| Capability | Implementation | Degradation |
| ---------- | -------------- | ----------- |
| Preference memory | `app/core/memory_store.py`, `PostgresStore`, namespace `("prefs", "user-{id}")`, key `analysis`; `_PrefExtract` extracts cities / period; persisted after a task, injected by ReportAgent | Failure sets `_store_disabled`; main flow unaffected |
| Checkpointer | `PostgresSaver` (`langgraph-checkpoint-postgres`) | Falls back to `MemorySaver` |
| MCP tool | `app/core/mcp_client.py` lazily loads `MultiServerMCPClient` (stdio `mcp_server.weather_server`); `get_weather_for_city` returns an empty string on failure | Reports skip weather when MCP is unavailable |
| Observability | `app/core/observability.py`: `build_callback_config(task_id, thread_id)` → Langfuse `CallbackHandler` | Returns `None` when disabled or no keys |
| Evaluation | `scripts/golden_set.json` + `scripts/eval_regression.py`; `/agent/capabilities` reports golden-case count | Skipped without an LLM |
| Red teaming | `GAUNTLET_CHAOS` / `GAUNTLET_FAULTS_PATH` / `GAUNTLET_SEED` / `GAUNTLET_SYS_CANARY`; `_chaos_wrap` injects faults, `_guard_canary_output` blocks canary leaks | All off by default; no production impact |

---

## 10. Startup & Configuration

### 10.1 Startup sequence (lifespan)

1. `Base.metadata.create_all`.
2. **Idempotent column patching**: `kb_documents.user_id`; `analysis_reports.user_id / llm_provider / llm_model / llm_tokens / llm_degraded`; `agent_tasks.user_id`; `query_history.result`; `rag_history.result`.
3. Seed admin `admin / 123456` (skipped if present).
4. **Startup self-healing**:
   - all `running` tasks are marked `failed` ("服务重启导致任务中断，请重新发起任务");
   - zombie `running` step rows are cleaned up;
   - `awaiting_approval` tasks are preserved and can still be approved.
5. Mount 8 routers; CORS defaults to `5173` / `4173`.

### 10.2 Local startup

```bash
cd fire_agent_back
conda create -n fire_agent_back python=3.11 -y
conda activate fire_agent_back
pip install -r requirements.txt

# prepare .env (see .env.example)
python scripts/init_db.py            # create tables + seed (lifespan also does this)
python scripts/run_all_imports.py    # import fire points / predictions / boundaries (optional)

uvicorn app.main:app --reload --port 8000
```

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 10.3 Environment variables (defaults from `app/core/config.py`)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `VERSION` | `1.0.1` | Service version |
| `ENV` | `development` | `development` / `production`; production disables `/docs`, `/redoc` and enables the secret self-check |
| `JWT_SECRET` | empty (blank in the example) | **You must supply a random value**: `python -c "import secrets;print(secrets.token_urlsafe(48))"`; production refuses to boot on empty / <32 bytes / a placeholder ever published in the repo |
| `ADMIN_INIT_PASSWORD` | empty | Seed admin password on first init; **production refuses to start when empty**, development falls back to `123456` (local only) |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:4173"]` | JSON array; must include the real frontend origin |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/fire_agent` | PostGIS database |
| `AMAP_KEY` | empty | AMap weather / MCP |
| `ACTIVE_LLM_PROVIDER` | `aliyun` | `aliyun` / `amd` / `ollama` / `longcat` |
| `LLM_API_KEY` / `LLM_API_BASE` | empty / Bailian default | Bailian |
| `LLM_MODEL` | `qwen-plus` | Primary LLM |
| `EMBEDDING_MODEL` | `qwen3.7-text-embedding-flash` | Always Bailian |
| `VISION_PROVIDER` / `VISION_MODEL` | `aliyun` / `qwen-vl-plus` | Vision recognition |
| `ASR_MODEL` | `qwen3-asr-flash` | Speech transcription |
| `TTS_PROVIDER` / `TTS_MODEL` | `aliyun` / `qwen3-tts-flash` | Speech synthesis |
| `OCR_PROVIDER` / `OCR_MODEL` | `local` / `MinerU2.5-Pro` | Document OCR (`local` / `amd`) |
| `AMD_API_KEY` / `AMD_API_BASE` / `AMD_MODEL` | empty / `https://developer.amd.com.cn/radeon/v1` / `DeepSeek-V4-Flash` | AMD GPU Cloud |
| `OLLAMA_API_BASE` / `OLLAMA_MODEL` | `http://localhost:11434/v1` / `qwen2.5:7b` | Ollama |
| `LONGCAT_API_KEY` / `LONGCAT_API_BASE` / `LONGCAT_MODEL` | empty / `https://api.longcat.chat/openai` / `LongCat-2.5-Preview` | LongCat |
| `QWEN3_8_*` | — | qwen3-8 time window |
| `KB_UPLOAD_DIR` | `data/knowledge_base` | KB original files |
| `KB_CHUNK_SIZE` / `KB_CHUNK_OVERLAP` | `500` / `50` | Chunking |
| `KB_TOP_K` | `5` | Retrieval size |
| `RERANK_ENABLED` / `RERANK_MODEL` | on / `qwen3-rerank` | Rerank |
| `AGENT_REQUIRE_APPROVAL` | on | HITL approval switch |
| `LLM_STREAM_ENABLED` | on | Report streaming deltas |
| `PREFERENCES_ENABLED` | on | Preference memory |
| `MCP_ENABLED` | on | MCP weather tool |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | empty | Langfuse |
| `GAUNTLET_CHAOS` / `GAUNTLET_FAULTS_PATH` / `GAUNTLET_SEED` / `GAUNTLET_SYS_CANARY` | `False` / empty / `42` / empty | AgentGauntlet red teaming |
| `REPORT_FOOTER` | system name / developer / email / repos / demo / GitHub | Report footer |

> `.env.example` covers the core items; for `LONGCAT_*`, `OCR_*` and `GAUNTLET_*`, the defaults above reflect the code and can be appended to `.env` directly.

---

## 11. Docker Deployment

```bash
# full stack (db + backend + frontend)
docker compose up -d --build

# with Langfuse (optional profile)
docker compose --profile langfuse up -d --build
```

- `db`: PostGIS image with a persistent volume.
- `backend`: built from `Dockerfile`, depends on `db` health check, mounts `data/`.
- `frontend`: built assets served by Nginx, `/api` reverse-proxied to backend.
- Production must set `ENV=production` and a random `JWT_SECRET` in the same edit before restarting (otherwise the app refuses to boot or every session is invalidated), plus `ADMIN_INIT_PASSWORD`, database credentials and the `CORS_ORIGINS` allowlist; SSE requires unbuffered proxying.

---

## 12. FAQ

| Problem | Solution |
| ------- | -------- |
| `relation does not exist` on startup | Run `python scripts/init_db.py`; lifespan also runs `create_all` and patches columns |
| PostGIS extension missing | `CREATE EXTENSION postgis;` then re-run migrations / `sql/public.sql` |
| All LLM calls fail | Check `ACTIVE_LLM_PROVIDER` and the matching key; use `/admin/test/llm`; inspect breaker status |
| Agent task stuck in running | A restart marks it failed via self-healing; a runtime orphan sweeper (45s grace, 30s interval) also fails tasks left by `--reload` restarts |
| Approval does nothing | The task must be `awaiting_approval`; `edit` requires `content`, `reject` requires `comment`; gate-not-ready / duplicates return 409 + `detail.code` (`approval_not_ready` / `already_resumed` / `approval_busy` / `task_finished` / `checkpoint_unavailable` / `task_busy`) |
| Review shows "未完成 · 转人工" | When the review LLM errors / fails to parse / gives no concrete issues, it degrades via `review_status=degraded`: no rewrite, the report goes straight to human approval |
| No SSE progress | Disable `proxy_buffering` in Nginx, raise `proxy_read_timeout`; ensure the request carries `Authorization` (**do not put the token in the URL**); a reconnect first receives `report_snapshot` with what was already streamed |
| Uploaded document yields no text | Check the four-layer extraction logs; scanned PDFs need `OCR_PROVIDER=amd` or local RapidOCR |
| TTS returns 402 / arrears | Bailian arrears propagate code + message; switch `TTS_PROVIDER=amd` |
| Empty report / review rejected | Review guards require ≥800 chars, required sections, real data; after 2 rounds it forces through |
| CORS errors | Add the frontend origin to `CORS_ORIGINS` (defaults 5173 / 4173) |

---

## 13. Version History

### Security hardening and streaming reliability (post-v1.0.1 iteration)

**Security hardening**

- **Authorization sweep**: all 62 routes declare their auth policy explicitly, cross-checked against OpenAPI operations by `scripts/check_auth_coverage.py`; only `/`, `/health`, `/auth/login`, `/auth/register` and `/dashboard/summary` are anonymous (the last returns aggregates only).
- **15-hour sliding session**: silent renewal via `X-Token-Refresh`; re-login is required only after 15 hours of inactivity. `users.token_version` revokes tokens on password change / deactivation.
- **Secret self-check**: with `ENV=production` the app refuses to boot on an empty / under-32-byte / publicly known placeholder `JWT_SECRET`, and refuses a missing `ADMIN_INIT_PASSWORD`; `/docs` and `/redoc` are disabled in production.
- **Upload triple validation** (size / extension / magic bytes); **log and error-message redaction** for API keys and tokens.

**Streaming reliability**

- The report channel keeps a per-task, per-round in-process copy of streamed text and sends it as the first `report_snapshot` frame on every new connection: switching pages or refreshing mid-stream no longer loses what was already displayed. The copy is dropped on terminal state and capped by task count and characters.

### Post-v1.0.1 iterations (current code state)

**LLM & capability expansion**

- New **LongCat** provider: `LONGCAT_API_KEY` / `LONGCAT_API_BASE` / `LONGCAT_MODEL`; `llm_invoker` chain extended to four providers; admin static catalog + `/models` validation.
- **AMD GPU Cloud four capability classes**: catalog crawl covers `text` / `vision` / `speech` / `ocr`, with free / limited-free / paid tiers.
- New `TTS_PROVIDER` (Bailian failure auto-falls back to AMD OmniVoice `/audio/speech`), `OCR_PROVIDER` (AMD `MinerU2.5-Pro` → local RapidOCR).
- TTS errors propagate arrears code + message.

**Knowledge base**

- `GET /rag/documents/{id}/content`: full text by concatenating chunks.
- `GET /rag/documents/{id}/file`: original file via `FileResponse` + RFC 5987 filename, inline preview and download.
- Document list now includes `file_type` / `chunk_count`.

**Stability**

- Startup self-healing: `running` tasks → `failed`, zombie `running` steps cleaned, `awaiting_approval` preserved.
- Idempotent column patching extended to `agent_tasks.user_id`, `query_history.result`, `rag_history.result`, etc.

**Quality & red teaming**

- AgentGauntlet settings and injection wrappers (`_chaos_wrap` / `_guard_canary_output`).
- Golden-set regression evaluation and real runtime state via `/agent/capabilities`.

### v1.0.1

- **Agent orchestration**: LangGraph 8 nodes, parallel fan-out/join, reflection retries, review loop, HITL `interrupt` / `resume`.
- **Streaming**: task SSE node-level progress + `report_delta`; RAG `ask/stream`.
- **LLM governance**: `llm_invoker` retry / breaker / provider-chain fallback / audit; AMD provider.
- **RAG**: four-layer PDF extraction, hybrid retrieval, `qwen3-rerank`, Adaptive RAG, Q&A history.
- **Enhancements**: PostgresStore preference memory, MCP AMap weather, Langfuse observability, golden-set evaluation.
- **Operations**: Docker Compose full stack, startup column patching and seeding, CORS allowlist.

### v1.0.0

Initial release: dashboard data, smart query, knowledge-base RAG, basic agent orchestration, report center, admin, JWT auth, vision recognition.

---

*Developer: wjl (19136220923@163.com) · Backend: https://gitee.com/WJLGraph/fire_agent_back · Frontend: https://gitee.com/WJLGraph/Fire_agent_front*
