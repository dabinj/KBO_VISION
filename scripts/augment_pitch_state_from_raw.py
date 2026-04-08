#!/usr/bin/env python3

import argparse
import csv
import json
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


def normalize_base(value: str | None) -> str:
    if value and value not in {"", "0"}:
        return "1"
    return "0"


def runner_state(base1: str, base2: str, base3: str) -> str:
    return f"{base1}{base2}{base3}"


def load_pitch_state_map(raw_path: Path) -> dict[str, dict]:
    payloads = json.loads(raw_path.read_text(encoding="utf-8"))
    state_map = {}
    for payload in payloads:
        relay = payload.get("result", {}).get("textRelayData", {})
        for text_relay in relay.get("textRelays", []):
            for option in text_relay.get("textOptions", []):
                pitch_id = option.get("ptsPitchId")
                current = option.get("currentGameState")
                if not pitch_id or not isinstance(current, dict):
                    continue
                b1 = normalize_base(current.get("base1"))
                b2 = normalize_base(current.get("base2"))
                b3 = normalize_base(current.get("base3"))
                state_map[str(pitch_id)] = {
                    "base1_state": b1,
                    "base2_state": b2,
                    "base3_state": b3,
                    "runner_state": runner_state(b1, b2, b3),
                    "runners_on": str(int(b1) + int(b2) + int(b3)),
                    "home_score": current.get("homeScore") or "0",
                    "away_score": current.get("awayScore") or "0",
                }
    return state_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment pitch CSV with runner state and score state from raw relay JSON.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    raw_dir = Path(args.raw_dir)
    state_maps = {}
    augmented = []

    for row in rows:
        game_id = row.get("game_id") or ""
        pitch_id = row.get("pitch_id") or ""
        if game_id not in state_maps:
            raw_path = raw_dir / f"naver_relay_all_innings_{game_id}.json"
            state_maps[game_id] = load_pitch_state_map(raw_path) if raw_path.exists() else {}
        state = state_maps[game_id].get(pitch_id, {})

        home_score = int(state.get("home_score", "0") or 0)
        away_score = int(state.get("away_score", "0") or 0)
        is_home_pitcher = row.get("home_team_code") == "SK" and row.get("pitcher_name") == row.get("pitcher_name")
        # Determine defense side from inning half: top(0) -> home team fields, bottom(1) -> away team fields.
        half = row.get("half")
        if half == "0":
            pitcher_score = home_score
            batter_score = away_score
        else:
            pitcher_score = away_score
            batter_score = home_score

        augmented.append(
            {
                **row,
                "base1_state": state.get("base1_state", "0"),
                "base2_state": state.get("base2_state", "0"),
                "base3_state": state.get("base3_state", "0"),
                "runner_state": state.get("runner_state", "000"),
                "runners_on": state.get("runners_on", "0"),
                "home_score": str(home_score),
                "away_score": str(away_score),
                "pitcher_score": str(pitcher_score),
                "batter_score": str(batter_score),
                "score_diff_pitcher": str(pitcher_score - batter_score),
            }
        )

    write_rows(Path(args.output_csv), augmented)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(augmented)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
