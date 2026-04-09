#!/usr/bin/env python3

import csv
from pathlib import Path


WIDTH = 1600
HEIGHT = 1100
PANEL_W = 700
PANEL_H = 420
LEFTS = [70, 830]
TOPS = [170, 620]

ZONE_LEFT = -0.708
ZONE_RIGHT = 0.708
ZONE_TOP = 3.5
ZONE_BOTTOM = 1.5

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


def to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def scale_x(x: float, panel_x: int) -> float:
    plot_x = panel_x + 30
    plot_w = 520
    min_x = -1.75
    max_x = 1.75
    ratio = (x - min_x) / (max_x - min_x)
    return plot_x + max(0.0, min(1.0, ratio)) * plot_w


def scale_y(z: float, panel_y: int) -> float:
    plot_y = panel_y + 70
    plot_h = 300
    min_z = 0.8
    max_z = 4.6
    ratio = (z - min_z) / (max_z - min_z)
    return plot_y + plot_h - max(0.0, min(1.0, ratio)) * plot_h


def draw_zone(panel_x: int, panel_y: int) -> list[str]:
    plot_x = panel_x + 30
    plot_y = panel_y + 70
    plot_w = 520
    plot_h = 300
    items = [
        f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" rx="18" fill="#fffdf8" stroke="#d8ccb5" stroke-width="1.5"/>'
    ]

    zone_x1 = scale_x(ZONE_LEFT, panel_x)
    zone_x2 = scale_x(ZONE_RIGHT, panel_x)
    zone_y1 = scale_y(ZONE_TOP, panel_y)
    zone_y2 = scale_y(ZONE_BOTTOM, panel_y)
    zone_w = zone_x2 - zone_x1
    zone_h = zone_y2 - zone_y1

    items.append(f'<rect x="{zone_x1:.1f}" y="{zone_y1:.1f}" width="{zone_w:.1f}" height="{zone_h:.1f}" fill="#fff5d6" stroke="#8c7b5f" stroke-width="2"/>')
    for frac in (1/3, 2/3):
        x = zone_x1 + zone_w * frac
        y = zone_y1 + zone_h * frac
        items.append(f'<line x1="{x:.1f}" y1="{zone_y1:.1f}" x2="{x:.1f}" y2="{zone_y2:.1f}" stroke="#baa98a" stroke-width="1.1"/>')
        items.append(f'<line x1="{zone_x1:.1f}" y1="{y:.1f}" x2="{zone_x2:.1f}" y2="{y:.1f}" stroke="#baa98a" stroke-width="1.1"/>')

    for x in [-1.5, -0.75, 0.0, 0.75, 1.5]:
        sx = scale_x(x, panel_x)
        items.append(f'<line x1="{sx:.1f}" y1="{plot_y}" x2="{sx:.1f}" y2="{plot_y + plot_h}" stroke="#eee6d7" stroke-width="1"/>')
    for z in [1.0, 2.0, 3.0, 4.0]:
        sy = scale_y(z, panel_y)
        items.append(f'<line x1="{plot_x}" y1="{sy:.1f}" x2="{plot_x + plot_w}" y2="{sy:.1f}" stroke="#eee6d7" stroke-width="1"/>')
    return items


def draw_points(rows: list[dict], panel_x: int, panel_y: int) -> tuple[list[str], int]:
    items = []
    plotted = 0
    for row in rows:
        x = to_float(row.get("cross_plate_x"))
        z = to_float(row.get("plate_z"))
        if x is None or z is None:
            continue
        pitch_type = row.get("pitch_type") or "UNKNOWN"
        color = PITCH_COLORS.get(pitch_type, PITCH_COLORS["UNKNOWN"])
        cx = scale_x(x, panel_x)
        cy = scale_y(z, panel_y)
        items.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.8" fill="{color}" fill-opacity="0.55" stroke="white" stroke-width="0.7"/>')
        plotted += 1
    return items, plotted


def build_groups() -> dict[str, list[dict]]:
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

    return {
        "KIA 전체 + 김태군": [row for row in kia_first if row.get("catcher_code") == "78122"],
        "KIA 전체 + 한준수": [row for row in kia_first if row.get("catcher_code") == "68646"],
        "네일 + 김태군": [row for row in naile_first if row.get("catcher_code") == "78122"],
        "네일 + 한준수": [row for row in naile_first if row.get("catcher_code") == "68646"],
    }


def render_svg(groups: dict[str, list[dict]]) -> str:
    order = [
        "KIA 전체 + 김태군",
        "KIA 전체 + 한준수",
        "네일 + 김태군",
        "네일 + 한준수",
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f5f1e8"/>',
        '<rect x="28" y="28" width="1544" height="1044" rx="30" fill="#fcfaf5" stroke="#d4c7ad" stroke-width="2"/>',
        '<text x="70" y="92" font-size="36" font-weight="700" fill="#2d2418">KIA 포수별 초구 스트라이크존 위치 비교</text>',
        '<text x="70" y="128" font-size="19" fill="#665844">4개 조합의 실제 초구 위치를 스트라이크존 위에 그대로 찍었습니다. 색은 구종입니다.</text>',
    ]

    for idx, title in enumerate(order):
        panel_x = LEFTS[idx % 2]
        panel_y = TOPS[idx // 2]
        rows = groups[title]
        parts.append(f'<rect x="{panel_x}" y="{panel_y}" width="{PANEL_W}" height="{PANEL_H}" rx="24" fill="#fffdf9" stroke="#d8ccb5" stroke-width="2"/>')
        parts.append(f'<text x="{panel_x + 24}" y="{panel_y + 38}" font-size="28" font-weight="700" fill="#2d2418">{title}</text>')
        parts.append(f'<text x="{panel_x + 24}" y="{panel_y + 62}" font-size="17" fill="#6a5a45">초구 표본 {len(rows)}개</text>')
        parts.extend(draw_zone(panel_x, panel_y))
        point_items, plotted = draw_points(rows, panel_x, panel_y)
        parts.extend(point_items)
        parts.append(f'<text x="{panel_x + 570}" y="{panel_y + 100}" font-size="16" fill="#6a5a45">표시 {plotted}개</text>')

    legend_x = 1410
    legend_y = 190
    parts.append(f'<text x="{legend_x - 120}" y="{legend_y}" font-size="24" font-weight="700" fill="#2d2418">구종 색상</text>')
    y = legend_y + 30
    for pitch_type, color in PITCH_COLORS.items():
        if pitch_type == "UNKNOWN":
            continue
        parts.append(f'<circle cx="{legend_x - 108}" cy="{y - 5}" r="7" fill="{color}" fill-opacity="0.75" stroke="white" stroke-width="0.8"/>')
        parts.append(f'<text x="{legend_x - 92}" y="{y}" font-size="16" fill="#3d3428">{pitch_type}</text>')
        y += 28

    parts.append('</svg>')
    return "\n".join(parts)


def main() -> None:
    output_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\kia_catcher_first_pitch_zone_2025.svg")
    groups = build_groups()
    output_path.write_text(render_svg(groups), encoding="utf-8")
    print(f"output_svg: {output_path}")


if __name__ == "__main__":
    main()
