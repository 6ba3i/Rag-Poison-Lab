# FINAL_SUMMARY.md

## Files created

- `tex/ppt/midterm/AUDIT.md`
- `tex/ppt/midterm/PRESENTATION_PLAN.md`
- `tex/ppt/midterm/slides.tex`
- `tex/ppt/midterm/export_pptx.py`
- `tex/ppt/midterm/BUILD.md`
- `tex/ppt/midterm/FINAL_SUMMARY.md`
- `tex/ppt/midterm/output/slides.pdf`
- `tex/ppt/midterm/output/midterm_slides.pptx`

## Slide count

- **10 slides total**

## PPTX path

- `tex/ppt/midterm/output/midterm_slides.pptx`

## PDF path

- `tex/ppt/midterm/output/slides.pdf`

## Unresolved issues

- The PPTX is generated through a local Python export path because the repo did not already include a direct Beamer-to-PPTX converter.
- The deck intentionally keeps final experimental results as a placeholder until the experiment set is finalized.
- Provider-dependent LLM rerank demos may still vary by environment, so tonight's safest live path is the deterministic lexical targeted-promotion setup.

## Suggested speaking flow

1. Start with the exact thesis title and say this is a framework/implementation midterm.
2. Explain the problem in one sentence: poisoned retrieval can affect final recommendations.
3. Walk through the framework from data preparation to evaluation.
4. Show the architecture and name the main tools.
5. Explain how MovieLens data becomes clean and poisoned indices.
6. Compare baseline vs attacked recommendation flow.
7. Show the implemented attack types and experiment steps.
8. Explain the metrics and what each one means.
9. Walk through the frontend demo path: settings -> run -> logs -> results -> trace.
10. Close with implementation status, remaining work, and the explicit final-results placeholder.
