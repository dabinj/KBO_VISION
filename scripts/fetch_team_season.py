#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path

from fetch_kbo_schedule import collect_kbo_games, parse_date
from test_naver_relay import (
    collect_relay_payloads,
    fetch_game,
    merge_pitch_rows,
    merge_player_maps,
    parse_current_inning,
    save_csv,
    save_json,
)


DEFAULT_OUTPUT_ROOT = Path("data/seasons")


def filter_team_games(rows: list[dict], team_code: str, round_code: str | None) -> list[dict]:
    team_code = team_code.upper()
    filtered = []
    for row in rows:
        if round_code and row.get("round_code") != round_code:
            continue
        if row.get("home_team_code") == team_code or row.get("away_team_code") == team_code:
            filtered.append(row)
    return filtered


def write_rows_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_season_pitch_rows(game_row: dict, pitch_rows: list[dict]) -> list[dict]:
    enriched = []
    for row in pitch_rows:
        merged = {
            "game_id": game_row.get("game_id"),
            "game_date": game_row.get("game_date"),
            "game_datetime": game_row.get("game_datetime"),
            "home_team_code": game_row.get("home_team_code"),
            "home_team_name": game_row.get("home_team_name"),
            "away_team_code": game_row.get("away_team_code"),
            "away_team_name": game_row.get("away_team_name"),
            **row,
        }
        enriched.append(merged)
    return enriched


def is_cancelled_game(game_row: dict) -> bool:
    return game_row.get("status_code") == "BEFORE" and game_row.get("status_info") == "경기취소"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch one KBO team's full-season game relays and pitch tables.")
    parser.add_argument("--season-year", type=int, required=True, help="Season year, e.g. 2025")
    parser.add_argument("--team-code", required=True, help="Team code, e.g. HH")
    parser.add_argument("--start-date", help="Optional explicit start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Optional explicit end date YYYY-MM-DD")
    parser.add_argument(
        "--round-code",
        default="kbo_r",
        help="Round code filter. Use kbo_r for regular season, kbo_e for exhibition, or empty string for all.",
    )
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output root directory")
    parser.add_argument("--limit-games", type=int, help="Optional limit for testing")
    args = parser.parse_args()

    season_year = args.season_year
    team_code = args.team_code.upper()
    start_date = parse_date(args.start_date) if args.start_date else parse_date(f"{season_year}-01-01")
    end_date = parse_date(args.end_date) if args.end_date else parse_date(f"{season_year}-12-31")
    round_code = args.round_code.strip() or None

    output_root = Path(args.output_root) / f"{season_year}_{team_code}"
    raw_dir = output_root / "raw"
    pitch_dir = output_root / "pitch"
    output_root.mkdir(parents=True, exist_ok=True)

    raw_daily, kbo_games = collect_kbo_games(start_date, end_date)
    team_games = filter_team_games(kbo_games, team_code, round_code)
    if args.limit_games is not None:
        team_games = team_games[: args.limit_games]

    save_json(output_root / f"schedule_{season_year}_{team_code}.json", raw_daily)
    write_rows_csv(output_root / f"games_{season_year}_{team_code}.csv", team_games)

    all_pitch_rows = []
    fetch_log = []

    for index, game_row in enumerate(team_games, start=1):
        game_id = game_row["game_id"]
        if is_cancelled_game(game_row):
            fetch_log.append(
                {
                    "game_id": game_id,
                    "game_date": game_row.get("game_date"),
                    "status": "skipped_cancelled",
                    "game_index": index,
                }
            )
            print(
                json.dumps(
                    {
                        "game_index": index,
                        "game_id": game_id,
                        "status": "skipped_cancelled",
                    },
                    ensure_ascii=False,
                )
            )
            continue

        try:
            game_payload = fetch_game(game_id)
            current_inning = parse_current_inning(game_payload["result"]["game"]["currentInning"])
            innings = list(range(1, current_inning + 1))
            payloads = collect_relay_payloads(game_id, innings)
            relay_blocks = [
                payload.get("result", {}).get("textRelayData")
                for payload in payloads
                if payload.get("result", {}).get("textRelayData")
            ]
            if not relay_blocks:
                fetch_log.append(
                    {
                        "game_id": game_id,
                        "game_date": game_row.get("game_date"),
                        "status": "skipped_no_relay",
                        "innings": current_inning,
                        "game_index": index,
                    }
                )
                print(
                    json.dumps(
                        {
                            "game_index": index,
                            "game_id": game_id,
                            "status": "skipped_no_relay",
                            "innings": current_inning,
                        },
                        ensure_ascii=False,
                    )
                )
                continue

            player_map = merge_player_maps(relay_blocks)
            pitch_rows = merge_pitch_rows(relay_blocks, player_map)

            save_json(raw_dir / f"naver_relay_all_innings_{game_id}.json", payloads)
            save_csv(pitch_dir / f"naver_relay_pitches_all_innings_{game_id}.csv", pitch_rows)

            all_pitch_rows.extend(build_season_pitch_rows(game_row, pitch_rows))
            fetch_log.append(
                {
                    "game_id": game_id,
                    "game_date": game_row.get("game_date"),
                    "status": "ok",
                    "innings": current_inning,
                    "pitch_rows": len(pitch_rows),
                    "game_index": index,
                }
            )
            print(
                json.dumps(
                    {
                        "game_index": index,
                        "game_id": game_id,
                        "status": "ok",
                        "innings": current_inning,
                        "pitch_rows": len(pitch_rows),
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:
            fetch_log.append(
                {
                    "game_id": game_id,
                    "game_date": game_row.get("game_date"),
                    "status": "error",
                    "error": str(exc),
                    "game_index": index,
                }
            )
            print(
                json.dumps(
                    {
                        "game_index": index,
                        "game_id": game_id,
                        "status": "error",
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )

    save_json(output_root / f"fetch_log_{season_year}_{team_code}.json", fetch_log)
    save_csv(output_root / f"pitches_{season_year}_{team_code}.csv", all_pitch_rows)

    print(f"season_year: {season_year}")
    print(f"team_code: {team_code}")
    print(f"round_code: {round_code}")
    print(f"team_games: {len(team_games)}")
    print(f"season_pitch_rows: {len(all_pitch_rows)}")
    print(f"output_root: {output_root}")
    print(f"games_csv: {output_root / f'games_{season_year}_{team_code}.csv'}")
    print(f"season_pitch_csv: {output_root / f'pitches_{season_year}_{team_code}.csv'}")
    print(f"fetch_log_json: {output_root / f'fetch_log_{season_year}_{team_code}.json'}")


if __name__ == "__main__":
    main()
