from __future__ import annotations

from pathlib import Path
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "thesis_presentation.pptx"
OUTPUT.parent.mkdir(exist_ok=True)

PAGE_BG = RGBColor(0x0D, 0x11, 0x17)
CARD_BG = RGBColor(0x14, 0x1B, 0x2D)
CARD_BORDER = RGBColor(0x1E, 0x2A, 0x45)
HEADING = RGBColor(0xEA, 0xEE, 0xF5)
BODY = RGBColor(0xC9, 0xD1, 0xE0)
MUTED = RGBColor(0x6B, 0x7A, 0x99)
CLEAN = RGBColor(0x4A, 0x9E, 0xFF)
RED = RGBColor(0xFF, 0x4D, 0x4D)
AMBER = RGBColor(0xFF, 0xB8, 0x00)
VIOLET = RGBColor(0x6C, 0x63, 0xFF)
GREEN = RGBColor(0x2E, 0xCC, 0x71)
ORANGE = RGBColor(0xFF, 0x6B, 0x35)
PROMPT = RGBColor(0xBF, 0x5F, 0xFF)
WHITE = RGBColor(255, 255, 255)

W, H = Inches(13.333), Inches(7.5)

def bg(slide):
    r = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, W, H)
    r.fill.solid(); r.fill.fore_color.rgb = PAGE_BG; r.line.color.rgb = PAGE_BG

def add_text(slide, text, x, y, w, h, size=20, color=BODY, bold=False, font="Aptos"):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame; tf.word_wrap = True; tf.clear()
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = text; r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold; r.font.name = font
    return box

def title(slide, text):
    add_text(slide, text, 0.55, 0.25, 11.8, 0.45, 23, HEADING, True)
    line = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.55), Inches(0.78), Inches(12.2), Inches(0.012))
    line.fill.solid(); line.fill.fore_color.rgb = CARD_BORDER; line.line.color.rgb = CARD_BORDER

def footer(slide, n):
    add_text(slide, f"RAG Poison Lab Defense | {n}/13", 10.65, 7.16, 2.25, 0.2, 8, MUTED)

def card(slide, text, x, y, w, h, border=CARD_BORDER, size=17):
    s = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = CARD_BG; s.line.color.rgb = border
    add_text(slide, text, x + 0.18, y + 0.16, w - 0.35, h - 0.25, size, BODY)
    return s

def placeholder(slide, text, y=1.35, h=4.7):
    card(slide, text, 1.05, y, 11.25, h, CARD_BORDER, 19)

def ref_card(slide, label, body, key, x, color):
    card(slide, f"{label}\n\n{body}\n\n{key}", x, 2.0, 3.45, 2.6, color, 14)


def attack_card(slide, name, objective, measure, refs, x, color):
    text = f"{name}\n\nObjective: {objective}\n\nMeasure/effect: {measure}\n\n{refs}"
    card(slide, text, x, 1.65, 3.55, 3.55, color, 12)

def add_diagram(slide, filename):
    path = ROOT / "diagrams" / filename
    slide.shapes.add_picture(str(path), Inches(0.75), Inches(1.08), width=Inches(11.85), height=Inches(6.62))

def badge(slide, text, x, y, color):
    s = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(1.15), Inches(0.38))
    s.fill.solid(); s.fill.fore_color.rgb = CARD_BG; s.line.color.rgb = color
    add_text(slide, text, x+0.18, y+0.06, 0.8, 0.2, 12, color, True, "Consolas")

def build():
    prs = Presentation(); prs.slide_width = W; prs.slide_height = H; blank = prs.slide_layouts[6]
    # 1
    s = prs.slides.add_slide(blank); bg(s)
    add_text(s, "DEFENSE // LOCAL BENCHMARK // TOP-K SECURITY", 0.95, 1.15, 8.5, 0.35, 14, ORANGE, True, "Consolas")
    add_text(s, "RAG Poison Lab", 0.95, 2.15, 8.8, 0.8, 40, HEADING, True)
    add_text(s, "Red-Teaming LLM-Powered Recommendation Systems", 0.98, 3.0, 10.5, 0.5, 22, BODY)
    add_text(s, "Sbaaoui Idriss · Undergraduate Thesis · May 2026 · 华东理工大学", 0.98, 5.35, 10.5, 0.35, 15, MUTED)
    # 2
    s = prs.slides.add_slide(blank); bg(s)
    title(s, "Problem: retrieved metadata becomes model-facing evidence"); footer(s,2); add_diagram(s, "2.jpg")
    # 3
    s=prs.slides.add_slide(blank); bg(s); title(s,"Research Question and Contributions"); footer(s,3); add_diagram(s, "3.jpg")
    # 4
    s=prs.slides.add_slide(blank); bg(s); title(s,"Related Work: three anchors for this defense"); footer(s,4)
    ref_card(s, "Retrieval poisoning", "Adversarial passages can change what downstream systems retrieve and use.", "zhong2023retrievalcorpora", 0.95, CLEAN)
    ref_card(s, "Indirect prompt injection", "External content can behave like instructions once it reaches an LLM context.", "greshake2023indirectpi", 4.95, PROMPT)
    ref_card(s, "RAG + recommender poisoning", "Connects poisoned retrieval with recommendation exposure and ranking effects.", "nazary2025poisonrag", 8.95, ORANGE)
    add_text(s, "Defensive scope: local MovieLens benchmark with paired clean/poisoned indices.", 0.95, 6.1, 10.8, 0.35, 12, MUTED)
    # 5
    s=prs.slides.add_slide(blank); bg(s); title(s,"System Architecture"); footer(s,5); add_diagram(s, "4.jpg")
    # 6
    s=prs.slides.add_slide(blank); bg(s); title(s,"Attack Scenarios"); footer(s,6); add_diagram(s, "5.jpg")
    # 7
    s=prs.slides.add_slide(blank); bg(s); title(s,"What each attack family means in this thesis"); footer(s,7)
    attack_card(s, "Targeted Promotion", "Increase visibility of one target item in top-k.", "ASR and target top-k appearance.", "zhong2023retrievalcorpora; nazary2025poisonrag", 0.75, ORANGE)
    attack_card(s, "Prompt Injection", "Test instruction-like metadata at LLM reranking.", "Scoped to reranking context; no payloads shown.", "greshake2023indirectpi; zhong2023retrievalcorpora", 4.88, PROMPT)
    attack_card(s, "Untargeted Degradation", "Reduce quality overall, not one target.", "Quality deltas: HR, NDCG, MRR.", "zhong2023retrievalcorpora; nazary2025poisonrag", 9.0, AMBER)
    add_text(s, "Defensive framing only: benchmark labels, not operational instructions.", 0.95, 6.15, 10.8, 0.3, 12, MUTED)
    # 8
    s=prs.slides.add_slide(blank); bg(s); title(s,"Experimental Loop and Metrics"); footer(s,8); add_diagram(s, "6.jpg")
    # 9
    s=prs.slides.add_slide(blank); bg(s); title(s,"Main Results: three distinct risk patterns"); footer(s,9); add_diagram(s, "7.jpg")
    # 10
    s=prs.slides.add_slide(blank); bg(s); title(s,"Experiments Page Screenshot"); footer(s,10); add_diagram(s, "8.png")
    # 11
    s=prs.slides.add_slide(blank); bg(s); title(s,"Results Page Screenshot"); footer(s,11); add_diagram(s, "9.png")
    # 12
    s=prs.slides.add_slide(blank); bg(s); title(s,"Security Interpretation, Limits, and Ethics"); footer(s,12); add_diagram(s, "10.jpg")
    # 13
    s=prs.slides.add_slide(blank); bg(s); title(s,"Conclusion"); footer(s,13); add_diagram(s, "11.jpg")
    prs.save(OUTPUT)
    print(f"wrote {OUTPUT}")

if __name__ == "__main__":
    build()
