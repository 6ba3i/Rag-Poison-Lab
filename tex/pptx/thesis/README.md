# Thesis Defense Presentation

This directory contains the thesis-only defense presentation package for RAG Poison Lab.

## Files created

- `thesis_presentation.tex` — 13-slide Beamer source using the RAG Poison Lab dark mission-control visual identity.
- `speaker_notes.md` — one section per slide with natural spoken notes and a final timing table.
- `diagrams.md` — manual-generation prompts for architecture, experiment loop, attack comparison, metrics, result matrix, ranker scope, and optional synthesis visuals.
- `export_pptx.py` — local `python-pptx` exporter following the existing midterm manual-export pattern.
- `output/` — build outputs after compiling/exporting.

## Build the TeX deck

From the repository root:

```bash
cd tex/pptx/thesis
localleaf -1 -m thesis_presentation.tex -e xelatex . -- -g --outdir=output
```

Expected PDF:

- `tex/pptx/thesis/output/thesis_presentation.pdf`

## Convert to PPTX using the existing midterm workflow pattern

The existing midterm workflow uses a manual Python exporter rather than a true Beamer-to-PPTX converter. This package follows that pattern with `export_pptx.py`.

If needed, install the dependency locally:

```bash
python3 -m pip install --user python-pptx
```

Then run:

```bash
cd tex/pptx/thesis
python3 export_pptx.py
```

Expected PPTX:

- `tex/pptx/thesis/output/thesis_presentation.pptx`

## Where to insert screenshots

- Slide 10: replace the Experiments page screenshot asset if a newer screenshot is needed.
- Slide 11: replace the Results page screenshot asset if a newer screenshot is needed.

Current screenshot assets are inserted from `diagrams/8.png` and `diagrams/9.png`.

## Where to insert generated diagrams

Use `diagrams.md` prompts and place final images under:

```text
tex/pptx/thesis/figures/
```

Recommended filenames:

- `diagrams/4.jpg` is currently used for slide 5 system architecture.
- `diagrams/6.jpg` is currently used for slide 8 experimental loop.
- `diagrams/7.jpg` is currently used for slide 9 main result matrix.
- Optional existing visual prompts remain in `diagrams.md`; the new Related Work and Attack Meaning slides are native card slides and do not require new generated images.

## Final checklist

Current deck update: 13 slides, including a short Related Work slide after the research question and an Attack Meaning slide after Attack Scenarios. Updated target timing is 7:55.


- [ ] Build `thesis_presentation.tex` to PDF.
- [ ] Export `thesis_presentation.pptx` if PPTX is needed.
- [ ] Keep or refresh the Experiments page screenshot on slide 10.
- [ ] Keep or refresh the Results page screenshot on slide 11.
- [ ] Keep generated diagrams aligned with the current 13-slide numbering.
- [ ] Keep speaker timing between 5 and 8 minutes.
- [ ] Keep slide text short; put explanation in `speaker_notes.md`.
- [ ] Do not add claims beyond the finished thesis.
- [ ] Keep security framing local, closed, reproducible, and defensive.
