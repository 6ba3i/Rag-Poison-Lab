# Speaker Notes (Proposal2 Deck)

These notes follow the exact slide order in `slides.tex`.

## Slide 1 — Title Page
What to say:
- Hello everyone. My name is Sbaaoui Idriss.
- Today I am presenting my undergraduate thesis proposal, titled **Red-Teaming Large Language Model-Powered Recommendation Systems**.
- This work is supervised by Professor 张恒润 at East China University of Science and Technology.
- The core system of this thesis is my own project, **Rag-Poison-Lab**.

Transition:
- I will start with a short overview of what I will cover.

## Slide 2 — Presentation Overview
What to say:
- This presentation has eight parts.
- First, I explain the problem and why it matters in LLM-driven recommendation systems.
- Second, I define the harmful retrieval poisoning threat model.
- Third, I introduce Rag-Poison-Lab and show baseline-versus-attacked workflow.
- Then I summarize related work, technical route, and experimental environment.
- Finally, I cover sustainability, budget, and my thesis schedule.

Transition:
- Next, I will state the core motivation and research question.

## Slide 3 — Abstract and Core Motivation
What to say:
- LLMs are now used in recommendation pipelines for retrieval, reranking, and explanation.
- This creates a new risk surface: if retrieval is poisoned, final recommendations can be manipulated.
- My thesis studies this through red team testing with Rag-Poison-Lab.
- I measure impact with HR@K, NDCG@K, MRR@K, ASR@K, candidate overlap, and target-rank lift.
- The key question is: where can the attacker influence earliest, and how much does output quality or direction change?

Transition:
- To answer this, I first explain the RAG recommendation background.

## Slide 4 — Research Background: RAG-Based Recommendation Systems
What to say:
- In my system, a user profile becomes a retrieval query.
- Candidates are retrieved from Elasticsearch, then ranked into top-K recommendations.
- In RAG-style systems, retrieval quality strongly affects final model behavior.
- So I support two ranking paths: deterministic ranking and LLM reranking, to compare both.
- I use MovieLens 100K because it is standard and reproducible on local hardware.

Transition:
- After this background, I define the exact threat model.

## Slide 5 — Threat Model: Harmful Retrieval Poisoning
What to say:
- The attacker does not need to retrain or directly modify the base model.
- The attacker can poison indexed retrieval content.
- If poisoned candidates are retrieved, ranking and final recommendations can shift.
- In my implementation, I evaluate three attack families:
- Targeted promotion,
- Prompt injection payload insertion,
- Untargeted degradation.

Transition:
- Now I will show the architecture of Rag-Poison-Lab.

## Slide 6 — Rag-Poison-Lab Architecture (Figure)
What to say:
- This figure shows the full system layout of Rag-Poison-Lab.
- The backend and CLI orchestrate data preparation, attack generation, indexing, recommendation calls, traces, and evaluation outputs.
- Elasticsearch stores both baseline and attacked indices.
- Optional LLM runtime is used for reranking experiments.
- The key idea is one controlled lab where we can reproduce every step and inspect every artifact.

Transition:
- Next is the baseline-versus-attacked comparison flow.

## Slide 7 — Baseline vs Attacked Workflow (Figure)
What to say:
- This slide shows the A/B comparison logic.
- For the same user and same request settings, I run two modes:
- Baseline mode reads from `movies`.
- Attacked mode reads from `movies_poisoned`.
- Then I compare retrieval traces, ranking behavior, and final outputs.
- This keeps the experiment fair because only the retrieval state changes.

Transition:
- I now connect this design to existing literature.

## Slide 8 — Related Work (Compact Review)
What to say:
- Related work supports this thesis from four directions.
- First, recommender poisoning literature shows manipulation risks across factorization, graph, top-N, and deep recommendation models.
- Second, RAG poisoning studies show that corrupted retrieval knowledge can shift downstream behavior.
- Third, recommendation-specific RAG poisoning work is close to my exact thesis problem.
- Fourth, ranking metrics like HR, MRR, and NDCG are established and suitable for this evaluation.

Transition:
- Based on that, here is my technical route.

## Slide 9 — Technical Route: Metrics and Methodology
What to say:
- I keep controlled comparison settings fixed: same users, same K, same ranking mode, same processed data snapshot.
- I report core quality metrics: HR@K, NDCG@K, MRR@K.
- I also report attack-oriented metrics: ASR@K, candidate overlap, and target-rank lift.
- Attack settings are stored in `attack_config.json`.
- The experiment pipeline has five fixed steps: prepare data, generate poisoned bulk, index both modes, run recommendations, then compute/export metrics.

Transition:
- This figure visualizes that pipeline end to end.

## Slide 10 — Experiment Pipeline Figure
What to say:
- This figure is the operational flow I execute in experiments.
- It starts from deterministic data preparation.
- Then attack generation creates poisoned bulk from baseline bulk.
- Next, baseline and attacked bulks are indexed separately.
- Recommendation and trace calls are executed under matched conditions.
- Finally, metrics and report artifacts are exported for analysis.

Transition:
- Now I will explain the actual runtime environment.

## Slide 11 — Experimental Environment: Backend Stack
What to say:
- The stack is containerized with Docker Compose.
- Main services are Elasticsearch, Kibana, Ollama, RagPoison backend, and an indexer profile.
- Health checks and startup ordering are used to reduce runtime failures.
- Backend API is split into routers for health, users, recs, trace, and LLM settings.
- CLI commands (`data`, `attack`, `index`, `eval`, `report`) make experiments reproducible and easier to rerun.

Transition:
- Next I go deeper on retrieval, inspection, and reranking behavior.

## Slide 12 — Experimental Environment: Elasticsearch, Kibana, LLM Runtime
What to say:
- Elasticsearch is the core retrieval layer.
- Retrieval uses weighted multi-match on title, genres, and synopsis, with seen-item filtering.
- Both baseline and attacked mappings use BM25 for lexical relevance.
- Kibana is used for inspection: index health, document counts, and poison marker/payload checks.
- For ranking, I support deterministic mode and `llm_rerank` mode.
- If reranking fails, the system falls back to deterministic ranking and records that in traces.

Transition:
- I will now summarize sustainability and budget planning.

## Slide 13 — Sustainability and Budget
What to say:
- This project is local-first, so it avoids heavy always-on cloud usage.
- I reduce compute waste by reusing processed artifacts and rebuilding poisoned bulk only when inputs change.
- I also use staged runs (single, batch, full) to avoid unnecessary full reruns during debugging.
- The planned one-semester budget is 4150 RMB.
- The largest controllable cost is API usage, so I cap token usage and keep cloud calls focused on important comparison runs.

Transition:
- Finally, this is my timeline.

## Slide 14 — Schedule (Spring 2026)
What to say:
- In March, I freeze scope and validate baseline reproducibility.
- In April, I run batch and full evaluations for all attack types under both ranking modes.
- In May, I complete metric and trace analysis and finalize writing.
- In early June, I do revision, reproducibility re-check, and final submission preparation.
- Risk plan: if full-scale runs are delayed, I prioritize stable batch checkpoints first.

Transition:
- I will close with a short thank-you.

## Slide 15 — Thank You
What to say:
- Thank you for your attention.
- I welcome your questions and feedback.

