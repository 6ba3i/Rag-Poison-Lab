# Image Generation Prompt Standard

Use this standard whenever writing prompts for diagrams, UI screenshots, thesis visuals, architecture visuals, charts, or presentation assets.

The goal is to prevent vague image-generation prompts that produce random decorations, wrong layouts, extra text, bad icons, distorted boxes, inconsistent style, or elements that were never requested.

A good image prompt is not just a description. It is a visual specification.

---

## 1. Core Rule

Every image prompt must define:

1. Purpose
2. Canvas
3. Style
4. Layout
5. Exact elements
6. Exact text
7. Colors
8. Typography
9. Icon rules
10. Spacing and alignment
11. Constraints
12. Negative constraints
13. Output requirements

Never write a prompt like:

> Create a modern diagram showing the system architecture.

That is too vague.

Instead, write a controlled visual brief.

---

## 2. Recommended Format

Use Markdown sections, not a single paragraph.

JSON can be useful when the prompt is consumed by code, but for image generation, Markdown sections are usually easier to maintain and review.

Use this structure:

```md
## Image Prompt: [Short Name]

### Purpose
Explain what this image is supposed to communicate in one sentence.

### Canvas
- Aspect ratio:
- Orientation:
- Background:
- Safe margins:
- Intended use:

### Visual Style
- Overall style:
- Mood:
- Level of detail:
- Rendering style:
- Avoided style:

### Layout
Describe the full composition from left to right or top to bottom.
Specify number of columns, rows, cards, panels, arrows, and groups.

### Required Elements
List every visual element that must appear.
Use exact names.

### Text Labels
Only include the following text, exactly as written:
- "..."
- "..."
- "..."

No other text is allowed.

### Color Palette
Use only these colors:
- Background:
- Card:
- Border:
- Primary:
- Secondary:
- Warning:
- Danger:
- Muted text:

### Typography
- Font style:
- Heading style:
- Label style:
- Number style:
- Text alignment:

### Icons
- Icon style:
- Icon count:
- Icon placement:
- Icon meaning:
- Do not use:

### Arrows and Connections
- Arrow direction:
- Arrow style:
- Arrow color:
- Arrow labels:
- Connection rules:

### Constraints
The image must:
- ...
- ...
- ...

### Negative Constraints
Do not include:
- extra labels
- random decorative shapes
- watermarks
- logos
- stock photo elements
- gradients unless explicitly requested
- duplicated icons
- malformed text
- floating boxes
- irrelevant background objects
- 3D effects unless requested
- realistic people unless requested

### Output Requirements
- Clean final image.
- High resolution.
- No visible prompt text.
- No watermark.
- No border around the full image unless requested.
````

---

## 3. Strong Prompt Template

Use this template for every generated diagram.

```md
## Image Prompt: [DIAGRAM NAME]

Create a polished [diagram / infographic / UI-style visual] for a thesis defense presentation.

### Purpose
The image must communicate: [ONE CLEAR IDEA].

### Canvas
- Aspect ratio: 16:9
- Orientation: landscape
- Background: [pure white / dark #0D1117 / transparent]
- Safe margins: 7% on all sides
- Intended use: PowerPoint thesis defense slide

### Visual Style
- Style: modern academic security research visual
- Mood: precise, controlled, evidence-driven
- Design language: clean rounded cards, thin borders, subtle shadows, structured spacing
- Detail level: medium, clear enough for a projector
- Avoid: decorative clutter, generic SaaS dashboard style, cartoon style, photorealism

### Layout
[Describe the composition exactly.]

Example:
Use a left-to-right flow with 5 main cards arranged horizontally:
1. User Query
2. Retriever
3. Retrieved Metadata
4. Recommender / Reranker
5. Final Recommendation

Place arrows between cards. The arrows must flow left to right. Keep all cards the same height and aligned on the same baseline.

### Required Elements
The image must contain exactly these elements:
- [Element 1]
- [Element 2]
- [Element 3]

No additional major elements.

### Text Labels
Use only these exact text labels:
- "User Query"
- "Retriever"
- "Metadata"
- "Ranker"
- "Recommendation"

Do not add any other text.

### Color Palette
Use only:
- Background: #0D1117
- Card background: #141B2D
- Card border: #1E2A45
- Heading text: #EAEEF5
- Body text: #C9D1E0
- Muted text: #6B7A99
- Baseline blue: #4A9EFF
- Poisoned red: #FF4D4D
- Warning amber: #FFB800
- Violet accent: #6C63FF

### Typography
- Use a clean modern sans-serif font.
- Use monospaced font only for numeric values or metric names.
- Labels must be short and readable.
- No tiny text below 18px equivalent.
- Text must be sharp and correctly spelled.

### Icons
- Use simple modern line icons.
- One icon per card maximum.
- Icons must be consistent in stroke width.
- Icons must not have transparency artifacts.
- Do not use emoji-style icons.
- Do not use realistic 3D icons.

### Arrows and Connections
- Use thin directional arrows.
- Arrow color: #6B7A99 or semantic accent color.
- Arrows must connect card centers cleanly.
- No crossing arrows.
- No diagonal arrows unless explicitly requested.

### Constraints
The image must:
- Preserve the exact layout described above.
- Keep all cards aligned.
- Keep spacing even.
- Make the visual readable on a projector.
- Look like a polished thesis defense visual.
- Use the requested color palette only.

### Negative Constraints
Do not include:
- extra labels
- invented components
- random decorations
- stock photo elements
- people
- laptops
- code screenshots
- watermarks
- logos
- misspelled text
- duplicated icons
- distorted boxes
- stretched cards
- overlapping arrows
- unnecessary gradients
- busy backgrounds

### Output Requirements
- High-resolution 16:9 image.
- Clean final asset ready to insert into a PowerPoint slide.
- No watermark.
- No outer frame unless explicitly requested.
```

---

## 4. JSON-Like Alternative

Use this only if you want machine-readable prompts.

Do not use JSON because it is “meta.”
Use it only because it makes the structure harder to ignore.

```json
{
  "image_type": "thesis_defense_diagram",
  "purpose": "Explain the clean vs poisoned experimental workflow.",
  "canvas": {
    "aspect_ratio": "16:9",
    "orientation": "landscape",
    "background": "#0D1117",
    "safe_margins": "7%"
  },
  "style": {
    "aesthetic": "modern academic security research interface",
    "mood": ["precise", "controlled", "evidence-driven"],
    "detail_level": "medium",
    "avoid": ["cartoon", "photorealistic", "generic SaaS", "decorative clutter"]
  },
  "layout": {
    "structure": "left-to-right workflow",
    "columns": 5,
    "alignment": "all cards same height, same baseline",
    "arrows": "thin directional arrows between cards"
  },
  "required_elements": [
    "Clean Dataset card",
    "Poisoned Dataset card",
    "Retriever card",
    "Ranker card",
    "Metrics card"
  ],
  "exact_text": [
    "Clean Dataset",
    "Poisoned Dataset",
    "Retriever",
    "Ranker",
    "HR / NDCG / MRR / ASR"
  ],
  "colors": {
    "background": "#0D1117",
    "card": "#141B2D",
    "border": "#1E2A45",
    "text_primary": "#EAEEF5",
    "text_secondary": "#C9D1E0",
    "muted": "#6B7A99",
    "baseline": "#4A9EFF",
    "poisoned": "#FF4D4D",
    "warning": "#FFB800",
    "accent": "#6C63FF"
  },
  "typography": {
    "font": "clean modern sans-serif",
    "numbers": "monospaced",
    "minimum_text_size": "18px equivalent",
    "rules": ["sharp text", "correct spelling", "no extra text"]
  },
  "icons": {
    "style": "simple modern line icons",
    "max_per_card": 1,
    "stroke": "consistent",
    "avoid": ["emoji", "3D", "transparent artifacts"]
  },
  "negative_constraints": [
    "no extra labels",
    "no invented components",
    "no watermarks",
    "no logos",
    "no stock photos",
    "no people",
    "no duplicated icons",
    "no distorted boxes",
    "no overlapping arrows"
  ],
  "output": {
    "resolution": "high",
    "ready_for": "PowerPoint slide",
    "outer_frame": false
  }
}
```

---

## 5. Tightening Rules

Apply these rules when rewriting a weak prompt.

### Bad

```md
Make a modern diagram of the architecture.
```

### Good

```md
Create a 16:9 dark thesis-defense architecture diagram showing the RAG Poison Lab system as five aligned rounded cards connected left to right: Dataset, Poisoning Module, Retriever, Ranker, Evaluation Metrics. Use background #0D1117, card background #141B2D, border #1E2A45, heading text #EAEEF5, clean blue #4A9EFF for baseline, poisoned red #FF4D4D for attacked data, amber #FFB800 for deltas. Use one simple line icon per card. Use only the exact labels listed. Do not add extra text, people, logos, watermarks, decorative objects, 3D effects, or unrelated UI elements.
```

---

## 6. Words That Improve Control

Use these words when relevant:

* "exactly"
* "only"
* "preserve"
* "do not add"
* "no extra text"
* "same baseline"
* "aligned"
* "even spacing"
* "consistent stroke width"
* "single visual style"
* "one icon per card"
* "left-to-right flow"
* "top-to-bottom hierarchy"
* "readable on a projector"
* "high contrast"
* "minimal labels"
* "clean final asset"

---

## 7. Words That Cause Bad Results

Avoid vague words unless you define them:

* "cool"
* "beautiful"
* "futuristic"
* "advanced"
* "professional"
* "modern"
* "nice"
* "cyber"
* "make it pop"
* "high tech"
* "dashboard-like"
* "with details"

These are not banned, but they must be anchored by specific visual instructions.

Bad:

```md
Make it futuristic and professional.
```

Good:

```md
Use a dark security-research console style with thin blue borders, muted grid texture, rounded data cards, monospaced numeric labels, and no decorative neon effects.
```

---

## 8. Text Rules

Image models often fail when text is vague or too long.

Always do this:

```md
Use only these exact labels:
- "Baseline"
- "Poisoned"
- "Retriever"
- "Ranker"
- "ASR"
```

Then add:

```md
Do not add any other text.
Do not paraphrase labels.
Do not invent captions.
All text must be correctly spelled and readable.
```

Never ask for long paragraphs inside the image.

---

## 9. Diagram Rules

For diagrams, always specify:

* number of cards
* card titles
* card order
* arrow direction
* arrow count
* grouping
* colors per group
* whether cards are equal size
* whether there are nested cards
* whether there is a title
* whether there is a legend
* whether there are labels on arrows

Example:

```md
Use exactly 3 large vertical cards, arranged left to right.
Each card contains 3 smaller inner cards.
All large cards must have equal width and height.
Place one simple line icon at the top of each large card.
Connect the large cards with two arrows only.
Do not add extra arrows.
Do not add a title.
```

---

## 10. Chart Rules

For charts, specify:

* chart type
* axes
* scale
* legend
* colors
* labels
* number formatting
* whether values are approximate or exact
* whether gridlines appear
* what not to include

Example:

```md
Create a grouped bar chart comparing Baseline vs Poisoned across HR, NDCG, MRR, and ASR.

Rules:
- X-axis labels: "HR", "NDCG", "MRR", "ASR"
- Y-axis from 0.0 to 1.0
- Baseline bars: #4A9EFF
- Poisoned bars: #FF4D4D
- Delta annotations: #FFB800
- Use monospaced numeric labels
- Use faint gridlines only
- No 3D bars
- No pie charts
- No decorative background
```

---

## 11. RAG Poison Lab Diagram Style

For this project, use this style unless the slide explicitly asks for a clean white thesis diagram.

```md
Style profile:
- Aesthetic: Mission Control meets Security Research Paper
- Background: #0D1117
- Card background: #141B2D
- Border: #1E2A45
- Hover/accent border look: #2E3F6A
- Heading text: #EAEEF5
- Body text: #C9D1E0
- Muted text: #6B7A99
- Baseline color: #4A9EFF
- Poisoned color: #FF4D4D
- Delta/warning color: #FFB800
- Active accent: #6C63FF
- Success/stable: #2ECC71
- Targeted promotion: #FF6B35
- Prompt injection: #BF5FFF
- Untargeted degradation: #FFB800
- Numeric values: monospaced font
- Icons: simple modern line icons
- Layout: card-based, aligned, precise
- Avoid: startup SaaS look, cartoon look, generic dashboard look, random neon cyberpunk
```

---

## 12. Codex Rewrite Instruction

Use this instruction when asking Codex to rewrite weak diagram prompts.

```md
Rewrite every image-generation prompt using `image_prompt_standard.md`.

For each prompt:
1. Preserve the original purpose.
2. Convert vague language into strict visual specifications.
3. Add canvas, layout, style, color, typography, icon, text, arrow, and negative constraints.
4. Use the RAG Poison Lab design system unless the prompt explicitly requests a white thesis diagram.
5. For every diagram, define exact card count, label text, arrow direction, icon type, and forbidden elements.
6. Do not generate the image.
7. Only rewrite the prompt.
8. The final prompt must be paste-ready for an image generation model.
9. Avoid long in-image text.
10. Add "Use only these exact labels" whenever text appears in the image.
11. Add "Do not add any other text" to prevent hallucinated labels.
12. Add "No logos, no watermarks, no stock-photo elements, no people, no extra decorative objects."
```

---

## 13. Final Prompt Quality Checklist

Before accepting an image prompt, verify:

* [ ] Does it say exactly what the image is for?
* [ ] Does it specify aspect ratio?
* [ ] Does it specify background?
* [ ] Does it specify layout?
* [ ] Does it list every required element?
* [ ] Does it list exact text labels?
* [ ] Does it forbid extra text?
* [ ] Does it specify colors with hex codes?
* [ ] Does it specify typography?
* [ ] Does it specify icons?
* [ ] Does it specify arrow direction?
* [ ] Does it prevent random decorations?
* [ ] Does it prevent watermarks and logos?
* [ ] Does it prevent duplicated icons and distorted boxes?
* [ ] Is it short enough to be understandable?
* [ ] Is it strict enough that a bad output is clearly wrong?