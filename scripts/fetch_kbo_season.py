#!/usr/bin/env python3

import argparse
import csv
import json
import time
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


def write_rows_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_rows_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def dedupe_games_by_id(rows: list[dict]) -> list[dict]:
    deduped = []
    seen_game_ids = set()
    for row in rows:
        game_id = row.get("game_id")
        if not game_id or game_id in seen_game_ids:
            continue
        seen_game_ids.add(game_id)
        deduped.append(row)
    return deduped


def filter_round_code(rows: list[dict], round_code: str | None) -> list[dict]:
    if not round_code:
        return rows
    return [row for row in rows if row.get("round_code") == round_code]


def build_enriched_pitch_rows(game_row: dict, pitch_rows: list[dict]) -> list[dict]:
    enriched = []
    for row in pitch_rows:
        enriched.append(
            {
                "game_id": game_row.get("game_id"),
                "game_date": game_row.get("game_date"),
                "game_datetime": game_row.get("game_datetime"),
                "home_team_code": game_row.get("home_team_code"),
                "home_team_name": game_row.get("home_team_name"),
                "away_team_code": game_row.get("away_team_code"),
                "away_team_name": game_row.get("away_team_name"),
                **row,
            }
        )
    return enriched


def is_cancelled_game(game_row: dict) -> bool:
    status_code = (game_row.get("status_code") or "").upper()
    status_info = (game_row.get("status_info") or "").strip()
    if "CANCEL" in status_code:
        return True
    return "취소" in status_info


def fetch_game_payloads_with_retry(game_id: str, max_retries: int, retry_delay: float) -> tuple[list[dict], int]:
    attempt = 0
    while True:
        attempt += 1
        try:
            game_payload = fetch_game(game_id)
            current_inning = parse_current_inning(game_payload["result"]["game"]["currentInning"])
            innings = list(range(1, current_inning + 1))
            payloads = collect_relay_payloads(game_id, innings)
            return payloads, current_inning
        except Exception:
            if attempt >= max_retries:
                raise
            time.sleep(retry_delay)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch full-league KBO game relays and pitch tables for a season.")
    parser.add_argument("--season-year", type=int, required=True, help="Season year, e.g. 2024")
    parser.add_argument("--start-date", help="Optional explicit start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Optional explicit end date YYYY-MM-DD")
    parser.add_argument(
        "--round-code",
        default="kbo_r",
        help="Round code filter. Use kbo_r for regular season, kbo_e for exhibition, or empty string for all.",
    )
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output root directory")
    parser.add_argument("--limit-games", type=int, help="Optional limit for testing")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse existing per-game raw/pitch files when they are already present.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Force refetch even when per-game outputs already exist.",
    )
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries per game fetch")
    parser.add_argument("--retry-delay-sec", type=float, default=1.0, help="Delay between retries in seconds")
    args = parser.parse_args()

    season_year = args.season_year
    start_date = parse_date(args.start_date) if args.start_date else parse_date(f"{season_year}-01-01")
    end_date = parse_date(args.end_date) if args.end_date else parse_date(f"{season_year}-12-31")
    if end_date < start_date:
        raise SystemExit("end-date must be on or after start-date")

    round_code = args.round_code.strip() or None
    output_root = Path(args.output_root) / f"{season_year}_FULL"
    raw_dir = output_root / "raw"
    pitch_dir = output_root / "pitch"
    output_root.mkdir(parents=True, exist_ok=True)

    raw_daily, kbo_games = collect_kbo_games(start_date, end_date)
    games = dedupe_games_by_id(filter_round_code(kbo_games, round_code))
    if args.limit_games is not None:
        games = games[: args.limit_games]

    save_json(output_root / f"schedule_{season_year}_FULL.json", raw_daily)
    write_rows_csv(output_root / f"games_{season_year}_FULL.csv", games)

    all_pitch_rows = []
    fetch_log = []

    for index, game_row in enumerate(games, start=1):
        game_id = game_row["game_id"]
        raw_path = raw_dir / f"naver_relay_all_innings_{game_id}.json"
        pitch_path = pitch_dir / f"naver_relay_pitches_all_innings_{game_id}.csv"

        if is_cancelled_game(game_row):
            fetch_log.append(
                {
                    "game_id": game_id,
                    "game_date": game_row.get("game_date"),
                    "status": "skipped_cancelled",
                    "game_index": index,
                }
            )
            print(json.dumps({"game_index": index, "game_id": game_id, "status": "skipped_cancelled"}, ensure_ascii=False))
            continue

        try:
            if args.reuse_existing and not args.overwrite_existing and raw_path.exists() and pitch_path.exists():
                pitch_rows = load_rows_csv(pitch_path)
                all_pitch_rows.extend(build_enriched_pitch_rows(game_row, pitch_rows))
                fetch_log.append(
                    {
                        "game_id": game_id,
                        "game_date": game_row.get("game_date"),
                        "status": "reused_existing",
                        "pitch_rows": len(pitch_rows),
                        "game_index": index,
                    }
                )
                print(
                    json.dumps(
                        {
                            "game_index": index,
                            "game_id": game_id,
                            "status": "reused_existing",
                            "pitch_rows": len(pitch_rows),
                        },
                        ensure_ascii=False,
                    )
                )
                continue

            payloads, current_inning = fetch_game_payloads_with_retry(
                game_id=game_id,
                max_retries=max(args.max_retries, 1),
                retry_delay=max(args.retry_delay_sec, 0.0),
            )
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

            save_json(raw_path, payloads)
            save_csv(pitch_path, pitch_rows)

            all_pitch_rows.extend(build_enriched_pitch_rows(game_row, pitch_rows))
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

    save_json(output_root / f"fetch_log_{season_year}_FULL.json", fetch_log)
    save_csv(output_root / f"pitches_{season_year}_FULL.csv", all_pitch_rows)

    print(f"season_year: {season_year}")
    print(f"start_date: {start_date.isoformat()}")
    print(f"end_date: {end_date.isoformat()}")
    print(f"round_code: {round_code}")
    print(f"games: {len(games)}")
    print(f"pitch_rows: {len(all_pitch_rows)}")
    print(f"reuse_existing: {args.reuse_existing and not args.overwrite_existing}")
    print(f"max_retries: {max(args.max_retries, 1)}")
    print(f"output_root: {output_root}")
    print(f"games_csv: {output_root / f'games_{season_year}_FULL.csv'}")
    print(f"pitch_csv: {output_root / f'pitches_{season_year}_FULL.csv'}")
    print(f"fetch_log_json: {output_root / f'fetch_log_{season_year}_FULL.json'}")


if __name__ == "__main__":
    main()
