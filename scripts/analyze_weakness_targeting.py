#!/usr/bin/env python3

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def render_svg(path: Path, summary: dict) -> None:
    width = 900
    height = 460
    left = summary["side_targeting"]
    groups = [group for group in left if group["weak_side"] in {"INSIDE", "OUTSIDE"}]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="34" font-size="24" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">White Weakness Targeting Snapshot</text>',
        '<text x="24" y="56" font-size="12" font-family="Segoe UI, Arial" fill="#486581">How often White targeted a batter&apos;s 2024 weak side on the current pitch and the next pitch</text>',
    ]

    chart_x = 120
    chart_y = 100
    chart_h = 250
    chart_w = 700
    for i in range(6):
        y = chart_y + (chart_h / 5) * i
        value = 100 - (i * 20)
        parts.append(f'<line x1="{chart_x}" y1="{y}" x2="{chart_x + chart_w}" y2="{y}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{chart_x-10}" y="{y+4}" text-anchor="end" font-size="10" font-family="Segoe UI, Arial" fill="#486581">{value}%</text>')

    group_gap = 120
    bar_gap = 18
    bar_w = 70
    colors = ["#2563eb", "#f97316"]
    labels = ["Current pitch", "Next pitch"]

    for idx, group in enumerate(groups):
        base_x = chart_x + 80 + idx * group_gap
        values = [group["current_match_pct"], group["next_match_pct"]]
        for bar_idx, value in enumerate(values):
            bh = (value / 100) * chart_h
            x = base_x + bar_idx * (bar_w + bar_gap)
            y = chart_y + chart_h - bh
            parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="5" fill="{colors[bar_idx]}"/>')
            parts.append(f'<text x="{x + bar_w/2}" y="{y - 8}" text-anchor="middle" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">{value:.1f}%</text>')
        parts.append(f'<text x="{base_x + bar_w + bar_gap/2}" y="{chart_y + chart_h + 26}" text-anchor="middle" font-size="13" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{group["weak_side"]}-weak</text>')
        parts.append(f'<text x="{base_x + bar_w + bar_gap/2}" y="{chart_y + chart_h + 45}" text-anchor="middle" font-size="11" font-family="Segoe UI, Arial" fill="#486581">n={group["rows"]}</text>')

    legend_x = 620
    for idx, label in enumerate(labels):
        parts.append(f'<rect x="{legend_x}" y="{94 + idx * 22}" width="12" height="12" rx="2" fill="{colors[idx]}"/>')
        parts.append(f'<text x="{legend_x + 20}" y="{104 + idx * 22}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">{label}</text>')

    insight = summary["headline"]
    parts.append(f'<text x="24" y="398" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">{insight}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze whether White targets 2024 batter weakness directions.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-svg", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    side_stats = defaultdict(lambda: {"rows": 0, "current": 0, "next": 0})

    for row in rows:
        weak_side = row.get("weak_side_2024") or "UNKNOWN"
        if weak_side not in {"INSIDE", "OUTSIDE", "MIDDLE"}:
            continue
        side_stats[weak_side]["rows"] += 1
        side_stats[weak_side]["current"] += 1 if row.get("current_pitch_targets_weak_side_2024") == "1" else 0
        side_stats[weak_side]["next"] += 1 if row.get("next_pitch_targets_weak_side_2024") == "1" else 0

    side_targeting = []
    for weak_side, stats in sorted(side_stats.items()):
        side_targeting.append(
            {
                "weak_side": weak_side,
                "rows": stats["rows"],
                "current_match_pct": pct(stats["current"], stats["rows"]),
                "next_match_pct": pct(stats["next"], stats["rows"]),
            }
        )

    inside = next((row for row in side_targeting if row["weak_side"] == "INSIDE"), None)
    outside = next((row for row in side_targeting if row["weak_side"] == "OUTSIDE"), None)
    headline = "약점 방향 공략 경향을 계산할 표본이 부족합니다."
    if inside and outside:
        headline = (
            f"INSIDE-weak 타자에게는 다음 공이 약한 방향으로 가는 비율이 {inside['next_match_pct']}%, "
            f"OUTSIDE-weak 타자에게는 {outside['next_match_pct']}%였습니다."
        )

    summary = {
        "input_csv": args.input_csv,
        "rows": len(rows),
        "side_targeting": side_targeting,
        "headline": headline,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    render_svg(Path(args.output_svg), summary)
    print(output_json)
    print(args.output_svg)


if __name__ == "__main__":
    main()
