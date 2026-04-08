#!/usr/bin/env python3

import csv
from pathlib import Path


ZONE_ORDER = [
    "HIGH_LEFT", "HIGH_MIDDLE", "HIGH_RIGHT",
    "MIDDLE_LEFT", "MIDDLE_MIDDLE", "MIDDLE_RIGHT",
    "LOW_LEFT", "LOW_MIDDLE", "LOW_RIGHT",
]


def read_rows(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def draw_zone_grid(parts: list[str], x: int, y: int, active_zone: str, title: str) -> None:
    parts.append(f'<text x="{x}" y="{y-10}" font-size="11" font-family="Segoe UI, Arial" fill="#486581">{title}</text>')
    size = 18
    gap = 4
    for idx, zone in enumerate(ZONE_ORDER):
        row = idx // 3
        col = idx % 3
        zx = x + col * (size + gap)
        zy = y + row * (size + gap)
        fill = "#dbeafe" if zone == active_zone else "#f8fafc"
        stroke = "#2563eb" if zone == active_zone else "#cbd5e1"
        parts.append(f'<rect x="{zx}" y="{zy}" width="{size}" height="{size}" rx="4" fill="{fill}" stroke="{stroke}"/>')
    out_fill = "#fecaca" if active_zone == "OUT" else "#f8fafc"
    out_stroke = "#dc2626" if active_zone == "OUT" else "#cbd5e1"
    parts.append(f'<rect x="{x}" y="{y + 3*(size+gap) + 2}" width="{3*size + 2*gap}" height="18" rx="4" fill="{out_fill}" stroke="{out_stroke}"/>')
    parts.append(f'<text x="{x + (3*size + 2*gap)/2}" y="{y + 3*(size+gap) + 15}" text-anchor="middle" font-size="10" font-family="Segoe UI, Arial" fill="#334155">OUT</text>')


def draw_card(parts: list[str], x: int, y: int, row: dict) -> None:
    width = 340
    height = 162
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append(f'<text x="{x+16}" y="{y+28}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{row["batter_name"]}</text>')
    parts.append(f'<text x="{x+108}" y="{y+28}" font-size="12" font-family="Segoe UI, Arial" fill="#486581">{row["stance"]}HB</text>')
    parts.append(f'<text x="{x+16}" y="{y+48}" font-size="11" font-family="Segoe UI, Arial" fill="#486581">PA {row["pas"]} | AVG {row["ba"]}</text>')
    draw_zone_grid(parts, x+16, y+76, row.get("weakest_zone_2025") or "UNKNOWN", "2025 시즌 약점 존")
    draw_zone_grid(parts, x+150, y+76, row.get("two_strike_most_whiff_zone_2025") or "UNKNOWN", "2스트라이크 헛스윙 최다 존")
    parts.append(f'<text x="{x+150}" y="{y+154}" font-size="10" font-family="Segoe UI, Arial" fill="#486581">헛스윙 count {row["two_strike_most_whiff_zone_count_2025"]}</text>')


def main() -> None:
    rows = read_rows("data/team_tables/hanwha_2025/hanwha_batters_2025_summary.csv")
    rows = sorted(rows, key=lambda row: int(row.get("pas") or 0), reverse=True)

    width = 1100
    height = 1300
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="38" font-size="28" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">Hanwha Batter Weak Zones 2025</text>',
        '<text x="24" y="62" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Left: 2025 season weakness zone by disadvantage score. Right: two-strike zone with the most whiffs.</text>',
        '<text x="24" y="82" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Players are ordered by plate appearances, and the chart is built only from Hanwha 2025 batter data.</text>',
    ]

    cols = 3
    card_w = 356
    card_h = 178
    for idx, row in enumerate(rows):
        col = idx % cols
        line = idx // cols
        x = 24 + col * card_w
        y = 110 + line * card_h
        draw_card(parts, x, y, row)

    parts.append('</svg>')
    Path("examples/hanwha_batter_weak_zones_2025.svg").write_text("\n".join(parts), encoding="utf-8")
    print("examples/hanwha_batter_weak_zones_2025.svg")


if __name__ == "__main__":
    main()
