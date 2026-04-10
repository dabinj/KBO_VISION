#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path

import requests


API_BASE_URL = "https://api-gw.sports.naver.com/statistics/categories/kbo/seasons/{season_code}/players"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.sports.naver.com/",
}
DEFAULT_OUTPUT_DIR = Path("data/records")
DEFAULT_TEAM_CODES = ["HH", "OB", "LG", "LT", "HT", "SS", "SK", "NC", "WO", "KT"]
SESSION = requests.Session()
SESSION.trust_env = False

SLIM_FIELDS = [
    "season_id",
    "year",
    "game_type",
    "team_code",
    "team_name",
    "player_id",
    "player_name",
    "back_number",
    "position",
    "ranking",
    "is_qualified",
    "hitter_hra",
    "hitter_rbi",
    "hitter_run",
    "hitter_hr",
    "hitter_hit",
    "hitter_h2",
    "hitter_h3",
    "hitter_game_count",
    "hitter_ab",
    "hitter_sb",
    "hitter_cs",
    "hitter_bb",
    "hitter_hp",
    "hitter_kk",
    "hitter_gd",
    "hitter_obp",
    "hitter_slg",
    "hitter_ops",
    "hitter_isop",
    "hitter_babip",
    "hitter_woba",
    "hitter_wrc_plus",
    "hitter_wpa",
    "hitter_war",
]


def fetch_team_hitter_stats(season_code: str, team_code: str, page_size: int = 100) -> tuple[list[dict], str | None]:
    page = 1
    all_rows: list[dict] = []
    game_type = None

    while True:
        params = {
            "teamCode": team_code,
            "sortField": "hra",
            "sortDirection": "desc",
            "page": page,
            "pageSize": page_size,
            "playerType": "HITTER",
        }
        response = SESSION.get(
            API_BASE_URL.format(season_code=season_code),
            headers=HEADERS,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result", {})
        rows = result.get("seasonPlayerStats", [])

        if game_type is None:
            game_type = result.get("gameType")

        if not rows:
            break

        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        page += 1

    return all_rows, game_type


def parse_profile(value: str | None) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def normalize_row(row: dict, team_code: str, game_type: str | None) -> dict:
    profile = parse_profile(row.get("profile"))
    return {
        "season_id": row.get("seasonId"),
        "year": row.get("year"),
        "game_type": game_type,
        "team_code": team_code,
        "team_name": row.get("teamName"),
        "player_id": row.get("playerId"),
        "player_name": row.get("playerName"),
        "back_number": row.get("backNumber"),
        "position": profile.get("position"),
        "ranking": row.get("ranking"),
        "is_qualified": row.get("isQualified"),
        "hitter_hra": row.get("hitterHra"),
        "hitter_rbi": row.get("hitterRbi"),
        "hitter_run": row.get("hitterRun"),
        "hitter_hr": row.get("hitterHr"),
        "hitter_hit": row.get("hitterHit"),
        "hitter_h2": row.get("hitterH2"),
        "hitter_h3": row.get("hitterH3"),
        "hitter_game_count": row.get("hitterGameCount"),
        "hitter_ab": row.get("hitterAb"),
        "hitter_sb": row.get("hitterSb"),
        "hitter_cs": row.get("hitterCs"),
        "hitter_bb": row.get("hitterBb"),
        "hitter_hp": row.get("hitterHp"),
        "hitter_kk": row.get("hitterKk"),
        "hitter_gd": row.get("hitterGd"),
        "hitter_obp": row.get("hitterObp"),
        "hitter_slg": row.get("hitterSlg"),
        "hitter_ops": row.get("hitterOps"),
        "hitter_isop": row.get("hitterIsop"),
        "hitter_babip": row.get("hitterBabip"),
        "hitter_woba": row.get("hitterWoba"),
        "hitter_wrc_plus": row.get("hitterWrcPlus"),
        "hitter_wpa": row.get("hitterWpa"),
        "hitter_war": row.get("hitterWar"),
    }


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


def build_slim_json(rows: list[dict], team_codes: list[str], season_code: str) -> dict:
    grouped = []
    for team_code in team_codes:
        team_rows = [row for row in rows if row["team_code"] == team_code]
        grouped.append(
            {
                "team_code": team_code,
                "team_name": team_rows[0]["team_name"] if team_rows else None,
                "player_count": len(team_rows),
                "players": team_rows,
            }
        )
    return {
        "season_code": season_code,
        "team_count": len(grouped),
        "player_count": len(rows),
        "teams": grouped,
    }


def collect_season_rows(season_code: str, team_codes: list[str]) -> list[dict]:
    normalized_rows = []

    for team_code in team_codes:
        rows, game_type = fetch_team_hitter_stats(season_code, team_code)
        normalized_rows.extend(normalize_row(row, team_code, game_type) for row in rows)

    normalized_rows.sort(
        key=lambda row: (
            row["team_code"] or "",
            row["ranking"] is None,
            row["ranking"] if row["ranking"] is not None else 999999,
            -(row["hitter_hra"] or 0),
            row["player_name"] or "",
        )
    )
    return normalized_rows


def save_season_outputs(output_dir: Path, season_code: str, team_codes: list[str], rows: list[dict]) -> tuple[Path, Path]:
    stem = f"kbo_hitter_stats_{season_code}_all_teams"
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    write_json(json_path, build_slim_json(rows, team_codes, season_code))
    write_csv(csv_path, rows)
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch KBO hitter stats by team from Naver Sports.")
    parser.add_argument("--season-code", default="2025", help="Single season code, e.g. 2025")
    parser.add_argument(
        "--season-codes",
        nargs="+",
        help="Multiple season codes, e.g. 2024 2025 2026",
    )
    parser.add_argument(
        "--team-codes",
        nargs="+",
        default=DEFAULT_TEAM_CODES,
        help="Team codes to fetch. Default: all 10 KBO teams",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    season_codes = args.season_codes or [args.season_code]

    print(f"season_codes: {','.join(season_codes)}")
    print(f"team_codes: {','.join(args.team_codes)}")
    print(f"teams_fetched: {len(args.team_codes)}")

    for season_code in season_codes:
        normalized_rows = collect_season_rows(season_code, args.team_codes)
        json_path, csv_path = save_season_outputs(output_dir, season_code, args.team_codes, normalized_rows)
        print(f"season_code: {season_code}")
        print(f"players_fetched: {len(normalized_rows)}")
        print(f"saved_json: {json_path}")
        print(f"saved_csv: {csv_path}")


if __name__ == "__main__":
    main()
