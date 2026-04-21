# codex.md

## Purpose

Build a reproducible experimental platform to study RAG poisoning against a movie recommender using MovieLens 100K. The platform includes:

- A modern dark themed web UI (React) for defense demos
- A full interactive CLI wizard for bulk experiments and reporting
- Elasticsearch as the retrieval layer
- Kibana for inspection, debugging, and thesis credibility
- Local LLM via Ollama as default, plus optional cloud providers
- A Python SDK client for programmatic experiments
- Pytest for unit and integration tests
- uv plus a real venv as the only Python environment workflow

The core thesis question: can an attacker LLM poison a RAG pipeline such that recommendations degrade or a target item is promoted, and can we measure it reliably.

## Hard constraints

- Python must be >= 3.12
- CPU-first execution
- No gradients in the UI
- Dark theme, rounded design, subtle animations
- No API keys in shell env by default
- Use Docker secrets for keys
- Persist LLM selection (provider and model) in a config file under data/config
- Avoid data loss even if someone runs `docker compose down -v`:
  - Processed data and raw dataset must be bind mounts (host directories), not named volumes
  - Only safe-to-rebuild data uses named volumes (Elasticsearch data, Ollama model cache)

## Image and tool versions (pinning policy)

We pin major infrastructure images to explicit tags.

- Elasticsearch: use an explicit version tag, no `latest` tag support. :contentReference[oaicite:0]{index=0}
- Proposed pin: `elasticsearch:8.19.11`. :contentReference[oaicite:1]{index=1}
- Kibana pin: `kibana:8.19.11`. :contentReference[oaicite:2]{index=2}
- Python base: `python:3.12-slim` (ensures 3.12 line). :contentReference[oaicite:3]{index=3}
- Node build stage: `node:20-bookworm-slim` (explicit Debian suite). :contentReference[oaicite:4]{index=4}
- uv in Docker: follow Astral guidance for Docker integration. :contentReference[oaicite:5]{index=5}
- Ollama image: `ollama/ollama:latest` by default, overridable via compose var. :contentReference[oaicite:6]{index=6}

Security note for Ollama:
- Do not publish Ollama to the internet. Keep it on the internal compose network only. There are real incidents of exposed Ollama servers. :contentReference[oaicite:7]{index=7}

## Repository structure (RAGFlow-inspired)

This is the complete intended repo map. Codex must keep this map updated if files are added.
```
├── api/
│ ├── app/
│ │ ├── main.py
│ │ ├── settings.py
│ │ ├── static/ # built web assets copied in Docker build
│ │ ├── routers/
│ │ │ ├── health.py
│ │ │ ├── users.py
│ │ │ ├── recs.py
│ │ │ ├── trace.py
│ │ │ └── settings_llm.py
│ │ ├── services/
│ │ │ ├── users_service.py
│ │ │ ├── recs_service.py
│ │ │ ├── trace_service.py
│ │ │ ├── indexing_service.py
│ │ │ └── attack_service.py
│ │ ├── llm/
│ │ │ ├── base.py
│ │ │ ├── registry.py
│ │ │ ├── local_ollama.py
│ │ │ ├── openai_compatible.py
│ │ │ ├── providers_chatgpt.py
│ │ │ ├── providers_claude.py
│ │ │ ├── providers_gemini.py
│ │ │ └── providers_qwen.py
│ │ ├── data/
│ │ │ ├── paths.py
│ │ │ ├── movielens_loader.py
│ │ │ ├── preprocess.py
│ │ │ ├── profiles.py
│ │ │ └── splits.py
│ │ ├── eval/
│ │ │ ├── metrics.py
│ │ │ ├── runner.py
│ │ │ └── reporting.py
│ │ ├── cli/
│ │ │ ├── cli.py
│ │ │ ├── wizard.py
│ │ │ ├── commands_data.py
│ │ │ ├── commands_index.py
│ │ │ ├── commands_attack.py
│ │ │ ├── commands_eval.py
│ │ │ └── commands_report.py
│ │ └── common/
│ │ ├── log.py
│ │ ├── jsonio.py
│ │ └── time.py
│ ├── tests/
│ │ ├── unit/
│ │ └── integration/
│ ├── pyproject.toml
│ └── uv.lock
│
├── web/
│ ├── src/
│ │ ├── api/
│ │ │ ├── client.ts
│ │ │ └── types.ts
│ │ ├── pages/
│ │ │ ├── UserSelect.tsx
│ │ │ ├── Dashboard.tsx
│ │ │ └── Settings.tsx
│ │ ├── components/
│ │ │ ├── Layout.tsx
│ │ │ ├── UserCard.tsx
│ │ │ ├── HistoryTable.tsx
│ │ │ ├── RecCompare.tsx
│ │ │ ├── TracePanel.tsx
│ │ │ └── LlmSelector.tsx
│ │ ├── styles/
│ │ └── main.tsx
│ ├── package.json
│ ├── tsconfig.json
│ └── vite.config.ts
│
├── rag/
│ ├── retrieval/
│ │ ├── es_client.py
│ │ ├── mappings.py
│ │ ├── query_builder.py
│ │ └── schemas.py
│ ├── recsys/
│ │ ├── candidate_gen.py
│ │ ├── ranker.py
│ │ ├── explain.py
│ │ └── prompts.py
│ └── trace/
│ ├── trace_types.py
│ └── trace_builder.py
│
├── agent/
│ ├── attacks/
│ │ ├── base.py
│ │ ├── poison_index.py
│ │ ├── prompt_injection.py
│ │ └── targeted_promotion.py
│ ├── policies/
│ │ └── attack_profiles.py
│ └── datasets/
│ ├── bulk_writer.py
│ └── poison_builder.py
│
├── common/
│ ├── schemas/
│ │ ├── api_types.py
│ │ ├── llm_config.py
│ │ ├── attack_config.py
│ │ └── rec_types.py
│ └── utils/
│ ├── fs.py
│ └── validation.py
│
├── conf/
│ ├── llm_models.yaml
│ ├── attack_profiles.yaml
│ └── app_defaults.yaml
│
├── docker/
│ ├── docker-compose.yml
│ ├── .env.example
│ ├── es/
│ │ ├── movies_index.json
│ │ └── movies_poisoned_index.json
│ └── scripts/
│ ├── wait-for-es.sh
│ ├── index_baseline.sh
│ ├── index_poisoned.sh
│ └── bootstrap_local_models.sh
│
├── sdk/
│ └── python/
│ ├── pyproject.toml
│ ├── uv.lock
│ └── ragpoison_sdk/
│ ├── __init__.py
│ ├── client.py
│ ├── types.py
│ └── errors.py
│
├── test/
│ └── smoke/
│ ├── test_stack_up.py
│ └── test_recs_roundtrip.py
│
├── tools/
│ ├── tmdb_enrich.py
│ └── dev_notes.md
│
├── data/ # host bind mount target
│ ├── config/
│ │ ├── llm_config.json
│ │ └── attack_config.json
│ ├── processed/
│ └── results/
│
├── ml-100/ # already present extracted MovieLens 100K
│
├── Dockerfile # root, multi-stage, builds web then backend
├── README.md
└── .gitignore
```

## Data locations and persistence

- Raw dataset is already inside repo under `ml-100/` (host directory)
- Processed outputs are written to `data/processed/` (host directory)
- Config files are written to `data/config/` (host directory)

Both `ml-100/` and `data/` must be bind mounted in compose. That prevents accidental deletion on `docker compose down -v`.

Named volumes are allowed only for:
- Elasticsearch storage (safe to rebuild, but big)
- Ollama model cache (safe to rebuild, but slow)

## Services and how they interact

### docker compose services

- app: single container serving API and static web
- elasticsearch: retrieval layer
- kibana: debugging UI
- ollama: local LLM server
- indexer: one-shot job that loads ES indices from bulk JSONL (runs on demand)

### Communication graph

- Web browser calls app HTTP routes
- app calls Elasticsearch HTTP
- app calls Ollama HTTP (internal compose network)
- app reads secrets from Docker secrets mount
- indexer calls Elasticsearch HTTP and reads bulk JSONL from bind mount

## LLM selection design

We support two roles:

- Victim LLM
- Attacker LLM

Selection is stored in `data/config/llm_config.json` and is editable by:

- CLI wizard
- Web Settings page

No API keys are stored in config.

### Provider names

- local
- chatgpt
- claude
- gemini
- qwen

### Keys

Keys must be provided via environment variables loaded from `.env` / `.env.key`:

- `CHATGPT_API_KEY`
- `CLAUDE_API_KEY`
- `GEMINI_API_KEY`
- `QWEN_API_KEY`

Default behavior:
- If a provider key is missing, the provider is disabled in UI and CLI wizard with a clear message.
- local provider always available.

### Model lists

- Local models are listed from Ollama `/api/tags`
- Cloud model dropdowns come from `conf/llm_models.yaml` for stability

### Recommended default config

- Victim: local `qwen2.5:1.5b` (or `phi3:mini`)
- Attacker: local `qwen2.5:1.5b`

Cloud is optional.

## Recommendation approach and metrics

### Baseline recommender (MVP)

- Retrieval: Elasticsearch BM25 only
- Ranking: deterministic ranker
- LLM usage: explanations only (stable metrics)

Later optional mode:
- LLM ranks and explains

### Metrics

- HR@K
- NDCG@K
- MRR@K
- ASR for targeted attacks

Aggregate across users.

## Attacks (MVP)

- Index poisoning: create movies_poisoned index with modified documents
- Prompt injection: embed short malicious instruction into document fields that are retrieved and passed as context
- Targeted promotion: bias retrieval towards a chosen movie_id

All attacks are parameterized by `data/config/attack_config.json` and presets in `conf/attack_profiles.yaml`.

## CLI wizard (primary UX)

Single command:

- `uv run python -m api.app.cli.cli wizard`

Wizard must cover:

- LLM configuration for victim and attacker, including local model list and optional model pull
- Data pipeline: preprocess, profiles, splits
- Indexing: baseline and poisoned
- Attack configuration
- Run evaluation
- Generate reports

Non-interactive commands still exist for automation and tests.

## Web UI requirements

- Modern dark theme, no gradients
- Rounded corners, subtle shadows
- Animations via Framer Motion
- Pages:
  - User selection
  - Dashboard: History, Recommendations before and after, Trace before and after
  - Settings: Victim and Attacker provider and model selection, model install status, key presence status

## Python environment requirements (uv + venv)

- Use uv for all dependency management
- Use a real venv `.venv`
- Commit `uv.lock`
- No pip requirements.txt

uv lockfile expectations: lockfile is checked into version control for reproducibility. :contentReference[oaicite:8]{index=8}

Docker builds should follow Astral uv Docker guidance. :contentReference[oaicite:9]{index=9}

## Testing requirements

Use pytest:

- Unit tests for data parsing, metrics, config validation
- Integration tests:
  - stack up
  - ES health
  - indexing completion
  - API endpoints respond
  - recommend baseline and attacked return schema

## Deliverables

Codex must implement:

- Root Dockerfile with multi-stage build (web build then Python app)
- docker/docker-compose.yml with pinned versions
- CLI wizard
- Web UI
- SDK client
- pytest suite

No feature creep beyond MVP until MVP tests pass.

## Definition of done (MVP)

- `docker compose up` brings up ES, Kibana, Ollama, app
- Wizard can preprocess MovieLens, index baseline and poisoned, run eval, generate report
- UI can:
  - select user
  - show history
  - show baseline and attacked recommendations
  - show trace
  - change LLM selection
- SDK can call at least: users, profile, history, recommendations, trace
- pytest suite passes locally and in container
