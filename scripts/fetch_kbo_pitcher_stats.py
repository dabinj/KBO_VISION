#!/usr/bin/env python3

import argparse
import csv
import json
import re
from html import unescape
from pathlib import Path

import requests


URL = "https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic1.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.koreabaseball.com/",
}
DEFAULT_OUTPUT_DIR = Path("data/records")
SESSION = requests.Session()
SESSION.trust_env = False

HIDDEN_FIELDS = [
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
]

FORM_PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    return " ".join(text.split()).strip()


def extract_hidden_fields(html: str) -> dict[str, str]:
    values = {}
    for name in HIDDEN_FIELDS:
        match = re.search(rf'name="{re.escape(name)}"[^>]*value="([^"]*)"', html)
        values[name] = match.group(1) if match else ""
    return values


def parse_rows_from_html(html: str) -> list[dict]:
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, flags=re.S)
    if not tbody_match:
        return []

    rows = []
    tbody = tbody_match.group(1)
    for tr_match in re.finditer(r"<tr>(.*?)</tr>", tbody, flags=re.S):
        tr_html = tr_match.group(1)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr_html, flags=re.S)
        if len(tds) < 19:
            continue

        player_anchor = re.search(r'PitcherDetail/Basic\.aspx\?playerId=(\d+)[^"]*"[^>]*>(.*?)</a>', tds[1], flags=re.S)
        player_id = player_anchor.group(1) if player_anchor else ""
        player_name = clean_html(player_anchor.group(2) if player_anchor else tds[1])

        row = {
            "rank": clean_html(tds[0]),
            "player_id": player_id,
            "player_name": player_name,
            "team_name": clean_html(tds[2]),
            "era": clean_html(tds[3]),
            "g": clean_html(tds[4]),
            "w": clean_html(tds[5]),
            "l": clean_html(tds[6]),
            "sv": clean_html(tds[7]),
            "hld": clean_html(tds[8]),
            "wpct": clean_html(tds[9]),
            "ip": clean_html(tds[10]),
            "h": clean_html(tds[11]),
            "hr": clean_html(tds[12]),
            "bb": clean_html(tds[13]),
            "hbp": clean_html(tds[14]),
            "so": clean_html(tds[15]),
            "r": clean_html(tds[16]),
            "er": clean_html(tds[17]),
            "whip": clean_html(tds[18]),
        }
        rows.append(row)
    return rows


def parse_current_page(html: str) -> int:
    match = re.search(rf'name="{re.escape(FORM_PREFIX + "hfPage")}"[^>]*value="(\d+)"', html)
    return int(match.group(1)) if match else 1


def next_event_target(html: str, current_page: int) -> str | None:
    next_page = current_page + 1
    target = f"{FORM_PREFIX}ucPager$btnNo{next_page}"
    if target in html:
        return target
    next_chunk = f"{FORM_PREFIX}ucPager$btnNext"
    if next_chunk in html:
        return next_chunk
    return None


def build_base_form(hidden: dict[str, str], season_code: str) -> dict[str, str]:
    form = dict(hidden)
    form.update(
        {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            FORM_PREFIX + "ddlSeason$ddlSeason": season_code,
            FORM_PREFIX + "ddlSeries$ddlSeries": "0",
            FORM_PREFIX + "ddlTeam$ddlTeam": "",
            FORM_PREFIX + "ddlSituation$ddlSituation": "",
            FORM_PREFIX + "ddlSituationDetail$ddlSituationDetail": "",
            FORM_PREFIX + "hfPage": "1",
            FORM_PREFIX + "hfOrderByCol": "INN2_CN",
            FORM_PREFIX + "hfOrderBy": "DESC",
        }
    )
    return form


def fetch_season_html(season_code: str) -> str:
    initial = SESSION.get(URL, headers=HEADERS, timeout=20)
    initial.raise_for_status()
    html = initial.text
    hidden = extract_hidden_fields(html)
    form = build_base_form(hidden, season_code)
    form["__EVENTTARGET"] = FORM_PREFIX + "ddlSeason$ddlSeason"

    response = SESSION.post(URL, headers=HEADERS, data=form, timeout=20)
    response.raise_for_status()
    return response.text


def fetch_all_pages_for_season(season_code: str) -> list[dict]:
    html = fetch_season_html(season_code)
    all_rows: list[dict] = []
    seen_pages: set[int] = set()

    while True:
        page = parse_current_page(html)
        if page in seen_pages:
            break
        seen_pages.add(page)
        all_rows.extend(parse_rows_from_html(html))

        target = next_event_target(html, page)
        if not target:
            break

        hidden = extract_hidden_fields(html)
        form = build_base_form(hidden, season_code)
        form["__EVENTTARGET"] = target
        form[FORM_PREFIX + "hfPage"] = str(page)
        response = SESSION.post(URL, headers=HEADERS, data=form, timeout=20)
        response.raise_for_status()
        html = response.text

    deduped: dict[str, dict] = {}
    for row in all_rows:
        player_id = row.get("player_id") or row.get("player_name") or ""
        deduped[player_id] = row
    return sorted(deduped.values(), key=lambda row: ip_to_outs(row.get("ip", "")), reverse=True)


def ip_to_outs(ip_text: str) -> int:
    if not ip_text:
        return 0
    parts = ip_text.split()
    if len(parts) == 1:
        try:
            return int(parts[0]) * 3
        except ValueError:
            return 0
    try:
        whole = int(parts[0])
    except ValueError:
        return 0
    frac = parts[1]
    frac_outs = {"1/3": 1, "2/3": 2}.get(frac, 0)
    return whole * 3 + frac_outs


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_payload(season_code: str, rows: list[dict]) -> dict:
    return {
        "season_code": season_code,
        "source": URL,
        "player_count": len(rows),
        "players": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch official KBO pitcher basic stats by season.")
    parser.add_argument("--season-code", default="2025")
    parser.add_argument("--season-codes", nargs="+")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    season_codes = args.season_codes or [args.season_code]
    print(f"season_codes: {','.join(season_codes)}")

    for season_code in season_codes:
        rows = fetch_all_pages_for_season(season_code)
        stem = f"kbo_pitcher_stats_{season_code}_all_teams"
        csv_path = output_dir / f"{stem}.csv"
        json_path = output_dir / f"{stem}.json"
        write_csv(csv_path, rows)
        write_json(json_path, build_payload(season_code, rows))
        print(f"season_code: {season_code}")
        print(f"players_fetched: {len(rows)}")
        print(f"saved_csv: {csv_path}")
        print(f"saved_json: {json_path}")


if __name__ == "__main__":
    main()
