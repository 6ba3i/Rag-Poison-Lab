# Rag-Poison-Lab Repo Health Audit

Date: 2026-04-22  
Scope: critical poisoning pipeline health across config, providers, retrieval/indexing, attack/defense, eval/reporting, and demo readiness.

## Method (evidence-first)

- Ran full backend unit suite: `uv run --project api pytest -q` -> `168 passed, 2 deselected`.
- Ran SDK tests from backend environment: `uv run --project api pytest -q sdk/python/tests` -> `9 passed`.
- Ran frontend checks: `npm --prefix web run typecheck && npm --prefix web run build` -> success.
- Brought up isolated Elasticsearch for reproducible checks: `docker compose -p rpldemo -f docker/docker-compose.yml up -d elasticsearch` and used `http://172.20.0.2:9200`.
- Reindexed baseline+poisoned with provenance: `uv run --project api python -m api.app.cli.cli index both --es-url http://172.20.0.2:9200 --processed-dir data/processed --attack-config data/config/attack_config.json`.
- Executed eval/report paths and demo search runs under `data/results/demo_search_20260422/`.
- Exercised provider setup/health/model catalog paths via `LlmRegistry` and `refresh_cloud_model_catalog`.

## Findings

| Status | Subsystem | Evidence | Impact | Recommended action |
|---|---|---|---|---|
| Healthy | Config loading | `api/app/settings.py` resolves env from repo root (`.env`, `.env.key`) and test suite passed env-loading contracts. | Stable config resolution across CLI/API when run from different working directories. | Keep env-first path; avoid introducing cwd-dependent fallbacks. |
| Healthy | Processed data artifacts | Runtime check: `movies.parquet=1682`, `ratings.parquet=100000`, `user_profiles.parquet=943`, `splits.parquet=100000`; bulk docs `1682` baseline + `1682` poisoned. | Dense/hybrid and eval pipelines have required artifacts. | Keep processed artifacts in sync with indexing/provenance checks. |
| Healthy | Baseline/poisoned indexing + provenance | `index both` produced `movies` and `movies_poisoned` with 1682 docs each; poisoned meta contains `attack_config_sha256`, `target_movie_id=1666`, `poisoned_docs=168`; index aliases updated. | Poisoned/baseline indices are reproducible and traceable to config and bulk artifacts. | Continue using canonical indexing path (`index both`) before eval/demo runs. |
| Healthy | Attack config validation + poison build assumptions | `common/schemas/attack_config.py` validation + runtime `attack_config_loaded` logs + `poison_build_complete` diagnostics (`target_is_poisoned=true`). | Prevents malformed attack config silently producing misleading poisoned corpora. | Keep targeted demo configs explicit (`target_movie_id`, `target_fields`, `target_boost_*`). |
| Healthy | Eval runner + reporting/artifacts | `run_experiments` runs generated `metrics.json`, `experiment_manifest.json`, `attack_trace.json`; `report generate` produced `summary.md`, `delta.csv`, snapshots. | End-to-end experiment evidence is reproducible and inspectable for supervisor demos. | Keep artifact generation in demo flow; always show trace + metrics together. |
| Healthy | Model catalog refresh path | `refresh_cloud_model_catalog` succeeded for `chatgpt`, `claude`, `gemini`, `qwen` (non-empty model lists). | Cloud model catalogs are retrievable and filter logic is functioning. | Refresh catalog before major demos if model sets drift. |
| Healthy | SDK/backend contract parity (unit-level) | `sdk/python/tests` passed; backend API schema tests passed after trace metadata changes. | API/SDK shape alignment remains intact for trace/recommendation flows. | Keep shared schema updates synchronized across `common/`, `sdk/`, `web/`. |
| Warning (env-specific) | Local provider health | `LlmRegistry` check: local provider available in config surface, but `ollama_connectivity=False`, `local_models=0`. | Local rerank demos will fail or fallback unless Ollama is running with pulled model. | For local demos, start Ollama and pre-pull model; otherwise prefer cloud-backed victim provider. |
| Warning (env-specific) | Claude provider usability | Client initializes and catalog refresh works, but generate calls return 400 with billing/credit error. | Claude appears configured but is not currently usable for live generation in this environment. | Do not pick Claude for live demo until account credits are restored. |
| Warning | LLM registry cloud healthcheck depth | Cloud provider `healthcheck()` currently treats API key presence as healthy; runtime failures (quota/billing/param issues) are only caught on generate/preflight use. | UI/ops can overestimate readiness if key exists but provider is not truly callable. | Keep preflight in eval path (already present); consider optional lightweight live ping for non-local providers if stricter readiness is needed. |
| Warning | Default demo-readiness (`llm_config.json`) | Current default config is `ranking_mode=llm_rerank` + `retrieval_mode=dense`; single-run health check produced all-zero baseline/attacked metrics for the viable user. | Defaults can make demos look broken/degenerate even when indexing/attack pipeline is healthy. | For supervisor demos, switch to lexical deterministic (recommended in `docs/best_demo_configs.md`). |
| Warning | Prompt injection single-user viability for this target | `attack_type=prompt_injection` with current target/user selection produced no attacked retrieval target for user 13 and zero delta. | Can hide poisoning effect in live demos if chosen blindly. | Avoid prompt-injection as primary supervisor demo unless you preselect a proven viable user/target pair. |

## Critical pipeline verdict

- **Healthy core pipeline:** config -> prepare artifacts -> poison build -> index baseline/poisoned -> eval -> report is functioning with reproducible artifacts and provenance.
- **Primary operational risks are environment/demo-profile risks, not core pipeline breakages:**
  - local Ollama unavailable,
  - Claude billing unavailable,
  - default dense+rerank config is low-signal for this dataset/user profile.

## Notes on strict retrieval and fallback visibility

- Eval uses `strict_retrieval=True`; with the new underflow behavior, strict mode now avoids silent filler and surfaces underflow explicitly in debug/trace paths.
- Rerank fallback metadata now carries requested vs effective mode, attempted flag, and fallback reason for unavailable client/generation/parse failures.

