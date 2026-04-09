#!/usr/bin/env python3

import csv
from collections import Counter
from pathlib import Path


WIDTH = 1200
HEIGHT = 920
BG = "#f5f1e8"
PANEL = "#fcfaf5"
TEXT = "#2d2418"
MUTED = "#6a5a45"
GRID = "#b8aa8e"

ZONE_ORDER = [
    "HIGH_LEFT",
    "HIGH_MIDDLE",
    "HIGH_RIGHT",
    "MIDDLE_LEFT",
    "MIDDLE_MIDDLE",
    "MIDDLE_RIGHT",
    "LOW_LEFT",
    "LOW_MIDDLE",
    "LOW_RIGHT",
]


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def zone_color(pct: float, max_pct: float) -> str:
    ratio = 0.0 if max_pct <= 0 else pct / max_pct
    light = int(245 - ratio * 110)
    red = int(245 - ratio * 10)
    green = int(232 - ratio * 120)
    blue = int(210 - ratio * 150)
    return f"rgb({red},{green},{blue})"


def render_svg(counter: Counter, total: int) -> str:
    zone_counts = {zone: counter.get(zone, 0) for zone in ZONE_ORDER}
    zone_pcts = {zone: (count / total * 100) if total else 0.0 for zone, count in zone_counts.items()}
    max_pct = max(zone_pcts.values()) if zone_pcts else 0.0
    out_pct = (counter.get("OUT", 0) / total * 100) if total else 0.0

    left = 150
    top = 180
    cell = 150

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        f'<rect x="30" y="30" width="{WIDTH-60}" height="{HEIGHT-60}" rx="28" fill="{PANEL}" stroke="#d4c7ad" stroke-width="2"/>',
        f'<text x="70" y="92" font-size="36" font-weight="700" fill="{TEXT}">네일 2025 초구 위치 확률 지도</text>',
        f'<text x="70" y="128" font-size="19" fill="{MUTED}">2025 전체 초구 기준입니다. 특정 타석 조건을 넣지 않은 전체 분포 prior로 보시면 됩니다.</text>',
        f'<text x="70" y="160" font-size="18" fill="{MUTED}">모델 위치 정확도 Top-1 45.9%는 이 분포 위에서 상황 피처를 넣어 세부 조정한 결과입니다.</text>',
    ]

    # Outer chase area
    parts.append(f'<rect x="{left-32}" y="{top-32}" width="{cell*3+64}" height="{cell*3+64}" rx="26" fill="#efe5d3" stroke="#cfbfa1" stroke-width="2"/>')
    parts.append(f'<rect x="{left}" y="{top}" width="{cell*3}" height="{cell*3}" rx="18" fill="#fffaf0" stroke="#8c7b5f" stroke-width="2.5"/>')

    for idx, zone in enumerate(ZONE_ORDER):
        row = idx // 3
        col = idx % 3
        x = left + col * cell
        y = top + row * cell
        pct = zone_pcts[zone]
        count = zone_counts[zone]
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{zone_color(pct, max_pct)}" stroke="{GRID}" stroke-width="1.4"/>')
        parts.append(f'<text x="{x+16}" y="{y+36}" font-size="18" font-weight="700" fill="{TEXT}">{zone.replace("_", " ")}</text>')
        parts.append(f'<text x="{x+16}" y="{y+78}" font-size="34" font-weight="700" fill="{TEXT}">{pct:.1f}%</text>')
        parts.append(f'<text x="{x+16}" y="{y+106}" font-size="18" fill="{MUTED}">{count} pitches</text>')

    for frac in (1, 2):
        x = left + frac * cell
        y = top + frac * cell
        parts.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + cell*3}" stroke="{GRID}" stroke-width="1.6"/>')
        parts.append(f'<line x1="{left}" y1="{y}" x2="{left + cell*3}" y2="{y}" stroke="{GRID}" stroke-width="1.6"/>')

    parts.append(f'<text x="{710}" y="{255}" font-size="28" font-weight="700" fill="{TEXT}">존 밖(OUT)</text>')
    parts.append(f'<rect x="710" y="280" width="360" height="120" rx="20" fill="#e7dcc8" stroke="#c9b896" stroke-width="2"/>')
    parts.append(f'<text x="740" y="335" font-size="46" font-weight="700" fill="{TEXT}">{out_pct:.1f}%</text>')
    parts.append(f'<text x="740" y="367" font-size="18" fill="{MUTED}">{counter.get("OUT", 0)} pitches</text>')
    parts.append(f'<text x="740" y="395" font-size="16" fill="{MUTED}">엣지/유인구 포함 전체 존 밖 비율</text>')

    top3 = sorted(zone_pcts.items(), key=lambda item: item[1], reverse=True)[:3]
    parts.append(f'<text x="710" y="470" font-size="28" font-weight="700" fill="{TEXT}">인존 상위 위치</text>')
    y = 510
    for zone, pct in top3:
        parts.append(f'<text x="720" y="{y}" font-size="21" fill="{TEXT}">{zone.replace("_", " ")}</text>')
        parts.append(f'<text x="960" y="{y}" font-size="21" font-weight="700" fill="{TEXT}">{pct:.1f}%</text>')
        y += 38

    parts.append(f'<text x="710" y="670" font-size="28" font-weight="700" fill="{TEXT}">해석</text>')
    notes = [
        "1. 전체 prior 기준으로는 OUT 비율이 가장 큽니다.",
        "2. 인존에서는 가운데와 낮은 코스가 상대적으로 많이 보입니다.",
        "3. 실제 예측은 여기에 주자상황, 아웃카운트, 포수, 타자 성향을 더해 조정됩니다.",
    ]
    y = 710
    for note in notes:
        parts.append(f'<text x="720" y="{y}" font-size="18" fill="{MUTED}">{note}</text>')
        y += 32

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    input_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_pitch_drivers_2025.csv")
    output_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_zone_probability_2025.svg")
    rows = read_rows(input_path)
    counter = Counter(row.get("first_zone_9") or "UNKNOWN" for row in rows)
    svg = render_svg(counter, len(rows))
    output_path.write_text(svg, encoding="utf-8")
    print(f"input_rows: {len(rows)}")
    print(f"output_svg: {output_path}")


if __name__ == "__main__":
    main()
