#!/usr/bin/env python3

import json
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render_metric_group(parts: list[str], x: int, y: int, title: str, before: dict, after: dict) -> None:
    width = 500
    height = 280
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append(f'<text x="{x+18}" y="{y+30}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{title}</text>')

    chart_x = x + 50
    chart_y = y + 70
    chart_h = 140
    chart_w = 400
    for i in range(6):
        gy = chart_y + (chart_h / 5) * i
        value = 1 - (i / 5)
        parts.append(f'<line x1="{chart_x}" y1="{gy}" x2="{chart_x + chart_w}" y2="{gy}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{chart_x - 10}" y="{gy + 4}" text-anchor="end" font-size="10" font-family="Segoe UI, Arial" fill="#486581">{value:.1f}</text>')

    groups = [
        ("Top-1", before["test_metrics"]["top1_accuracy"], after["test_metrics"]["top1_accuracy"]),
        ("Top-3", before["test_metrics"]["top3_accuracy"], after["test_metrics"]["top3_accuracy"]),
    ]
    group_gap = 120
    bar_w = 52
    for idx, (label, base_value, weak_value) in enumerate(groups):
        base_x = chart_x + 45 + idx * group_gap
        for bar_idx, (value, color) in enumerate([(base_value, "#94a3b8"), (weak_value, "#2563eb")]):
            bh = value * chart_h
            bx = base_x + bar_idx * (bar_w + 18)
            by = chart_y + chart_h - bh
            parts.append(f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" rx="5" fill="{color}"/>')
            parts.append(f'<text x="{bx + bar_w/2}" y="{by - 8}" text-anchor="middle" font-size="11" font-family="Segoe UI, Arial" fill="#102a43">{value:.3f}</text>')
        parts.append(f'<text x="{base_x + bar_w + 9}" y="{chart_y + chart_h + 24}" text-anchor="middle" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">{label}</text>')

    parts.append(f'<rect x="{x+290}" y="{y+28}" width="12" height="12" rx="2" fill="#94a3b8"/>')
    parts.append(f'<text x="{x+310}" y="{y+38}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">Baseline</text>')
    parts.append(f'<rect x="{x+380}" y="{y+28}" width="12" height="12" rx="2" fill="#2563eb"/>')
    parts.append(f'<text x="{x+400}" y="{y+38}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">+ 2024 weakness</text>')

    before_loss = before["test_metrics"]["log_loss"]
    after_loss = after["test_metrics"]["log_loss"]
    delta = round(after["test_metrics"]["top1_accuracy"] - before["test_metrics"]["top1_accuracy"], 4)
    parts.append(f'<text x="{x+18}" y="{y+238}" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Log loss: {before_loss:.4f} -> {after_loss:.4f}</text>')
    parts.append(f'<text x="{x+18}" y="{y+258}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">Top-1 delta: {delta:+.4f}</text>')


def main() -> None:
    next_pitch_before = load("data/models/xgb_white_next_pitch_type_first_only_2025.json")
    next_pitch_after = load("data/models/xgb_white_next_pitch_type_first_only_2025_weakness.json")
    next_zone_before = load("data/models/xgb_white_next_zone_first_only_2025.json")
    next_zone_after = load("data/models/xgb_white_next_zone_first_only_2025_weakness.json")

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="650">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="36" font-size="26" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">Impact of 2024 Batter Weakness Prior</text>',
        '<text x="24" y="60" font-size="12" font-family="Segoe UI, Arial" fill="#486581">White first-pitch-to-next-pitch XGBoost comparison before and after weakness-profile features</text>',
    ]

    render_metric_group(parts, 24, 100, "Next Pitch Type", next_pitch_before, next_pitch_after)
    render_metric_group(parts, 536, 100, "Next Zone (3x3+OUT)", next_zone_before, next_zone_after)

    parts.append('<rect x="24" y="420" width="1012" height="170" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append('<text x="42" y="452" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">Reading</text>')
    parts.append('<text x="42" y="482" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">1. 2024 약점 prior는 다음 구종 자체보다 다음 위치 예측에 더 직접적으로 기여했습니다.</text>')
    parts.append('<text x="42" y="507" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">2. 구종 모델은 feature 수가 늘면서 과적합이 커졌고, 위치 모델은 Top-1이 소폭 개선되었습니다.</text>')
    parts.append('<text x="42" y="532" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">3. 즉 약점 정보는 지금 단계에서 “무슨 공”보다 “어디로 공략하나”에 더 가까운 signal로 읽는 것이 자연스럽습니다.</text>')
    parts.append('</svg>')

    Path("examples/weakness_prior_impact.svg").write_text("\n".join(parts), encoding="utf-8")
    print("examples/weakness_prior_impact.svg")


if __name__ == "__main__":
    main()
