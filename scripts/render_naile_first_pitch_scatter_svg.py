#!/usr/bin/env python3

import argparse
import csv
import html
from collections import Counter
from pathlib import Path


ZONE_LEFT = -0.708
ZONE_RIGHT = 0.708
ZONE_TOP = 3.5
ZONE_BOTTOM = 1.5

WIDTH = 1400
HEIGHT = 1080
PLOT_X = 80
PLOT_Y = 170
PLOT_W = 920
PLOT_H = 820

RESULT_STYLE = {
    "BALL": {"fill": "#ff6b6b", "stroke": "#8b1e2d"},
    "STRIKE": {"fill": "#2f80ed", "stroke": "#123d7a"},
    "INPLAY": {"fill": "#8d99ae", "stroke": "#465066"},
}

PITCH_SHAPES = {
    "투심": "circle",
    "체인지업": "diamond",
    "슬라이더": "triangle",
    "커터": "square",
    "스위퍼": "triangle_down",
    "직구": "cross",
    "커브": "star",
}


def find_state_csv(input_dir: Path) -> Path:
    matches = sorted(input_dir.glob("*_state.csv"))
    if not matches:
        raise FileNotFoundError(f"No *_state.csv found under {input_dir}")
    return matches[0]


def read_first_pitches(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row.get("pitch_num") == "1"]


def to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def classify_result(pitch_result: str) -> str:
    if pitch_result == "B":
        return "BALL"
    if pitch_result in {"T", "S", "F"}:
        return "STRIKE"
    return "INPLAY"


def scale_x(x_value: float) -> float:
    min_x = -1.75
    max_x = 1.75
    ratio = (x_value - min_x) / (max_x - min_x)
    return PLOT_X + max(0.0, min(1.0, ratio)) * PLOT_W


def scale_y(z_value: float) -> float:
    min_z = 0.8
    max_z = 4.6
    ratio = (z_value - min_z) / (max_z - min_z)
    return PLOT_Y + PLOT_H - max(0.0, min(1.0, ratio)) * PLOT_H


def draw_shape(shape: str, cx: float, cy: float, size: float, fill: str, stroke: str) -> str:
    if shape == "circle":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" fill-opacity="0.72" />'
    if shape == "square":
        s = size * 1.7
        return f'<rect x="{cx - s/2:.1f}" y="{cy - s/2:.1f}" width="{s:.1f}" height="{s:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" fill-opacity="0.72" rx="1.5" />'
    if shape == "diamond":
        s = size * 1.9
        points = f"{cx:.1f},{cy - s/2:.1f} {cx + s/2:.1f},{cy:.1f} {cx:.1f},{cy + s/2:.1f} {cx - s/2:.1f},{cy:.1f}"
        return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" fill-opacity="0.72" />'
    if shape == "triangle":
        s = size * 2.0
        points = f"{cx:.1f},{cy - s/2:.1f} {cx + s/2:.1f},{cy + s/2:.1f} {cx - s/2:.1f},{cy + s/2:.1f}"
        return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" fill-opacity="0.72" />'
    if shape == "triangle_down":
        s = size * 2.0
        points = f"{cx - s/2:.1f},{cy - s/2:.1f} {cx + s/2:.1f},{cy - s/2:.1f} {cx:.1f},{cy + s/2:.1f}"
        return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" fill-opacity="0.72" />'
    if shape == "cross":
        s = size * 1.7
        return (
            f'<g stroke="{stroke}" stroke-width="2.0" stroke-linecap="round">'
            f'<line x1="{cx - s/2:.1f}" y1="{cy:.1f}" x2="{cx + s/2:.1f}" y2="{cy:.1f}" />'
            f'<line x1="{cx:.1f}" y1="{cy - s/2:.1f}" x2="{cx:.1f}" y2="{cy + s/2:.1f}" />'
            f'</g>'
        )
    if shape == "star":
        s = size * 1.8
        return (
            f'<g stroke="{stroke}" stroke-width="1.8" stroke-linecap="round">'
            f'<line x1="{cx - s/2:.1f}" y1="{cy:.1f}" x2="{cx + s/2:.1f}" y2="{cy:.1f}" />'
            f'<line x1="{cx:.1f}" y1="{cy - s/2:.1f}" x2="{cx:.1f}" y2="{cy + s/2:.1f}" />'
            f'<line x1="{cx - s/2.6:.1f}" y1="{cy - s/2.6:.1f}" x2="{cx + s/2.6:.1f}" y2="{cy + s/2.6:.1f}" />'
            f'<line x1="{cx - s/2.6:.1f}" y1="{cy + s/2.6:.1f}" x2="{cx + s/2.6:.1f}" y2="{cy - s/2.6:.1f}" />'
            f'</g>'
        )
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" fill-opacity="0.72" />'


def summary_text(rows: list[dict]) -> tuple[list[str], Counter, Counter]:
    pitch_counter = Counter(row.get("pitch_type") or "UNKNOWN" for row in rows)
    result_counter = Counter(classify_result(row.get("pitch_result") or "") for row in rows)
    top_lines = [
        f"총 초구: {len(rows)}개",
        "구종: " + ", ".join(f"{name} {count}개" for name, count in pitch_counter.most_common(6)),
        "결과: " + ", ".join(f"{name} {count}개" for name, count in result_counter.items()),
    ]
    return top_lines, pitch_counter, result_counter


def render_svg(rows: list[dict]) -> str:
    top_lines, pitch_counter, result_counter = summary_text(rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f5f1e8" />',
        '<rect x="28" y="28" width="1344" height="1024" rx="26" fill="#fcfaf5" stroke="#d4c7ad" stroke-width="2" />',
        '<text x="80" y="92" font-size="34" font-weight="700" fill="#2d2418">2025 네일 초구 664개 위치 시각화</text>',
        '<text x="80" y="128" font-size="18" fill="#665844">모양은 구종, 색은 결과입니다. 파랑=스트라이크, 빨강=볼, 회색=인플레이/기타</text>',
    ]
    for idx, line in enumerate(top_lines):
        parts.append(f'<text x="1040" y="{120 + idx*26}" font-size="18" fill="#3d3428">{html.escape(line)}</text>')

    plot_bg = f'<rect x="{PLOT_X}" y="{PLOT_Y}" width="{PLOT_W}" height="{PLOT_H}" rx="18" fill="#fffdf8" stroke="#d7ccb5" stroke-width="1.6" />'
    parts.append(plot_bg)

    zone_x1 = scale_x(ZONE_LEFT)
    zone_x2 = scale_x(ZONE_RIGHT)
    zone_y1 = scale_y(ZONE_TOP)
    zone_y2 = scale_y(ZONE_BOTTOM)
    zone_w = zone_x2 - zone_x1
    zone_h = zone_y2 - zone_y1

    parts.append(f'<rect x="{zone_x1:.1f}" y="{zone_y1:.1f}" width="{zone_w:.1f}" height="{zone_h:.1f}" fill="#fff8e1" stroke="#8c7b5f" stroke-width="2.2" />')
    for frac in (1/3, 2/3):
        x = zone_x1 + zone_w * frac
        y = zone_y1 + zone_h * frac
        parts.append(f'<line x1="{x:.1f}" y1="{zone_y1:.1f}" x2="{x:.1f}" y2="{zone_y2:.1f}" stroke="#b9ab90" stroke-width="1.2" />')
        parts.append(f'<line x1="{zone_x1:.1f}" y1="{y:.1f}" x2="{zone_x2:.1f}" y2="{y:.1f}" stroke="#b9ab90" stroke-width="1.2" />')

    for z in [1.0, 2.0, 3.0, 4.0]:
        y = scale_y(z)
        parts.append(f'<line x1="{PLOT_X}" y1="{y:.1f}" x2="{PLOT_X + PLOT_W}" y2="{y:.1f}" stroke="#ebe2d0" stroke-width="1" />')
        parts.append(f'<text x="{PLOT_X - 36}" y="{y + 5:.1f}" font-size="14" fill="#7a6d57">{z:.1f}</text>')
    for x in [-1.5, -0.75, 0, 0.75, 1.5]:
        sx = scale_x(x)
        parts.append(f'<line x1="{sx:.1f}" y1="{PLOT_Y}" x2="{sx:.1f}" y2="{PLOT_Y + PLOT_H}" stroke="#ebe2d0" stroke-width="1" />')
        parts.append(f'<text x="{sx - 12:.1f}" y="{PLOT_Y + PLOT_H + 28}" font-size="14" fill="#7a6d57">{x:.2f}</text>')

    plotted = 0
    skipped = 0
    for row in rows:
        x_value = to_float(row.get("cross_plate_x"))
        z_value = to_float(row.get("plate_z"))
        if x_value is None or z_value is None:
            skipped += 1
            continue
        cx = scale_x(x_value)
        cy = scale_y(z_value)
        pitch_type = row.get("pitch_type") or "UNKNOWN"
        result_group = classify_result(row.get("pitch_result") or "")
        style = RESULT_STYLE[result_group]
        shape = PITCH_SHAPES.get(pitch_type, "circle")
        parts.append(draw_shape(shape, cx, cy, 5.2, style["fill"], style["stroke"]))
        plotted += 1

    parts.append(f'<text x="80" y="1028" font-size="17" fill="#5a4d3a">좌표가 있는 초구 {plotted}개 표시, 좌표 누락 {skipped}개 제외</text>')

    legend_x = 1040
    legend_y = 250
    parts.append(f'<text x="{legend_x}" y="{legend_y}" font-size="22" font-weight="700" fill="#2d2418">결과 범례</text>')
    for idx, (name, style) in enumerate(RESULT_STYLE.items()):
        y = legend_y + 34 + idx * 36
        parts.append(f'<circle cx="{legend_x + 14}" cy="{y - 6}" r="8" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="1.5" />')
        parts.append(f'<text x="{legend_x + 34}" y="{y}" font-size="17" fill="#3d3428">{name}</text>')

    shape_legend_y = 410
    parts.append(f'<text x="{legend_x}" y="{shape_legend_y}" font-size="22" font-weight="700" fill="#2d2418">구종 범례</text>')
    ordered_types = [name for name, _ in pitch_counter.most_common()]
    for idx, pitch_type in enumerate(ordered_types):
        y = shape_legend_y + 34 + idx * 34
        parts.append(draw_shape(PITCH_SHAPES.get(pitch_type, "circle"), legend_x + 14, y - 6, 5.0, "#f3c969", "#6e5b1a"))
        parts.append(f'<text x="{legend_x + 34}" y="{y}" font-size="17" fill="#3d3428">{html.escape(pitch_type)} ({pitch_counter[pitch_type]})</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Naile 2025 first-pitch scatter SVG.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-svg", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    state_csv = find_state_csv(input_dir)
    rows = read_first_pitches(state_csv)
    svg = render_svg(rows)
    output_path = Path(args.output_svg)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(f"state_csv: {state_csv}")
    print(f"first_pitch_rows: {len(rows)}")
    print(f"output_svg: {output_path}")


if __name__ == "__main__":
    main()
