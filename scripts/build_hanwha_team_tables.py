#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ZONE_LEFT = -0.708
ZONE_RIGHT = 0.708
HANWHA_CODE = "HH"


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
    z_col = zone_col(to_float(row.get("cross_plate_x")))
    z_row = zone_row(to_float(row.get("plate_z")), to_float(row.get("bottom_sz")), to_float(row.get("top_sz")))
    if "UNKNOWN" in (z_col, z_row):
        return "UNKNOWN"
    if "OUT" in (z_col, z_row):
        return "OUT"
    return f"{z_row}_{z_col}"


def pitch_family(pitch_type: str) -> str:
    return "FASTBALL" if pitch_type in {"직구", "투심", "커터"} else "BREAKING"


def batter_team_code(row: dict) -> str:
    half = row.get("half")
    return row.get("away_team_code") if half == "0" else row.get("home_team_code")


def pitcher_team_code(row: dict) -> str:
    half = row.get("half")
    return row.get("home_team_code") if half == "0" else row.get("away_team_code")


def is_swinging_miss(event_text: str) -> bool:
    return "헛스윙" in (event_text or "")


def is_swing(event_text: str) -> bool:
    text = event_text or ""
    swing_keywords = ["헛스윙", "파울", "타격", "번트", "인플레이"]
    return any(keyword in text for keyword in swing_keywords)


def classify_pa_result(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "UNKNOWN"
    if "볼넷" in text or "고의4구" in text or "몸에 맞는 볼" in text:
        return "WALK"
    if "홈런" in text:
        return "HR"
    if "3루타" in text:
        return "TRIPLE"
    if "2루타" in text:
        return "DOUBLE"
    if "1루타" in text or "안타" in text or "출루" in text:
        return "SINGLE"
    if "삼진" in text:
        return "K"
    if "희생" in text:
        return "SAC"
    return "OUT"


def is_hit(pa_result: str) -> bool:
    return pa_result in {"SINGLE", "DOUBLE", "TRIPLE", "HR"}


def is_ab(pa_result: str) -> bool:
    return pa_result not in {"WALK", "SAC", "UNKNOWN"}


def relative_side(zone_label: str, stance: str) -> str:
    if zone_label in {"OUT", "UNKNOWN"}:
        return zone_label
    row_part, col_part = zone_label.split("_", 1)
    if col_part == "MIDDLE":
        return "MIDDLE"
    if stance == "L":
        return "INSIDE" if col_part == "RIGHT" else "OUTSIDE"
    return "INSIDE" if col_part == "LEFT" else "OUTSIDE"


def disadvantage_score(row: dict) -> float:
    plate_result = (row.get("plate_result_text") or "").strip()
    event_text = (row.get("event_text") or "").strip()
    pa_result = classify_pa_result(plate_result)

    if pa_result == "HR":
        return -2.0
    if pa_result in {"TRIPLE", "DOUBLE", "SINGLE"}:
        return -1.4
    if pa_result == "WALK":
        return -1.0
    if pa_result == "K":
        return 1.4
    if pa_result == "OUT":
        return 1.0

    if "헛스윙" in event_text:
        return 1.0
    if "스트라이크" in event_text:
        return 0.6
    if "파울" in event_text:
        return 0.2
    if "볼" in event_text:
        return -0.3
    return 0.0


def group_plate_appearances(rows: list[dict]) -> list[list[dict]]:
    grouped = []
    current = []
    previous_game = None
    previous_batter = None

    sorted_rows = sorted(rows, key=lambda row: (row.get("game_date") or "", row.get("game_id") or "", int(row.get("seqno") or 0)))
    for row in sorted_rows:
        game_id = row.get("game_id")
        batter_code = row.get("batter_code")
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


def pick_best(counter: Counter, minimum_count: int = 5, fallback: str = "UNKNOWN") -> tuple[str, int]:
    eligible = [(name, count) for name, count in counter.items() if count >= minimum_count]
    if not eligible:
        if not counter:
            return fallback, 0
        name, count = counter.most_common(1)[0]
        return name, count
    return max(eligible, key=lambda item: item[1])


def build_batter_tables(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    hanwha_rows = [row for row in rows if batter_team_code(row) == HANWHA_CODE]
    pa_groups = group_plate_appearances(hanwha_rows)

    summary = {}
    zone_detail = defaultdict(lambda: {"pitches": 0, "two_strike_pitches": 0, "two_strike_whiffs": 0, "disadv_sum": 0.0})

    for pa in pa_groups:
        batter_code = pa[0].get("batter_code") or ""
        batter_name = pa[0].get("batter_name") or ""
        stance = pa[0].get("stance") or "UNKNOWN"
        batter = summary.setdefault(
            batter_code,
            {
                "batter_code": batter_code,
                "batter_name": batter_name,
                "stance": stance,
                "games": set(),
                "pas": 0,
                "ab": 0,
                "hits": 0,
                "hrs": 0,
                "pitches_seen": 0,
                "swings": 0,
                "whiffs": 0,
                "two_strike_pitches": 0,
                "two_strike_swings": 0,
                "two_strike_whiffs": 0,
                "zone_two_strike_whiffs": Counter(),
                "zone_two_strike_pitches": Counter(),
                "pitch_zone_two_strike_whiffs": Counter(),
                "pitch_zone_two_strike_pitches": Counter(),
                "zone_disadvantage": defaultdict(float),
                "zone_pitches": Counter(),
                "family_two_strike_whiffs": Counter(),
                "family_two_strike_pitches": Counter(),
            },
        )

        pa_result = classify_pa_result(pa[-1].get("plate_result_text") or "")
        batter["games"].add(pa[0].get("game_id") or "")
        batter["pas"] += 1
        if is_ab(pa_result):
            batter["ab"] += 1
        if is_hit(pa_result):
            batter["hits"] += 1
        if pa_result == "HR":
            batter["hrs"] += 1

        pre_strikes = 0
        for pitch in pa:
            event_text = pitch.get("event_text") or ""
            current_zone = zone_9(pitch)
            family = pitch_family(pitch.get("pitch_type") or "")
            batter["pitches_seen"] += 1
            batter["zone_pitches"][current_zone] += 1
            batter["zone_disadvantage"][current_zone] += disadvantage_score(pitch)

            zone_bucket = zone_detail[(batter_code, current_zone)]
            zone_bucket["pitches"] += 1
            zone_bucket["disadv_sum"] += disadvantage_score(pitch)

            if is_swing(event_text):
                batter["swings"] += 1
            if is_swinging_miss(event_text):
                batter["whiffs"] += 1

            if pre_strikes >= 2:
                batter["two_strike_pitches"] += 1
                batter["zone_two_strike_pitches"][current_zone] += 1
                batter["family_two_strike_pitches"][family] += 1
                pitch_zone_key = (pitch.get("pitch_type") or "UNKNOWN", current_zone)
                batter["pitch_zone_two_strike_pitches"][pitch_zone_key] += 1
                zone_bucket["two_strike_pitches"] += 1
                if is_swing(event_text):
                    batter["two_strike_swings"] += 1
                if is_swinging_miss(event_text):
                    batter["two_strike_whiffs"] += 1
                    batter["zone_two_strike_whiffs"][current_zone] += 1
                    batter["family_two_strike_whiffs"][family] += 1
                    batter["pitch_zone_two_strike_whiffs"][pitch_zone_key] += 1
                    zone_bucket["two_strike_whiffs"] += 1

            pre_strikes = int(pitch.get("strikes") or pre_strikes)

    summary_rows = []
    for batter in sorted(summary.values(), key=lambda item: (-item["pas"], item["batter_name"])):
        whiff_zone, whiff_zone_count = pick_best(batter["zone_two_strike_whiffs"])
        whiff_pitch_zone, whiff_pitch_zone_count = pick_best(batter["pitch_zone_two_strike_whiffs"], minimum_count=1, fallback=("UNKNOWN", "UNKNOWN"))
        in_zone_pitch_whiff_counter = Counter(
            {key: value for key, value in batter["pitch_zone_two_strike_whiffs"].items() if key[1] not in {"OUT", "UNKNOWN"}}
        )
        in_zone_pitch_zone, in_zone_pitch_zone_count = pick_best(in_zone_pitch_whiff_counter, minimum_count=1, fallback=("UNKNOWN", "UNKNOWN"))
        weak_zone = "UNKNOWN"
        weak_score = None
        if batter["zone_pitches"]:
            weak_zone = max(
                batter["zone_pitches"],
                key=lambda zone: batter["zone_disadvantage"][zone] / max(batter["zone_pitches"][zone], 1),
            )
            weak_score = round(batter["zone_disadvantage"][weak_zone] / max(batter["zone_pitches"][weak_zone], 1), 4)

        weak_family, _ = pick_best(batter["family_two_strike_whiffs"], minimum_count=1)
        whiff_pitch, whiff_pitch_zone_label = whiff_pitch_zone if isinstance(whiff_pitch_zone, tuple) else ("UNKNOWN", "UNKNOWN")
        in_zone_pitch, in_zone_zone_label = in_zone_pitch_zone if isinstance(in_zone_pitch_zone, tuple) else ("UNKNOWN", "UNKNOWN")
        summary_rows.append(
            {
                "batter_code": batter["batter_code"],
                "batter_name": batter["batter_name"],
                "stance": batter["stance"],
                "games": len(batter["games"]),
                "pas": batter["pas"],
                "ab": batter["ab"],
                "hits": batter["hits"],
                "hrs": batter["hrs"],
                "ba": round(batter["hits"] / batter["ab"], 4) if batter["ab"] else 0.0,
                "pitches_seen": batter["pitches_seen"],
                "swing_rate": round(batter["swings"] / batter["pitches_seen"], 4) if batter["pitches_seen"] else 0.0,
                "whiff_rate": round(batter["whiffs"] / batter["swings"], 4) if batter["swings"] else 0.0,
                "two_strike_pitches": batter["two_strike_pitches"],
                "two_strike_whiffs": batter["two_strike_whiffs"],
                "two_strike_whiff_rate": round(batter["two_strike_whiffs"] / batter["two_strike_swings"], 4) if batter["two_strike_swings"] else 0.0,
                "weakest_zone_2025": weak_zone,
                "weakest_zone_score_2025": weak_score if weak_score is not None else 0.0,
                "two_strike_most_whiff_zone_2025": whiff_zone,
                "two_strike_most_whiff_zone_count_2025": whiff_zone_count,
                "two_strike_most_whiff_zone_rate_2025": round(
                    batter["zone_two_strike_whiffs"][whiff_zone] / max(batter["zone_two_strike_pitches"][whiff_zone], 1),
                    4,
                ) if whiff_zone != "UNKNOWN" else 0.0,
                "two_strike_most_whiff_family_2025": weak_family,
                "two_strike_most_whiff_pitch_2025": whiff_pitch,
                "two_strike_most_whiff_pitch_zone_2025": whiff_pitch_zone_label,
                "two_strike_most_whiff_pitch_zone_count_2025": whiff_pitch_zone_count,
                "two_strike_most_whiff_pitch_zone_rate_2025": round(
                    batter["pitch_zone_two_strike_whiffs"][whiff_pitch_zone] / max(batter["pitch_zone_two_strike_pitches"][whiff_pitch_zone], 1),
                    4,
                ) if whiff_pitch != "UNKNOWN" else 0.0,
                "two_strike_in_zone_most_whiff_pitch_2025": in_zone_pitch,
                "two_strike_in_zone_most_whiff_zone_2025": in_zone_zone_label,
                "two_strike_in_zone_most_whiff_count_2025": in_zone_pitch_zone_count,
                "two_strike_in_zone_most_whiff_rate_2025": round(
                    batter["pitch_zone_two_strike_whiffs"][in_zone_pitch_zone] / max(batter["pitch_zone_two_strike_pitches"][in_zone_pitch_zone], 1),
                    4,
                ) if in_zone_pitch != "UNKNOWN" else 0.0,
            }
        )

    detail_rows = []
    for (batter_code, zone_label), bucket in sorted(zone_detail.items()):
        batter_name = next((row["batter_name"] for row in summary_rows if row["batter_code"] == batter_code), "")
        detail_rows.append(
            {
                "batter_code": batter_code,
                "batter_name": batter_name,
                "zone_9": zone_label,
                "pitches_seen": bucket["pitches"],
                "two_strike_pitches": bucket["two_strike_pitches"],
                "two_strike_whiffs": bucket["two_strike_whiffs"],
                "two_strike_whiff_rate": round(bucket["two_strike_whiffs"] / bucket["two_strike_pitches"], 4) if bucket["two_strike_pitches"] else 0.0,
                "disadvantage_score_avg": round(bucket["disadv_sum"] / bucket["pitches"], 4) if bucket["pitches"] else 0.0,
            }
        )
    return summary_rows, detail_rows


def build_pitcher_tables(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    hanwha_rows = [row for row in rows if pitcher_team_code(row) == HANWHA_CODE]
    pa_groups = group_plate_appearances(hanwha_rows)

    faced_by_pitcher = defaultdict(set)
    for pa in pa_groups:
        last = pa[-1]
        pitcher_code = last.get("pitcher_code") or ""
        faced_by_pitcher[pitcher_code].add((last.get("game_id") or "", last.get("pa_number_in_game") or "", last.get("batter_code") or ""))

    summary = {}
    zone_detail = defaultdict(lambda: {"pitches": 0, "strikes": 0, "whiffs": 0, "velo_sum": 0.0, "velo_count": 0})

    for row in hanwha_rows:
        pitcher_code = row.get("pitcher_code") or ""
        pitcher_name = row.get("pitcher_name") or ""
        pitcher = summary.setdefault(
            pitcher_code,
            {
                "pitcher_code": pitcher_code,
                "pitcher_name": pitcher_name,
                "games": set(),
                "pitches": 0,
                "strikes": 0,
                "balls_in_play_whiffs": 0,
                "first_pitch_total": 0,
                "first_pitch_strikes": 0,
                "two_strike_pitches": 0,
                "putaway_whiffs": 0,
                "velo_sum": 0.0,
                "velo_count": 0,
                "pitch_mix": Counter(),
            },
        )
        event_text = row.get("event_text") or ""
        current_zone = zone_9(row)
        speed = to_float(row.get("speed"))

        pitcher["games"].add(row.get("game_id") or "")
        pitcher["pitches"] += 1
        pitcher["pitch_mix"][row.get("pitch_type") or "UNKNOWN"] += 1
        if any(keyword in event_text for keyword in ["스트라이크", "헛스윙", "파울"]):
            pitcher["strikes"] += 1
        if is_swinging_miss(event_text):
            pitcher["balls_in_play_whiffs"] += 1
        if row.get("pitch_num") == "1":
            pitcher["first_pitch_total"] += 1
            if any(keyword in event_text for keyword in ["스트라이크", "헛스윙", "파울"]):
                pitcher["first_pitch_strikes"] += 1

        pre_strikes = max(int(row.get("strikes") or 0) - (1 if any(keyword in event_text for keyword in ["스트라이크", "헛스윙"]) and int(row.get("strikes") or 0) > 0 else 0), 0)
        if pre_strikes >= 2:
            pitcher["two_strike_pitches"] += 1
            if is_swinging_miss(event_text):
                pitcher["putaway_whiffs"] += 1

        if speed is not None:
            pitcher["velo_sum"] += speed
            pitcher["velo_count"] += 1

        zone_bucket = zone_detail[(pitcher_code, current_zone)]
        zone_bucket["pitches"] += 1
        zone_bucket["strikes"] += 1 if any(keyword in event_text for keyword in ["스트라이크", "헛스윙", "파울"]) else 0
        zone_bucket["whiffs"] += 1 if is_swinging_miss(event_text) else 0
        if speed is not None:
            zone_bucket["velo_sum"] += speed
            zone_bucket["velo_count"] += 1

    summary_rows = []
    for pitcher in sorted(summary.values(), key=lambda item: (-item["pitches"], item["pitcher_name"])):
        top_pitch, top_pitch_count = pick_best(pitcher["pitch_mix"], minimum_count=1)
        summary_rows.append(
            {
                "pitcher_code": pitcher["pitcher_code"],
                "pitcher_name": pitcher["pitcher_name"],
                "games": len(pitcher["games"]),
                "batters_faced": len(faced_by_pitcher[pitcher["pitcher_code"]]),
                "pitches": pitcher["pitches"],
                "strike_rate": round(pitcher["strikes"] / pitcher["pitches"], 4) if pitcher["pitches"] else 0.0,
                "whiff_per_pitch": round(pitcher["balls_in_play_whiffs"] / pitcher["pitches"], 4) if pitcher["pitches"] else 0.0,
                "first_pitch_strike_rate": round(pitcher["first_pitch_strikes"] / pitcher["first_pitch_total"], 4) if pitcher["first_pitch_total"] else 0.0,
                "two_strike_pitches": pitcher["two_strike_pitches"],
                "putaway_whiff_rate": round(pitcher["putaway_whiffs"] / pitcher["two_strike_pitches"], 4) if pitcher["two_strike_pitches"] else 0.0,
                "avg_velocity": round(pitcher["velo_sum"] / pitcher["velo_count"], 3) if pitcher["velo_count"] else 0.0,
                "primary_pitch": top_pitch,
                "primary_pitch_pct": round(top_pitch_count / pitcher["pitches"], 4) if pitcher["pitches"] else 0.0,
            }
        )

    detail_rows = []
    for (pitcher_code, zone_label), bucket in sorted(zone_detail.items()):
        pitcher_name = next((row["pitcher_name"] for row in summary_rows if row["pitcher_code"] == pitcher_code), "")
        detail_rows.append(
            {
                "pitcher_code": pitcher_code,
                "pitcher_name": pitcher_name,
                "zone_9": zone_label,
                "pitches": bucket["pitches"],
                "strike_rate": round(bucket["strikes"] / bucket["pitches"], 4) if bucket["pitches"] else 0.0,
                "whiff_per_pitch": round(bucket["whiffs"] / bucket["pitches"], 4) if bucket["pitches"] else 0.0,
                "avg_velocity": round(bucket["velo_sum"] / bucket["velo_count"], 3) if bucket["velo_count"] else 0.0,
            }
        )
    return summary_rows, detail_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Hanwha 2025 batter and pitcher tracking tables.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    batter_summary, batter_zone_detail = build_batter_tables(rows)
    pitcher_summary, pitcher_zone_detail = build_pitcher_tables(rows)

    write_rows(output_dir / "hanwha_batters_2025_summary.csv", batter_summary)
    write_rows(output_dir / "hanwha_batters_2025_zone_detail.csv", batter_zone_detail)
    write_rows(output_dir / "hanwha_pitchers_2025_summary.csv", pitcher_summary)
    write_rows(output_dir / "hanwha_pitchers_2025_zone_detail.csv", pitcher_zone_detail)

    manifest = {
        "input_csv": args.input_csv,
        "team_code": HANWHA_CODE,
        "batter_rows": len(batter_summary),
        "pitcher_rows": len(pitcher_summary),
        "generated_files": [
            "hanwha_batters_2025_summary.csv",
            "hanwha_batters_2025_zone_detail.csv",
            "hanwha_pitchers_2025_summary.csv",
            "hanwha_pitchers_2025_zone_detail.csv",
        ],
    }
    (output_dir / "hanwha_team_tables_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
