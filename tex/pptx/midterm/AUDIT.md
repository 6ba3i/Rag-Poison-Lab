# RAG Poison Lab Midterm Audit

This audit is based on the current local repository state in `/home/idriss/Rag-Poison-Lab` on 2026-04-29.
DeepWiki was treated as supporting documentation only; local files and local run artifacts were used as the source of truth.

## 1. Project framing

### Finding
RAGPoison is a local, reproducible MovieLens 100K research framework for studying how poisoning changes retrieval, ranking, traces, and evaluation outputs in recommendation pipelines.

### Evidence
- `README.md`
- `api/app/main.py`
- `api/app/services/recs_service.py`
- `api/app/services/trace_service.py`
- `api/app/eval/runner.py`
- `graphify-out/GRAPH_REPORT.md`

## 2. Architecture

### Finding
The system is organized as a Python backend plus a React frontend, with Elasticsearch as the retrieval store and a separate poisoning layer that prepares attacked corpora.

### Main architectural pieces
- **Backend API and orchestration**: FastAPI app mounts health, users, recommendations, trace, settings, experiments, and results routes.
- **Poisoning subsystem**: `agent/` mutates clean bulk documents into poisoned ones according to `attack_config.json`.
- **Retrieval and ranking**: `rag/` handles query building, retrieval, candidate generation, ranking, and trace shaping.
- **Evaluation/reporting**: `api/app/eval/` computes metrics and exports run artifacts.
- **Frontend demo surface**: `web/src/` provides Overview, Experiments, Users, UserDetail, Results, and Settings pages.

### Evidence
- `api/app/main.py`
- `api/app/routers/experiments.py`
- `api/app/services/orchestration_service.py`
- `agent/datasets/poison_builder.py`
- `rag/retrieval/es_client.py`
- `web/src/main.tsx`
- `graphify-out/GRAPH_REPORT.md`
- `tex/proposal/figures/architecture.png`

## 3. Backend components

### Finding
The backend is not just an API wrapper; it owns the operational experiment workflow.

### Components
| Component | Current role | Supporting files |
|---|---|---|
| FastAPI app | Registers `/api` routes and serves the SPA | `api/app/main.py` |
| Experiment router | Starts normal and streaming experiment runs | `api/app/routers/experiments.py` |
| Orchestrator | Plans and executes prepare/index/eval/report stages | `api/app/services/orchestration_service.py` |
| Recommendation service | Builds user context, retrieves candidates, ranks, explains, and returns debug payloads | `api/app/services/recs_service.py` |
| Trace service | Reconstructs retrieval query, retrieval docs, rerank details, and retrieval debug state | `api/app/services/trace_service.py` |
| Results service | Lists stored runs and exposes run detail artifacts | `api/app/services/results_service.py` |
| Indexing service | Resolves mappings, uploads bulk data, and records provenance | `api/app/services/indexing_service.py` |

### Notes
- The experiments route supports an SSE stream via `/api/experiments/run/stream`, so the web UI can show the same log path used by the orchestrator.
- The orchestration service supports two run profiles: `pipeline` and `single_demo`.

### Evidence
- `api/app/routers/experiments.py`
- `api/app/services/orchestration_service.py`
- `api/app/services/recs_service.py`
- `api/app/services/trace_service.py`
- `api/app/services/results_service.py`
- `api/app/services/indexing_service.py`
- `common/schemas/api_types.py`

## 4. Frontend components

### Finding
The frontend is a live experiment/demo interface, not a static report viewer.

### Components
| Component/page | Current role | Supporting files |
|---|---|---|
| `Overview` | high-level dashboard metrics and recent outcomes | `web/src/pages/Overview.tsx` |
| `Experiments` | launches runs, streams logs, and shows latest run detail | `web/src/pages/Experiments.tsx` |
| `Results` | browses stored runs and detailed run summaries | `web/src/pages/Results.tsx` |
| `Users` / `UserDetail` | user-level inspection and baseline-vs-attacked comparison | `web/src/pages/Users.tsx`, `web/src/pages/UserDetail.tsx` |
| `Settings` | edits runtime controls | `web/src/pages/Settings.tsx` |
| `RunResultView` | presentation-oriented result narrative | `web/src/components/results/RunResultView.tsx` |
| `RecCompare` and `TracePanel` | recommendation diffs and trace inspection | `web/src/components/RecCompare.tsx`, `web/src/components/TracePanel.tsx` |

### Notes
- The routed shell is defined in `web/src/main.tsx`.
- The results and experiment views are already structured for presentation, especially around metrics, outcome labeling, and artifact drill-down.

### Evidence
- `web/src/main.tsx`
- `web/src/pages/Experiments.tsx`
- `web/src/pages/Results.tsx`
- `web/src/components/results/RunResultView.tsx`
- `web/src/components/TracePanel.tsx`
- `web/src/lib/runPresentation.ts`

## 5. Data flow

### Finding
The data flow is explicit and file-based, which is useful for reproducibility.

### Current flow
1. Load MovieLens 100K raw data.
2. Build ratings splits and user profiles.
3. Write processed parquet artifacts.
4. Export baseline Elasticsearch bulk.
5. Export poison-ready Elasticsearch bulk with poison fields.
6. Build final poisoned bulk from attack config.
7. Index clean and poisoned corpora into Elasticsearch.
8. Run evaluation and reporting against stored corpora.

### Key files produced by preprocessing
- `movies.parquet`
- `ratings.parquet`
- `splits.parquet`
- `user_profiles.parquet`
- `es_bulk_movies.jsonl`
- `es_bulk_poisoned_movies.jsonl`

### Evidence
- `api/app/data/preprocess.py`
- `api/app/data/paths.py`
- `api/app/data/profiles.py`
- `api/app/data/splits.py`
- `README.md`
- `graphify-out/GRAPH_REPORT.md`

## 6. Poisoning pipeline

### Finding
The poisoning layer is configurable, explicit, and currently centered on bulk mutation before indexing.

### Implemented attack types
| Attack type | Status | What the code does | Supporting files |
|---|---|---|---|
| `targeted_promotion` | implemented | marks selected docs, applies payload text, and boosts target textual fields | `agent/attacks/targeted_promotion.py` |
| `prompt_injection` | implemented | marks selected docs, inserts payload text, and can append keyword content to target synopsis | `agent/attacks/prompt_injection.py` |
| `untargeted_degradation` | implemented | rotates genres and replaces synopsis text to degrade relevance | `agent/attacks/poison_index.py` |

### Configuration surface
- `attack_type`
- `poison_fraction`
- `target_movie_id`
- `payload_text`
- `keyword_list`
- `target_boost_policy`
- `target_boost_strength`
- `target_fields`

### Pipeline behavior
- Attack config is validated by Pydantic.
- Poisoned bulk metadata includes config hash, source/output hashes, poisoned doc count, and diagnostics.
- Freshness checks rebuild poisoned bulk when the source bulk or attack config changes.

### Evidence
- `common/schemas/attack_config.py`
- `agent/attacks/poison_index.py`
- `agent/attacks/targeted_promotion.py`
- `agent/attacks/prompt_injection.py`
- `agent/datasets/poison_builder.py`
- `conf/attack_profiles.yaml`

## 7. Retrieval, ranking, and trace flow

### Finding
The core experimental comparison is baseline vs attacked retrieval over two different corpora with shared user context.

### Retrieval
- Index choice switches between `movies` and `movies_poisoned`.
- Retrieval modes are `lexical`, `dense`, and `hybrid`.
- Lexical retrieval uses Elasticsearch queries.
- Dense retrieval uses hashed vectors over processed local rows.
- Hybrid retrieval combines lexical and dense ranks with RRF-style fusion.

### Ranking
- Ranking modes are `deterministic` and `llm_rerank`.
- `llm_rerank` uses the victim model only.
- The recommendation path records rerank fallback details when generation or parsing fails.

### Trace
- The trace path rebuilds the retrieval query, query body, retrieved docs, rerank prompt, raw rerank response, parsed order, and retrieval debug payload.
- This makes it possible to explain attack effects before they reach the final top-K list.

### Evidence
- `common/schemas/llm_config.py`
- `api/app/services/recs_service.py`
- `api/app/services/trace_service.py`
- `rag/retrieval/es_client.py`
- `rag/recsys/candidate_gen.py`
- `rag/trace/trace_builder.py`

## 8. Experiment pipeline

### Finding
The current repo already supports a full end-to-end experiment loop.

### Pipeline stages
1. `data prepare`
2. poison build / refresh
3. `index baseline` / `index poisoned` / `index both`
4. `eval run`
5. `report generate`

### Execution surfaces
- CLI commands under `api/app/cli/`
- orchestration service for shared semantics
- web experiment page via `/api/experiments/run` and `/api/experiments/run/stream`
- helper scripts in `tools/`

### Existing helper scripts
- `tools/run_experiment_single_demo.sh`
- `tools/run_experiment_batch10.sh`
- `tools/run_experiment_full.sh`
- `tools/run_full_matrix.sh`

### Evidence
- `api/app/cli/cli.py`
- `api/app/cli/commands_data.py`
- `api/app/cli/commands_index.py`
- `api/app/cli/commands_eval.py`
- `api/app/cli/commands_report.py`
- `api/app/services/orchestration_service.py`
- `tools/run_experiment_single_demo.sh`
- `tools/run_experiment_batch10.sh`
- `tools/run_experiment_full.sh`

## 9. Metrics and evaluation outputs

### Finding
The current evaluation stack clearly implements ranking and attack-success metrics, plus artifact-level evidence for interpretation.

### Implemented metrics
| Metric | Implemented in code | Notes |
|---|---|---|
| HR@K | yes | final top-K relevance hit |
| NDCG@K | yes | position-aware ranking quality |
| MRR@K | yes | first relevant hit quality |
| ASR@K | yes | target movie presence in final top-K |

### Additional evidence fields used in experiments
- target retrieval presence/rate
- target retrieval rank baseline vs attacked
- per-user rows in `metrics.json`
- rerank fallback and strict retrieval warnings
- run reports such as `summary.md` and `delta.csv`

### Current artifact set
- `metrics.json`
- `experiment_manifest.json`
- `attack_trace.json`
- `llm_config.runtime.json`
- `attack_config.runtime.json`
- `defense_config.runtime.json`
- `summary.md`
- `delta.csv`

### Latency status
Latency is **not** currently exported as a standard evaluation metric in the inspected run artifact schema. It can only be discussed as future work unless a new metric pipeline is added.

### Evidence
- `api/app/eval/metrics.py`
- `api/app/eval/runner.py`
- `api/app/eval/reporting.py`
- `api/app/services/results_service.py`
- `web/src/lib/runPresentation.ts`
- `data/results/runs/*/metrics.json`

## 10. Elasticsearch and indexing behavior

### Finding
Elasticsearch is a first-class experimental dependency, not just a storage backend.

### Current indexing behavior
- mapping resolution supports env override, repo path, and packaged fallback
- baseline and poisoned corpora have separate logical indices
- provenance metadata is stored alongside indexed state
- host/container guidance is built into connection error hints

### Stack tools
- Elasticsearch
- Kibana
- Docker Compose
- indexer container profile

### Evidence
- `api/app/services/indexing_service.py`
- `docker/docker-compose.yml`
- `docker/es/movies_index.json`
- `docker/es/movies_poisoned_index.json`
- `graphify-out/GRAPH_REPORT.md`

## 11. Current implementation status for a midterm presentation

### Strongly presentable now
- clear local architecture
- reproducible prepare -> poison -> index -> eval -> report workflow
- attack configuration and attack code
- evaluation metrics and result artifacts
- usable frontend demo path
- trace-based explanation of poisoning effects

### Suitable to show as current demo path
The strongest currently documented demo path is the deterministic lexical targeted-promotion configuration described in `docs/best_demo_configs.md`.

### Evidence
- `docs/best_demo_configs.md`
- `docs/repo_health_audit.md`
- `web/src/pages/Experiments.tsx`
- `web/src/pages/Results.tsx`

## 12. Missing, incomplete, or still fragile parts

### Findings
| Area | Current state | Why it matters | Supporting files |
|---|---|---|---|
| Final experiment results | not thesis-finalized | the presentation should keep final results as placeholder | `docs/repo_health_audit.md`, `data/results/runs/` |
| Latency metric | not standard in run outputs | should not be presented as a current metric | `api/app/eval/metrics.py`, `api/app/services/results_service.py` |
| Provider-dependent rerank demos | environment-sensitive | local Ollama and some cloud providers can be unavailable or unstable | `docs/repo_health_audit.md`, `api/app/services/recs_service.py` |
| Prompt-injection demo viability | implemented, but not the strongest current live demo | should not be overclaimed in the midterm | `docs/best_demo_configs.md` |
| Final thesis-grade analysis | still pending | results interpretation and conclusion should remain provisional | `tex/thesis/sections/08_results_discussion.tex`, `docs/repo_health_audit.md` |

## 13. Slide-useful files and visuals

### Best repo files to reuse in the deck
- `tex/proposal/main.tex` for exact title
- `tex/pptx/proposal/slides.tex` for Beamer theme/style conventions
- `tex/proposal/figures/architecture.png`
- `tex/proposal/figures/baseline_vs_attacked_workflow.png`
- `graphify-out/GRAPH_REPORT.md` for architecture/community summary
- `docs/best_demo_configs.md` for tonight's demo path
- `docs/repo_health_audit.md` for current implementation status and caveats

## 14. Conclusion for the midterm package

The current repository already supports a strong midterm presentation centered on the real framework and workflow:
- what the system is,
- how data becomes clean and poisoned corpora,
- how baseline and attacked recommendation paths are compared,
- what metrics are implemented now,
- how the frontend supports the demo,
- and what remains unfinished.

The one major presentation boundary is that final thesis results should remain a placeholder until the experiment set is fully locked and narrated.
