#!/usr/bin/env python3

import argparse
import csv
import json
import re
from pathlib import Path


ADDED_FIELDS = [
    "batter_season_hra",
    "batter_today_hra",
    "batter_today_ab",
    "batter_today_hit",
    "batter_today_bb",
    "batter_today_hr",
    "batter_today_rbi",
    "batter_today_so",
    "batter_prev_season_hra",
]


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_payloads(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return [payload]


def infer_game_id(row: dict, input_csv: Path) -> str:
    game_id = row.get("game_id") or ""
    if game_id:
        return game_id

    match = re.search(r"(\d{8}[A-Z]{4}\d{5})", input_csv.name)
    if match:
        return match.group(1)

    pitch_id = row.get("pitch_id") or ""
    if pitch_id.startswith("20"):
        return pitch_id[:6]

    return ""


def infer_season_year(row: dict, game_id: str) -> int | None:
    game_date = row.get("game_date") or ""
    if len(game_date) >= 4 and game_date[:4].isdigit():
        return int(game_date[:4])
    if len(game_id) >= 4 and game_id[-4:].isdigit():
        return int(game_id[-4:])
    return None


def extract_batter_snapshot(record: dict | None) -> dict:
    record = record or {}
    return {
        "batter_season_hra": record.get("seasonHra", ""),
        "batter_today_hra": record.get("todayHra", ""),
        "batter_today_ab": record.get("ab", ""),
        "batter_today_hit": record.get("hit", ""),
        "batter_today_bb": record.get("bb", ""),
        "batter_today_hr": record.get("hr", ""),
        "batter_today_rbi": record.get("rbi", ""),
        "batter_today_so": record.get("so", ""),
    }


def build_pitch_snapshot_map(raw_path: Path) -> dict[str, dict]:
    payloads = load_payloads(raw_path)
    option_items = []
    for payload in payloads:
        relay = payload.get("result", {}).get("textRelayData", {})
        for text_relay in relay.get("textRelays", []):
            for option in text_relay.get("textOptions", []):
                option_items.append(option)

    option_items.sort(key=lambda option: option.get("seqno") or 0)
    latest_snapshot_by_batter: dict[str, dict] = {}
    pitch_snapshot_map: dict[str, dict] = {}

    for option in option_items:
        current = option.get("currentGameState")
        if not isinstance(current, dict):
            continue

        batter_code = str(current.get("batter") or "")
        if not batter_code:
            continue

        if isinstance(option.get("batterRecord"), dict):
            latest_snapshot_by_batter[batter_code] = extract_batter_snapshot(option["batterRecord"])

        pitch_id = option.get("ptsPitchId")
        if pitch_id:
            pitch_snapshot_map[str(pitch_id)] = latest_snapshot_by_batter.get(
                batter_code,
                extract_batter_snapshot(None),
            )

    return pitch_snapshot_map


def load_prev_season_lookup(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        return {
            (row.get("player_id") or ""): (row.get("hitter_hra") or "")
            for row in rows
            if row.get("player_id")
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Augment pitch CSV with batter snapshot stats from raw relay JSON and previous-season HRA."
    )
    parser.add_argument("--input-csv", required=True, help="Pitch CSV with pitch_id and batter_code")
    parser.add_argument("--raw-dir", required=True, help="Directory containing naver_relay_all_innings_{game_id}.json")
    parser.add_argument("--records-dir", default="data/records", help="Directory containing season hitter stat CSVs")
    parser.add_argument("--output-csv", required=True, help="Output CSV path")
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    raw_dir = Path(args.raw_dir)
    records_dir = Path(args.records_dir)
    rows = read_rows(input_csv)

    snapshot_maps: dict[str, dict[str, dict]] = {}
    prev_season_lookups: dict[int, dict[str, str]] = {}
    augmented = []

    for row in rows:
        game_id = infer_game_id(row, input_csv)
        pitch_id = row.get("pitch_id") or ""
        batter_code = row.get("batter_code") or ""

        snapshot = {field: "" for field in ADDED_FIELDS if field != "batter_prev_season_hra"}
        if game_id:
            if game_id not in snapshot_maps:
                raw_path = raw_dir / f"naver_relay_all_innings_{game_id}.json"
                snapshot_maps[game_id] = build_pitch_snapshot_map(raw_path) if raw_path.exists() else {}
            snapshot = snapshot_maps[game_id].get(pitch_id, snapshot)

        prev_hra = ""
        season_year = infer_season_year(row, game_id)
        if season_year is not None:
            prev_season = season_year - 1
            if prev_season not in prev_season_lookups:
                prev_path = records_dir / f"kbo_hitter_stats_{prev_season}_all_teams.csv"
                prev_season_lookups[prev_season] = load_prev_season_lookup(prev_path)
            prev_hra = prev_season_lookups[prev_season].get(batter_code, "")

        augmented.append(
            {
                **row,
                "batter_season_hra": snapshot.get("batter_season_hra", ""),
                "batter_today_hra": snapshot.get("batter_today_hra", ""),
                "batter_today_ab": snapshot.get("batter_today_ab", ""),
                "batter_today_hit": snapshot.get("batter_today_hit", ""),
                "batter_today_bb": snapshot.get("batter_today_bb", ""),
                "batter_today_hr": snapshot.get("batter_today_hr", ""),
                "batter_today_rbi": snapshot.get("batter_today_rbi", ""),
                "batter_today_so": snapshot.get("batter_today_so", ""),
                "batter_prev_season_hra": prev_hra,
            }
        )

    write_rows(Path(args.output_csv), augmented)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(augmented)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
