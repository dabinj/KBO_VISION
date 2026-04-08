#!/usr/bin/env python3

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


SCHEDULE_URL = "https://api-gw.sports.naver.com/schedule/games"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.sports.naver.com/",
}
DEFAULT_OUTPUT_DIR = Path("data/schedule")
SESSION = requests.Session()
SESSION.trust_env = False


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def fetch_schedule_for_day(target_date: date) -> list[dict]:
    params = {
        "fields": "basic,schedule,baseball,manualRelayUrl",
        "upperCategoryId": "kbaseball",
        "fromDate": target_date.isoformat(),
        "toDate": target_date.isoformat(),
        "size": 500,
    }
    response = SESSION.get(SCHEDULE_URL, headers=HEADERS, params=params, timeout=20)
    response.raise_for_status()
    response.encoding = "utf-8"
    payload = response.json()
    return payload["result"]["games"]


def normalize_game(row: dict) -> dict:
    return {
        "game_id": row.get("gameId"),
        "game_date": row.get("gameDate"),
        "game_datetime": row.get("gameDateTime"),
        "category_id": row.get("categoryId"),
        "status_code": row.get("statusCode"),
        "status_info": row.get("statusInfo"),
        "stadium": row.get("stadium"),
        "home_team_code": row.get("homeTeamCode"),
        "home_team_name": row.get("homeTeamName"),
        "away_team_code": row.get("awayTeamCode"),
        "away_team_name": row.get("awayTeamName"),
        "home_score": row.get("homeTeamScore"),
        "away_score": row.get("awayTeamScore"),
        "home_starter_name": row.get("homeStarterName"),
        "away_starter_name": row.get("awayStarterName"),
        "win_pitcher_name": row.get("winPitcherName"),
        "lose_pitcher_name": row.get("losePitcherName"),
        "broad_channel": row.get("broadChannel"),
        "manual_relay_url": row.get("manualRelayUrl"),
        "round_code": row.get("roundCode"),
        "title": row.get("title"),
    }


def collect_kbo_games(start_date: date, end_date: date) -> tuple[list[dict], list[dict]]:
    raw_daily = []
    kbo_games = []

    for target_date in daterange(start_date, end_date):
        games = fetch_schedule_for_day(target_date)
        raw_daily.append({"date": target_date.isoformat(), "games": games})
        for game in games:
            if game.get("categoryId") != "kbo":
                continue
            kbo_games.append(normalize_game(game))

    kbo_games.sort(key=lambda row: (row["game_date"], row["game_datetime"], row["game_id"]))
    return raw_daily, kbo_games


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch KBO game schedule list from Naver Sports.")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    if end_date < start_date:
        raise SystemExit("end-date must be on or after start-date")

    output_dir = Path(args.output_dir)
    raw_daily, kbo_games = collect_kbo_games(start_date, end_date)

    stem = f"kbo_schedule_{start_date.isoformat()}_{end_date.isoformat()}"
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"

    write_json(json_path, raw_daily)
    write_csv(csv_path, kbo_games)

    print(f"start_date: {start_date.isoformat()}")
    print(f"end_date: {end_date.isoformat()}")
    print(f"kbo_games: {len(kbo_games)}")
    print(f"saved_json: {json_path}")
    print(f"saved_csv: {csv_path}")
    print("first_5_games:")
    for row in kbo_games[:5]:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
