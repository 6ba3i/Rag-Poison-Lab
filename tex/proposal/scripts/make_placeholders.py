#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class PlaceholderSpec:
    filename: str
    title: str
    explanation: str
    layout: str


FIGURES = [
    PlaceholderSpec(
        filename="placeholder_system_architecture.png",
        title="Figure Placeholder: Rag-Poison-Lab System Architecture",
        explanation=(
            "The final figure should show how the data pipeline, poisoning module, "
            "Elasticsearch indices, API services, and frontend are connected."
        ),
        layout=(
            "Suggested layout: left-to-right blocks for data preparation -> poisoning -> "
            "baseline/attacked indices -> recommendation and trace services -> dashboard and reports."
        ),
    ),
    PlaceholderSpec(
        filename="placeholder_baseline_vs_attacked_workflow.png",
        title="Figure Placeholder: Baseline vs Attacked Workflow",
        explanation=(
            "The final figure should compare two parallel runs with the same user profile and settings, "
            "while only changing retrieval index mode."
        ),
        layout=(
            "Suggested layout: mirrored swimlanes for baseline and attacked paths, with highlighted "
            "differences in retrieved documents, ranking order, and top-K outputs."
        ),
    ),
    PlaceholderSpec(
        filename="placeholder_experiment_pipeline.png",
        title="Figure Placeholder: Experiment and Evaluation Pipeline",
        explanation=(
            "The final figure should show the reproducible evaluation loop: configure -> run -> "
            "measure -> export metrics and traces."
        ),
        layout=(
            "Suggested layout: cyclic pipeline including attack config, indexing checks, eval run modes "
            "(single/batch/full), metric computation, and report artifact generation."
        ),
    ),
]


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        font_path = Path(path)
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    xy: tuple[int, int],
    max_width: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_spacing: int = 6,
) -> int:
    x, y = xy
    words = text.split()
    line: list[str] = []
    for word in words:
        trial = " ".join(line + [word])
        trial_width = draw.textbbox((0, 0), trial, font=font)[2]
        if trial_width <= max_width or not line:
            line.append(word)
            continue
        draw.text((x, y), " ".join(line), font=font, fill=fill)
        y += font.size + line_spacing
        line = [word]
    if line:
        draw.text((x, y), " ".join(line), font=font, fill=fill)
        y += font.size + line_spacing
    return y


def _make_background(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), color=(237, 245, 255))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        ratio = y / max(1, height - 1)
        r = int(230 - 28 * ratio)
        g = int(242 - 35 * ratio)
        b = int(255 - 15 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return image


def _render_placeholder(output_path: Path, spec: PlaceholderSpec) -> None:
    width, height = 1600, 900
    image = _make_background(width, height)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(48)
    body_font = _load_font(30)
    small_font = _load_font(24)

    margin = 80
    panel_top = 120
    panel_bottom = height - 120

    draw.rounded_rectangle(
        [(margin, panel_top), (width - margin, panel_bottom)],
        radius=28,
        fill=(248, 252, 255),
        outline=(45, 103, 196),
        width=5,
    )

    draw.rectangle(
        [(margin, panel_top), (width - margin, panel_top + 78)],
        fill=(45, 103, 196),
    )
    draw.text((margin + 24, panel_top + 16), spec.title, font=body_font, fill=(255, 255, 255))

    y = panel_top + 120
    y = _draw_wrapped_text(
        draw,
        "What this figure should show:",
        xy=(margin + 35, y),
        max_width=width - (2 * margin) - 70,
        font=body_font,
        fill=(18, 59, 128),
    )

    y = _draw_wrapped_text(
        draw,
        spec.explanation,
        xy=(margin + 35, y + 4),
        max_width=width - (2 * margin) - 70,
        font=small_font,
        fill=(36, 61, 95),
    )

    y = _draw_wrapped_text(
        draw,
        "Imagined final layout:",
        xy=(margin + 35, y + 20),
        max_width=width - (2 * margin) - 70,
        font=body_font,
        fill=(18, 59, 128),
    )

    _draw_wrapped_text(
        draw,
        spec.layout,
        xy=(margin + 35, y + 4),
        max_width=width - (2 * margin) - 70,
        font=small_font,
        fill=(36, 61, 95),
    )

    draw.text((margin + 30, panel_bottom - 48), "Draft placeholder generated by scripts/make_placeholders.py", font=small_font, fill=(86, 112, 148))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def main() -> None:
    base = Path(__file__).resolve().parents[1] / "figures"
    for spec in FIGURES:
        _render_placeholder(base / spec.filename, spec)


if __name__ == "__main__":
    main()
