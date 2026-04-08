#!/usr/bin/env python3

import argparse
import csv
from collections import defaultdict
from pathlib import Path


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


def is_hit(result_text: str) -> bool:
    hit_keywords = ["안타", "1루타", "2루타", "3루타", "홈런", "내야안타"]
    return any(keyword in result_text for keyword in hit_keywords)


def is_walk_like(result_text: str) -> bool:
    keywords = ["볼넷", "고의4구", "몸에 맞는 볼", "출루"]
    return any(keyword in result_text for keyword in keywords)


def is_sacrifice(result_text: str) -> bool:
    keywords = ["희생번트", "희생플라이", "희생 플라이"]
    return any(keyword in result_text for keyword in keywords)


def is_at_bat(result_text: str) -> bool:
    if not result_text:
        return False
    if is_walk_like(result_text) or is_sacrifice(result_text):
        return False
    return True


def ba_bucket(value: float) -> str:
    if value < 0.200:
        return "lt_200"
    if value < 0.250:
        return "200_249"
    if value < 0.300:
        return "250_299"
    if value < 0.350:
        return "300_349"
    return "ge_350"


def pitch_family(pitch_type: str) -> str:
    fastball_family = {"직구", "투심", "커터"}
    if pitch_type in fastball_family:
        return "FASTBALL"
    return "BREAKING"


def add_realtime_batter_stats(rows: list[dict]) -> list[dict]:
    batter_stats = defaultdict(lambda: {"ab": 0, "h": 0, "pa": 0})
    enriched = []

    for row in rows:
        batter_code = row.get("batter_code") or ""
        stats = batter_stats[batter_code]
        ab_before = stats["ab"]
        h_before = stats["h"]
        pa_before = stats["pa"]
        ba_before = round(h_before / ab_before, 4) if ab_before else 0.0

        enriched_row = {
            **row,
            "batter_season_pa_before_pitch": pa_before,
            "batter_season_ab_before_pitch": ab_before,
            "batter_season_h_before_pitch": h_before,
            "batter_season_ba_before_pitch": ba_before,
            "batter_season_ba_bucket": ba_bucket(ba_before),
            "batter_stance": row.get("stance") or "UNKNOWN",
            "pitch_family": pitch_family(row.get("pitch_type") or ""),
        }
        enriched.append(enriched_row)

        result_text = (row.get("plate_result_text") or "").strip()
        if result_text:
            stats["pa"] += 1
            if is_at_bat(result_text):
                stats["ab"] += 1
            if is_hit(result_text):
                stats["h"] += 1

    return enriched


def select_columns(rows: list[dict], columns: list[str]) -> list[dict]:
    return [{column: row.get(column, "") for column in columns} for row in rows]


def build_pitcher_routine_table(rows: list[dict]) -> list[dict]:
    columns = [
        "game_id",
        "game_date",
        "pitcher_code",
        "pitcher_name",
        "catcher_code",
        "catcher_name",
        "batter_code",
        "batter_name",
        "batter_stance",
        "batter_seen_count_in_game",
        "batter_season_pa_before_pitch",
        "batter_season_ab_before_pitch",
        "batter_season_h_before_pitch",
        "batter_season_ba_before_pitch",
        "batter_season_ba_bucket",
        "inning",
        "half",
        "outs",
        "runner_state",
        "runners_on",
        "score_diff_pitcher",
        "balls",
        "strikes",
        "count_state",
        "pitch_index_in_pa",
        "pitch_index_in_inning",
        "pitch_index_in_game",
        "prev_pitch_type_pa_1",
        "prev_pitch_type_pa_2",
        "prev_pitch_type_pa_3",
        "prev_pitch_type_inning_1",
        "prev_pitch_type_game_1",
        "prev_zone_9_pa_1",
        "zone_9",
        "pitch_family",
        "pitch_type",
    ]
    return select_columns(rows, columns)


def build_catcher_situation_table(rows: list[dict]) -> list[dict]:
    columns = [
        "game_id",
        "game_date",
        "catcher_code",
        "catcher_name",
        "pitcher_code",
        "pitcher_name",
        "batter_stance",
        "runner_state",
        "runners_on",
        "score_diff_pitcher",
        "inning",
        "half",
        "outs",
        "pitch_index_in_pa",
        "pitch_index_in_inning",
        "pitch_index_in_game",
        "prev_pitch_type_pa_1",
        "prev_pitch_type_pa_2",
        "prev_pitch_type_inning_1",
        "prev_pitch_type_game_1",
        "prev_zone_9_pa_1",
        "zone_9",
        "pitch_family",
        "pitch_type",
    ]
    return select_columns(rows, columns)


def build_catcher_batter_count_table(rows: list[dict]) -> list[dict]:
    columns = [
        "game_id",
        "game_date",
        "catcher_code",
        "catcher_name",
        "pitcher_code",
        "pitcher_name",
        "batter_code",
        "batter_name",
        "batter_stance",
        "batter_seen_count_in_game",
        "batter_season_pa_before_pitch",
        "batter_season_ab_before_pitch",
        "batter_season_h_before_pitch",
        "batter_season_ba_before_pitch",
        "batter_season_ba_bucket",
        "runner_state",
        "runners_on",
        "score_diff_pitcher",
        "balls",
        "strikes",
        "count_state",
        "prev_pitch_type_pa_1",
        "prev_pitch_type_pa_2",
        "prev_pitch_type_pa_3",
        "prev_zone_9_pa_1",
        "zone_9",
        "pitch_family",
        "pitch_type",
    ]
    return select_columns(rows, columns)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build model-ready tables from context pitch CSV.")
    parser.add_argument("--input-csv", required=True, help="Context-enriched pitch CSV")
    parser.add_argument("--table-kind", required=True, choices=["pitcher_routine", "catcher_situation", "catcher_batter_count"])
    parser.add_argument("--output-csv", required=True, help="Output model table CSV")
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    rows = add_realtime_batter_stats(rows)

    if args.table_kind == "pitcher_routine":
        output_rows = build_pitcher_routine_table(rows)
    elif args.table_kind == "catcher_situation":
        output_rows = build_catcher_situation_table(rows)
    else:
        output_rows = build_catcher_batter_count_table(rows)

    write_rows(Path(args.output_csv), output_rows)
    print(f"table_kind: {args.table_kind}")
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(output_rows)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
