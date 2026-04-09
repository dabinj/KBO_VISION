#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


COUNT_ORDER = ["0-0", "0-1", "0-2", "1-0", "1-1", "1-2", "2-0", "2-1", "2-2", "3-0", "3-1", "3-2"]
ZONE_LEFT = -0.708
ZONE_RIGHT = 0.708


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def zone_col(cross_plate_x: float | None) -> str:
    if cross_plate_x is None:
        return "UNKNOWN"
    if cross_plate_x < ZONE_LEFT or cross_plate_x > ZONE_RIGHT:
        return "OUT"
    band = (ZONE_RIGHT - ZONE_LEFT) / 3.0
    if cross_plate_x < ZONE_LEFT + band:
        return "LEFT"
    if cross_plate_x < ZONE_LEFT + 2 * band:
        return "MIDDLE"
    return "RIGHT"


def zone_row(plate_z: float | None, bottom_sz: float | None, top_sz: float | None) -> str:
    if plate_z is None or bottom_sz is None or top_sz is None:
        return "UNKNOWN"
    if plate_z < bottom_sz or plate_z > top_sz:
        return "OUT"
    band = (top_sz - bottom_sz) / 3.0
    if plate_z < bottom_sz + band:
        return "LOW"
    if plate_z < bottom_sz + 2 * band:
        return "MIDDLE"
    return "HIGH"


def zone_9(row: dict) -> str:
    col = zone_col(to_float(row.get("cross_plate_x")))
    z_row = zone_row(to_float(row.get("plate_z")), to_float(row.get("bottom_sz")), to_float(row.get("top_sz")))
    if "UNKNOWN" in (col, z_row):
        return "UNKNOWN"
    if "OUT" in (col, z_row):
        return "OUT"
    return f"{z_row}_{col}"


def pct_rows(counter: Counter, limit: int = 10) -> list[dict]:
    total = sum(counter.values())
    rows = []
    for name, count in counter.most_common(limit):
        rows.append(
            {
                "name": name,
                "count": count,
                "pct": round((count / total) * 100, 3) if total else 0.0,
            }
        )
    return rows


def group_plate_appearances(rows: list[dict]) -> list[list[dict]]:
    grouped = []
    current = []
    previous_game = None
    previous_batter = None

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("seqno") or 0),
        ),
    )
    for row in sorted_rows:
        game_id = row.get("game_id") or ""
        batter_code = row.get("batter_code") or ""
        should_start = (
            not current
            or game_id != previous_game
            or batter_code != previous_batter
            or (current and current[-1].get("plate_result_text"))
        )
        if should_start and current:
            grouped.append(current)
            current = []
        current.append(row)
        previous_game = game_id
        previous_batter = batter_code

    if current:
        grouped.append(current)
    return grouped


def annotate_pre_pitch_counts(pa_groups: list[list[dict]]) -> list[dict]:
    annotated = []
    for pa in pa_groups:
        balls = 0
        strikes = 0
        for row in pa:
            copied = dict(row)
            copied["pre_count_state"] = f"{balls}-{strikes}"
            annotated.append(copied)

            result = row.get("pitch_result") or ""
            if result == "B":
                balls = min(3, balls + 1)
            elif result in {"T", "S"}:
                strikes = min(2, strikes + 1)
            elif result == "F":
                if strikes < 2:
                    strikes += 1
    return annotated


def summarize(rows: list[dict]) -> dict:
    pa_groups = group_plate_appearances(rows)
    annotated_rows = annotate_pre_pitch_counts(pa_groups)
    grouped_pitch = defaultdict(lambda: defaultdict(Counter))
    grouped_zone = defaultdict(lambda: defaultdict(Counter))
    grouped_pitch_zone = defaultdict(lambda: defaultdict(Counter))

    for row in annotated_rows:
        count = row.get("pre_count_state") or "UNKNOWN"
        stance = row.get("stance") or "UNKNOWN"
        pitch = row.get("pitch_type") or "UNKNOWN"
        zone = zone_9(row)
        grouped_pitch[count][stance][pitch] += 1
        grouped_zone[count][stance][zone] += 1
        grouped_pitch_zone[count][stance][f"{pitch} @ {zone}"] += 1

    ordered_counts = [count for count in COUNT_ORDER if count in grouped_pitch] + [
        count for count in sorted(grouped_pitch) if count not in COUNT_ORDER
    ]

    count_rows = []
    for count in ordered_counts:
        stance_rows = []
        for stance in ["L", "R", "UNKNOWN"]:
            pitch_counter = grouped_pitch[count].get(stance, Counter())
            zone_counter = grouped_zone[count].get(stance, Counter())
            pitch_zone_counter = grouped_pitch_zone[count].get(stance, Counter())
            total = sum(pitch_counter.values())
            if total == 0:
                continue
            stance_rows.append(
                {
                    "stance": stance,
                    "total_pitches": total,
                    "top_pitch_types": pct_rows(pitch_counter, limit=6),
                    "top_zones": pct_rows(zone_counter, limit=6),
                    "top_pitch_zone_combos": pct_rows(pitch_zone_counter, limit=8),
                }
            )
        count_rows.append({"count_state": count, "stances": stance_rows})

    return {"count_state_rows": count_rows}


def render_markdown(title: str, summary: dict) -> str:
    lines = [f"# {title}", ""]
    lines.append("## 카운트 x 타자 좌/우 구종/위치 규칙")
    lines.append("")
    for row in summary["count_state_rows"]:
        lines.append(f"## {row['count_state']}")
        for stance_row in row["stances"]:
            lines.append(f"### {stance_row['stance']}타 (`{stance_row['total_pitches']}`구)")
            lines.append("- 구종 상위: " + ", ".join(f"{item['name']} {item['pct']}%" for item in stance_row["top_pitch_types"]))
            lines.append("- 위치 상위: " + ", ".join(f"{item['name']} {item['pct']}%" for item in stance_row["top_zones"]))
            lines.append("- 구종+위치 상위: " + ", ".join(f"{item['name']} {item['pct']}%" for item in stance_row["top_pitch_zone_combos"][:6]))
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze pitch type and location rules by count and batter stance.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    summary = summarize(rows)
    write_json(Path(args.output_json), summary)
    write_text(Path(args.output_md), render_markdown(args.title, summary))
    print(f"rows: {len(rows)}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")


if __name__ == "__main__":
    main()
