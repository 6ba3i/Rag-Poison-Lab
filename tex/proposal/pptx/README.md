# Beamer Slides (LaTeX)

This folder contains a beamer presentation generated from the thesis proposal content.

## Files

- `slides.tex`: main beamer source
- `build.sh`: one-command build script
- `Makefile`: convenience build targets
- `output/`: generated PDF and intermediates

## Build

From this folder:

```bash
bash build.sh
```

or

```bash
make
```

Direct command:

```bash
localleaf -1 -m slides.tex -e xelatex . -- -g --outdir=output
```
