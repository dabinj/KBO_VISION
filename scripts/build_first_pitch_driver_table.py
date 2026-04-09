#!/usr/bin/env python3

import argparse
import csv
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


def relative_side_from_zone(zone_label: str, stance: str) -> str:
    if not zone_label or zone_label in {"OUT", "UNKNOWN"}:
        return zone_label or "UNKNOWN"
    parts = zone_label.split("_")
    if len(parts) != 2:
        return "UNKNOWN"
    col = parts[1]
    if col == "MIDDLE":
        return "MIDDLE"
    if stance == "L":
        return "INSIDE" if col == "RIGHT" else "OUTSIDE"
    return "INSIDE" if col == "LEFT" else "OUTSIDE"


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


def annotate_pre_pitch_counts(pa_groups: list[list[dict]]) -> list[list[dict]]:
    annotated = []
    for pa in pa_groups:
        balls = 0
        strikes = 0
        copied_pa = []
        for index, row in enumerate(pa, start=1):
            copied = dict(row)
            copied["pre_count_state"] = f"{balls}-{strikes}"
            copied["pitch_index_in_pa"] = str(index)
            copied_pa.append(copied)

            result = row.get("pitch_result") or ""
            if result == "B":
                balls = min(3, balls + 1)
            elif result in {"T", "S"}:
                strikes = min(2, strikes + 1)
            elif result == "F" and strikes < 2:
                strikes += 1
        annotated.append(copied_pa)
    return annotated


def opponent_team(row: dict, pitcher_team_code: str) -> tuple[str, str]:
    if (row.get("home_team_code") or "") == pitcher_team_code:
        return row.get("away_team_code") or "", row.get("away_team_name") or ""
    return row.get("home_team_code") or "", row.get("home_team_name") or ""


def load_profiles(path: Path) -> dict[str, dict]:
    return {row["batter_code"]: row for row in read_rows(path)}


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


def build_rows(rows: list[dict], profiles: dict[str, dict], swing_profiles: dict[str, dict], pitcher_team_code: str) -> list[dict]:
    batter_stats = defaultdict(lambda: {"ab": 0, "h": 0, "pa": 0})
    output = []
    pa_groups = annotate_pre_pitch_counts(group_plate_appearances(rows))

    for pa in pa_groups:
        if not pa:
            continue
        first = pa[0]
        batter_code = first.get("batter_code") or ""
        stats = batter_stats[batter_code]
        ab_before = stats["ab"]
        h_before = stats["h"]
        pa_before = stats["pa"]
        ba_before = round(h_before / ab_before, 4) if ab_before else 0.0
        zone = zone_9(first)
        stance = first.get("stance") or "UNKNOWN"
        opp_code, opp_name = opponent_team(first, pitcher_team_code)
        profile = profiles.get(
            batter_code,
            {
                "weak_side_2024": "UNKNOWN",
                "weak_height_2024": "UNKNOWN",
                "weak_pitch_family_2024": "UNKNOWN",
                "weak_zone_2024": "UNKNOWN",
                "weakness_score_inside_2024": "0.0",
                "weakness_score_middle_side_2024": "0.0",
                "weakness_score_outside_2024": "0.0",
                "weakness_score_high_2024": "0.0",
                "weakness_score_middle_height_2024": "0.0",
                "weakness_score_low_2024": "0.0",
                "weakness_score_fastball_2024": "0.0",
                "weakness_score_breaking_2024": "0.0",
                "weakness_score_weak_zone_2024": "0.0",
            },
        )
        swing_profile = swing_profiles.get(
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
        pitch_type = first.get("pitch_type") or "UNKNOWN"
        family = pitch_family(pitch_type)
        zone_side_rel = relative_side_from_zone(zone, stance)
        first_pitch_swing_rate = float(swing_profile.get("first_pitch_swing_rate", "0.0") or 0.0)

        output.append(
            {
                "game_id": first.get("game_id") or "",
                "game_date": first.get("game_date") or "",
                "pitcher_code": first.get("pitcher_code") or "",
                "pitcher_name": first.get("pitcher_name") or "",
                "catcher_code": first.get("catcher_code") or "",
                "catcher_name": first.get("catcher_name") or "",
                "opponent_team_code": opp_code,
                "opponent_team_name": opp_name,
                "batter_code": batter_code,
                "batter_name": first.get("batter_name") or "",
                "batter_stance": stance,
                "inning": first.get("inning") or "",
                "half": first.get("half") or "",
                "outs": first.get("outs") or "",
                "runner_state": first.get("runner_state") or "",
                "batter_season_pa_before_pitch": pa_before,
                "batter_season_ab_before_pitch": ab_before,
                "batter_season_h_before_pitch": h_before,
                "batter_season_ba_before_pitch": ba_before,
                "batter_season_ba_bucket": ba_bucket(ba_before),
                "balls": "0",
                "strikes": "0",
                "count_state": "0-0",
                "first_pitch_type": pitch_type,
                "first_pitch_family": family,
                "first_zone_9": zone,
                "first_zone_side_rel": zone_side_rel,
                "weakness_source": "prior_2024" if batter_code in profiles else "none",
                "weak_side_2024": profile.get("weak_side_2024", "UNKNOWN"),
                "weak_height_2024": profile.get("weak_height_2024", "UNKNOWN"),
                "weak_pitch_family_2024": profile.get("weak_pitch_family_2024", "UNKNOWN"),
                "weak_zone_2024": profile.get("weak_zone_2024", "UNKNOWN"),
                "weakness_score_inside_2024": profile.get("weakness_score_inside_2024", "0.0"),
                "weakness_score_middle_side_2024": profile.get("weakness_score_middle_side_2024", "0.0"),
                "weakness_score_outside_2024": profile.get("weakness_score_outside_2024", "0.0"),
                "weakness_score_high_2024": profile.get("weakness_score_high_2024", "0.0"),
                "weakness_score_middle_height_2024": profile.get("weakness_score_middle_height_2024", "0.0"),
                "weakness_score_low_2024": profile.get("weakness_score_low_2024", "0.0"),
                "weakness_score_fastball_2024": profile.get("weakness_score_fastball_2024", "0.0"),
                "weakness_score_breaking_2024": profile.get("weakness_score_breaking_2024", "0.0"),
                "weakness_score_weak_zone_2024": profile.get("weakness_score_weak_zone_2024", "0.0"),
                "first_pitch_targets_weak_side_2024": "1" if zone_side_rel == profile.get("weak_side_2024") else "0",
                "first_pitch_targets_weak_height_2024": "1" if zone.split("_")[0] == profile.get("weak_height_2024") else "0",
                "first_pitch_targets_weak_family_2024": "1" if family == profile.get("weak_pitch_family_2024") else "0",
                "batter_first_pitch_seen_2025": swing_profile.get("first_pitch_seen", "0"),
                "batter_first_pitch_swing_rate_2025": swing_profile.get("first_pitch_swing_rate", "0.0"),
                "batter_first_pitch_swing_bucket_2025": swing_bucket(first_pitch_swing_rate),
                "batter_first_pitch_whiff_rate_2025": swing_profile.get("first_pitch_whiff_rate", "0.0"),
                "batter_first_pitch_inplay_rate_2025": swing_profile.get("first_pitch_inplay_rate", "0.0"),
                "batter_first_pitch_ball_take_rate_2025": swing_profile.get("first_pitch_ball_take_rate", "0.0"),
                "batter_first_pitch_called_strike_take_rate_2025": swing_profile.get("first_pitch_called_strike_take_rate", "0.0"),
                "batter_first_pitch_in_zone_swing_rate_2025": swing_profile.get("first_pitch_in_zone_swing_rate", "0.0"),
                "batter_first_pitch_out_zone_swing_rate_2025": swing_profile.get("first_pitch_out_zone_swing_rate", "0.0"),
            }
        )

        plate_result_text = ((pa[-1].get("plate_result_text") or "")).strip()
        if plate_result_text:
            stats["pa"] += 1
            if is_at_bat(plate_result_text):
                stats["ab"] += 1
            if is_hit(plate_result_text):
                stats["h"] += 1

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a first-pitch-only driver table for a pitcher.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--weakness-csv", required=True)
    parser.add_argument("--swing-csv", required=True)
    parser.add_argument("--pitcher-team-code", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    profiles = load_profiles(Path(args.weakness_csv))
    swing_profiles = load_profiles(Path(args.swing_csv))
    output_rows = build_rows(rows, profiles, swing_profiles, args.pitcher_team_code)
    write_rows(Path(args.output_csv), output_rows)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(output_rows)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
