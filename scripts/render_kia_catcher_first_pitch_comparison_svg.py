#!/usr/bin/env python3

import csv
from collections import Counter
from pathlib import Path


WIDTH = 1600
HEIGHT = 1040
PANEL_W = 700
PANEL_H = 360
LEFTS = [70, 830]
TOPS = [160, 560]

PITCH_COLORS = {
    "직구": "#d94f45",
    "투심": "#d98b2b",
    "체인지업": "#2d9c6c",
    "슬라이더": "#2f6fd6",
    "커터": "#7b61c7",
    "스위퍼": "#1ea7b6",
    "커브": "#8c6239",
    "포크": "#c95ca6",
    "UNKNOWN": "#9aa3ad",
}


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct_rows(counter: Counter) -> list[tuple[str, int, float]]:
    total = sum(counter.values())
    rows = []
    for pitch_type, count in counter.most_common():
        rows.append((pitch_type, count, (count / total * 100) if total else 0.0))
    return rows


def build_distributions() -> dict[str, list[tuple[str, int, float]]]:
    all_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\ranges\2025-03-01_2025-10-31\pitches_2025-03-01_2025-10-31.csv")
    naile_dir = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile")
    naile_path = next(naile_dir.glob("*_state.csv"))

    all_rows = read_rows(all_path)
    kia_first = [
        row for row in all_rows
        if row.get("pitch_num") == "1" and ((row.get("home_team_code") == "HT") or (row.get("away_team_code") == "HT"))
    ]

    naile_rows = read_rows(naile_path)
    naile_first = [row for row in naile_rows if row.get("pitch_num") == "1"]

    scopes = {
        "KIA 전체 + 김태군": [row for row in kia_first if row.get("catcher_code") == "78122"],
        "KIA 전체 + 한준수": [row for row in kia_first if row.get("catcher_code") == "68646"],
        "네일 + 김태군": [row for row in naile_first if row.get("catcher_code") == "78122"],
        "네일 + 한준수": [row for row in naile_first if row.get("catcher_code") == "68646"],
    }

    return {
        name: pct_rows(Counter(row.get("pitch_type") or "UNKNOWN" for row in rows))
        for name, rows in scopes.items()
    }


def draw_panel(title: str, rows: list[tuple[str, int, float]], x: int, y: int) -> str:
    panel = [
        f'<rect x="{x}" y="{y}" width="{PANEL_W}" height="{PANEL_H}" rx="24" fill="#fffdf9" stroke="#d8ccb5" stroke-width="2"/>',
        f'<text x="{x + 24}" y="{y + 42}" font-size="28" font-weight="700" fill="#2d2418">{title}</text>',
    ]
    total = sum(count for _, count, _ in rows)
    panel.append(f'<text x="{x + 24}" y="{y + 72}" font-size="17" fill="#6a5a45">초구 표본 {total}개</text>')

    bar_x = x + 24
    bar_y = y + 100
    bar_h = 24
    gap = 12
    max_pct = max((pct for _, _, pct in rows), default=1.0)
    scale = 450 / max_pct if max_pct else 1.0

    for idx, (pitch_type, count, pct) in enumerate(rows[:8]):
        cy = bar_y + idx * (bar_h + gap)
        color = PITCH_COLORS.get(pitch_type, PITCH_COLORS["UNKNOWN"])
        width = pct * scale
        panel.append(f'<text x="{bar_x}" y="{cy + 18}" font-size="17" fill="#3d3428">{pitch_type}</text>')
        panel.append(f'<rect x="{bar_x + 120}" y="{cy}" width="460" height="{bar_h}" rx="10" fill="#efe7d7"/>')
        panel.append(f'<rect x="{bar_x + 120}" y="{cy}" width="{width:.1f}" height="{bar_h}" rx="10" fill="{color}"/>')
        panel.append(f'<text x="{bar_x + 592}" y="{cy + 18}" font-size="16" fill="#3d3428">{pct:.1f}% ({count})</text>')
    return "\n".join(panel)


def render_svg(distributions: dict[str, list[tuple[str, int, float]]]) -> str:
    order = [
        "KIA 전체 + 김태군",
        "KIA 전체 + 한준수",
        "네일 + 김태군",
        "네일 + 한준수",
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f5f1e8"/>',
        '<rect x="28" y="28" width="1544" height="984" rx="30" fill="#fcfaf5" stroke="#d4c7ad" stroke-width="2"/>',
        '<text x="70" y="92" font-size="36" font-weight="700" fill="#2d2418">KIA 포수별 초구 구종 분포 비교</text>',
        '<text x="70" y="128" font-size="19" fill="#665844">2025 KIA 전체와 2025 네일 조합만 따로 분리해, 김태군과 한준수의 초구 배합을 비교했습니다.</text>',
    ]

    for idx, title in enumerate(order):
        x = LEFTS[idx % 2]
        y = TOPS[idx // 2]
        parts.append(draw_panel(title, distributions[title], x, y))

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    output_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\kia_catcher_first_pitch_comparison_2025.svg")
    distributions = build_distributions()
    svg = render_svg(distributions)
    output_path.write_text(svg, encoding="utf-8")
    print(f"output_svg: {output_path}")


if __name__ == "__main__":
    main()
