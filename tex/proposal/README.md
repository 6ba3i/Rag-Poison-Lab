### localleaf build 

```bash
cd tex/proposal
localleaf -1 -m main.tex -e xelatex . -- --outdir=output
```
```bash
cd tex/proposal/pptx
localleaf -1 -m slides.tex -e xelatex . -- --outdir=output
```