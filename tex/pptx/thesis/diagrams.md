# Thesis Defense Diagram and Chart Prompts

Each section below is a **standalone prompt**. Copy only one `## Image Prompt` section at a time into the image/diagram generator. Do not prepend shared instructions from this file; each prompt includes its own context, palette, typography, constraints, and negative constraints. Do **not** generate the actual diagrams automatically from this file.

---

## Image Prompt: Slide 2 Problem — Metadata Becomes Evidence

### Slide Mapping
- Slide number: 2
- Suggested filename: `figures/slide02_metadata_becomes_evidence.png`
- Exact placeholder text to insert if used: `[PLACEHOLDER: insert metadata-as-evidence problem visual]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab, a local benchmark for red-teaming RAG-style LLM-powered movie recommendation systems. The thesis compares clean and poisoned retrieval conditions and keeps the framing defensive, reproducible, and non-operational.

### Purpose
The image must communicate: in a RAG-style recommender, retrieved movie metadata becomes evidence for ranking or reranking, so poisoned metadata can affect the final recommendation before the user sees it.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense slide 2

### Visual Style
- Style: modern academic security research visual, mission-control console feel
- Mood: precise, controlled, defensive, evidence-driven
- Design language: dark rounded cards, thin borders, structured arrows, small status chips
- Detail level: medium; readable from a projector
- Rendering style: flat vector / UI infographic, not 3D
- Avoided style: generic SaaS dashboard, playful icons, photorealism, cyberpunk clutter

### Layout
Use a clean left-to-right flow across the center of the canvas with 5 aligned cards:

1. `User`
2. `Retriever`
3. `Metadata`
4. `Ranker / Reranker`
5. `Top-k List`

Place a red warning capsule below the `Metadata` card labeled `Poisoned Metadata`. Draw a dashed red arrow from `Poisoned Metadata` into `Metadata`. Draw normal blue arrows from left to right across the five cards. Add one thin amber bracket above cards 2 to 4 labeled `security boundary`.

### Required Elements
The image must contain exactly these major elements:
- Five main flow cards
- One red warning capsule under the metadata card
- One amber bracket above retriever, metadata, and ranker cards
- Four left-to-right blue arrows
- One dashed red upward arrow

No additional major panels or background objects.

### Text Labels
Only include the following text, exactly as written:
- `User`
- `Retriever`
- `Metadata`
- `Ranker / Reranker`
- `Top-k List`
- `Poisoned Metadata`
- `security boundary`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Clean arrows: `#4A9EFF`
- Poison warning: `#FF4D4D`
- Boundary bracket: `#FFB800`
- Ranker accent: `#6C63FF`

### Typography
- Use a clean modern sans-serif font.
- Card labels must be 24px equivalent or larger.
- `Top-k` keeps the lowercase `k` exactly.
- Text must be sharp and correctly spelled.
- Align labels centered inside cards.

### Icons
- Icon style: simple line icons, consistent stroke width.
- Icon count: one icon per main card maximum.
- Suggested icons: user silhouette, magnifier, document, ordered list, recommendation list.
- Warning capsule icon: small triangle or shield only.
- Do not use emoji icons, realistic people, laptops, or code screenshots.

### Arrows and Connections
- Main arrows: left to right, thin, blue `#4A9EFF`, connect card centers.
- Poison arrow: dashed, red `#FF4D4D`, vertical or slight diagonal upward, no crossing.
- Boundary bracket: amber `#FFB800`, above cards 2 to 4, not touching text.

### Constraints
The image must:
- Preserve the exact 5-card flow.
- Keep all main cards equal height and aligned on one baseline.
- Make the metadata card visually central.
- Look like a polished thesis defense visual.
- Leave enough empty space so the slide does not feel crowded.

### Negative Constraints
Do not include:
- extra labels
- payload examples
- invented metrics
- random binary/code decorations
- people
- provider logos
- stock photos
- watermarks
- misspelled text
- floating boxes
- gradient-heavy cyber backgrounds
- arrows that cross or point backward

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 3 Research Question and Contributions

### Slide Mapping
- Slide number: 3
- Suggested filename: `figures/slide03_research_question_contributions.png`
- Exact placeholder text to insert if used: `[PLACEHOLDER: insert research question and contributions visual]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. The deck needs one central research-question visual and three contribution cards, grounded only in the finished thesis: controlled clean-vs-poisoned benchmark, three attack families, and reproducible evidence artifacts.

### Purpose
The image must communicate: the thesis is organized around one central research question and three bounded engineering contributions.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense slide 3

### Visual Style
- Style: thesis defense decision board, security research paper aesthetic
- Mood: disciplined, academic, compact
- Design language: one large question panel above three contribution cards
- Detail level: medium-low; no dense prose
- Rendering style: flat vector UI cards
- Avoided style: startup pitch deck, motivational poster, cartoon diagram

### Layout
Use a two-tier composition:

Top tier: one wide centered card spanning about 80% of slide width. This is the research question card. It should have a violet border and a small terminal-style header line.

Bottom tier: three equal contribution cards aligned horizontally with even spacing:

1. Controlled benchmark
2. Three attack families
3. Reproducible evidence

Use subtle colored top bars on each contribution card: blue, orange, green. Keep the question visually dominant but not text-heavy.

### Required Elements
The image must contain exactly:
- One research question card
- Three contribution cards
- Three small icons, one per contribution card
- No arrows unless they are extremely subtle downward connectors from the question card to the three cards

### Text Labels
Only include the following text, exactly as written:
- `Research Question`
- `How do clean and poisoned retrieval conditions change recommendation behavior?`
- `Controlled benchmark`
- `Three attack families`
- `Reproducible evidence`
- `paired runs`
- `promotion · injection · degradation`
- `metrics · configs · traces`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Research question violet: `#6C63FF`
- Benchmark blue: `#4A9EFF`
- Attack orange: `#FF6B35`
- Evidence green: `#2ECC71`

### Typography
- Use clean modern sans-serif.
- Research question label: bold, 24px equivalent.
- Research question sentence: 28px equivalent, readable, centered.
- Contribution labels: bold, 22px equivalent.
- Sub-labels: 18px equivalent, muted text.
- No tiny text.

### Icons
- Icon style: simple line icons with consistent stroke.
- Controlled benchmark icon: split rails or paired comparison.
- Three attack families icon: three stacked warning cards or triad nodes.
- Reproducible evidence icon: archive box or document checklist.
- Do not use shields for every card; avoid visual repetition.

### Arrows and Connections
- Optional: three thin muted downward connectors from the question card to each contribution card.
- Connector color: `#6B7A99` at low opacity.
- No crossing arrows.
- No animated or curved decorative arrows.

### Constraints
The image must:
- Keep exactly three contribution cards.
- Keep all cards aligned and evenly spaced.
- Make the question card feel like the governing thesis question.
- Avoid long paragraphs.
- Be readable from the back of a classroom.

### Negative Constraints
Do not include:
- more than three contributions
- citations
- references
- invented claims
- random charts
- generic icons like rockets or lightbulbs
- stock photos
- decorative particle fields
- misspelled text
- provider logos
- watermarks

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 4 System Architecture

### Slide Mapping
- Slide number: 4
- Suggested filename: `figures/system_architecture_defense.png`
- Exact placeholder text in slide: `[PLACEHOLDER: insert system architecture diagram]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. The architecture should summarize the finished thesis system: MovieLens 100K data, poisoning builder, clean and poisoned Elasticsearch indices, recommendation/ranking services, evaluation artifacts, and React UI. It must stay high-level and defensive.

### Purpose
The image must communicate: RAG Poison Lab is an inspectable benchmark architecture with separate data, poisoning, retrieval, ranking/reranking, evaluation, and UI artifact surfaces.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 6% on all sides
- Intended use: PowerPoint thesis defense slide 4

### Visual Style
- Style: mission-control architecture map for a security research paper
- Mood: technical, calm, reproducible
- Design language: thin bordered cards, split clean/poisoned rails, artifact chips
- Detail level: medium; enough structure without implementation clutter
- Rendering style: flat vector architecture diagram
- Avoided style: cloud vendor architecture, colorful SaaS dashboard, network spaghetti

### Layout
Use a left-to-right architecture flow with 5 vertical zones:

1. Data source
2. Poisoning and bulk generation
3. Retrieval store with two parallel indices
4. Recommendation and ranking services
5. Evidence and UI outputs

The retrieval store zone must split into two stacked cards: clean index above, poisoned index below. The two rails rejoin at an evaluation comparison node near the right. Place React UI and artifacts as two output cards on the far right.

### Required Elements
The image must contain exactly these elements:
- `MovieLens 100K`
- `Poisoning Builder`
- `Clean Index`
- `Poisoned Index`
- `Retriever`
- `Ranker / Reranker`
- `Evaluation Runner`
- `Metrics + Traces`
- `React UI`

No additional named services.

### Text Labels
Only include the following text, exactly as written:
- `MovieLens 100K`
- `Poisoning Builder`
- `Clean Index`
- `Poisoned Index`
- `Retriever`
- `Ranker / Reranker`
- `Evaluation Runner`
- `Metrics + Traces`
- `React UI`
- `paired conditions`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Clean rail: `#4A9EFF`
- Poisoned rail: `#FF4D4D`
- Evaluation/artifacts: `#2ECC71`
- UI accent: `#6C63FF`
- Warning accent: `#FFB800`

### Typography
- Use a clean modern sans-serif font.
- Use monospaced font only if rendering artifact chips; otherwise avoid mono.
- Labels must be short and readable.
- No text below 18px equivalent.
- Text must be sharp and correctly spelled.

### Icons
- Icon style: simple modern line icons.
- One icon per card maximum.
- Suggested icons: database cylinder, wrench, index stack, magnifier, ranked list, chart, dashboard.
- Do not use cloud logos, vendor logos, mascots, or realistic server racks.

### Arrows and Connections
- Data flow arrows move left to right.
- Clean path arrow: `#4A9EFF`.
- Poisoned path arrow: `#FF4D4D`.
- Comparison/evidence arrows: `#2ECC71` or muted `#6B7A99`.
- No crossing arrows except the two rails rejoining cleanly at `Evaluation Runner`.

### Constraints
The image must:
- Preserve the five-zone layout.
- Clearly show two separate clean and poisoned indices.
- Make the architecture inspectable rather than decorative.
- Avoid implementation-level filenames or code paths.
- Leave enough empty space for slide title and speaker focus.

### Negative Constraints
Do not include:
- extra services
- AWS/Azure/GCP icons
- provider names
- code snippets
- payload text
- giant background grids
- random locks/skulls
- people
- watermarks
- misspelled labels
- more than one UI output card

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 5 Attack Scenario Comparison

### Slide Mapping
- Slide number: 5
- Suggested filename: `figures/slide05_attack_scenario_comparison.png`
- Exact placeholder text to insert if used: `[PLACEHOLDER: insert three attack scenario comparison visual]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. The thesis evaluates three poisoning scenarios: targeted promotion, prompt-injection-style metadata poisoning, and untargeted degradation. The visual must compare these scenarios without showing payloads, exploit instructions, or implementation details.

### Purpose
The image must communicate: the thesis studies three different poisoning scenarios, each with a different observable effect, without exposing operational payload details.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense slide 5

### Visual Style
- Style: security research comparison board
- Mood: controlled, defensive, non-operational
- Design language: three structured cards with semantic color headers and metric chips
- Detail level: medium-low
- Rendering style: flat vector infographic
- Avoided style: threat-hacker poster, malware graphic, cartoon villain, red-alert overload

### Layout
Use three equal cards arranged horizontally across the canvas. Each card has:

- A semantic colored top strip
- One line icon near the top left
- One attack family title
- One short effect label
- One metric chip at the bottom

The three cards must have equal width and height and align perfectly. Put no arrows between cards; this is a comparison, not a process flow.

### Required Elements
The image must contain exactly:
- Card 1: targeted promotion
- Card 2: prompt-injection-style metadata poisoning
- Card 3: untargeted degradation
- Three metric chips
- Three icons

### Text Labels
Only include the following text, exactly as written:
- `Targeted Promotion`
- `target item enters top-k`
- `ASR`
- `Metadata Poisoning`
- `instruction-like text reaches reranker`
- `LLM Rerank`
- `Untargeted Degradation`
- `overall quality drops`
- `HR · NDCG · MRR`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Targeted promotion: `#FF6B35`
- Metadata poisoning: `#BF5FFF`
- Untargeted degradation: `#FFB800`
- Danger accent: `#FF4D4D`

### Typography
- Use a clean modern sans-serif font.
- Attack family titles: bold, 24px equivalent.
- Effect labels: 18px equivalent, muted/body text.
- Metric chips: monospaced, 18px equivalent.
- Text must be sharp and correctly spelled.

### Icons
- Icon style: modern line icons, consistent stroke width.
- Card 1 icon: target reticle.
- Card 2 icon: document with warning mark.
- Card 3 icon: descending ranking bars.
- One icon per card only.
- Do not use skulls, bombs, masks, hooded hackers, or realistic malware imagery.

### Arrows and Connections
- No arrows.
- No connectors.
- No flow lines.

### Constraints
The image must:
- Keep all cards equal size.
- Keep text minimal and exactly as specified.
- Avoid showing attack payload content.
- Look suitable for an undergraduate thesis defense.
- Make the three scenarios visually distinct but part of one system.

### Negative Constraints
Do not include:
- operational payloads
- code strings
- provider names
- exact target movie IDs
- exploit instructions
- more than three cards
- dense bullet lists
- random warning icons outside cards
- watermarks
- logos
- misspelled text

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 6 Clean vs Poisoned Experimental Loop

### Slide Mapping
- Slide number: 6
- Suggested filename: `figures/slide06_clean_poisoned_experiment_loop.png`
- Exact placeholder text in slide: `[PLACEHOLDER: insert clean vs poisoned experiment loop diagram]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. The thesis compares baseline and attacked recommendations using paired clean and poisoned retrieval conditions, the same users, the same top-k setting, and the same metric code. The visual should emphasize reproducibility and paired comparison.

### Purpose
The image must communicate: each experiment compares clean and poisoned retrieval conditions using the same users, same top-k setting, same metric code, and saved artifacts.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense slide 6

### Visual Style
- Style: controlled benchmark loop diagram
- Mood: reproducible, precise, engineering-focused
- Design language: split-lane loop with central control badge and artifact endpoint
- Detail level: medium; not a busy pipeline chart
- Rendering style: flat vector process diagram
- Avoided style: circular infographic with random icons, generic agile loop, decorative swirl

### Layout
Use a horizontal loop with two parallel lanes:

Top lane is clean and blue. Bottom lane is poisoned and red. Both lanes start at a shared `Prepare Data` card on the left and end at a shared `Compare Metrics` card on the right. Between them:

- Top lane: `Clean Index` -> `Baseline Run`
- Bottom lane: `Poisoned Index` -> `Attacked Run`

Place a central control badge between the two lanes labeled `same users · same k=10 · same metric code`. Place a green `Saved Artifacts` card after `Compare Metrics` on the far right.

### Required Elements
The image must contain exactly:
- One shared `Prepare Data` card
- Two lane cards for clean path
- Two lane cards for poisoned path
- One central control badge
- One `Compare Metrics` card
- One `Saved Artifacts` card
- Arrows connecting the loop left to right

### Text Labels
Only include the following text, exactly as written:
- `Prepare Data`
- `Clean Index`
- `Baseline Run`
- `Poisoned Index`
- `Attacked Run`
- `same users · same k=10 · same metric code`
- `Compare Metrics`
- `Saved Artifacts`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Clean lane: `#4A9EFF`
- Poisoned lane: `#FF4D4D`
- Delta/compare: `#FFB800`
- Artifact/success: `#2ECC71`

### Typography
- Use a clean modern sans-serif font.
- Use monospaced font for `k=10` only.
- Main labels: 20px equivalent or larger.
- Central badge: 18px equivalent, readable.
- Text must be sharp and correctly spelled.

### Icons
- Icon style: simple line icons, consistent stroke.
- `Prepare Data`: dataset stack icon.
- Index cards: database/index icon.
- Run cards: play/terminal icon.
- Compare card: delta chart icon.
- Saved artifacts: archive/checklist icon.
- Do not use more than one icon per card.

### Arrows and Connections
- Clean lane arrows: blue `#4A9EFF`.
- Poisoned lane arrows: red `#FF4D4D`.
- Both lanes merge into `Compare Metrics` using a clean fork/merge shape.
- Arrow from `Compare Metrics` to `Saved Artifacts`: green `#2ECC71`.
- No crossing arrows.

### Constraints
The image must:
- Clearly show paired clean and poisoned paths.
- Keep clean and poisoned lanes parallel.
- Make the central control badge visually obvious.
- Avoid circular clutter; use a clean split-lane workflow.
- Be readable on a projector.

### Negative Constraints
Do not include:
- extra experiment stages
- provider names
- payload details
- full metric definitions
- dense notes
- random dashboards
- watermarks
- logos
- misspelled text
- arrows that cross or reverse direction

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 6 Metrics Explanation Mini-Diagram

### Slide Mapping
- Slide number: 6, optional inset or backup visual
- Suggested filename: `figures/slide06_metrics_explainer.png`
- Exact placeholder text to insert if used: `[PLACEHOLDER: insert metrics explanation mini-diagram]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. It explains the metrics used in the thesis at a high level: HR, NDCG, and MRR for recommendation quality, and ASR for target-oriented attack success. It should be compact enough to use as an inset or backup visual.

### Purpose
The image must communicate: HR, NDCG, MRR, and ASR answer different evaluation questions and should be interpreted together.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 8% on all sides
- Intended use: PowerPoint thesis defense backup or slide 6 inset

### Visual Style
- Style: metric badge explainer, security benchmark UI
- Mood: precise, compact, educational
- Design language: 2x2 metric tiles with small visual metaphors
- Detail level: low-medium
- Rendering style: flat vector UI tiles
- Avoided style: statistical textbook page, dense formula sheet, generic dashboard widgets

### Layout
Create a 2x2 grid of four equal tiles. Each tile has a large monospaced metric name at the top, one icon in the middle, and one short meaning label at the bottom.

Top row: `HR`, `NDCG`
Bottom row: `MRR`, `ASR`

### Required Elements
The image must contain exactly:
- Four equal metric tiles
- Four metric names
- Four icons
- Four meaning labels

### Text Labels
Only include the following text, exactly as written:
- `HR`
- `hit in top-k`
- `NDCG`
- `position-aware gain`
- `MRR`
- `first relevant rank`
- `ASR`
- `target appears`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Quality metric blue: `#4A9EFF`
- Target metric orange: `#FF6B35`
- Success green: `#2ECC71`
- Warning amber: `#FFB800`

### Typography
- Metric names: monospaced, bold, 32px equivalent.
- Meaning labels: clean sans-serif, 18px equivalent.
- Center-align all tile text.
- Text must be sharp and correctly spelled.

### Icons
- HR icon: checkmark in a top-k list.
- NDCG icon: descending stair-step bars.
- MRR icon: flag on first relevant item.
- ASR icon: target reticle inside a ranked list.
- Icon style: line icons, one color per tile, consistent stroke.
- Do not use formulas or mathematical notation.

### Arrows and Connections
- No arrows.
- No connectors.

### Constraints
The image must:
- Make metric names dominant.
- Keep all four tiles equal size.
- Use minimal text.
- Be readable as a small inset.
- Avoid implying one metric is sufficient alone.

### Negative Constraints
Do not include:
- formulas
- long definitions
- extra metrics
- full tables
- random charts
- decorative icons outside tiles
- watermarks
- misspelled text

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 7 Main Result Matrix

### Slide Mapping
- Slide number: 7
- Suggested filename: `figures/slide07_main_result_matrix.png`
- Exact placeholder text in slide: `[PLACEHOLDER: insert main result matrix / chart visual]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. It summarizes the final thesis result matrix: 15 successful runs across three attack families. The thesis does **not** rank providers. It compares attack-family behavior using mean metric deltas. Every matrix cell must contain a value or an explicit `n/a`; no metric cell should be left blank or visually disabled unless it is truly not applicable.

### Purpose
The image must communicate: the final thesis results show three distinct risk patterns across all relevant metrics. Targeted promotion and prompt injection are strongest on ASR, while untargeted degradation is strongest across the recommendation-quality metrics HR, NDCG, and MRR.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense slide 7

### Visual Style
- Style: thesis result matrix / security benchmark chart
- Mood: empirical, cautious, evidence-backed
- Design language: compact heatmap matrix with all metric cells filled, plus a small interpretation area
- Detail level: medium; enough numbers to be scientifically honest, but not the full 15-run table
- Rendering style: flat vector chart, not a spreadsheet screenshot
- Avoided style: dense appendix table, Excel chart, generic business analytics dashboard, decorative infographic

### Layout
Use a 3-row by 4-column result matrix occupying the left 72% of the canvas.

Rows, top to bottom:
1. `Targeted Promotion`
2. `Prompt Injection`
3. `Untargeted Degradation`

Columns, left to right:
1. `ΔHR`
2. `ΔNDCG`
3. `ΔMRR`
4. `ΔASR`

Every row-column cell must contain a value. Use muted but readable cells for small secondary deltas; do **not** gray out HR, NDCG, or MRR for targeted promotion or prompt injection. Use `n/a` only for untargeted degradation ASR, because ASR is not applicable to that family.

Place a small top status chip above the matrix: `15 / 15 successful runs`.

On the right 28% of the canvas, place three stacked interpretation chips:
1. `target steering`
2. `LLM rerank sensitivity`
3. `quality degradation`

Use row-colored connectors or alignment guides from each matrix row to the matching interpretation chip. Keep the connectors subtle and non-crossing.

### Required Elements
The image must contain exactly:
- One status chip
- One 3x4 matrix with all 12 cells filled
- Three interpretation chips
- One small legend with two labels: `target effect` and `quality loss`
- Optional row icons, maximum three total

### Text Labels
Only include the following text, exactly as written:
- `15 / 15 successful runs`
- `Targeted Promotion`
- `Prompt Injection`
- `Untargeted Degradation`
- `ΔHR`
- `ΔNDCG`
- `ΔMRR`
- `ΔASR`
- `-0.007`
- `-0.002`
- `-0.006`
- `+0.348`
- `-0.002`
- `-0.001`
- `-0.004`
- `+0.157`
- `-0.078`
- `-0.011`
- `-0.033`
- `n/a`
- `target steering`
- `LLM rerank sensitivity`
- `quality degradation`
- `target effect`
- `quality loss`

No other text is allowed.

### Cell Value Mapping
Render the matrix values exactly as follows:

| Attack family | ΔHR | ΔNDCG | ΔMRR | ΔASR |
|---|---:|---:|---:|---:|
| `Targeted Promotion` | `-0.007` | `-0.002` | `-0.006` | `+0.348` |
| `Prompt Injection` | `-0.002` | `-0.001` | `-0.004` | `+0.157` |
| `Untargeted Degradation` | `-0.078` | `-0.011` | `-0.033` | `n/a` |

### Emphasis Rules
- Emphasize `+0.348` in targeted orange `#FF6B35` as the strongest target-steering signal.
- Emphasize `+0.157` in prompt-injection violet `#BF5FFF` as the LLM-rerank target-steering signal.
- Emphasize all three untargeted degradation quality-loss cells: `-0.078`, `-0.011`, and `-0.033`. Do not emphasize only NDCG.
- Use red/amber quality-loss coloring for negative quality deltas, with stronger color intensity for larger magnitude.
- Keep the small negative quality deltas for targeted promotion and prompt injection visible and readable, but less visually dominant than their ASR cells.
- Render `n/a` as muted text, not as an empty gray box.

### Color Palette
Use only:
- Background: `#0D1117`
- Card/cell background: `#141B2D`
- Grid/border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Targeted promotion orange: `#FF6B35`
- Prompt injection violet: `#BF5FFF`
- Degradation amber: `#FFB800`
- Loss red: `#FF4D4D`
- Success green: `#2ECC71`

### Typography
- Matrix row and column labels: clean sans-serif, 18px equivalent or larger.
- Numeric values: monospaced, bold, 22px equivalent or larger.
- Status chip: monospaced, 18px equivalent.
- Interpretation chips: clean sans-serif, 18px equivalent.
- Text must be sharp and correctly spelled.
- Align numeric values centered in their cells.

### Icons
- Optional small row icons only: target reticle for targeted promotion, warning document for prompt injection, descending bars for untargeted degradation.
- Maximum three icons total.
- Icons must not replace text labels.
- Do not use provider/model icons.

### Arrows and Connections
- No process arrows.
- Optional thin connector from each matrix row to its matching interpretation chip.
- Connector color should match the row accent but be subtle.
- No crossing connectors.

### Constraints
The image must:
- Fill all 12 matrix cells with the exact mapped values.
- Use `n/a` only for untargeted degradation ASR.
- Keep HR, NDCG, and MRR visible for every attack family.
- Make untargeted degradation visibly strong across HR, NDCG, and MRR, not only NDCG.
- Avoid claiming a provider ranking.
- Avoid showing the full 15-run table.
- Make the three qualitative patterns clear without hiding secondary metrics.

### Negative Constraints
Do not include:
- blank metric cells
- grayed-out HR/NDCG/MRR cells for targeted promotion or prompt injection
- only one highlighted untargeted degradation metric
- any additional numbers beyond the listed values
- model/provider names
- full table rows
- p-values or confidence intervals
- fake charts
- 3D bars
- gradients that reduce readability
- watermarks
- misspelled metric names

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.
---

## Image Prompt: Slide 7 Deterministic Ranker vs LLM Reranker Scope

### Slide Mapping
- Slide number: optional slide 7 inset or backup slide
- Suggested filename: `figures/slide07_ranker_scope_comparison.png`
- Exact placeholder text to insert if used: `[PLACEHOLDER: insert deterministic vs LLM reranker scope visual]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. It is a scope clarification: final matrix rows use deterministic ranking for targeted promotion and untargeted degradation, while prompt-injection rows use LLM reranking. The visual must not imply a universal ranker benchmark or provider ranking.

### Purpose
The image must communicate: the final matrix includes both deterministic and LLM reranking paths, but the thesis does not claim a universal ranker or provider benchmark.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: optional thesis defense backup visual

### Visual Style
- Style: scoped comparison diagram
- Mood: careful, caveated, evidence-backed
- Design language: two large cards plus a caution strip
- Detail level: low-medium
- Rendering style: flat vector UI diagram
- Avoided style: head-to-head contest chart, scoreboard, vendor comparison

### Layout
Use two large side-by-side cards centered horizontally:

Left card: deterministic ranker, blue accent.
Right card: LLM reranker, violet accent.

A single input card labeled `Candidate List` sits above and points down to both cards. A bottom amber caution strip spans both cards.

### Required Elements
The image must contain exactly:
- One `Candidate List` input card
- One `Deterministic Ranker` card
- One `LLM Reranker` card
- One caution strip
- Three arrows: one input split into two branches, one muted line from both ranker cards to caution strip

### Text Labels
Only include the following text, exactly as written:
- `Candidate List`
- `Deterministic Ranker`
- `targeted + degradation rows`
- `LLM Reranker`
- `prompt injection rows`
- `scope: final matrix only`
- `not a provider ranking`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Deterministic blue: `#4A9EFF`
- LLM violet: `#6C63FF`
- Prompt violet: `#BF5FFF`
- Caution amber: `#FFB800`

### Typography
- Main labels: clean sans-serif, bold, 24px equivalent.
- Scope labels: clean sans-serif, 18px equivalent.
- The word `scope` can be monospaced only if it remains readable.
- Text must be sharp and correctly spelled.

### Icons
- Deterministic icon: rule sliders or ordered bars.
- LLM icon: abstract neural/chat bubble.
- Candidate list icon: stacked list.
- Caution strip icon: small shield or triangle.
- Do not use any provider logos.

### Arrows and Connections
- Candidate list splits into two downward arrows.
- Arrow to deterministic card: `#4A9EFF`.
- Arrow to LLM card: `#6C63FF`.
- Muted connector to caution strip: `#6B7A99`.
- No crossing arrows.

### Constraints
The image must:
- Make the scope caveat obvious.
- Avoid implying one ranker is generally better.
- Avoid showing performance scores.
- Keep the visual simple enough for a backup explanation.

### Negative Constraints
Do not include:
- provider names
- model names
- winner badges
- rankings
- extra metrics
- logos
- charts
- watermarks
- misspelled labels

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 10 Security Interpretation, Limits, and Ethics

### Slide Mapping
- Slide number: 10
- Suggested filename: `figures/slide10_security_limits_ethics.png`
- Exact placeholder text to insert if used: `[PLACEHOLDER: insert security interpretation limits ethics visual]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. It must communicate the responsible security framing: retrieved metadata can shift ranking behavior, the benchmark does not claim universal live-service generalization, and the setup is closed, local, and reproducible.

### Purpose
The image must communicate: the benchmark has a meaningful security interpretation, clear limits, and a safe closed local setup.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense slide 10

### Visual Style
- Style: responsible security interpretation board
- Mood: cautious, ethical, defensible
- Design language: three evidence cards with a shared base line labeled local benchmark
- Detail level: medium-low
- Rendering style: flat vector thesis-defense visual
- Avoided style: fear-based cybersecurity poster, legal disclaimer wall, dense ethics slide

### Layout
Use three equal cards arranged horizontally across the center:

1. What it implies
2. What it does not claim
3. Why it is safe

Each card has a large icon, one title, and one compact label. A thin green baseline runs under all three cards and connects to a small bottom badge labeled `closed local benchmark`.

### Required Elements
The image must contain exactly:
- Three equal cards
- Three icons
- One green baseline
- One bottom badge

### Text Labels
Only include the following text, exactly as written:
- `What it implies`
- `metadata can shift ranking`
- `What it does not claim`
- `no universal provider ranking`
- `Why it is safe`
- `closed local benchmark`
- `MovieLens data · saved artifacts`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Implication red: `#FF4D4D`
- Limit amber: `#FFB800`
- Safe green: `#2ECC71`
- Clean blue: `#4A9EFF`

### Typography
- Card titles: clean sans-serif, bold, 24px equivalent.
- Compact labels: clean sans-serif, 18px equivalent.
- Bottom badge: monospaced or compact sans-serif, 18px equivalent.
- Text must be sharp and correctly spelled.

### Icons
- What it implies icon: ranking bars with one shifted item.
- What it does not claim icon: boundary frame or caution sign.
- Why it is safe icon: closed lab box or shielded archive.
- Icon style: line icons, consistent stroke, not cartoonish.
- Do not use police badges, locks everywhere, skulls, malware symbols, or real people.

### Arrows and Connections
- No arrows between cards.
- A single thin green baseline connects all cards to the bottom badge.
- No crossing connectors.

### Constraints
The image must:
- Keep the ethics and limitations visible, not hidden.
- Avoid fear-based framing.
- Show the setup as local, closed, and reproducible.
- Avoid suggesting deployed-system compromise.
- Remain readable from a projector.

### Negative Constraints
Do not include:
- operational attack instructions
- payload examples
- legal boilerplate
- provider names
- live-service screenshots
- dramatic hacker imagery
- extra claims
- watermarks
- logos
- misspelled labels

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.

---

## Image Prompt: Slide 11 Optional Final Synthesis Diagram

### Slide Mapping
- Slide number: 11, optional replacement or backup visual
- Suggested filename: `figures/slide11_final_synthesis.png`
- Exact placeholder text to insert if used: `[PLACEHOLDER: insert final synthesis diagram]`

### Context
This visual belongs to an undergraduate thesis defense for RAG Poison Lab. It is an optional closing synthesis that connects metadata as a security boundary, multi-metric evaluation, and reproducible artifacts into one evaluation environment. It should not introduce new claims.

### Purpose
The image must communicate: RAG Poison Lab connects metadata security, multi-metric evaluation, and reproducible artifacts into one evaluation environment.

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: dark `#0D1117`
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense closing slide or backup

### Visual Style
- Style: final thesis synthesis diagram
- Mood: conclusive, calm, precise
- Design language: triangle of three takeaway nodes around a central lab badge
- Detail level: low-medium
- Rendering style: flat vector concept diagram
- Avoided style: motivational poster, flashy startup ending slide, decorative abstract art

### Layout
Use a triangle layout:

- Top node: metadata boundary
- Bottom left node: multi-metric evaluation
- Bottom right node: reproducible artifacts
- Center node: RAG Poison Lab

Use thin circular arrows around the triangle and subtle inward connectors to the center.

### Required Elements
The image must contain exactly:
- Three takeaway nodes
- One center badge
- Three circular arrows
- Three inward connectors

### Text Labels
Only include the following text, exactly as written:
- `metadata boundary`
- `multi-metric evaluation`
- `reproducible artifacts`
- `RAG Poison Lab`
- `ASR + quality`
- `paired runs + traces`

No other text is allowed.

### Color Palette
Use only:
- Background: `#0D1117`
- Card background: `#141B2D`
- Card border: `#1E2A45`
- Heading text: `#EAEEF5`
- Body text: `#C9D1E0`
- Muted text: `#6B7A99`
- Clean blue: `#4A9EFF`
- Target orange: `#FF6B35`
- Success green: `#2ECC71`
- Active violet: `#6C63FF`

### Typography
- Use clean modern sans-serif.
- Center badge: bold, 28px equivalent.
- Node labels: bold, 22px equivalent.
- Sub-labels: 18px equivalent.
- Use monospaced font only for `ASR` if needed.

### Icons
- Metadata boundary icon: shielded document.
- Multi-metric evaluation icon: compact chart.
- Reproducible artifacts icon: archive/checklist.
- Center badge icon: terminal/lab mark.
- One icon per node maximum.

### Arrows and Connections
- Circular arrows: muted `#6B7A99` or violet `#6C63FF`, thin.
- Inward connectors: subtle, no arrowheads required.
- No crossing arrows.

### Constraints
The image must:
- Feel like a final synthesis, not a new method slide.
- Avoid adding new claims.
- Keep text minimal.
- Use the same dark visual identity as the rest of the deck.

### Negative Constraints
Do not include:
- extra takeaways
- new metrics
- provider names
- citations
- photos
- logos
- watermarks
- random decorations
- misspelled text

### Output Requirements
- Clean final image.
- High resolution, minimum 1920x1080.
- No visible prompt text.
- No watermark.
- No border around the full image.
