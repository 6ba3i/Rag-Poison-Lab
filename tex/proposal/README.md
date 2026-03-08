# Proposal2 LaTeX Build Notes

This folder contains the undergraduate thesis proposal for **Rag-Poison-Lab**.

## Structure

- `main.tex`: master LaTeX file
- `sections/`: section-level content files
- `references.bib`: BibTeX entries used by the proposal
- `references.md`: audit log for all references and why each was used
- `scripts/make_placeholders.py`: generates blue-themed figure placeholders
- `figures/`: generated placeholder images
- `output/`: build artifacts (final PDF expected at `output/main.pdf`)

## Build Commands

### 1) Recommended one-command build

```bash
cd tex/proposal2
bash ./build.sh
```

### 2) Makefile build

```bash
cd tex/proposal2
make build
```

### 3) Direct localleaf build (manual)

```bash
cd tex/proposal2
localleaf -1 -m main.tex -e xelatex . -- --outdir=output
```

### 4) Fallback latexmk build (manual)

```bash
cd tex/proposal2
latexmk -xelatex -bibtex -interaction=nonstopmode -file-line-error -outdir=output main.tex
latexmk -xelatex -bibtex -interaction=nonstopmode -file-line-error -outdir=output main.tex
```

## Notes

- `build.sh` always regenerates placeholders before building.
- `build.sh` attempts `localleaf` first and falls back to `latexmk` if needed.
- Final PDF target: `tex/proposal2/output/main.pdf`.
