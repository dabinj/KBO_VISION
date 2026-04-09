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


def load_profiles(path: Path) -> dict[str, dict]:
    return {row["batter_code"]: row for row in read_rows(path)}


def load_swing_profiles(path: Path) -> dict[str, dict]:
    return {row["batter_code"]: row for row in read_rows(path)}


def pitch_family(pitch_type: str) -> str:
    return "FASTBALL" if pitch_type in {"직구", "투심", "커터"} else "BREAKING"


def is_hit(result_text: str) -> bool:
    keywords = ["안타", "1루타", "2루타", "3루타", "홈런", "내야안타"]
    return any(keyword in result_text for keyword in keywords)


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


def swing_bucket(value: float) -> str:
    if value < 0.10:
        return "lt_10"
    if value < 0.20:
        return "10_19"
    if value < 0.30:
        return "20_29"
    if value < 0.40:
        return "30_39"
    return "ge_40"


def build_rows(rows: list[dict], profiles: dict[str, dict], swings: dict[str, dict]) -> list[dict]:
    batter_stats = defaultdict(lambda: {"ab": 0, "h": 0, "pa": 0})
    output = []

    for row in rows:
        batter_code = row.get("batter_code") or ""
        stats = batter_stats[batter_code]
        ab_before = stats["ab"]
        h_before = stats["h"]
        pa_before = stats["pa"]
        ba_before = round(h_before / ab_before, 4) if ab_before else 0.0

        profile = profiles.get(
            batter_code,
            {
                "weak_side_2024": "UNKNOWN",
                "weak_height_2024": "UNKNOWN",
                "weak_pitch_family_2024": "UNKNOWN",
                "weak_zone_2024": "UNKNOWN",
                "weakness_score_inside_2024": "0.0",
                "weakness_score_outside_2024": "0.0",
                "weakness_score_high_2024": "0.0",
                "weakness_score_low_2024": "0.0",
            },
        )
        swing = swings.get(
            batter_code,
            {
                "first_pitch_seen": "0",
                "first_pitch_swing_rate": "0.0",
                "first_pitch_whiff_rate": "0.0",
                "first_pitch_inplay_rate": "0.0",
                "first_pitch_ball_take_rate": "0.0",
                "first_pitch_called_strike_take_rate": "0.0",
                "first_pitch_in_zone_swing_rate": "0.0",
                "first_pitch_out_zone_swing_rate": "0.0",
            },
        )

        swing_rate = float(swing.get("first_pitch_swing_rate", "0.0") or 0.0)
        pitch_type = row.get("pitch_type") or "UNKNOWN"

        output.append(
            {
                "game_id": row.get("game_id") or "",
                "game_date": row.get("game_date") or "",
                "pitcher_code": row.get("pitcher_code") or "",
                "pitcher_name": row.get("pitcher_name") or "",
                "catcher_code": row.get("catcher_code") or "",
                "catcher_name": row.get("catcher_name") or "",
                "batter_code": batter_code,
                "batter_name": row.get("batter_name") or "",
                "batter_stance": row.get("stance") or "UNKNOWN",
                "opponent_team_code": row.get("away_team_code") if (row.get("home_team_code") == "HT") else row.get("home_team_code"),
                "inning": row.get("inning") or "",
                "half": row.get("half") or "",
                "outs": row.get("outs") or "",
                "runner_state": row.get("runner_state") or "000",
                "runners_on": row.get("runners_on") or "0",
                "score_diff_pitcher": row.get("score_diff_pitcher") or "0",
                "balls": row.get("balls") or "",
                "strikes": row.get("strikes") or "",
                "count_state": f"{row.get('balls')}-{row.get('strikes')}",
                "pitch_index_in_pa": row.get("pitch_index_in_pa") or row.get("pitch_num") or "",
                "pitch_index_in_inning": row.get("pitch_index_in_inning") or "",
                "pitch_index_in_game": row.get("pitch_index_in_game") or row.get("seqno") or "",
                "prev_pitch_type_pa_1": row.get("prev_pitch_type_pa_1") or "",
                "prev_pitch_type_pa_2": row.get("prev_pitch_type_pa_2") or "",
                "prev_pitch_type_pa_3": row.get("prev_pitch_type_pa_3") or "",
                "prev_pitch_type_inning_1": row.get("prev_pitch_type_inning_1") or "",
                "prev_pitch_type_game_1": row.get("prev_pitch_type_game_1") or "",
                "prev_zone_9_pa_1": row.get("prev_zone_9_pa_1") or "",
                "zone_9": row.get("zone_9") or "",
                "batter_seen_count_in_game": row.get("batter_seen_count_in_game") or "",
                "batter_season_pa_before_pitch": str(pa_before),
                "batter_season_ab_before_pitch": str(ab_before),
                "batter_season_h_before_pitch": str(h_before),
                "batter_season_ba_before_pitch": f"{ba_before:.4f}",
                "batter_season_ba_bucket": ba_bucket(ba_before),
                "pitch_family": pitch_family(pitch_type),
                "pitch_type": pitch_type,
                "weakness_source": "prior_2024" if batter_code in profiles else "none",
                "weak_side_2024": profile.get("weak_side_2024", "UNKNOWN"),
                "weak_height_2024": profile.get("weak_height_2024", "UNKNOWN"),
                "weak_pitch_family_2024": profile.get("weak_pitch_family_2024", "UNKNOWN"),
                "weak_zone_2024": profile.get("weak_zone_2024", "UNKNOWN"),
                "weakness_score_inside_2024": profile.get("weakness_score_inside_2024", "0.0"),
                "weakness_score_outside_2024": profile.get("weakness_score_outside_2024", "0.0"),
                "weakness_score_high_2024": profile.get("weakness_score_high_2024", "0.0"),
                "weakness_score_low_2024": profile.get("weakness_score_low_2024", "0.0"),
                "batter_first_pitch_seen_2025": swing.get("first_pitch_seen", "0"),
                "batter_first_pitch_swing_rate_2025": swing.get("first_pitch_swing_rate", "0.0"),
                "batter_first_pitch_swing_bucket_2025": swing_bucket(swing_rate),
                "batter_first_pitch_whiff_rate_2025": swing.get("first_pitch_whiff_rate", "0.0"),
                "batter_first_pitch_inplay_rate_2025": swing.get("first_pitch_inplay_rate", "0.0"),
                "batter_first_pitch_ball_take_rate_2025": swing.get("first_pitch_ball_take_rate", "0.0"),
                "batter_first_pitch_called_strike_take_rate_2025": swing.get("first_pitch_called_strike_take_rate", "0.0"),
                "batter_first_pitch_in_zone_swing_rate_2025": swing.get("first_pitch_in_zone_swing_rate", "0.0"),
                "batter_first_pitch_out_zone_swing_rate_2025": swing.get("first_pitch_out_zone_swing_rate", "0.0"),
            }
        )

        plate_result_text = (row.get("plate_result_text") or "").strip()
        if plate_result_text:
            stats["pa"] += 1
            if is_at_bat(plate_result_text):
                stats["ab"] += 1
            if is_hit(plate_result_text):
                stats["h"] += 1

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build all-pitch driver table for pitch-type modeling.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--weakness-csv", required=True)
    parser.add_argument("--swing-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("pitch_index_in_game") or row.get("seqno") or 0),
        ),
    )
    profiles = load_profiles(Path(args.weakness_csv))
    swings = load_swing_profiles(Path(args.swing_csv))
    output = build_rows(rows, profiles, swings)
    write_rows(Path(args.output_csv), output)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(output)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
