#!/usr/bin/env python3
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


# 5x7 bitmap font (subset needed for labels)
FONT: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def write_png(path: Path, width: int, height: int, rgb: bytearray) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter type 0
        row_start = y * stride
        raw.extend(rgb[row_start: row_start + stride])

    png = bytearray()
    png.extend(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png.extend(chunk(b"IHDR", ihdr))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
    png.extend(chunk(b"IEND", b""))
    path.write_bytes(png)


def make_gradient(width: int, height: int) -> bytearray:
    buf = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 3
            t = x / max(width - 1, 1)
            u = y / max(height - 1, 1)
            r = int(18 + 20 * t)
            g = int(62 + 45 * (1 - u))
            b = int(150 + 70 * t)
            buf[i:i + 3] = bytes((r, g, b))
    return buf


def set_px(buf: bytearray, width: int, height: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    i = (y * width + x) * 3
    buf[i:i + 3] = bytes(color)


def fill_rect(
    buf: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            set_px(buf, width, height, x, y, color)


def draw_border(buf: bytearray, width: int, height: int) -> None:
    border = (195, 223, 255)
    thickness = 10
    fill_rect(buf, width, height, 24, 24, width - 48, thickness, border)
    fill_rect(buf, width, height, 24, height - 24 - thickness, width - 48, thickness, border)
    fill_rect(buf, width, height, 24, 24, thickness, height - 48, border)
    fill_rect(buf, width, height, width - 24 - thickness, 24, thickness, height - 48, border)


def draw_char(
    buf: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    ch: str,
    scale: int,
    color: tuple[int, int, int],
) -> int:
    glyph = FONT.get(ch, FONT[" "])
    glyph_w = len(glyph[0]) * scale
    for y, row in enumerate(glyph):
        for x, bit in enumerate(row):
            if bit != "1":
                continue
            fill_rect(buf, width, height, x0 + x * scale, y0 + y * scale, scale, scale, color)
    return glyph_w


def text_width(text: str, scale: int, spacing: int) -> int:
    if not text:
        return 0
    return sum(len(FONT.get(ch, FONT[" "])[0]) * scale for ch in text) + spacing * (len(text) - 1)


def draw_centered_text(
    buf: bytearray,
    width: int,
    height: int,
    text: str,
    y_center: int,
    scale: int = 6,
    spacing: int = 4,
) -> None:
    label = text.upper()
    w = text_width(label, scale, spacing)
    h = 7 * scale
    x = max((width - w) // 2, 40)
    y = max(y_center - h // 2, 40)
    color = (236, 246, 255)
    shadow = (10, 35, 80)

    cursor = x
    for ch in label:
        gw = len(FONT.get(ch, FONT[" "])[0]) * scale
        draw_char(buf, width, height, cursor + 2, y + 2, ch, scale, shadow)
        draw_char(buf, width, height, cursor, y, ch, scale, color)
        cursor += gw + spacing


def generate_placeholder(path: Path, label: str, subtitle: str) -> None:
    width, height = 1600, 900
    canvas = make_gradient(width, height)
    draw_border(canvas, width, height)

    # subtle central panel
    panel_w, panel_h = 1350, 420
    px = (width - panel_w) // 2
    py = (height - panel_h) // 2
    fill_rect(canvas, width, height, px, py, panel_w, panel_h, (23, 74, 165))
    fill_rect(canvas, width, height, px + 8, py + 8, panel_w - 16, panel_h - 16, (29, 91, 190))

    draw_centered_text(canvas, width, height, label, y_center=height // 2 - 45, scale=10, spacing=6)
    draw_centered_text(canvas, width, height, subtitle, y_center=height // 2 + 95, scale=5, spacing=3)

    write_png(path, width, height, canvas)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    figures = root / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    specs = [
        ("architecture_placeholder.png", "System Architecture", "RAG-POISON-LAB"),
        ("workflow_placeholder.png", "Baseline Vs Poisoned Workflow", "RED-TEAM EVALUATION"),
        ("evaluation_pipeline_placeholder.png", "Evaluation Pipeline", "RETRIEVAL RANKING LLM ANALYSIS"),
    ]

    for filename, label, subtitle in specs:
        generate_placeholder(figures / filename, label=label, subtitle=subtitle)
        print(f"Generated {figures / filename}")


if __name__ == "__main__":
    main()
