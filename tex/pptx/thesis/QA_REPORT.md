# UltraQA Report: Thesis Defense Presentation Related-Work Update

## Goal and success criteria
- Goal: Verify the thesis defense deck update that adds a short Related Work slide and a non-operational attack-explanation slide under `tex/pptx/thesis`.
- Stop condition: New slides exist, use only selected thesis bibliography keys, every new slide has notes, timing remains 5--8 minutes, safety checks find no payloads/instructions, PDF builds, and PPTX exports.
- Safety bounds applied: No external sources, no thesis-source edits, no operational payload detail, no exploit steps, no live-system testing.

## Scenario matrix

| ID | User/attacker model | Scenario | Command/harness | Expected signal | Actual result | Status | Evidence | Cleanup |
|---|---|---|---|---|---|---|---|---|
| QA-001 | Normal presenter | Slide count and placement | static frame scan | Related Work after RQ; Attack Meaning after Attack Scenarios | 13 frames with required order | PASS | `thesis_presentation.tex` scan | no temp artifacts |
| QA-002 | Citation reviewer | BibTeX key existence | static `references.bib` lookup | selected keys exist | all three keys found | PASS | `zhong2023retrievalcorpora`, `greshake2023indirectpi`, `nazary2025poisonrag` | none |
| QA-003 | Scope reviewer | Related Work source limit | static slide-key extraction | only selected keys used | Related Work uses exactly selected keys | PASS | static Python check | none |
| QA-004 | Attack-content reviewer | Attack cards connect to same related work | static card scan | same selected works referenced | all attack families cite selected works | PASS | static Python check | none |
| QA-005 | Safety attacker | Payload or operational instruction leakage | static forbidden-string scan | no payload strings, code payload fields, or how-to wording | forbidden strings absent | PASS | static grep/Python check | none |
| QA-006 | Notes reviewer | Speaker notes coverage | static count | 13 slide-note sections for 13 frames | 13 notes sections | PASS | `speaker_notes.md` | none |
| QA-007 | Timing reviewer | Defense duration | timing table | 5--8 minutes | total `7:55` | PASS | final timing table | none |
| QA-008 | Build user | LaTeX compile | `localleaf -1 -m thesis_presentation.tex -e xelatex . -- -g --outdir=output` | exit 0 and 13-page PDF | PDF produced | PASS | localleaf output `[1]...[13]` | outputs kept |
| QA-009 | PPTX user | PPTX export | `python3 export_pptx.py` | exit 0 and 13-slide PPTX | PPTX produced | PASS | exporter output path | output kept |

## Commands run
- `[0] omx explore --prompt ...` — located deck sources, thesis bibliography, attack slide placement, notes, and build/export commands.
- `[0] python3 -m py_compile tex/pptx/thesis/export_pptx.py` — exporter syntax check.
- `[0] cd tex/pptx/thesis && localleaf -1 -m thesis_presentation.tex -e xelatex . -- -g --outdir=output` — PDF build.
- `[0] cd tex/pptx/thesis && python3 export_pptx.py` — PPTX export.
- `[0] static Python/grep checks` — frame count, notes count, BibTeX key existence, selected-key-only checks, forbidden-string checks, timing table.

## Fixes applied
- Added native-card Related Work slide after Research Question and Contributions.
- Added native-card Attack Meaning slide after Attack Scenarios.
- Updated speaker notes and timing table from 6:25 / 11 slides to 7:55 / 13 slides.
- Updated manual PPTX exporter and README for 13-slide numbering.

## Residual risks
- The PPTX exporter is still a manual reconstruction following the existing midterm workflow; it is not an automatic Beamer conversion.
- The new card slides use citation keys as compact labels rather than a rendered bibliography slide, matching the deck's existing lightweight style.

## Evidence
- Selected keys: `zhong2023retrievalcorpora`, `greshake2023indirectpi`, `nazary2025poisonrag`.
- Frame count: 13.
- Speaker-note slide sections: 13.
- Timing: 7:55.
- PDF: `tex/pptx/thesis/output/thesis_presentation.pdf`.
- PPTX: `tex/pptx/thesis/output/thesis_presentation.pptx`.
