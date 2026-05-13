# Midterm Presentation Plan

Target deck size: **10 slides**

## Slide 1 — Title and project framing
- **Key message:** This is the midterm presentation for the existing thesis project, not a new proposal.
- **Bullets:**
  - Use the exact thesis proposal title.
  - Frame the work around the local RAGPoison lab.
  - Keep focus on implementation and workflow.
- **Suggested visual:** clean title slide with subtitle and thesis metadata.
- **Use:** `tex/proposal/main.tex`, `tex/pptx/proposal/slides.tex`

## Slide 2 — Why this project exists
- **Key message:** Poisoned indexed content can change final recommendation output without retraining the model.
- **Bullets:**
  - LLM-based recommendation pipelines depend on retrieval.
  - Retrieval poisoning can propagate into ranking and explanations.
  - The project exists to measure that effect end to end.
- **Suggested visual:** one short problem statement with three-step arrow: retrieval -> ranking -> output.
- **Use:** `README.md`, `api/app/services/recs_service.py`, `api/app/services/trace_service.py`

## Slide 3 — RAG Poison Lab framework overview
- **Key message:** The repo is an end-to-end experimental framework, not a single attack script.
- **Bullets:**
  - prepare data
  - build poisoned bulk
  - index clean and attacked corpora
  - run evaluation and reporting
  - inspect results in UI
- **Suggested visual:** simple stage diagram or numbered flow.
- **Use:** `README.md`, `api/app/services/orchestration_service.py`, `graphify-out/GRAPH_REPORT.md`

## Slide 4 — Architecture and tools
- **Key message:** The project combines backend orchestration, retrieval infrastructure, poisoning logic, and a demo frontend.
- **Bullets:**
  - FastAPI backend
  - React/Vite frontend
  - Elasticsearch + Kibana
  - Docker Compose + uv
  - local/cloud LLM providers
- **Suggested visual:** existing architecture figure.
- **Use:** `tex/proposal/figures/architecture.png`, `docker/docker-compose.yml`, `api/app/main.py`

## Slide 5 — Dataset and indexing pipeline
- **Key message:** MovieLens data is transformed into reproducible processed artifacts and indexable corpora.
- **Bullets:**
  - MovieLens 100K as the local benchmark dataset
  - build profiles and train/test splits
  - export baseline and poison-ready bulks
  - index `movies` and `movies_poisoned`
- **Suggested visual:** pipeline bullets plus artifact names.
- **Use:** `api/app/data/preprocess.py`, `api/app/data/paths.py`, `api/app/services/indexing_service.py`

## Slide 6 — Clean vs poisoned recommendation workflow
- **Key message:** The same user context is run against two corpora to observe attack impact.
- **Bullets:**
  - same user profile and top-K target
  - baseline query hits clean index
  - attacked query hits poisoned index
  - compare retrieval, ranking, and final list
- **Suggested visual:** existing baseline-vs-attacked workflow figure.
- **Use:** `tex/proposal/figures/baseline_vs_attacked_workflow.png`, `api/app/services/recs_service.py`, `api/app/services/trace_service.py`

## Slide 7 — Attack types and experiment steps
- **Key message:** The project already implements multiple attack modes and a runnable experiment loop.
- **Bullets:**
  - targeted promotion
  - prompt injection
  - untargeted degradation
  - single / batch / full runs
  - report artifacts after evaluation
- **Suggested visual:** two-column layout: attack types vs experiment steps.
- **Use:** `common/schemas/attack_config.py`, `agent/attacks/`, `tools/run_experiment_single_demo.sh`

## Slide 8 — Metrics and evaluation logic
- **Key message:** Evaluation already tracks both recommendation quality and attack success.
- **Bullets:**
  - HR@K, NDCG@K, MRR@K
  - ASR@K for targeted attack success
  - target retrieval rank / presence as supporting evidence
  - trace and fallback metadata for interpretation
  - latency not yet a standard reported metric
- **Suggested visual:** compact metric table.
- **Use:** `api/app/eval/metrics.py`, `api/app/eval/runner.py`, `data/results/runs/*/metrics.json`

## Slide 9 — Frontend demo walkthrough
- **Key message:** The frontend helps configure, run, observe, and explain experiments live.
- **Bullets:**
  - Settings for configuration
  - Experiments page for launch + live logs
  - Results page for stored run analysis
  - Trace and comparison components for explanation
  - tonight's recommended demo is deterministic lexical targeted promotion
- **Suggested visual:** UI flow diagram from Settings -> Experiments -> Results -> Trace.
- **Use:** `web/src/pages/Experiments.tsx`, `web/src/pages/Results.tsx`, `docs/best_demo_configs.md`

## Slide 10 — Current status and next steps
- **Key message:** The framework is implemented and demoable, while final thesis-grade results remain intentionally open.
- **Bullets:**
  - core pipeline implemented
  - demo flow implemented
  - metrics/report artifacts implemented
  - finalize experiment matrix and analysis next
  - keep final results as placeholder for now
- **Suggested visual:** status checklist plus highlighted results placeholder box.
- **Use:** `docs/repo_health_audit.md`, `docs/best_demo_configs.md`, `tex/thesis/sections/08_results_discussion.tex`
