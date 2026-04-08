#!/usr/bin/env python3

import json
from pathlib import Path


BG = "#f8fafc"
PANEL = "#ffffff"
STROKE = "#d9e2ec"
TEXT = "#102a43"
MUTED = "#486581"
TOP1 = "#d1495b"
TOP3 = "#2d6a4f"
BAR = "#2563eb"


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metric_panel(parts: list[str], x: int, y: int, title: str, report: dict, subtitle: str) -> None:
    width = 360
    height = 220
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="{PANEL}" stroke="{STROKE}"/>')
    parts.append(f'<text x="{x+18}" y="{y+30}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="{TEXT}">{title}</text>')
    parts.append(f'<text x="{x+18}" y="{y+49}" font-size="11" font-family="Segoe UI, Arial" fill="{MUTED}">{subtitle}</text>')

    test_metrics = report["test_metrics"]
    values = [
        ("Top-1", test_metrics["top1_accuracy"], TOP1),
        ("Top-3", test_metrics.get("top3_accuracy", 0.0), TOP3),
    ]
    chart_x = x + 28
    chart_y = y + 90
    chart_h = 96
    bar_w = 78
    gap = 42

    for i in range(6):
        gy = chart_y + (chart_h / 5) * i
        value = 1 - (i / 5)
        parts.append(f'<line x1="{chart_x-8}" y1="{gy}" x2="{x+width-18}" y2="{gy}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{chart_x-14}" y="{gy+4}" text-anchor="end" font-size="10" font-family="Segoe UI, Arial" fill="{MUTED}">{value:.1f}</text>')

    for idx, (label, value, color) in enumerate(values):
        bx = chart_x + idx * (bar_w + gap)
        bh = max(0.0, min(1.0, value)) * chart_h
        by = chart_y + chart_h - bh
        parts.append(f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" rx="5" fill="{color}"/>')
        parts.append(f'<text x="{bx + bar_w/2}" y="{by - 8}" text-anchor="middle" font-size="14" font-family="Segoe UI, Arial" font-weight="700" fill="{TEXT}">{value:.3f}</text>')
        parts.append(f'<text x="{bx + bar_w/2}" y="{chart_y + chart_h + 22}" text-anchor="middle" font-size="12" font-family="Segoe UI, Arial" fill="{TEXT}">{label}</text>')

    parts.append(f'<text x="{x+232}" y="{y+104}" font-size="12" font-family="Segoe UI, Arial" fill="{MUTED}">Test rows</text>')
    parts.append(f'<text x="{x+232}" y="{y+123}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="{TEXT}">{test_metrics["rows"]}</text>')
    parts.append(f'<text x="{x+232}" y="{y+154}" font-size="12" font-family="Segoe UI, Arial" fill="{MUTED}">Log loss</text>')
    parts.append(f'<text x="{x+232}" y="{y+173}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="{TEXT}">{test_metrics["log_loss"]:.3f}</text>')


def importance_panel(parts: list[str], x: int, y: int, title: str, report: dict) -> None:
    width = 744
    height = 300
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="{PANEL}" stroke="{STROKE}"/>')
    parts.append(f'<text x="{x+18}" y="{y+30}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="{TEXT}">{title}</text>')
    parts.append(f'<text x="{x+18}" y="{y+49}" font-size="11" font-family="Segoe UI, Arial" fill="{MUTED}">Gain-based feature importance from the XGBoost test setup</text>')

    top_items = report["feature_importance_gain"][:6]
    max_gain = max((item["gain"] for item in top_items), default=1.0)
    chart_x = x + 190
    chart_y = y + 82
    chart_w = width - 220
    row_h = 32

    for idx, item in enumerate(top_items):
        iy = chart_y + idx * row_h
        bar_w = (item["gain"] / max_gain) * chart_w
        parts.append(f'<text x="{x+18}" y="{iy+18}" font-size="12" font-family="Segoe UI, Arial" fill="{TEXT}">{item["feature"]}</text>')
        parts.append(f'<rect x="{chart_x}" y="{iy+4}" width="{bar_w}" height="16" rx="4" fill="{BAR}"/>')
        parts.append(f'<text x="{chart_x + bar_w + 8}" y="{iy+18}" font-size="11" font-family="Segoe UI, Arial" fill="{MUTED}">{item["gain"]:.3f}</text>')


def main() -> None:
    overall = load("data/models/xgb_white_pitch_type_2025.json")
    next_type = load("data/models/xgb_white_next_pitch_type_first_only_2025.json")
    next_zone = load("data/models/xgb_white_next_zone_first_only_2025.json")
    combo = load("data/models/xgb_white_next_pitch_zone_combo_first_only_2025.json")

    width = 1180
    height = 860
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        f'<text x="24" y="36" font-size="28" font-family="Segoe UI, Arial" font-weight="700" fill="{TEXT}">White XGBoost Prediction Snapshot</text>',
        f'<text x="24" y="60" font-size="13" font-family="Segoe UI, Arial" fill="{MUTED}">2025 White pitch model and first-pitch-to-next-pitch prediction experiments</text>',
        f'<text x="24" y="82" font-size="12" font-family="Segoe UI, Arial" fill="{MUTED}">Input context: count, runner state, score diff, batter stance, live season BA bucket, catcher, and previous pitch/zone context</text>',
    ]

    metric_panel(parts, 24, 118, "Pitch Type", overall, "White full-pitch multiclass")
    metric_panel(parts, 408, 118, "Next Pitch Type", next_type, "After the first pitch in a plate appearance")
    metric_panel(parts, 792, 118, "Next Zone (3x3+OUT)", next_zone, "9-zone location target")
    metric_panel(parts, 24, 370, "Next Pitch x Zone", combo, "Joint combo target")
    importance_panel(parts, 408, 370, "Key Drivers: White Next Pitch Type", next_type)
    importance_panel(parts, 24, 690, "Key Drivers: White Pitch Type", overall)

    parts.append("</svg>")
    Path("examples/xgb_white_prediction_snapshot.svg").write_text("\n".join(parts), encoding="utf-8")
    print("examples/xgb_white_prediction_snapshot.svg")


if __name__ == "__main__":
    main()
