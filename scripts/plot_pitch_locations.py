#!/usr/bin/env python3

import argparse
import csv
from html import escape
from pathlib import Path
from urllib.parse import quote


DEFAULT_INPUT = Path("data/raw/naver_relay_pitches_20260405HHOB02026.csv")
DEFAULT_OUTPUT_DIR = Path("plots")

CANVAS_WIDTH = 720
CANVAS_HEIGHT = 860
PADDING_LEFT = 90
PADDING_RIGHT = 60
PADDING_TOP = 60
PADDING_BOTTOM = 90
X_MIN = -2.0
X_MAX = 2.0
Z_MIN = 0.0
Z_MAX = 5.0
ZONE_LEFT = -0.7083
ZONE_RIGHT = 0.7083

RESULT_COLORS = {
    "S": "#2563eb",
    "B": "#dc2626",
    "F": "#f59e0b",
    "H": "#16a34a",
    "T": "#7c3aed",
}
DEFAULT_COLOR = "#475569"

PITCH_TYPE_SHAPES = {
    "직구": "circle",
    "투심": "circle",
    "싱커": "diamond",
    "커터": "square",
    "슬라이더": "square",
    "스위퍼": "triangle_left",
    "커브": "triangle_down",
    "포크": "diamond",
    "체인지업": "triangle_up",
    "체인저": "triangle_up",
    "너클": "hexagon",
}


def parse_float(value: str) -> float | None:
    if value == "":
        return None
    return float(value)


def parse_int(value: str) -> int | None:
    if value == "":
        return None
    return int(value)


def load_rows(csv_path: Path) -> list[dict]:
    rows = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row["seqno"] = parse_int(row["seqno"])
            row["inning"] = parse_int(row["inning"])
            row["pitch_num"] = parse_int(row["pitch_num"])
            row["balls"] = parse_int(row["balls"])
            row["strikes"] = parse_int(row["strikes"])
            row["outs"] = parse_int(row["outs"])
            row["plate_result_type"] = parse_int(row["plate_result_type"])
            row["cross_plate_x"] = parse_float(row["cross_plate_x"])
            row["cross_plate_y_plane"] = parse_float(row["cross_plate_y_plane"])
            row["plate_z"] = parse_float(row["plate_z"])
            row["top_sz"] = parse_float(row["top_sz"])
            row["bottom_sz"] = parse_float(row["bottom_sz"])
            rows.append(row)
    return sorted(rows, key=lambda row: (row["seqno"] or 0, row["pitch_num"] or 0))


def group_plate_appearances(rows: list[dict]) -> list[list[dict]]:
    groups = []
    current_group = []

    for row in rows:
        if not current_group:
            current_group = [row]
            continue

        previous = current_group[-1]
        starts_new_pa = (
            row["pitch_num"] == 1
            or row["batter_code"] != previous["batter_code"]
            or row["inning"] != previous["inning"]
            or row["half"] != previous["half"]
        )
        if starts_new_pa:
            groups.append(current_group)
            current_group = [row]
        else:
            current_group.append(row)

    if current_group:
        groups.append(current_group)
    return groups


def x_to_svg(value: float) -> float:
    plot_width = CANVAS_WIDTH - PADDING_LEFT - PADDING_RIGHT
    return PADDING_LEFT + ((value - X_MIN) / (X_MAX - X_MIN)) * plot_width


def z_to_svg(value: float) -> float:
    plot_height = CANVAS_HEIGHT - PADDING_TOP - PADDING_BOTTOM
    return CANVAS_HEIGHT - PADDING_BOTTOM - ((value - Z_MIN) / (Z_MAX - Z_MIN)) * plot_height


def draw_axes() -> list[str]:
    parts = []
    x_axis_y = z_to_svg(Z_MIN)
    y_axis_x = x_to_svg(X_MIN)
    parts.append(
        f'<line x1="{PADDING_LEFT}" y1="{x_axis_y}" x2="{CANVAS_WIDTH - PADDING_RIGHT}" y2="{x_axis_y}" '
        'stroke="#94a3b8" stroke-width="1.5" />'
    )
    parts.append(
        f'<line x1="{y_axis_x}" y1="{PADDING_TOP}" x2="{y_axis_x}" y2="{CANVAS_HEIGHT - PADDING_BOTTOM}" '
        'stroke="#94a3b8" stroke-width="1.5" />'
    )

    for value in [-2, -1, 0, 1, 2]:
        x = x_to_svg(value)
        parts.append(
            f'<line x1="{x}" y1="{PADDING_TOP}" x2="{x}" y2="{CANVAS_HEIGHT - PADDING_BOTTOM}" '
            'stroke="#e2e8f0" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{x}" y="{CANVAS_HEIGHT - PADDING_BOTTOM + 28}" text-anchor="middle" '
            'font-size="14" fill="#334155">{value}</text>'
        )

    for value in [0, 1, 2, 3, 4, 5]:
        y = z_to_svg(value)
        parts.append(
            f'<line x1="{PADDING_LEFT}" y1="{y}" x2="{CANVAS_WIDTH - PADDING_RIGHT}" y2="{y}" '
            'stroke="#e2e8f0" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{PADDING_LEFT - 18}" y="{y + 5}" text-anchor="end" '
            'font-size="14" fill="#334155">{value}</text>'
        )

    parts.append(
        f'<text x="{(PADDING_LEFT + CANVAS_WIDTH - PADDING_RIGHT) / 2}" y="{CANVAS_HEIGHT - 24}" '
        'text-anchor="middle" font-size="16" fill="#0f172a">cross_plate_x (ft)</text>'
    )
    parts.append(
        f'<text x="24" y="{(PADDING_TOP + CANVAS_HEIGHT - PADDING_BOTTOM) / 2}" '
        'text-anchor="middle" font-size="16" fill="#0f172a" transform="rotate(-90 24 '
        f'{(PADDING_TOP + CANVAS_HEIGHT - PADDING_BOTTOM) / 2})">plate_z (ft)</text>'
    )
    return parts


def draw_zone(top_sz: float | None, bottom_sz: float | None) -> list[str]:
    if top_sz is None or bottom_sz is None:
        return []

    top = z_to_svg(top_sz)
    bottom = z_to_svg(bottom_sz)
    left = x_to_svg(ZONE_LEFT)
    right = x_to_svg(ZONE_RIGHT)
    third_1 = left + (right - left) / 3
    third_2 = left + 2 * (right - left) / 3
    height_third_1 = bottom - (bottom - top) / 3
    height_third_2 = bottom - 2 * (bottom - top) / 3

    parts = [
        f'<rect x="{left}" y="{top}" width="{right - left}" height="{bottom - top}" '
        'fill="none" stroke="#0f172a" stroke-width="2.5" />',
        f'<line x1="{third_1}" y1="{top}" x2="{third_1}" y2="{bottom}" stroke="#94a3b8" stroke-width="1" />',
        f'<line x1="{third_2}" y1="{top}" x2="{third_2}" y2="{bottom}" stroke="#94a3b8" stroke-width="1" />',
        f'<line x1="{left}" y1="{height_third_1}" x2="{right}" y2="{height_third_1}" stroke="#94a3b8" stroke-width="1" />',
        f'<line x1="{left}" y1="{height_third_2}" x2="{right}" y2="{height_third_2}" stroke="#94a3b8" stroke-width="1" />',
    ]
    return parts


def format_pitch_label(row: dict) -> str:
    pitch_type = row["pitch_type"] or "미상"
    result = row["pitch_result"] or "?"
    speed = row["speed"] or "?"
    return f'{row["pitch_num"]}구 {pitch_type} {result} {speed}km/h'


def shape_name_for_pitch_type(pitch_type: str | None) -> str:
    if not pitch_type:
        return "circle"
    return PITCH_TYPE_SHAPES.get(pitch_type, "circle")


def draw_marker_shape(x: float, z: float, radius: int, shape: str, color: str, title: str) -> str:
    if shape == "square":
        size = radius * 1.7
        half = size / 2
        return (
            f'<rect x="{x - half}" y="{z - half}" width="{size}" height="{size}" '
            f'fill="{color}" fill-opacity="0.9" stroke="white" stroke-width="2">'
            f'<title>{escape(title)}</title></rect>'
        )

    if shape == "diamond":
        points = [
            (x, z - radius * 1.3),
            (x + radius * 1.1, z),
            (x, z + radius * 1.3),
            (x - radius * 1.1, z),
        ]
    elif shape == "triangle_down":
        points = [
            (x - radius * 1.15, z - radius * 0.95),
            (x + radius * 1.15, z - radius * 0.95),
            (x, z + radius * 1.3),
        ]
    elif shape == "triangle_up":
        points = [
            (x - radius * 1.15, z + radius * 0.95),
            (x + radius * 1.15, z + radius * 0.95),
            (x, z - radius * 1.3),
        ]
    elif shape == "triangle_left":
        points = [
            (x + radius * 1.1, z - radius),
            (x + radius * 1.1, z + radius),
            (x - radius * 1.35, z),
        ]
    elif shape == "hexagon":
        points = [
            (x - radius * 1.0, z),
            (x - radius * 0.5, z - radius * 0.95),
            (x + radius * 0.5, z - radius * 0.95),
            (x + radius * 1.0, z),
            (x + radius * 0.5, z + radius * 0.95),
            (x - radius * 0.5, z + radius * 0.95),
        ]
    else:
        return (
            f'<circle cx="{x}" cy="{z}" r="{radius}" fill="{color}" fill-opacity="0.9" '
            f'stroke="white" stroke-width="2"><title>{escape(title)}</title></circle>'
        )

    points_attr = " ".join(f"{px},{py}" for px, py in points)
    return (
        f'<polygon points="{points_attr}" fill="{color}" fill-opacity="0.9" '
        f'stroke="white" stroke-width="2"><title>{escape(title)}</title></polygon>'
    )


def draw_pitch(row: dict, radius: int = 12) -> str:
    x = x_to_svg(row["cross_plate_x"])
    z = z_to_svg(row["plate_z"])
    color = RESULT_COLORS.get(row["pitch_result"], DEFAULT_COLOR)
    shape = shape_name_for_pitch_type(row["pitch_type"])
    plate_result = row.get("plate_result_text") or ""
    detail = (
        f'{row["pitch_num"]}구 | {row["pitch_type"] or "미상"} | {row["pitch_result"]} | '
        f'{row["speed"]}km/h | x={row["cross_plate_x"]:.3f}, z={row["plate_z"]:.3f} | '
        f'{row.get("event_text") or ""}'
    )
    if plate_result:
        detail += f" | 결과: {plate_result}"
    return (
        f'<g>{draw_marker_shape(x, z, radius, shape, color, detail)}'
        f'<text x="{x}" y="{z + 5}" text-anchor="middle" font-size="12" font-weight="700" fill="white">'
        f'{row["pitch_num"]}</text></g>'
    )


def build_svg(title: str, subtitle: str, rows: list[dict], zone_top: float | None, zone_bottom: float | None) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" '
        f'viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f8fafc" />',
        f'<text x="{PADDING_LEFT}" y="30" font-size="28" font-weight="700" fill="#0f172a">{escape(title)}</text>',
        f'<text x="{PADDING_LEFT}" y="52" font-size="15" fill="#475569">{escape(subtitle)}</text>',
    ]
    parts.extend(draw_axes())
    parts.extend(draw_zone(zone_top, zone_bottom))
    for row in rows:
        if row["cross_plate_x"] is None or row["plate_z"] is None:
            continue
        parts.append(draw_pitch(row))

    legend_x = CANVAS_WIDTH - PADDING_RIGHT - 150
    legend_y = 80
    parts.append(
        f'<rect x="{legend_x - 18}" y="{legend_y - 28}" width="168" height="208" rx="10" '
        'fill="white" stroke="#cbd5e1" stroke-width="1" />'
    )
    parts.append(
        f'<text x="{legend_x}" y="{legend_y - 8}" font-size="14" font-weight="700" fill="#0f172a">pitch_result</text>'
    )
    for index, (result, color) in enumerate([("S", RESULT_COLORS["S"]), ("B", RESULT_COLORS["B"]), ("F", RESULT_COLORS["F"]), ("H", RESULT_COLORS["H"]), ("T", RESULT_COLORS["T"])]):
        y = legend_y + index * 20
        parts.append(f'<circle cx="{legend_x}" cy="{y}" r="6" fill="{color}" />')
        parts.append(f'<text x="{legend_x + 14}" y="{y + 5}" font-size="13" fill="#334155">{result}</text>')

    parts.append(
        f'<text x="{legend_x}" y="{legend_y + 116}" font-size="14" font-weight="700" fill="#0f172a">pitch_type</text>'
    )
    legend_shapes = [
        ("직구", "circle"),
        ("커브", "triangle_down"),
        ("슬라이더", "square"),
        ("포크", "diamond"),
        ("체인지업", "triangle_up"),
        ("스위퍼", "triangle_left"),
    ]
    for index, (label, shape) in enumerate(legend_shapes):
        y = legend_y + 136 + index * 18
        parts.append(draw_marker_shape(legend_x, y, 6, shape, "#64748b", label))
        parts.append(f'<text x="{legend_x + 14}" y="{y + 5}" font-size="13" fill="#334155">{label}</text>')

    event_box_x = PADDING_LEFT
    event_box_y = CANVAS_HEIGHT - 150
    event_box_width = CANVAS_WIDTH - PADDING_LEFT - PADDING_RIGHT
    event_box_height = 96
    parts.append(
        f'<rect x="{event_box_x}" y="{event_box_y}" width="{event_box_width}" height="{event_box_height}" rx="10" '
        'fill="white" stroke="#cbd5e1" stroke-width="1" />'
    )
    parts.append(
        f'<text x="{event_box_x + 14}" y="{event_box_y + 22}" font-size="14" font-weight="700" fill="#0f172a">pitch events</text>'
    )
    for index, row in enumerate(rows[:8]):
        text_y = event_box_y + 42 + index * 16
        event_label = f'{row["pitch_num"]}구 {row.get("event_text") or ""}'
        if row.get("plate_result_text"):
            event_label += f' -> {row["plate_result_text"]}'
        parts.append(
            f'<text x="{event_box_x + 14}" y="{text_y}" font-size="12" fill="#334155">{escape(event_label)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-").lower() or "plot"


def render_plate_appearance(output_dir: Path, index: int, rows: list[dict]) -> Path:
    first = rows[0]
    pitch_count = max((row["pitch_num"] or 0) for row in rows)
    title = f'PA {index:02d} | {first["pitcher_name"]} vs {first["batter_name"]}'
    subtitle = (
        f'{first["inning"]}회 {"초" if first["half"] == "0" else "말"} | '
        f'{pitch_count} pitches | zone {first["bottom_sz"]:.3f} - {first["top_sz"]:.3f} ft'
    )
    svg = build_svg(title, subtitle, rows, first["top_sz"], first["bottom_sz"])
    filename = f'pa_{index:02d}_{safe_slug(first["pitcher_name"])}_vs_{safe_slug(first["batter_name"])}.svg'
    path = output_dir / filename
    write_text(path, svg)
    return path


def render_all_pitches(output_dir: Path, rows: list[dict]) -> Path:
    title = "All Pitches"
    subtitle = "Pitch order is shown by seqno order. Zone uses average top/bottom across rows."
    valid_top = [row["top_sz"] for row in rows if row["top_sz"] is not None]
    valid_bottom = [row["bottom_sz"] for row in rows if row["bottom_sz"] is not None]
    avg_top = sum(valid_top) / len(valid_top) if valid_top else None
    avg_bottom = sum(valid_bottom) / len(valid_bottom) if valid_bottom else None

    display_rows = []
    for index, row in enumerate(rows, start=1):
        display_row = dict(row)
        display_row["pitch_num"] = index
        display_rows.append(display_row)

    svg = build_svg(title, subtitle, display_rows, avg_top, avg_bottom)
    path = output_dir / "all_pitches.svg"
    write_text(path, svg)
    return path


def render_index(output_dir: Path, all_pitches_path: Path, pa_paths: list[Path]) -> Path:
    lines = [
        "<!doctype html>",
        '<html lang="ko"><head><meta charset="utf-8"><title>Pitch Location Plots</title>',
        '<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:32px;line-height:1.5;}'
        'a{color:#0f172a;text-decoration:none;}a:hover{text-decoration:underline;}'
        'ul{padding-left:20px;}li{margin:8px 0;}</style></head><body>',
        "<h1>Pitch Location Plots</h1>",
        f'<p><a href="{quote(all_pitches_path.name)}">all_pitches.svg</a></p>',
        "<ul>",
    ]
    for path in pa_paths:
        lines.append(f'<li><a href="{quote(path.name)}">{escape(path.name)}</a></li>')
    lines.append("</ul></body></html>")
    index_path = output_dir / "index.html"
    write_text(index_path, "\n".join(lines))
    return index_path


def infer_game_id(csv_path: Path) -> str:
    stem = csv_path.stem
    parts = stem.split("_")
    return parts[-1] if parts else "unknown_game"


def filter_rows(
    rows: list[dict],
    batter_name: str | None = None,
    pitcher_name: str | None = None,
) -> list[dict]:
    filtered = rows
    if batter_name:
        filtered = [row for row in filtered if row.get("batter_name") == batter_name]
    if pitcher_name:
        filtered = [row for row in filtered if row.get("pitcher_name") == pitcher_name]
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Render strike zone pitch location SVGs from extracted pitch CSV.")
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT), help="Input pitch CSV path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for output SVGs")
    parser.add_argument("--batter-name", help="Filter to a single batter name")
    parser.add_argument("--pitcher-name", help="Filter to a single pitcher name")
    args = parser.parse_args()

    csv_path = Path(args.input_csv)
    rows = load_rows(csv_path)
    rows = filter_rows(rows, batter_name=args.batter_name, pitcher_name=args.pitcher_name)
    if not rows:
        raise SystemExit("No rows found in input CSV.")

    game_id = infer_game_id(csv_path)
    output_dir = Path(args.output_dir) / game_id
    if args.batter_name:
        output_dir = output_dir / f"batter_{safe_slug(args.batter_name)}"
    if args.pitcher_name:
        output_dir = output_dir / f"pitcher_{safe_slug(args.pitcher_name)}"
    output_dir.mkdir(parents=True, exist_ok=True)

    pa_groups = group_plate_appearances(rows)
    all_pitches_path = render_all_pitches(output_dir, rows)
    pa_paths = [render_plate_appearance(output_dir, index, group) for index, group in enumerate(pa_groups, start=1)]
    index_path = render_index(output_dir, all_pitches_path, pa_paths)

    print(f"game_id: {game_id}")
    print(f"input_csv: {csv_path}")
    print(f"plate_appearances: {len(pa_groups)}")
    print(f"all_pitches_plot: {all_pitches_path}")
    print(f"index_html: {index_path}")
    print("plate_appearance_plots:")
    for path in pa_paths:
        print(path)


if __name__ == "__main__":
    main()
