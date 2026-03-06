# RAG Poisoning Recommender System — Updated Full Project Plan

## 0) Objective

Build a reproducible platform to study **RAG poisoning attacks** against a recommender system using **MovieLens 100K**.

The platform has two primary modes:

1. **Web UI (React)** for defense demo

* Choose a simulated user
* Show their history
* Show baseline vs attacked recommendations
* Show retrieval traces and poisoned content
* Change victim and attacker LLM provider and model in a Settings page

2. **CLI wizard** for full experiments

* Configure LLMs
* Run preprocessing and indexing
* Build attack variants
* Run bulk evaluation across users
* Generate thesis-ready reports

---

## 1) Dataset and data strategy

### Dataset

* MovieLens 100K is used
* The extracted dataset folder is already present in repo: `ml-100/`

### Data persistence

* Processed outputs stored under: `data/processed/`
* Config stored under: `data/config/`
* Results stored under: `data/results/`

### Why this structure

* `ml-100/` and `data/` are **bind mounts** in Docker Compose
* This makes parsed outputs safe even if someone runs `docker compose down -v`
* Only Elasticsearch data and Ollama model cache use Docker volumes, since those can be rebuilt

---

## 2) Preprocessing and “pre-parsed” outputs

### Inputs

* Read raw files from `ml-100/` (detect actual filenames present)

### Outputs

Write deterministic artifacts into `data/processed/`:

* `movies.parquet`
* `ratings.parquet`
* `user_profiles.parquet`
* `splits.parquet`
* `es_bulk_movies.jsonl` (baseline)
* `es_bulk_poisoned_movies.jsonl` (poisoned)

### Split policy for evaluation

Timestamp split per user:

* Train: earlier interactions
* Test: last N interactions (default N=10, configurable)

---

## 3) Retrieval layer and indices (Elasticsearch + Kibana)

Elasticsearch is the core RAG retrieval component.

### Indices

* Baseline index: `movies`
* Poisoned index: `movies_poisoned`

Before vs after is a pure index switch, which is perfect for:

* UI comparisons
* CLI evaluation
* clean experimental control

### Kibana

Always included in the stack:

* used to inspect baseline vs poisoned docs
* used to validate poisoning took effect
* used for thesis credibility and debugging

---

## 4) Recommender and RAG design

### MVP victim recommender design

* Retrieval: Elasticsearch BM25
* Ranking: deterministic ranker
* LLM usage: explanations only

Reason:

* Metrics remain stable
* Poisoning effects can be attributed to attack, not generation randomness

Later optional mode:

* LLM ranks and explains

### RAG context pack

For a user:

* compact user profile summary
* retrieved candidate movie docs
* optional poison markers and payload are included in attacked mode, to enable prompt injection experiments

---

## 5) LLM usage and selection system

### Roles

* Victim LLM
* Attacker LLM

### Providers supported

* local (Ollama)
* chatgpt
* claude
* gemini
* qwen (cloud)

### Key handling

* No keys in `.env`
* No keys in shell env by default
* Keys stored as **Docker secrets** in `secrets/` files:

  * `chatgpt_api_key.txt`
  * `claude_api_key.txt`
  * `gemini_api_key.txt`
  * `qwen_api_key.txt`

Backend reads them from `/run/secrets/<name>`.

### Provider and model selection

Selection is stored in:

* `data/config/llm_config.json`

This config contains only:

* provider name
* model name
  No keys.

Selection is editable through:

* CLI wizard
* Web Settings page

### Local models

Ollama is always running in compose, so local provider is always available.

Model list for local provider:

* fetched from Ollama `/api/tags`
  If a model is not installed:
* wizard can guide install (pull) flow
* UI can show “not installed” state and guide next step

---

## 6) Attacks (MVP scope)

Attacker operates mainly by generating a poisoned movie index.

### Attack types

1. Targeted promotion
   Goal: push target movie into top K for many users

2. Untargeted degradation
   Goal: reduce overall recommendation quality

3. Prompt injection
   Goal: inject instructions into retrieved docs to influence victim generation

### Attack configuration

Stored at:

* `data/config/attack_config.json`

Presets stored at:

* `conf/attack_profiles.yaml`

Outputs:

* `data/processed/es_bulk_poisoned_movies.jsonl` created by attack builder

---

## 7) Metrics and evaluation

### Per-user metrics

* HR@K
* NDCG@K
* MRR@K

### Attack-specific metrics

* Delta NDCG@K (before minus after)
* ASR (attack success rate) for targeted promotion
* Rank shift metrics (optional)

### Aggregation

CLI evaluation produces:

* baseline metrics
* attacked metrics
* deltas
* run summaries for thesis

Outputs stored in:

* `data/results/runs/<label>/`

---

## 8) UI plan (React)

### Style requirements

* modern dark theme
* rounded components
* subtle animations
* no gradients

Use:

* React + TypeScript + Vite
* Tailwind
* Framer Motion

### Pages

1. User selection
2. Dashboard with tabs:

* History
* Recommendations (baseline vs attacked)
* Trace (baseline vs attacked)

3. Settings page:

* victim provider and model selection
* attacker provider and model selection
* key presence status for cloud providers
* local model installed status

---

## 9) CLI wizard plan

CLI wizard is the primary workflow, not a set of loose commands.

Single entrypoint:

* `wizard`

Wizard sections:

1. Environment checks
2. Configure LLMs
3. Data pipeline
4. Elasticsearch indexing
5. Configure attack
6. Run experiments
7. Generate reports
8. Utilities

Non-interactive commands still exist underneath for automation and tests, but wizard is the default UX.

---

## 10) Docker and build strategy

### Root Dockerfile only

No per-service Dockerfiles.

Root Dockerfile is multi-stage:

* Node stage builds web UI
* Python stage installs backend using uv
* Web build output copied into `api/app/static/`
* Backend serves API and SPA

### Compose services

* app (API + UI)
* elasticsearch
* kibana
* ollama
* indexer (one-shot)

---

## 11) Python environment policy

* Must use uv
* Must use a venv
* No pip, no poetry

Lockfiles:

* `api/uv.lock`
* `sdk/python/uv.lock`

---

## 12) SDK client

Include Python SDK under `sdk/python/`:

* minimal at first
* grows as endpoints stabilize
* used for programmatic experiments and notebooks

---

## 13) Tests (pytest)

Testing is required from the start:

* include at least one placeholder test early to keep `uv run pytest` green
* unit tests for parsing, splits, metrics, config validation
* integration tests require the compose stack up

---

## 14) Execution phases

### Phase 1

Repo scaffold and uv setup.

### Phase 2

Docker Compose stack with ES, Kibana, Ollama, app skeleton.

### Phase 3

Data pipeline producing processed artifacts and baseline ES bulk.

### Phase 4

Index mappings and indexer scripts.

### Phase 5

Backend endpoints for UI, settings, and recs pipeline.

### Phase 6

Attack builder producing poisoned bulk and indexing it.

### Phase 7

Evaluation runner and reporting.

### Phase 8

Modern UI implementation.

### Phase 9

SDK expansion and full pytest suite.