#!/usr/bin/env python3

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


ZONE_LEFT = -0.708
ZONE_RIGHT = 0.708


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def in_zone(row: dict) -> bool | None:
    x = to_float(row.get("cross_plate_x"))
    z = to_float(row.get("plate_z"))
    bot = to_float(row.get("bottom_sz"))
    top = to_float(row.get("top_sz"))
    if None in {x, z, bot, top}:
        return None
    return ZONE_LEFT <= x <= ZONE_RIGHT and bot <= z <= top


def classify_first_pitch_action(pitch_result: str) -> str:
    swing_codes = {"F", "S", "H", "W", "V"}
    take_codes = {"B", "T"}
    if pitch_result in swing_codes:
        return "swing"
    if pitch_result in take_codes:
        return "take"
    return "other"


def safe_rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def build_summary(rows: list[dict]) -> tuple[list[dict], dict]:
    first_rows = [row for row in rows if row.get("pitch_num") == "1"]
    batter_store = defaultdict(
        lambda: {
            "batter_name": "",
            "stance": "",
            "first_pitch_seen": 0,
            "first_pitch_swing": 0,
            "first_pitch_take": 0,
            "first_pitch_other": 0,
            "first_pitch_whiff": 0,
            "first_pitch_foul": 0,
            "first_pitch_inplay": 0,
            "first_pitch_ball_take": 0,
            "first_pitch_called_strike_take": 0,
            "in_zone_seen": 0,
            "in_zone_swing": 0,
            "out_zone_seen": 0,
            "out_zone_swing": 0,
        }
    )

    for row in first_rows:
        batter_code = row.get("batter_code") or ""
        if not batter_code:
            continue
        store = batter_store[batter_code]
        store["batter_name"] = row.get("batter_name") or store["batter_name"]
        store["stance"] = row.get("stance") or store["stance"] or "UNKNOWN"
        store["first_pitch_seen"] += 1

        result = row.get("pitch_result") or ""
        action = classify_first_pitch_action(result)
        if action == "swing":
            store["first_pitch_swing"] += 1
        elif action == "take":
            store["first_pitch_take"] += 1
        else:
            store["first_pitch_other"] += 1

        if result == "S":
            store["first_pitch_whiff"] += 1
        elif result == "F":
            store["first_pitch_foul"] += 1
        elif result in {"H", "W", "V"}:
            store["first_pitch_inplay"] += 1
        elif result == "B":
            store["first_pitch_ball_take"] += 1
        elif result == "T":
            store["first_pitch_called_strike_take"] += 1

        zone_flag = in_zone(row)
        if zone_flag is True:
            store["in_zone_seen"] += 1
            if action == "swing":
                store["in_zone_swing"] += 1
        elif zone_flag is False:
            store["out_zone_seen"] += 1
            if action == "swing":
                store["out_zone_swing"] += 1

    summary_rows = []
    for batter_code, store in sorted(batter_store.items(), key=lambda item: (-item[1]["first_pitch_seen"], item[1]["batter_name"])):
        seen = store["first_pitch_seen"]
        swing = store["first_pitch_swing"]
        summary_rows.append(
            {
                "batter_code": batter_code,
                "batter_name": store["batter_name"],
                "stance": store["stance"] or "UNKNOWN",
                "first_pitch_seen": seen,
                "first_pitch_swing": swing,
                "first_pitch_take": store["first_pitch_take"],
                "first_pitch_other": store["first_pitch_other"],
                "first_pitch_swing_rate": safe_rate(swing, seen),
                "first_pitch_whiff": store["first_pitch_whiff"],
                "first_pitch_whiff_rate": safe_rate(store["first_pitch_whiff"], seen),
                "first_pitch_foul": store["first_pitch_foul"],
                "first_pitch_foul_rate": safe_rate(store["first_pitch_foul"], seen),
                "first_pitch_inplay": store["first_pitch_inplay"],
                "first_pitch_inplay_rate": safe_rate(store["first_pitch_inplay"], seen),
                "first_pitch_ball_take": store["first_pitch_ball_take"],
                "first_pitch_ball_take_rate": safe_rate(store["first_pitch_ball_take"], seen),
                "first_pitch_called_strike_take": store["first_pitch_called_strike_take"],
                "first_pitch_called_strike_take_rate": safe_rate(store["first_pitch_called_strike_take"], seen),
                "first_pitch_in_zone_seen": store["in_zone_seen"],
                "first_pitch_in_zone_swing": store["in_zone_swing"],
                "first_pitch_in_zone_swing_rate": safe_rate(store["in_zone_swing"], store["in_zone_seen"]),
                "first_pitch_out_zone_seen": store["out_zone_seen"],
                "first_pitch_out_zone_swing": store["out_zone_swing"],
                "first_pitch_out_zone_swing_rate": safe_rate(store["out_zone_swing"], store["out_zone_seen"]),
            }
        )

    payload = {
        "first_pitch_rows": len(first_rows),
        "batters": len(summary_rows),
        "top_first_pitch_swing_rate_min_20": [
            row for row in summary_rows if int(row["first_pitch_seen"]) >= 20
        ][:0],
    }
    top_swing = sorted(
        [row for row in summary_rows if int(row["first_pitch_seen"]) >= 20],
        key=lambda row: (-float(row["first_pitch_swing_rate"]), -int(row["first_pitch_seen"]), row["batter_name"]),
    )[:20]
    low_swing = sorted(
        [row for row in summary_rows if int(row["first_pitch_seen"]) >= 20],
        key=lambda row: (float(row["first_pitch_swing_rate"]), -int(row["first_pitch_seen"]), row["batter_name"]),
    )[:20]
    payload["top_first_pitch_swing_rate_min_20"] = top_swing
    payload["low_first_pitch_swing_rate_min_20"] = low_swing
    return summary_rows, payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build first-pitch swing tendency table for all batters.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    summary_rows, payload = build_summary(rows)
    write_rows(Path(args.output_csv), summary_rows)
    write_json(Path(args.output_json), payload)
    print(f"input_rows: {len(rows)}")
    print(f"summary_rows: {len(summary_rows)}")
    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")


if __name__ == "__main__":
    main()
