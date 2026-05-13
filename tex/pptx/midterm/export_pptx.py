from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "midterm_slides.pptx"
PROPOSAL_FIGURES = ROOT / "figures"
PRIMARY = RGBColor(17, 82, 147)
ACCENT = RGBColor(45, 117, 191)
SOFT = RGBColor(233, 241, 250)
WHITE = RGBColor(255, 255, 255)
BLACK = RGBColor(20, 20, 20)
MUTED = RGBColor(80, 80, 80)


def add_title_bar(slide, title: str) -> None:
    bar = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.8))
    bar.fill.solid()
    bar.fill.fore_color.rgb = PRIMARY
    bar.line.color.rgb = PRIMARY
    box = slide.shapes.add_textbox(Inches(0.35), Inches(0.14), Inches(12.3), Inches(0.45))
    p = box.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = title
    r.font.size = Pt(24)
    r.font.bold = True
    r.font.color.rgb = WHITE


def add_footer(slide, note: str) -> None:
    box = slide.shapes.add_textbox(Inches(0.35), Inches(7.15), Inches(12.2), Inches(0.2))
    p = box.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = note
    r.font.size = Pt(9)
    r.font.color.rgb = MUTED


def add_bullets(slide, bullets, x, y, w, h, font_size=22):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.clear()
    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = bullet
        p.level = 0
        p.bullet = True
        p.font.size = Pt(font_size)
        p.font.color.rgb = BLACK


def add_numbered(slide, items, x, y, w, h, font_size=20):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.clear()
    for i, item in enumerate(items, start=1):
        p = tf.paragraphs[0] if i == 1 else tf.add_paragraph()
        p.text = f"{i}. {item}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = BLACK


def add_panel(slide, title, x, y, w, h):
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = SOFT
    shape.line.color.rgb = ACCENT
    title_box = slide.shapes.add_textbox(x + Inches(0.15), y + Inches(0.08), w - Inches(0.3), Inches(0.25))
    p = title_box.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = title
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = PRIMARY
    return shape


def add_panel_bullets(slide, title, bullets, x, y, w, h, font_size=16):
    add_panel(slide, title, x, y, w, h)
    box = slide.shapes.add_textbox(x + Inches(0.18), y + Inches(0.42), w - Inches(0.36), h - Inches(0.5))
    tf = box.text_frame
    tf.word_wrap = True
    tf.clear()
    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = bullet
        p.bullet = True
        p.font.size = Pt(font_size)
        p.font.color.rgb = BLACK


def add_picture_fit(slide, image_path: Path, x, y, w, h):
    slide.shapes.add_picture(str(image_path), x, y, w, h)


def build() -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # Slide 1
    slide = prs.slides.add_slide(blank)
    bg = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = PRIMARY
    bg.line.color.rgb = PRIMARY
    box = slide.shapes.add_textbox(Inches(0.75), Inches(1.15), Inches(11.8), Inches(2.2))
    tf = box.text_frame
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Red-Teaming Large Language Model-Powered\nRecommendation Systems"
    r.font.size = Pt(28)
    r.font.bold = True
    r.font.color.rgb = WHITE
    p2 = tf.add_paragraph()
    p2.text = "Midterm Presentation: RAG Poison Lab Framework, Attack Workflow, and Experiment Pipeline"
    p2.font.size = Pt(18)
    p2.font.color.rgb = WHITE
    meta = slide.shapes.add_textbox(Inches(0.8), Inches(4.8), Inches(8.5), Inches(1.0))
    mt = meta.text_frame
    for text, size in [
        ("Sbaaoui Idriss  |  Student ID: 22060004", 18),
        ("Computer Science, 华东理工大学", 16),
        ("Supervisor: 张恒润", 16),
    ]:
        p = mt.paragraphs[0] if len(mt.paragraphs) == 1 and not mt.paragraphs[0].text else mt.add_paragraph()
        p.text = text
        p.font.size = Pt(size)
        p.font.color.rgb = WHITE

    # Slide 2
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Why this project exists")
    add_bullets(slide, [
        "Modern recommendation systems increasingly combine retrieval, ranking, and LLM-based reasoning.",
        "If indexed content is poisoned, the final recommendation output can change without retraining the model.",
        "RAGPoison is a controllable local lab for tracing that effect from data preparation to final top-K output.",
        "The project goal is practical: measure how poisoning changes retrieval evidence, ranking, and user-visible recommendations.",
    ], Inches(0.65), Inches(1.3), Inches(12.0), Inches(4.8), font_size=22)
    add_footer(slide, "Repo sources: README.md, api/app/services/recs_service.py, api/app/services/trace_service.py")

    # Slide 3
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "RAG Poison Lab framework overview")
    add_panel_bullets(slide, "Core workflow", [
        "Prepare MovieLens 100K data",
        "Export baseline bulk and poisoned bulk",
        "Index movies and movies_poisoned",
        "Run baseline vs attacked evaluation",
        "Save metrics, traces, and reports",
    ], Inches(0.55), Inches(1.1), Inches(6.0), Inches(5.2), font_size=17)
    add_panel_bullets(slide, "Main subsystems", [
        "FastAPI backend",
        "Poisoning / attack builder",
        "Elasticsearch retrieval layer",
        "Evaluation and reporting",
        "React demo frontend",
    ], Inches(6.75), Inches(1.1), Inches(5.95), Inches(4.1), font_size=17)
    add_footer(slide, "Repo sources: README.md, api/app/services/orchestration_service.py, graphify-out/GRAPH_REPORT.md")

    # Slide 4
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Architecture and tools")
    add_picture_fit(slide, PROPOSAL_FIGURES / "architecture.png", Inches(0.45), Inches(1.05), Inches(12.4), Inches(5.6))
    add_footer(slide, "Tools in current repo: FastAPI, React/Vite, Elasticsearch, Kibana, Docker Compose, uv, local/cloud LLM providers")

    # Slide 5
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Dataset and indexing pipeline")
    add_panel_bullets(slide, "Pipeline", [
        "MovieLens 100K -> movies / ratings / temporal splits / user profiles",
        "Preprocess writes movies.parquet, ratings.parquet, splits.parquet, user_profiles.parquet",
        "Bulk export produces es_bulk_movies.jsonl and es_bulk_poisoned_movies.jsonl",
        "Indexing resolves mappings, validates bulk, and swaps aliases",
    ], Inches(0.55), Inches(1.1), Inches(7.0), Inches(4.9), font_size=17)
    add_panel_bullets(slide, "Index surfaces", [
        "movies",
        "movies_poisoned",
        "BM25 lexical mapping",
        "dense / hybrid retrieval support",
    ], Inches(7.85), Inches(1.55), Inches(4.85), Inches(3.1), font_size=18)
    add_footer(slide, "Repo sources: api/app/data/preprocess.py, api/app/data/paths.py, api/app/services/indexing_service.py")

    # Slide 6
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Clean vs poisoned recommendation workflow")
    add_picture_fit(slide, PROPOSAL_FIGURES / "baseline_vs_attacked_workflow.png", Inches(0.35), Inches(1.05), Inches(12.65), Inches(5.7))
    add_footer(slide, "Same user context and top-K target; different retrieval corpus: clean index vs poisoned index")

    # Slide 7
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Attack types and experiment workflow")
    add_panel_bullets(slide, "Implemented / configured attacks", [
        "targeted_promotion",
        "prompt_injection",
        "untargeted_degradation",
    ], Inches(0.55), Inches(1.1), Inches(5.8), Inches(2.25), font_size=19)
    add_panel_bullets(slide, "Attack controls", [
        "poison fraction",
        "target movie id",
        "payload text",
        "keyword burst / aggressive boost",
        "target fields: title, genres, synopsis",
    ], Inches(0.55), Inches(3.55), Inches(5.8), Inches(2.45), font_size=16)
    add_panel_bullets(slide, "Experiment execution", [
        "set attack_config.json",
        "prepare data",
        "build poisoned bulk",
        "index baseline + attacked corpora",
        "run single / batch / full eval",
        "generate metrics.json, attack_trace.json, summary.md",
    ], Inches(6.7), Inches(1.1), Inches(6.0), Inches(4.9), font_size=17)
    add_footer(slide, "Repo sources: common/schemas/attack_config.py, agent/attacks/, tools/run_experiment_single_demo.sh")

    # Slide 8
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Metrics and evaluation logic")
    rows = [
        ("HR@K", "whether at least one relevant movie appears in the final top-K"),
        ("NDCG@K", "recommendation quality with position-aware gain"),
        ("MRR@K", "first-hit quality in the ranked list"),
        ("ASR@K", "whether the configured target movie appears in the final top-K"),
        ("Target retrieval rank / presence", "whether the target enters retrieval and how far it moves before final ranking"),
        ("Trace + fallback metadata", "whether reranking, strict retrieval, or fallback behavior affected interpretation"),
        ("Latency", "not yet a standard exported run metric in the current artifact set"),
    ]
    table_x = Inches(0.65); table_y = Inches(1.25)
    left_w = Inches(3.2); right_w = Inches(8.8); row_h = Inches(0.72)
    for i, (left, right) in enumerate(rows):
        y = table_y + row_h * i
        for x, w, text, fill in [
            (table_x, left_w, left, SOFT),
            (table_x + left_w, right_w, right, RGBColor(248, 250, 252)),
        ]:
            rect = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, x, y, w, row_h)
            rect.fill.solid(); rect.fill.fore_color.rgb = fill; rect.line.color.rgb = ACCENT
            box = slide.shapes.add_textbox(x + Inches(0.08), y + Inches(0.05), w - Inches(0.16), row_h - Inches(0.1))
            p = box.text_frame.paragraphs[0]
            p.text = text
            p.font.size = Pt(14 if x != table_x else 15)
            p.font.bold = x == table_x
            p.font.color.rgb = BLACK
    add_footer(slide, "Repo sources: api/app/eval/metrics.py, api/app/eval/runner.py, data/results/runs/*/metrics.json")

    # Slide 9
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Frontend demo role and live walkthrough")
    add_panel_bullets(slide, "What the frontend is for", [
        "inspect settings and attack configuration",
        "run experiments from the web UI",
        "stream live orchestration logs",
        "compare run outputs in a presentation-friendly view",
        "inspect traces and recommendation diffs",
    ], Inches(0.55), Inches(1.15), Inches(5.95), Inches(4.9), font_size=17)
    add_panel_bullets(slide, "Tonight's demo flow", [
        "show Settings / attack configuration",
        "launch a single-user experiment",
        "follow SSE log stream in Experiments",
        "open Results and the run summary",
        "inspect trace / recommendation comparison",
    ], Inches(6.8), Inches(1.15), Inches(5.95), Inches(4.9), font_size=17)
    add_footer(slide, "Recommended live config: deterministic ranking + lexical retrieval + targeted promotion")

    # Slide 10
    slide = prs.slides.add_slide(blank)
    add_title_bar(slide, "Current status, remaining work, and results placeholder")
    add_panel_bullets(slide, "Current implementation status", [
        "data preparation pipeline implemented",
        "poisoning and index build workflow implemented",
        "baseline / attacked evaluation implemented",
        "metrics, traces, and reports implemented",
        "frontend demo surfaces implemented",
    ], Inches(0.55), Inches(1.1), Inches(5.95), Inches(4.6), font_size=16)
    add_panel_bullets(slide, "What remains", [
        "finalize experiment matrix and thesis-grade analysis",
        "stabilize provider-dependent rerank demos",
        "decide final result tables and figures",
        "add final conclusion only after experiment lock",
    ], Inches(6.8), Inches(1.1), Inches(5.95), Inches(4.0), font_size=16)
    placeholder = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(6.05), Inches(11.3), Inches(0.72))
    placeholder.fill.solid(); placeholder.fill.fore_color.rgb = RGBColor(252, 241, 224); placeholder.line.color.rgb = RGBColor(209, 122, 34)
    tb = slide.shapes.add_textbox(Inches(1.2), Inches(6.2), Inches(10.9), Inches(0.35))
    p = tb.text_frame.paragraphs[0]
    p.text = "Results placeholder: keep final quantitative conclusions out of the midterm until the experiment set is finalized."
    p.font.size = Pt(16); p.font.bold = True; p.font.color.rgb = RGBColor(120, 70, 20)
    add_footer(slide, "Status sources: docs/repo_health_audit.md and docs/best_demo_configs.md")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    build()
