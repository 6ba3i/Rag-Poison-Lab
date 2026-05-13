# BUILD.md

## 1. LaTeX Beamer deck

Authoritative slide source:
- `tex/ppt/midterm/slides.tex`
- local image assets copied into `tex/ppt/midterm/figures/` from the proposal figure set for stable builds inside the `localleaf` container

Compile from the repository root:

```bash
cd tex/ppt/midterm
localleaf -1 -m slides.tex -e xelatex . -- -g --outdir=output
```

Expected PDF output:
- `tex/ppt/midterm/output/slides.pdf`

## 2. PPTX generation

The repo did **not** contain a native Beamer-to-PPTX conversion path.
For this package, the PPTX was generated with a local Python exporter script based on the same slide content outline:
- `tex/ppt/midterm/export_pptx.py`

If `python-pptx` is not installed, install it locally:

```bash
python3 -m pip install --user python-pptx
```

Then generate the PPTX:

```bash
cd tex/ppt/midterm
python3 export_pptx.py
```

Expected PPTX output:
- `tex/ppt/midterm/output/midterm_slides.pptx`

## 3. Exact commands used in this run

```bash
cd /home/idriss/Rag-Poison-Lab/tex/ppt/midterm
localleaf -1 -m slides.tex -e xelatex . -- -g --outdir=output
python3 -m pip install --user python-pptx
python3 export_pptx.py
```

## 4. Dependency / environment notes

- `localleaf` is available in this environment and was used for the Beamer build.
- `xelatex` is invoked through the `localleaf` workflow.
- `python-pptx` was not preinstalled in the current environment and had to be installed before PPTX export.
- No repo-native `.pptx` conversion script existed before this package.

## 5. Output checklist

- Beamer source: `tex/ppt/midterm/slides.tex`
- PDF deck: `tex/ppt/midterm/output/slides.pdf`
- PPTX deck: `tex/ppt/midterm/output/midterm_slides.pptx`
- Audit: `tex/ppt/midterm/AUDIT.md`
- Slide plan: `tex/ppt/midterm/PRESENTATION_PLAN.md`
- Final summary: `tex/ppt/midterm/FINAL_SUMMARY.md`
