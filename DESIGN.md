# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-05-27
- Primary product surfaces: RAG Poison Lab React thesis demo app; Overview, Experiments, Users, Results, Matrix Results, Settings; thesis defense deck under `tex/pptx/thesis`.
- Evidence reviewed: `web/src/components/Layout.tsx`, `web/src/pages/Overview.tsx`, `web/src/pages/Experiments.tsx`, `web/src/pages/Results.tsx`, `web/src/components/results/MetricComparisonChart.tsx`, `web/src/styles/index.css`, `web/package.json`, `data/results/full/combined_results.csv`, `data/results/full/combined_results.md`, `tex/thesis/main.tex`, `tex/thesis/sections/*.tex`, `tex/pptx/midterm/slides.tex`, `tex/pptx/midterm/export_pptx.py`.

## Brand
- Personality: Dark research console, security benchmark, academic thesis defense, credible and controlled.
- Trust signals: Real artifact provenance, exact row counts, source-path disclosure, conservative labels, computed metrics only.
- Avoid: Generic pastel SaaS styling, fake/demo values, pie/donut charts, excessive red decoration, looping motion, whole-app redesign, and dark-only components that break white mode.

## Product goals
- Goals: Make baseline-vs-attacked behavior legible; expose matrix experiment coverage; support thesis defense storytelling with traceable evidence.
- Non-goals: Replace the existing Results tab; trigger new experiments from matrix results; serve as a live backend data explorer.
- Success signals: Matrix Results has its own nav/route, computes all values from the CSV snapshot, and preserves existing app build/results behavior. Thesis defense slides are visual-first, thesis-only, 5--8 minutes, and use the dark mission-control palette without text-heavy frames.

## Personas and jobs
- Primary personas: Thesis author/presenter, advisor/reviewer, technical evaluator.
- User jobs: Explain attack effects, compare scenarios/rankers, inspect run-level evidence, verify raw data backing.
- Key contexts of use: Thesis demos, defense presentations, local research audits.

## Information architecture
- Primary navigation: Overview -> Experiments -> Users -> Results -> Matrix Results -> Settings.
- Core routes/screens: `/results` remains run-history/detail; `/matrix-results` is the full matrix dashboard.
- Content hierarchy: Hero/provenance, KPIs, filters, main comparison, scenario/ranker/heatmap proof, run explorer, raw table.

## Design principles
- Principle 1: Evidence before ornament; every number must be source-backed.
- Principle 2: Preserve existing console language; extend tokens rather than replacing them.
- Principle 3: Progressive disclosure; charts first, raw table last.
- Tradeoffs: Static snapshot is simpler and safer for frontend delivery but needs visible provenance to manage drift.

## Visual language
- Color: Existing dark and light theme variables with matrix palette mapped to baseline blue, attack red, targeted orange, injection purple, degradation amber, indigo accent. Thesis deck palette: page `#0D1117`, card `#141B2D`, border `#1E2A45`, headings `#EAEEF5`, body `#C9D1E0`, muted `#6B7A99`, clean blue `#4A9EFF`, poisoned red `#FF4D4D`, amber `#FFB800`, violet `#6C63FF`, green `#2ECC71`, targeted orange `#FF6B35`, prompt violet `#BF5FFF`. Matrix-specific surfaces must define light-mode overrides.
- Typography: Existing sans-serif; monospaced numeric KPIs, metric badges, and artifact identifiers.
- Spacing/layout rhythm: Existing page wrap, surface cards, split grids, compact badges.
- Shape/radius/elevation: Existing rounded dark surfaces with subtle borders and hover glow.
- Motion: One-shot and short transitions only; no looping.
- Imagery/iconography: Text/badge/SVG-style data visualization; no decorative illustrations required.

## Components
- Existing components to reuse: Layout shell, page headers, metric cards, badges, data-table styling, dumbbell chart idiom.
- New/changed components: Matrix Results page sections, custom matrix parser, custom heatmap/run drawer/raw table; thesis defense slide cards, badges, placeholder zones, speaker notes, diagram prompts, and manual PPTX exporter.
- Variants and states: Loading, error, empty filtered set, unavailable metric, selected row, drawer open/closed.
- Token/component ownership: `web/src/styles/index.css` remains the styling source; no new design-system package.

## Accessibility
- Theme mode: Matrix Results must remain readable in both dark and white modes using the existing app toggle.
- Target standard: Practical WCAG-friendly contrast and semantic controls.
- Keyboard/focus behavior: Buttons, filters, drawer close, raw-table controls keyboard reachable.
- Contrast/readability: Dark surfaces with high-contrast labels and compact but legible values.
- Screen-reader semantics: Tables remain real tables; chart sections include textual labels/values.
- Reduced motion and sensory considerations: Respect `prefers-reduced-motion`; animations are one-shot and nonessential.

## Responsive behavior
- Supported breakpoints/devices: Desktop-first thesis demo; graceful wrapping for narrower viewports.
- Layout adaptations: Cards and split panels collapse to one column under existing responsive rules.
- Touch/hover differences: Hover glow is enhancement only; click targets remain visible.

## Interaction states
- Loading: Compact surface loading state while fetching public CSV snapshot.
- Empty: Filtered empty state explains no rows match.
- Error: Data load/parse errors shown in dark error card.
- Success: Provenance and row-count badges confirm loaded snapshot.
- Disabled: Play Attack disabled when selected metric lacks baseline/attacked pairs.
- Offline/slow network, if applicable: Static public assets should load with the app; failures are surfaced.

## Content voice
- Tone: Precise, academic, defensive, evidence-backed; for the thesis defense, spoken notes carry detail while slides remain sparse.
- Terminology: Baseline, attacked, attack type, ranker, ASR, NDCG, MRR, HR, delta, provenance.
- Microcopy rules: Avoid causal claims not directly supported by computed values; avoid operationally harmful payload detail in security slides.

## Implementation constraints
- Framework/styling system: React 18, Vite, TypeScript, plain CSS/Tailwind base, existing Nivo/framer-motion dependencies.
- Design-token constraints: Extend existing CSS variables/classes; no broad theme rewrite.
- Performance constraints: Small 15-row CSV snapshot; avoid heavy dependencies.
- Compatibility constraints: Keep `/results` API flow intact.
- Test/screenshot expectations: Build/typecheck pass; route smoke and computed-data integrity checks.

## Open questions
- [ ] Whether future versions should replace the static snapshot with a backend matrix-results API / owner: thesis author / impact: freshness vs implementation scope.
