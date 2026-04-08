#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def render_panel(parts: list[str], x0: int, y0: int, width: int, height: int, title: str, stages: list[dict]) -> None:
    parts.append(f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="12" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append(f'<text x="{x0+18}" y="{y0+28}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{title}</text>')
    parts.append(f'<text x="{x0+18}" y="{y0+46}" font-size="11" font-family="Segoe UI, Arial" fill="#486581">Test Top-1 / Top-3 by cumulative feature stage</text>')

    chart_x = x0 + 54
    chart_y = y0 + 70
    chart_w = width - 80
    chart_h = height - 100

    for i in range(6):
        y = chart_y + (chart_h / 5) * i
        value = 1 - (i / 5)
        parts.append(f'<line x1="{chart_x}" y1="{y}" x2="{chart_x+chart_w}" y2="{y}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{chart_x-8}" y="{y+4}" text-anchor="end" font-size="10" font-family="Segoe UI, Arial" fill="#486581">{value:.1f}</text>')

    n = len(stages)
    group_w = chart_w / max(n, 1)
    bar_w = max(12, min(22, (group_w - 20) / 2))

    for i, stage in enumerate(stages):
        base_x = chart_x + i * group_w + (group_w - (bar_w * 2 + 8)) / 2
        t1 = stage["test"]["top1_accuracy"]
        t3 = stage["test"]["top3_accuracy"]
        h1 = t1 * chart_h
        h3 = t3 * chart_h
        parts.append(f'<rect x="{base_x}" y="{chart_y + chart_h - h1}" width="{bar_w}" height="{h1}" rx="3" fill="#d1495b"/>')
        parts.append(f'<rect x="{base_x + bar_w + 8}" y="{chart_y + chart_h - h3}" width="{bar_w}" height="{h3}" rx="3" fill="#2d6a4f"/>')
        parts.append(f'<text x="{base_x + bar_w/2}" y="{chart_y + chart_h - h1 - 5}" text-anchor="middle" font-size="9" font-family="Segoe UI, Arial" fill="#7f1d1d">{t1:.3f}</text>')
        parts.append(f'<text x="{base_x + bar_w + 8 + bar_w/2}" y="{chart_y + chart_h - h3 - 5}" text-anchor="middle" font-size="9" font-family="Segoe UI, Arial" fill="#14532d">{t3:.3f}</text>')
        label = stage["label"]
        parts.append(f'<text x="{base_x + bar_w + 4}" y="{y0 + height - 12}" text-anchor="middle" font-size="9" font-family="Segoe UI, Arial" fill="#102a43">{label}</text>')


def main() -> None:
    parser = argparse.ArgumentParser(description="Render SVG summary for experiment comparison.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-svg", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.input_json).read_text(encoding="utf-8"))

    width = 1200
    height = 860
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="34" font-size="24" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">2025 Pitch Baseline Comparison</text>',
        '<text x="24" y="56" font-size="12" font-family="Segoe UI, Arial" fill="#486581">White overall, White second-pitch, and SSG primary catcher receiving baselines</text>',
        '<rect x="930" y="22" width="12" height="12" rx="2" fill="#d1495b"/>',
        '<text x="948" y="32" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">Top-1</text>',
        '<rect x="1000" y="22" width="12" height="12" rx="2" fill="#2d6a4f"/>',
        '<text x="1018" y="32" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">Top-3</text>',
    ]

    render_panel(parts, 24, 80, 560, 350, "White Overall", report["white_overall"])
    render_panel(parts, 612, 80, 560, 350, "White Second Pitch Only", report["white_second_pitch_only"])
    render_panel(parts, 24, 460, 560, 350, "Jo Hyung-woo Overall", report["jo_overall"])
    render_panel(parts, 612, 460, 560, 350, "Lee Ji-young Overall", report["lee_overall"])
    parts.append("</svg>")

    Path(args.output_svg).write_text("\n".join(parts), encoding="utf-8")
    print(args.output_svg)


if __name__ == "__main__":
    main()
