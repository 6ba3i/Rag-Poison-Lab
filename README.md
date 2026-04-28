# RAGPoison

RAGPoison is a reproducible MovieLens 100K platform for studying retrieval poisoning effects on recommendations, traces, and evaluation metrics across baseline and attacked indices.  
[Sources: api/app/main.py, api/app/services/recs_service.py, api/app/services/trace_service.py, api/app/eval/runner.py, docker/docker-compose.yml]

## Table of Contents

- [Overview](#overview)
- [Quickstart](#quickstart)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the project](#running-the-project)
- [Project layout](#project-layout)
- [Usage](#usage)
- [Development](#development)
- [CI and releases](#ci-and-releases)
- [Troubleshooting](#troubleshooting)

## Overview

### Purpose

This repository implements an end-to-end poisoning research workflow on MovieLens data: data prep, poisoned bulk generation, Elasticsearch indexing, API access, UI visualization, and metric/report generation.  
[Sources: api/app/data/preprocess.py, agent/datasets/poison_builder.py, api/app/services/indexing_service.py, api/app/main.py, api/app/eval/runner.py, api/app/eval/reporting.py]

### Key features

- FastAPI backend serving API routes under `/api` plus SPA/static fallback.  
  [Source: api/app/main.py]
- Recommendation and trace APIs that switch between `movies` and `movies_poisoned` indices by mode (`baseline` or `attacked`).  
  [Sources: api/app/routers/recs.py, api/app/routers/trace.py, api/app/services/recs_service.py]
- Configurable victim/attacker LLM roles and ranking mode (`deterministic` or `llm_rerank`).  
  [Sources: common/schemas/llm_config.py, api/app/routers/settings_llm.py, api/app/services/recs_service.py]
- Interactive CLI wizard and non-interactive commands for data, attack, indexing, evaluation, reports, and model-catalog refresh.  
  [Sources: api/app/cli/cli.py, api/app/cli/wizard.py, api/app/cli/commands_data.py, api/app/cli/commands_attack.py, api/app/cli/commands_index.py, api/app/cli/commands_eval.py, api/app/cli/commands_report.py, api/app/cli/commands_llm.py]
- React + Vite frontend for user selection, dashboard, and settings.  
  [Sources: web/package.json, web/src/main.tsx, web/src/pages/UserSelect.tsx, web/src/pages/Dashboard.tsx, web/src/pages/Settings.tsx]
- Python SDK client for typed API consumption.  
  [Sources: sdk/python/ragpoison_sdk/client.py, sdk/python/ragpoison_sdk/types.py]

### High level architecture

- `api/`: application service layer (routers, services, CLI, evaluation).
- `agent/`: poisoning logic and poisoned bulk writer.
- `rag/`: recommendation candidate generation, ranking, explanations, and trace shaping.
- `web/`: frontend UI.
- `docker/`: compose stack, mappings, and indexing scripts.
- `sdk/python/`: Python client.
- `data/` and `ml-100/`: runtime dataset/config/results locations (bind-mounted in compose).

[Sources: docker/docker-compose.yml, api/app/services/recs_service.py, agent/datasets/poison_builder.py, rag/recsys/candidate_gen.py, sdk/python/ragpoison_sdk/client.py, api/app/data/paths.py]

## Quickstart

The shortest path to a working local stack:

Run the following commands from the repository root. If you are inside a subdirectory such as `sdk/python`, pass the correct relative project path (for example `uv run --project ../../api ...`).

```bash
# 1) Prepare processed outputs from MovieLens files.
uv run --project api python -m api.app.cli.cli data prepare

# 2) Start Elasticsearch, Kibana, Ollama, and app.
docker compose -f docker/docker-compose.yml up -d --build

# 3) Build baseline + poisoned indices.
docker compose -f docker/docker-compose.yml --profile indexing run --rm indexer

# 4) Verify backend health.
curl -s http://localhost:8000/api/health
```

Open:

- App: `http://localhost:8000`
- Kibana: `http://localhost:5601`

[Sources: api/app/cli/commands_data.py, docker/docker-compose.yml, api/app/routers/health.py, tools/dev_notes.md]

## Prerequisites

- Python `>=3.12` for backend and SDK.  
  [Sources: api/pyproject.toml, sdk/python/pyproject.toml]
- `uv` for Python dependency management and command execution in this repo.  
  [Sources: Dockerfile, tools/dev_notes.md]
- Docker Engine + Docker Compose plugin for full stack services (`elasticsearch`, `kibana`, `ollama`, `app`, optional `indexer`).  
  [Source: docker/docker-compose.yml]
- Node/npm for frontend local workflows (`dev`, `build`, `typecheck`, `preview`).  
  [Source: web/package.json]

Service roles in the default stack:

- Elasticsearch: retrieval/index storage.
- Ollama: local model endpoint.
- Kibana: index inspection UI.
- App: FastAPI backend + static SPA serving.

[Sources: docker/docker-compose.yml, api/app/main.py, api/app/settings.py]

## Installation

### Backend (API)

```bash
uv sync --project api --frozen
```

[Sources: api/pyproject.toml, api/uv.lock, Dockerfile]

### SDK (optional)

```bash
uv sync --project sdk/python --frozen
```

[Sources: sdk/python/pyproject.toml, sdk/python/uv.lock]

### Web frontend

```bash
npm --prefix web install
```

[Source: web/package.json]

### Build frontend assets

```bash
npm --prefix web run build
```

[Source: web/package.json]

### Build container image (optional)

```bash
docker build -t ragpoison:dev -f Dockerfile .
```

[Source: Dockerfile]

## Configuration

### Environment variables

#### App/runtime variables

| Name | Required | Default | Description | Where used |
|---|---|---|---|---|
| `ELASTICSEARCH_URL` | No | `http://localhost:9200` | Elasticsearch base URL for app/indexing in host mode. Compose app service overrides this to `http://elasticsearch:9200` for container DNS. | `api/app/settings.py`, `api/app/services/indexing_service.py`, `docker/docker-compose.yml` |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Local Ollama base URL (host mode default). Docker compose app service overrides this to `http://ollama:11434`. | `api/app/settings.py`, `docker/docker-compose.yml` |
| `OLLAMA_TIMEOUT_SECONDS` | No | `60` | Timeout for local Ollama generation requests. Increase this if `llm_rerank` prompts time out on slower CPUs. | `api/app/settings.py`, `api/app/llm/registry.py`, `api/app/llm/local_ollama.py` |
| `OPENAI_COMPAT_BASE_URL` | No | none | Optional shared OpenAI-compatible gateway base URL (transit). Used as fallback for ChatGPT base URL. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `OPENAI_COMPAT_API_KEY` | Conditional | none | Optional shared transit key for OpenAI-compatible providers (`chatgpt`, `claude`, `gemini`) when provider-specific key is unset. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `CHATGPT_BASE_URL` | No | `https://api.openai.com/v1` | ChatGPT/OpenAI-compatible base URL override. | `api/app/settings.py`, `api/app/llm/credentials.py`, `api/app/llm/providers_chatgpt.py`, `docker/docker-compose.yml` |
| `CHATGPT_API_KEY` | Conditional | none | Primary ChatGPT API key env var. | `api/app/settings.py`, `api/app/llm/credentials.py`, `api/app/llm/providers_chatgpt.py`, `docker/docker-compose.yml` |
| `CLAUDE_BASE_URL` | No | `https://api.anthropic.com/v1` | Claude Messages API base URL override. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `CLAUDE_API_KEY` | Conditional | none | Primary Claude API key env var. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `GEMINI_BASE_URL` | No | `https://generativelanguage.googleapis.com/v1beta` | Gemini Generative Language API base URL override. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `GEMINI_API_KEY` | Conditional | none | Primary Gemini API key env var. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `QWEN_BASE_URL` | No | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Qwen OpenAI-compatible base URL override. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `QWEN_API_KEY` | Conditional | none | Primary Qwen API key env var for standalone Qwen access. | `api/app/settings.py`, `api/app/llm/credentials.py`, `docker/docker-compose.yml` |
| `DATA_ROOT` | No | auto-resolved | Optional override for data root path. | `api/app/settings.py` |
| `CONFIG_ROOT` | No | auto-resolved | Optional override for config directory. | `api/app/settings.py` |
| `PROCESSED_ROOT` | No | auto-resolved | Optional override for processed outputs directory. | `api/app/settings.py` |
| `STATIC_ROOT` | No | `api/app/static` | Optional override for served SPA/static root. | `api/app/settings.py`, `api/app/main.py` |
| `LLM_MODELS_FILE` | No | `conf/llm_models.yaml` | Optional override for curated cloud model list file. Refresh it with `llm refresh-models` when official provider catalogs change. | `api/app/settings.py`, `api/app/llm/registry.py`, `api/app/cli/commands_llm.py` |

#### Compose/image selection variables

| Name | Required | Default | Description | Where used |
|---|---|---|---|---|
| `ELASTICSEARCH_IMAGE` | No | `elasticsearch:8.19.11` | Elasticsearch image tag override. | `docker/docker-compose.yml`, `docker/.env.example` |
| `KIBANA_IMAGE` | No | `kibana:8.19.11` | Kibana image tag override. | `docker/docker-compose.yml`, `docker/.env.example` |
| `OLLAMA_IMAGE` | No | `ollama/ollama:latest` | Ollama image tag override. | `docker/docker-compose.yml`, `docker/.env.example` |

#### Script and test variables

| Name | Required | Default | Description | Where used |
|---|---|---|---|---|
| `ES_URL` | No | falls back to `ELASTICSEARCH_URL` | Explicit ES URL override for shell index/wait scripts. | `docker/scripts/wait-for-es.sh`, `docker/scripts/index_baseline.sh`, `docker/scripts/index_poisoned.sh` |
| `MAPPING_FILE` | No | script default | Mapping file override for index scripts. | `docker/scripts/index_baseline.sh`, `docker/scripts/index_poisoned.sh` |
| `BULK_FILE` | No | script default | Bulk JSONL input override for index scripts. | `docker/scripts/index_baseline.sh`, `docker/scripts/index_poisoned.sh` |
| `ES_WAIT_RETRIES` | No | `60` | Wait loop retry count for ES readiness script. | `docker/scripts/wait-for-es.sh` |
| `ES_WAIT_SLEEP_SECONDS` | No | `2` | Wait loop sleep interval in seconds. | `docker/scripts/wait-for-es.sh` |
| `KIBANA_URL` | No | `http://kibana:5601` | Wizard Kibana health/status URL override. | `api/app/cli/wizard.py` |
| `RAGPOISON_API_URL` | No | `http://localhost:8000` | Smoke test API base override. | `test/smoke/test_stack_up.py`, `test/smoke/test_recs_roundtrip.py` |

### Config files

- `data/config/llm_config.json`: victim/attacker providers + models + `ranking_mode`. Read/write via settings API and wizard.  
  [Sources: api/app/routers/settings_llm.py, api/app/services/recs_service.py, api/app/cli/wizard.py, data/config/llm_config.json]
- `data/config/attack_config.json`: attack type and poisoning parameters.  
  [Sources: common/schemas/attack_config.py, agent/datasets/poison_builder.py, api/app/cli/wizard.py, data/config/attack_config.json]
- `conf/llm_models.yaml`: curated cloud model options by provider, generated from official provider APIs. Qwen entries are sourced from Aliyun China DashScope, not the global catalog.  
  [Sources: api/app/llm/registry.py, api/app/llm/model_catalog.py, conf/llm_models.yaml]
- `docker/es/movies_index.json` and `docker/es/movies_poisoned_index.json`: index mapping payloads used by index workflows.  
  [Sources: api/app/services/indexing_service.py, docker/scripts/index_baseline.sh, docker/scripts/index_poisoned.sh]

### Secrets and security notes

- Env vars are the primary credential source. The app loads `.env` by default and also supports `.env.key` as an optional alias.
- Compose reads provider keys from repo-root `.env` / `.env.key`, with `.env.key` overriding `.env`; `secrets/` files are no longer used.  
  [Sources: docker/docker-compose.yml, api/app/settings.py]
- Cloud providers are marked unavailable when no API key env configuration is present.  
  [Sources: api/app/llm/registry.py, api/app/routers/settings_llm.py]
- `chatgpt`, `claude`, `gemini`, and `qwen` all have real generate paths when their env keys are configured.  
  [Sources: api/app/llm/providers_chatgpt.py, api/app/llm/providers_claude.py, api/app/llm/providers_gemini.py, api/app/llm/providers_qwen.py]

### Provider key setup

1. Copy `.env.example` to `.env`.
2. Set provider keys in `.env` (`CHATGPT_API_KEY`, `CLAUDE_API_KEY`, `GEMINI_API_KEY`, `QWEN_API_KEY`) and optional transit vars (`OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_API_KEY`).
3. Restart the app or compose stack after updating keys so the backend reloads the env-backed settings snapshot.

## Running the project

### Local development commands

Run API CLI help:

```bash
uv run --project api python -m api.app.cli.cli --help
```

Refresh the curated cloud model catalog from official provider APIs:

```bash
uv run --project api python -m api.app.cli.cli llm refresh-models
```

Run API server directly:

```bash
uv run --project api uvicorn api.app.main:app --host 0.0.0.0 --port 8000
```

Run web dev server:

```bash
npm --prefix web run dev
```

Optional host-run wizard command (requires Elasticsearch published to host; see `Optional host-run mode (dev)` below):

```bash
ELASTICSEARCH_URL=http://localhost:9200 uv run --project api python -m api.app.cli.cli wizard
```

[Sources: api/app/cli/cli.py, api/pyproject.toml, Dockerfile, web/package.json] 

### Docker/Compose workflow

Start long-lived services:

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

Run interactive workflow wizard (recommended, inside the app container):

```bash
docker compose -f docker/docker-compose.yml exec RagPoison uv run --project api python -m api.app.cli.cli wizard
```

Optional host-run mode (dev, explicitly publish Elasticsearch):

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build
```

Then run host commands with `ELASTICSEARCH_URL=http://localhost:9200`.

Host mode (`uv run` on your machine) uses `http://localhost:11434` and requires Ollama reachable on that port. Compose publishes Ollama only on `127.0.0.1:11434` for host access, while services inside the Docker network use `http://ollama:11434`.

Run one-shot indexer profile:

```bash
docker compose -f docker/docker-compose.yml --profile indexing run --rm indexer
```

Stop services:

```bash
docker compose -f docker/docker-compose.yml down
```

Data persistence note:

- `../data` and `../ml-100` are bind mounts in compose.
- `es_data` and `ollama_data` are named volumes.

[Sources: docker/docker-compose.yml, docker/docker-compose.dev.yml]

### Production run notes

TODO: production deployment topology, ingress/TLS, and operations guidance are not defined in this repository.

## Project layout

```text
api/              FastAPI app, CLI, evaluation logic, settings
web/              React + Vite frontend
agent/            Poisoning transformations and bulk generation
rag/              Candidate generation, ranking, explanation, trace shaping
common/           Shared schemas
docker/           Compose stack, index mappings, helper scripts
sdk/python/       Python SDK client package
data/             Runtime config, processed outputs, results
ml-100/           MovieLens source files
```

[Sources: docker/docker-compose.yml, api/app/main.py, api/app/cli/cli.py, agent/datasets/poison_builder.py, rag/recsys/candidate_gen.py, sdk/python/ragpoison_sdk/client.py, api/app/data/paths.py]

## Usage

### Common CLI workflows

Prepare data:

```bash
uv run --project api python -m api.app.cli.cli data prepare
```

Build poisoned bulk from baseline bulk:

```bash
uv run --project api python -m api.app.cli.cli attack build-poisoned
```

Index baseline + poisoned data and print stats:

```bash
uv run --project api python -m api.app.cli.cli index both
```

Run evaluation:

```bash
uv run --project api python -m api.app.cli.cli eval run --mode full --label demo_run
```

Generate reports for a run:

```bash
uv run --project api python -m api.app.cli.cli report generate --label demo_run
```

[Sources: api/app/cli/commands_data.py, api/app/cli/commands_attack.py, api/app/cli/commands_index.py, api/app/cli/commands_eval.py, api/app/cli/commands_report.py]

### API endpoints

Defined API routes:

- `GET /api/health`
- `GET /api/users`
- `GET /api/users/{user_id}/profile`
- `GET /api/users/{user_id}/history?split=train|all`
- `POST /api/recommendations`
- `POST /api/trace`
- `GET /api/settings/llm`
- `PUT /api/settings/llm`
- `GET /api/settings/llm/options`

[Sources: api/app/main.py, api/app/routers/health.py, api/app/routers/users.py, api/app/routers/recs.py, api/app/routers/trace.py, api/app/routers/settings_llm.py]

Example requests:

```bash
curl -s http://localhost:8000/api/users?limit=10

curl -s -X POST http://localhost:8000/api/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"mode":"baseline","k":10}'

curl -s -X POST http://localhost:8000/api/trace \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"mode":"attacked","k_retrieval":20}'
```

Request/response schemas are defined in `common/schemas/api_types.py`.

### Python SDK example

```python
from ragpoison_sdk import RagPoisonClient

client = RagPoisonClient("http://localhost:8000")
users = client.list_users(limit=5)
recs = client.recommend(user_id=users[0].user_id, mode="baseline", k=10)
trace = client.trace(user_id=users[0].user_id, mode="attacked", k_retrieval=20)
```

[Sources: sdk/python/ragpoison_sdk/client.py, sdk/python/ragpoison_sdk/types.py]

## Development

### Code style and static checks

- Python dependencies include `ruff` and `mypy`; no project-level tool configuration file is currently present in this repo root.  
  [Sources: api/pyproject.toml, repository file listing]
- Web type checks are available via:

```bash
npm --prefix web run typecheck
```

[Source: web/package.json]

### Testing

Default test run (integration tests excluded by default marker expression):

```bash
uv run pytest
```

Run integration tests explicitly:

```bash
uv run pytest -m integration
```

Marker and default selection behavior are defined in `pytest.ini`.

[Sources: pytest.ini, test/smoke/test_stack_up.py, test/smoke/test_recs_roundtrip.py]

### Debugging tips

- Use wizard `Environment checks` for dataset path, data write permissions, Elasticsearch/Kibana/Ollama reachability, and provider secret presence.  
  [Source: api/app/cli/wizard.py]
- Use `index stats` to verify index existence and document counts.  
  [Sources: api/app/cli/commands_index.py, api/app/services/indexing_service.py]
- Use Kibana to inspect `movies*` indices.  
  [Source: docker/docker-compose.yml]

### Implementation-status TODO

TODO: confirm whether these zero-length placeholders are intentional roadmap stubs or deprecated artifacts:

- `rag/retrieval/es_client.py`
- `rag/retrieval/mappings.py`
- `rag/retrieval/query_builder.py`
- `rag/retrieval/schemas.py`
- `docker/scripts/bootstrap_local_models.sh`
- `conf/app_defaults.yaml`

## CI and releases

TODO: no CI workflow definitions or release automation files were found (for example under `.github/workflows/`).

## Troubleshooting

- `503` from user/profile/history/recommendation/trace endpoints can occur if required parquet files are missing. Run `data prepare` first.  
  [Sources: api/app/routers/users.py, api/app/routers/recs.py, api/app/routers/trace.py, api/app/services/users_service.py]
- Recommendation/trace quality may look empty or unexpected if indices are missing or stale. Rebuild with `index both` or compose `indexer`.  
  [Sources: api/app/cli/commands_index.py, docker/docker-compose.yml]
- Host shell DNS cannot resolve compose service names like `elasticsearch` by default. Use `http://elasticsearch:9200` only inside compose containers; use `http://localhost:9200` on host when ES is published (for example via `docker/docker-compose.dev.yml`).  
  [Sources: docker/docker-compose.yml, docker/docker-compose.dev.yml]
- `eval run` now fails loudly when Elasticsearch retrieval is unreachable/misconfigured instead of silently falling back to local-only candidates. If you run `uv` on host, make sure Elasticsearch is published (`docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build`) and indices are present (`index both`).  
  [Sources: api/app/eval/runner.py, api/app/services/recs_service.py, rag/recsys/candidate_gen.py]
- `index reset` refuses to run without explicit confirmation flag:

```bash
uv run --project api python -m api.app.cli.cli index reset --yes
```

[Source: api/app/cli/commands_index.py]

- Cloud providers can fail selection/save if key files are missing for the selected provider.  
  [Sources: api/app/routers/settings_llm.py, api/app/llm/registry.py]
