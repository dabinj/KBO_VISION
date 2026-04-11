#!/usr/bin/env python3

import argparse
import csv
from collections import Counter
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


def zone_9_label(row_label: str, col_label: str) -> str:
    if "UNKNOWN" in (row_label, col_label):
        return "UNKNOWN"
    if "OUT" in (row_label, col_label):
        return "OUT"
    return f"{row_label}_{col_label}"


def zone_col_5(cross_plate_x: float | None) -> str:
    if cross_plate_x is None:
        return "UNKNOWN"
    band = (ZONE_RIGHT - ZONE_LEFT) / 3.0
    extended_left = ZONE_LEFT - band
    extended_right = ZONE_RIGHT + band

    if cross_plate_x <= ZONE_LEFT:
        if cross_plate_x <= extended_left:
            return "1"
        return "2"
    if cross_plate_x < ZONE_LEFT + band:
        return "2"
    if cross_plate_x < ZONE_LEFT + 2 * band:
        return "3"
    if cross_plate_x < ZONE_RIGHT:
        return "4"
    if cross_plate_x < extended_right:
        return "5"
    return "5"


def zone_row_5(plate_z: float | None, bottom_sz: float | None, top_sz: float | None) -> str:
    if plate_z is None or bottom_sz is None or top_sz is None:
        return "UNKNOWN"
    band = (top_sz - bottom_sz) / 3.0
    extended_bottom = bottom_sz - band
    extended_top = top_sz + band

    if plate_z >= top_sz:
        if plate_z >= extended_top:
            return "A"
        return "B"
    if plate_z >= bottom_sz + 2 * band:
        return "B"
    if plate_z >= bottom_sz + band:
        return "C"
    if plate_z >= bottom_sz:
        return "D"
    if plate_z >= extended_bottom:
        return "E"
    return "E"


def zone_25_label(row5: str, col5: str) -> str:
    if "UNKNOWN" in (row5, col5):
        return "UNKNOWN"
    return f"{row5}{col5}"


def build_context_rows(rows: list[dict]) -> list[dict]:
    rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("seqno") or 0),
        ),
    )

    game_pitch_index = Counter()
    inning_pitch_index = Counter()
    game_pa_index = Counter()
    current_pa_key_by_game = {}
    previous_by_game = {}
    previous_by_inning = {}
    previous_by_pa = {}
    previous_zone_by_game = {}
    previous_zone_by_inning = {}
    previous_zone_by_pa = {}
    batter_seen_by_game = Counter()

    enriched = []

    for row in rows:
        game_id = row.get("game_id") or ""
        inning_key = (game_id, row.get("inning") or "", row.get("half") or "")
        batter_code = row.get("batter_code") or ""
        pitch_num = int(row.get("pitch_num") or 0)
        current_pa_key = (game_id, inning_key[1], inning_key[2], batter_code, pitch_num == 1)

        if pitch_num == 1 or current_pa_key_by_game.get(game_id) is None:
            game_pa_index[game_id] += 1
            pa_number = game_pa_index[game_id]
            pa_key = (game_id, pa_number)
            current_pa_key_by_game[game_id] = pa_key
            previous_by_pa[pa_key] = []
            batter_seen_by_game[(game_id, batter_code)] += 1
        else:
            pa_key = current_pa_key_by_game[game_id]

        game_pitch_index[game_id] += 1
        inning_pitch_index[inning_key] += 1

        pitch_type = row.get("pitch_type") or "UNKNOWN"
        prev_game = previous_by_game.get(game_id, [])
        prev_inning = previous_by_inning.get(inning_key, [])
        prev_pa = previous_by_pa.get(pa_key, [])
        prev_game_zone = previous_zone_by_game.get(game_id, [])
        prev_inning_zone = previous_zone_by_inning.get(inning_key, [])
        prev_pa_zone = previous_zone_by_pa.get(pa_key, [])

        cross_plate_x = to_float(row.get("cross_plate_x"))
        plate_z = to_float(row.get("plate_z"))
        bottom_sz = to_float(row.get("bottom_sz"))
        top_sz = to_float(row.get("top_sz"))
        z_row = zone_row(plate_z, bottom_sz, top_sz)
        z_col = zone_col(cross_plate_x)
        z9 = zone_9_label(z_row, z_col)
        z_row_5 = zone_row_5(plate_z, bottom_sz, top_sz)
        z_col_5 = zone_col_5(cross_plate_x)
        z25 = zone_25_label(z_row_5, z_col_5)

        enriched_row = {
            **row,
            "pa_number_in_game": game_pa_index[game_id],
            "pitch_index_in_game": game_pitch_index[game_id],
            "pitch_index_in_inning": inning_pitch_index[inning_key],
            "pitch_index_in_pa": pitch_num,
            "batter_seen_count_in_game": batter_seen_by_game[(game_id, batter_code)],
            "prev_pitch_type_game_1": prev_game[-1] if len(prev_game) >= 1 else "",
            "prev_pitch_type_game_2": prev_game[-2] if len(prev_game) >= 2 else "",
            "prev_pitch_type_game_3": prev_game[-3] if len(prev_game) >= 3 else "",
            "prev_pitch_type_inning_1": prev_inning[-1] if len(prev_inning) >= 1 else "",
            "prev_pitch_type_inning_2": prev_inning[-2] if len(prev_inning) >= 2 else "",
            "prev_pitch_type_pa_1": prev_pa[-1] if len(prev_pa) >= 1 else "",
            "prev_pitch_type_pa_2": prev_pa[-2] if len(prev_pa) >= 2 else "",
            "prev_pitch_type_pa_3": prev_pa[-3] if len(prev_pa) >= 3 else "",
            "prev_zone_9_game_1": prev_game_zone[-1] if len(prev_game_zone) >= 1 else "",
            "prev_zone_9_inning_1": prev_inning_zone[-1] if len(prev_inning_zone) >= 1 else "",
            "prev_zone_9_pa_1": prev_pa_zone[-1] if len(prev_pa_zone) >= 1 else "",
            "count_state": f"{row.get('balls')}-{row.get('strikes')}",
            "zone_row_3": z_row,
            "zone_col_3": z_col,
            "zone_9": z9,
            "zone_row_5": z_row_5,
            "zone_col_5": z_col_5,
            "zone_25": z25,
        }
        enriched.append(enriched_row)

        previous_by_game.setdefault(game_id, []).append(pitch_type)
        previous_by_inning.setdefault(inning_key, []).append(pitch_type)
        previous_by_pa.setdefault(pa_key, []).append(pitch_type)
        previous_zone_by_game.setdefault(game_id, []).append(z9)
        previous_zone_by_inning.setdefault(inning_key, []).append(z9)
        previous_zone_by_pa.setdefault(pa_key, []).append(z9)

    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description="Build context features for a pitch-level CSV.")
    parser.add_argument("--input-csv", required=True, help="Input pitch CSV")
    parser.add_argument("--output-csv", required=True, help="Output enriched CSV")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)
    rows = read_rows(input_path)
    enriched = build_context_rows(rows)
    write_rows(output_path, enriched)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(enriched)}")
    print(f"output_csv: {output_path}")


if __name__ == "__main__":
    main()
