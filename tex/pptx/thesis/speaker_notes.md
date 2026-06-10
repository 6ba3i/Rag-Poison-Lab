# Thesis Defense Speaker Notes

Total target: about 7 minutes 55 seconds. Speak naturally; do not read the slide text.

## Slide 1: Title
- Time: 25 to 35 sec
- Say:
  Welcome. My thesis is about RAG Poison Lab, a controlled benchmark for studying poisoning risks in LLM-powered recommendation systems. The key idea is simple: recommendation pipelines increasingly retrieve text metadata before ranking or reranking. If that retrieved text is manipulated, the final recommendation can change even when the model itself is not retrained. Today I will focus on the engineering benchmark, the experiment loop, and the main security interpretation.
- Transition: I will start with the problem that makes retrieved metadata security-relevant.

## Slide 2: Problem
- Time: 35 to 45 sec
- Say:
  In a RAG-style recommender, the retrieved movie record is not passive storage anymore. It becomes evidence for ranking, reranking, or explanation. That means the attack surface moves earlier in the pipeline, into the indexed metadata. The thesis studies this boundary: a clean index and a poisoned index are evaluated under the same user and metric conditions, so the difference is attributable to the retrieval condition rather than to a new model or a different user sample.
- Transition: That leads to the research question and the compact contribution set.

## Slide 3: Research Question and Contributions
- Time: 40 to 50 sec
- Say:
  The central question is how to compare clean and poisoned retrieval conditions while keeping the experiment auditable. The project contributes three things. First, a controlled local benchmark with clean and poisoned indices. Second, three attack families that represent different failure modes rather than one isolated trick. Third, a reproducible evidence trail: metrics, runtime configuration, traces, and a final experiment matrix. I am intentionally not claiming that this proves every recommender is unsafe; it is a local benchmark for studying behavior.
- Transition: Before the system design, I will anchor the work in the small set of references that matter most for this defense.

## Slide 4: Related Work
- Time: 25 to 35 sec
- Say:
  This is intentionally a short related-work slide. The thesis builds on three nearby threads. Retrieval poisoning shows that modified passages or records can change what a downstream system sees. Indirect prompt injection explains why external content can become instruction-like once it reaches an LLM context. RAG poisoning in recommender systems connects those ideas to exposure and ranking. My thesis does not expand the literature review here; it uses these works to motivate a local, reproducible MovieLens benchmark.
- Transition: With that positioning in mind, I will show how the benchmark is organized.

## Slide 5: System Architecture
- Time: 40 to 50 sec
- Say:
  This slide is reserved for the architecture diagram. The system is built around a FastAPI backend, Elasticsearch retrieval, a poisoning builder, an evaluation runner, and a React frontend. The important defense point is separation: data preparation, poisoning, indexing, recommendation, and reporting are distinct stages. That lets the project preserve evidence about what changed and where it changed, instead of reducing the experiment to a single opaque model response.
- Transition: With that architecture in place, the thesis evaluates three scenario families.

## Slide 6: Attack Scenarios
- Time: 35 to 45 sec
- Say:
  The thesis uses three scenario families: targeted promotion, prompt injection, and untargeted degradation. This overview slide shows them as categories in the benchmark, not as a how-to for carrying them out. Each category stresses a different part of the retrieval-to-ranking path, which is why one shared metric would not be enough.
- Transition: I will make those three labels precise before moving to the experiment loop.

## Slide 7: Attack Meaning
- Time: 55 to 65 sec
- Say:
  Targeted promotion asks whether a chosen item becomes more visible in the top-k list, so it is measured mainly by ASR and target appearance. This connects to retrieval and ranking manipulation from the related-work slide. Prompt injection is different: it asks whether instruction-like metadata can influence an LLM reranker after retrieval, so the scope is metadata that reaches the reranking stage; it connects to indirect prompt injection and retrieved-context vulnerability. Untargeted degradation does not promote one item. It asks whether recommendation quality drops overall, so HR, NDCG, and MRR matter most. Across all three, the framing is defensive evaluation only; I am not showing payloads or operational instructions.
- Transition: The experiment loop is what keeps these comparisons controlled across attack families.

## Slide 8: Experimental Loop and Metrics
- Time: 45 to 55 sec
- Say:
  Each run follows the same basic loop: prepare MovieLens data, create a clean and poisoned corpus, index them separately, run baseline and attacked recommendations, then compute metrics and save artifacts. HR, NDCG, and MRR measure recommendation quality at top-k. ASR measures whether a configured target appears in the top-k list, so it is meaningful for target-oriented attacks. The notes and final matrix are important because no single metric explains all three attack types.
- Transition: The result slide summarizes the strongest patterns without turning the defense into a table reading exercise.

## Slide 9: Main Results
- Time: 55 to 65 sec
- Say:
  The final thesis matrix contains 15 successful runs across three attack families and five attacker configurations. The strongest target-oriented pattern is targeted promotion, with mean delta ASR around plus 0.348. Prompt-injection rows use LLM reranking in the final matrix and show mean delta ASR around plus 0.157, while quality changes are comparatively small. Untargeted degradation does not use ASR in the same way; it shows the largest quality loss, including mean delta HR around minus 0.078. The key interpretation is that targeted attacks may look small on quality metrics, while degradation is obvious on quality metrics.
- Transition: Now I will briefly show where the system is operated in the project UI.

## Slide 10: Experiments Page Screenshot
- Time: 10 sec
- Say:
  This screenshot slot is for the Experiments page. In the defense, I would use it only briefly to show the operational run configuration and execution view.
- Transition: The next screenshot is where the per-run evidence is inspected.

## Slide 11: Results Page Screenshot
- Time: 10 sec
- Say:
  This screenshot slot is for the Results page. It should show the per-run inspection view: metric comparison, recommendation differences, and trace access.
- Transition: The UI view supports the larger security interpretation, limits, and ethics.

## Slide 12: Security Interpretation, Limits, and Ethics
- Time: 45 to 55 sec
- Say:
  The security implication is that retrieved metadata should be treated as a boundary, not just as harmless catalog text. The benchmark also has clear limits: it is MovieLens-based, local, and not a universal provider ranking or live-service claim. That is intentional. It avoids real user impact and keeps tampering inside a closed reproducible setup. The defensive lesson is to evaluate retrieval, ranking, traces, and metrics together before deployment.
- Transition: I will close with the three takeaways.

## Slide 13: Conclusion
- Time: 35 to 45 sec
- Say:
  The first takeaway is that metadata can become a security boundary when it is retrieved into a ranking or reranking pipeline. The second is that ASR and quality metrics answer different questions and must be interpreted together. The third is that reproducibility comes from paired clean and poisoned runs, saved configs, traces, and a final matrix. RAG Poison Lab is therefore best understood as a reproducible evaluation environment for studying retrieval poisoning in LLM-powered recommendation pipelines.

## Final Timing Table

| Slide | Target time |
|---:|---:|
| 1 | 0:30 |
| 2 | 0:40 |
| 3 | 0:45 |
| 4 | 0:30 |
| 5 | 0:45 |
| 6 | 0:40 |
| 7 | 1:00 |
| 8 | 0:50 |
| 9 | 1:00 |
| 10 | 0:10 |
| 11 | 0:10 |
| 12 | 0:50 |
| 13 | 0:45 |
| **Total** | **7:55** |
