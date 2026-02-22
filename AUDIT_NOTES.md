# Audit Notes

## Scope and method

This audit was built from implementation and operational files in the repository, primarily:

- `api/app/**`
- `api/pyproject.toml`
- `web/package.json`
- `sdk/python/pyproject.toml`
- `docker/docker-compose.yml`
- `Dockerfile`
- `docker/scripts/**`
- `conf/**`
- `data/config/**`
- `pytest.ini`
- `api/tests/**`
- `test/smoke/**`

Planning docs were treated as non-authoritative unless corroborated by code/config.

## Evidence map

### Product scope and architecture

- Platform scope (data prep, poisoning, indexing, API, trace, evaluation):
  - `api/app/data/preprocess.py`
  - `agent/datasets/poison_builder.py`
  - `api/app/services/indexing_service.py`
  - `api/app/services/recs_service.py`
  - `api/app/services/trace_service.py`
  - `api/app/eval/runner.py`
  - `api/app/eval/reporting.py`
- Backend serves API routes and SPA fallback/static assets:
  - `api/app/main.py`
- Compose service topology (app + elasticsearch + kibana + ollama + indexer):
  - `docker/docker-compose.yml`

### Setup and run commands

- CLI entrypoint and command groups:
  - `api/app/cli/cli.py`
  - `api/app/cli/commands_data.py`
  - `api/app/cli/commands_attack.py`
  - `api/app/cli/commands_index.py`
  - `api/app/cli/commands_eval.py`
  - `api/app/cli/commands_report.py`
- Docker runtime entrypoint (`uvicorn api.app.main:app`):
  - `Dockerfile`
- Compose indexer orchestration for both indices:
  - `docker/docker-compose.yml`
  - `docker/scripts/wait-for-es.sh`
  - `docker/scripts/index_baseline.sh`
  - `docker/scripts/index_poisoned.sh`

### API contracts

- Route registration and prefixes:
  - `api/app/main.py`
- Health route:
  - `api/app/routers/health.py`
- Users routes:
  - `api/app/routers/users.py`
- Recommendations route:
  - `api/app/routers/recs.py`
- Trace route:
  - `api/app/routers/trace.py`
- LLM settings routes:
  - `api/app/routers/settings_llm.py`
- Request/response schema models:
  - `common/schemas/api_types.py`

### Data and indexing behavior

- Default data and processed paths:
  - `api/app/data/paths.py`
- MovieLens file detection and parsing:
  - `api/app/data/movielens_loader.py`
- Deterministic outputs and generated artifacts (`parquet`, bulk JSONL):
  - `api/app/data/preprocess.py`
- Poisoning from baseline bulk to poisoned bulk:
  - `agent/datasets/poison_builder.py`
  - `agent/attacks/poison_index.py`
  - `agent/attacks/targeted_promotion.py`
  - `agent/attacks/prompt_injection.py`
  - `agent/attacks/base.py`
- Direct index operations and validation:
  - `api/app/services/indexing_service.py`

### LLM/provider config and secrets

- Settings/env mapping and default secret paths:
  - `api/app/settings.py`
- Provider registry availability and model loading:
  - `api/app/llm/registry.py`
- Local provider implementation:
  - `api/app/llm/local_ollama.py`
- Cloud provider adapters and implementation status:
  - `api/app/llm/providers_chatgpt.py`
  - `api/app/llm/providers_claude.py`
  - `api/app/llm/providers_gemini.py`
  - `api/app/llm/providers_qwen.py`
- Curated model list:
  - `conf/llm_models.yaml`
- Runtime role config and attack config examples:
  - `data/config/llm_config.json`
  - `data/config/attack_config.json`
- Docker secrets mapping:
  - `docker/docker-compose.yml`

### Frontend and SDK

- Frontend scripts and toolchain:
  - `web/package.json`
  - `web/vite.config.ts`
  - `web/tsconfig.json`
  - `web/postcss.config.cjs`
  - `web/tailwind.config.ts`
- Frontend app routes/pages:
  - `web/src/main.tsx`
  - `web/src/pages/UserSelect.tsx`
  - `web/src/pages/Dashboard.tsx`
  - `web/src/pages/Settings.tsx`
- SDK client interfaces:
  - `sdk/python/ragpoison_sdk/client.py`
  - `sdk/python/ragpoison_sdk/types.py`
  - `sdk/python/pyproject.toml`

### Testing and validation behavior

- Default marker selection and test paths:
  - `pytest.ini`
- Integration/smoke assumptions and `RAGPOISON_API_URL`:
  - `test/smoke/test_stack_up.py`
  - `test/smoke/test_recs_roundtrip.py`
- Unit test coverage examples (API, CLI, poisoning, rerank, config):
  - `api/tests/unit/test_backend_api_fastapi.py`
  - `api/tests/unit/test_cli_eval_report_workflow.py`
  - `api/tests/unit/test_agent_poisoning.py`
  - `api/tests/unit/test_llm_rerank.py`
  - `api/tests/unit/test_config_validation.py`
  - `api/tests/unit/test_data_pipeline_ml100k.py`
  - `sdk/python/tests/test_client.py`

## TODO items inserted into README.md

1. Production deployment guidance is not defined.
2. Placeholder module/script intent is unclear for zero-length files.
3. CI/release workflows are not defined.
4. License is not defined in a license file or package metadata.

## Questions for maintainers

1. What is the canonical project license? Please add `LICENSE` and, if needed, package metadata license fields.
2. What CI workflow should be documented (test matrix, lint/type checks, release checks)? There is currently no `.github/workflows/*`.
3. What is the intended production deployment model (single container, compose, orchestration platform, ingress/TLS, persistence expectations)?
4. Are the following zero-length files intentional future stubs or deprecated artifacts that should be removed?
   - `rag/retrieval/es_client.py`
   - `rag/retrieval/mappings.py`
   - `rag/retrieval/query_builder.py`
   - `rag/retrieval/schemas.py`
   - `api/app/services/attack_service.py`
   - `common/schemas/rec_types.py`
   - `common/utils/fs.py`
   - `common/utils/validation.py`
   - `agent/policies/attack_profiles.py`
   - `tools/tmdb_enrich.py`
   - `docker/scripts/bootstrap_local_models.sh`
   - `conf/app_defaults.yaml`
5. Should `docker/.env.example` variables `HOST_DATA_DIR` and `HOST_ML100_DIR` be wired into `docker/docker-compose.yml`, or removed to avoid confusion?
6. Should `claude`, `gemini`, and `qwen` stay exposed as selectable providers while `generate()` is unimplemented, or should documentation/UI mark them as config-only until implemented?
7. Do you want a formal `CONTRIBUTING.md` with branch naming, commit convention, review policy, and release process?
