#!/usr/bin/env python3

import argparse
import csv
import json
import math
import re
from pathlib import Path

import requests


DEFAULT_GAME_ID = "20260405HHOB02026"
DEFAULT_OUTPUT_DIR = Path("data/raw")
RELAY_URL = "https://api-gw.sports.naver.com/schedule/games/{game_id}/relay"
GAME_URL = "https://api-gw.sports.naver.com/schedule/games/{game_id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.sports.naver.com/",
}
SESSION = requests.Session()
SESSION.trust_env = False
DEFENSIVE_POSITIONS = {
    "투수",
    "포수",
    "1루수",
    "2루수",
    "3루수",
    "유격수",
    "좌익수",
    "중견수",
    "우익수",
}


def fetch_game(game_id: str) -> dict:
    url = GAME_URL.format(game_id=game_id)
    response = SESSION.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.json()


def fetch_relay(game_id: str, inning: int | None = None) -> dict:
    url = RELAY_URL.format(game_id=game_id)
    if inning is not None:
        url = f"{url}?inning={inning}"
    response = SESSION.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.json()


def collect_relay_payloads(game_id: str, innings: list[int] | None) -> list[dict]:
    if not innings:
        return [fetch_relay(game_id)]
    return [fetch_relay(game_id, inning=inning) for inning in innings]


def choose_current_catcher(lineup: list[dict]) -> dict | None:
    catchers = [row for row in lineup if row.get("posName") == "포수"]
    if not catchers:
        return None

    current = [row for row in catchers if row.get("cin") == "true" or not row.get("cout")]
    if current:
        return sorted(current, key=lambda row: row.get("seqno", 0), reverse=True)[0]
    return sorted(catchers, key=lambda row: row.get("seqno", 0), reverse=True)[0]


def build_player_map(relay_data: dict) -> dict[str, str]:
    player_map = {}
    for side in ["homeLineup", "awayLineup", "homeEntry", "awayEntry"]:
        block = relay_data.get(side, {})
        if not isinstance(block, dict):
            continue

        for group in ["pitcher", "batter"]:
            for row in block.get(group, []):
                pcode = row.get("pcode")
                name = row.get("name")
                if pcode and name:
                    player_map[str(pcode)] = name
    return player_map


def merge_player_maps(relay_blocks: list[dict]) -> dict[str, str]:
    player_map = {}
    for relay_data in relay_blocks:
        player_map.update(build_player_map(relay_data))
    return player_map


def build_player_team_map(relay_blocks: list[dict]) -> dict[str, str]:
    player_team_map = {}
    for relay_data in relay_blocks:
        for side in ["home", "away"]:
            for block_name in [f"{side}Lineup", f"{side}Entry"]:
                block = relay_data.get(block_name, {})
                if not isinstance(block, dict):
                    continue
                for group in ["pitcher", "batter"]:
                    for row in block.get(group, []):
                        pcode = row.get("pcode")
                        if pcode:
                            player_team_map[str(pcode)] = side
    return player_team_map


def choose_starting_catcher(relay_blocks: list[dict], side: str) -> dict | None:
    catchers = []
    for relay_data in relay_blocks:
        lineup = relay_data.get(f"{side}Lineup", {}).get("batter", [])
        for row in lineup:
            if row.get("posName") == "포수":
                catchers.append(row)
    if not catchers:
        return None
    return sorted(catchers, key=lambda row: row.get("seqno", 999999))[0]


def build_starting_defense(relay_blocks: list[dict], side: str) -> dict[str, dict]:
    starters_by_pos = {}
    for relay_data in relay_blocks:
        lineup = relay_data.get(f"{side}Lineup", {})
        if not isinstance(lineup, dict):
            continue

        for row in lineup.get("batter", []):
            pos_name = row.get("posName")
            if pos_name in DEFENSIVE_POSITIONS:
                current = starters_by_pos.get(pos_name)
                if current is None or row.get("seqno", 999999) < current.get("seqno", 999999):
                    starters_by_pos[pos_name] = row

        for row in lineup.get("pitcher", []):
            pos_name = row.get("posName") or row.get("pos")
            if pos_name == "투수":
                current = starters_by_pos.get("투수")
                if current is None or row.get("seqno", 999999) < current.get("seqno", 999999):
                    starters_by_pos["투수"] = row

    defense = {}
    for pos_name, row in starters_by_pos.items():
        pcode = row.get("pcode")
        if pcode:
            defense[pos_name] = {"pcode": str(pcode), "name": row.get("name")}
    return defense


def collect_change_texts(option: dict, player_change: dict) -> list[str]:
    texts = [option.get("text"), player_change.get("liveText"), player_change.get("shiftMessage")]
    return [text.strip() for text in texts if isinstance(text, str) and text.strip()]


def extract_shift_target_position(texts: list[str]) -> str | None:
    for text in texts:
        match = re.search(r"([가-힣0-9]+)\(으\)로 수비위치 변경", text)
        if match:
            return match.group(1)
    return None


def calculate_plate_z(track: dict) -> float | None:
    required = ["crossPlateY", "y0", "vy0", "ay", "z0", "vz0", "az"]
    if any(track.get(key) is None for key in required):
        return None

    target_y = track["crossPlateY"]
    a = 0.5 * track["ay"]
    b = track["vy0"]
    c = track["y0"] - target_y
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return None

    roots = [
        (-b + math.sqrt(discriminant)) / (2 * a),
        (-b - math.sqrt(discriminant)) / (2 * a),
    ]
    positive_roots = [root for root in roots if root > 0]
    if not positive_roots:
        return None

    time_to_plate = min(positive_roots)
    return track["z0"] + track["vz0"] * time_to_plate + 0.5 * track["az"] * time_to_plate * time_to_plate


def extract_pitch_rows(relay_data: dict, player_map: dict[str, str]) -> list[dict]:
    pitch_track_by_id = {}
    for relay in relay_data.get("textRelays", []):
        for pts in relay.get("ptsOptions", []):
            pitch_track_by_id[pts["pitchId"]] = pts

    options = []
    for relay in relay_data.get("textRelays", []):
        for option in relay.get("textOptions", []):
            options.append(
                {
                    "relay_inning": relay.get("inn"),
                    "relay_half": relay.get("homeOrAway"),
                    "option": option,
                }
            )
    options.sort(key=lambda item: item["option"].get("seqno") or 0)

    pitch_rows = []
    last_pitch_index = None
    result_event_types = {13, 23}

    for item in options:
        option = item["option"]
        pitch_id = option.get("ptsPitchId")
        if pitch_id:
            game_state = option.get("currentGameState", {})
            track = pitch_track_by_id.get(pitch_id, {})
            plate_z = calculate_plate_z(track)
            pitch_rows.append(
                {
                    "seqno": option.get("seqno"),
                    "inning": item["relay_inning"],
                    "half": item["relay_half"],
                    "pitch_id": pitch_id,
                    "pitch_num": option.get("pitchNum"),
                    "event_text": option.get("text"),
                    "pitch_result": option.get("pitchResult"),
                    "pitch_type": option.get("stuff"),
                    "speed": option.get("speed"),
                    "pitcher_code": game_state.get("pitcher"),
                    "pitcher_name": player_map.get(str(game_state.get("pitcher"))),
                    "batter_code": game_state.get("batter"),
                    "batter_name": player_map.get(str(game_state.get("batter"))),
                    "balls": game_state.get("ball"),
                    "strikes": game_state.get("strike"),
                    "outs": game_state.get("out"),
                    "cross_plate_x": track.get("crossPlateX"),
                    "cross_plate_y_plane": track.get("crossPlateY"),
                    "plate_z": plate_z,
                    "top_sz": track.get("topSz"),
                    "bottom_sz": track.get("bottomSz"),
                    "stance": track.get("stance"),
                    "plate_result_text": None,
                    "plate_result_type": None,
                }
            )
            last_pitch_index = len(pitch_rows) - 1
            continue

        if (
            option.get("type") in result_event_types
            and last_pitch_index is not None
            and pitch_rows[last_pitch_index]["inning"] == item["relay_inning"]
            and pitch_rows[last_pitch_index]["half"] == item["relay_half"]
        ):
            pitch_rows[last_pitch_index]["plate_result_text"] = option.get("text")
            pitch_rows[last_pitch_index]["plate_result_type"] = option.get("type")
            last_pitch_index = None

    return sorted(pitch_rows, key=lambda row: (row.get("seqno") or 0, row.get("pitch_num") or 0))


def merge_pitch_rows(relay_blocks: list[dict], player_map: dict[str, str]) -> list[dict]:
    player_team_map = build_player_team_map(relay_blocks)
    defense_positions = {
        "home": build_starting_defense(relay_blocks, "home"),
        "away": build_starting_defense(relay_blocks, "away"),
    }
    defense_player_positions = {
        side: {player["pcode"]: pos for pos, player in positions.items()}
        for side, positions in defense_positions.items()
    }

    pitch_track_by_id = {}
    option_items = []
    for relay_data in relay_blocks:
        for relay in relay_data.get("textRelays", []):
            for pts in relay.get("ptsOptions", []):
                pitch_track_by_id[pts["pitchId"]] = pts
            for option in relay.get("textOptions", []):
                option_items.append(
                    {
                        "relay_inning": relay.get("inn"),
                        "relay_half": relay.get("homeOrAway"),
                        "option": option,
                    }
                )

    option_items.sort(key=lambda item: item["option"].get("seqno") or 0)
    rows = []
    last_pitch_index = None
    result_event_types = {13, 23}

    def remove_defender(team: str, player_id: str | None) -> None:
        if not player_id:
            return
        current_pos = defense_player_positions[team].pop(player_id, None)
        if current_pos and defense_positions[team].get(current_pos, {}).get("pcode") == player_id:
            defense_positions[team].pop(current_pos, None)

    def assign_defender(team: str, position: str, player_id: str | None, player_name: str | None) -> None:
        if not player_id or position not in DEFENSIVE_POSITIONS:
            return

        remove_defender(team, player_id)
        current_player = defense_positions[team].get(position, {})
        current_player_id = current_player.get("pcode")
        if current_player_id:
            defense_player_positions[team].pop(current_player_id, None)

        defense_positions[team][position] = {"pcode": str(player_id), "name": player_name}
        defense_player_positions[team][str(player_id)] = position

    def update_catcher_from_change(option: dict) -> None:
        player_change = option.get("playerChange")
        if not isinstance(player_change, dict):
            return

        change_type = player_change.get("type")
        texts = collect_change_texts(option, player_change)
        if change_type == "substitution":
            in_player = player_change.get("inPlayer", {})
            out_player = player_change.get("outPlayer", {})
            team = player_team_map.get(str(in_player.get("playerId"))) or player_team_map.get(str(out_player.get("playerId")))
            if not team:
                return

            in_player_id = str(in_player.get("playerId")) if in_player.get("playerId") is not None else None
            out_player_id = str(out_player.get("playerId")) if out_player.get("playerId") is not None else None
            in_pos = in_player.get("playerPos")
            out_pos = out_player.get("playerPos")

            remove_defender(team, out_player_id)
            if in_player_id:
                player_team_map[in_player_id] = team

            if in_pos in DEFENSIVE_POSITIONS:
                assign_defender(team, in_pos, in_player_id, in_player.get("playerName"))
            elif out_pos in DEFENSIVE_POSITIONS:
                remove_defender(team, out_player_id)

        if change_type == "shift":
            shift_player = player_change.get("shiftPlayer", {})
            team = player_team_map.get(str(shift_player.get("playerId")))
            if not team:
                return

            target_pos = extract_shift_target_position(texts) or shift_player.get("playerPos")
            shift_player_id = str(shift_player.get("playerId")) if shift_player.get("playerId") is not None else None

            if target_pos in DEFENSIVE_POSITIONS:
                assign_defender(team, target_pos, shift_player_id, shift_player.get("playerName"))

    for item in option_items:
        option = item["option"]
        pitch_id = option.get("ptsPitchId")
        if pitch_id:
            game_state = option.get("currentGameState", {})
            track = pitch_track_by_id.get(pitch_id, {})
            plate_z = calculate_plate_z(track)
            fielding_team = "home" if item["relay_half"] == "0" else "away"
            catcher = defense_positions.get(fielding_team, {}).get("포수", {})
            rows.append(
                {
                    "seqno": option.get("seqno"),
                    "inning": item["relay_inning"],
                    "half": item["relay_half"],
                    "pitch_id": pitch_id,
                    "pitch_num": option.get("pitchNum"),
                    "event_text": option.get("text"),
                    "pitch_result": option.get("pitchResult"),
                    "pitch_type": option.get("stuff"),
                    "speed": option.get("speed"),
                    "pitcher_code": game_state.get("pitcher"),
                    "pitcher_name": player_map.get(str(game_state.get("pitcher"))),
                    "catcher_code": catcher.get("pcode"),
                    "catcher_name": catcher.get("name"),
                    "batter_code": game_state.get("batter"),
                    "batter_name": player_map.get(str(game_state.get("batter"))),
                    "balls": game_state.get("ball"),
                    "strikes": game_state.get("strike"),
                    "outs": game_state.get("out"),
                    "cross_plate_x": track.get("crossPlateX"),
                    "cross_plate_y_plane": track.get("crossPlateY"),
                    "plate_z": plate_z,
                    "top_sz": track.get("topSz"),
                    "bottom_sz": track.get("bottomSz"),
                    "stance": track.get("stance"),
                    "plate_result_text": None,
                    "plate_result_type": None,
                }
            )
            last_pitch_index = len(rows) - 1
            continue

        if (
            option.get("type") in result_event_types
            and last_pitch_index is not None
            and rows[last_pitch_index]["inning"] == item["relay_inning"]
            and rows[last_pitch_index]["half"] == item["relay_half"]
        ):
            rows[last_pitch_index]["plate_result_text"] = option.get("text")
            rows[last_pitch_index]["plate_result_type"] = option.get("type")
            last_pitch_index = None

        update_catcher_from_change(option)

    return sorted(rows, key=lambda row: (row.get("seqno") or 0, row.get("pitch_num") or 0))


def parse_current_inning(value: str | int) -> int:
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", str(value))
    if not match:
        raise ValueError(f"Could not parse inning from {value!r}")
    return int(match.group())


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Naver Sports relay API for KBO games.")
    parser.add_argument("--game-id", default=DEFAULT_GAME_ID, help="KBO game id, e.g. 20260405HHOB02026")
    parser.add_argument(
        "--all-innings",
        action="store_true",
        help="Fetch inning=1..currentInning and merge them into one pitch table",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where raw JSON and extracted pitch CSV will be written",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    innings = None
    if args.all_innings:
        game_payload = fetch_game(args.game_id)
        current_inning = parse_current_inning(game_payload["result"]["game"]["currentInning"])
        innings = list(range(1, current_inning + 1))

    payloads = collect_relay_payloads(args.game_id, innings)
    relay_blocks = [payload["result"]["textRelayData"] for payload in payloads]
    latest_relay_data = payloads[-1]["result"]["textRelayData"]

    if args.all_innings:
        raw_path = output_dir / f"naver_relay_all_innings_{args.game_id}.json"
        csv_path = output_dir / f"naver_relay_pitches_all_innings_{args.game_id}.csv"
    else:
        raw_path = output_dir / f"naver_relay_{args.game_id}.json"
        csv_path = output_dir / f"naver_relay_pitches_{args.game_id}.csv"

    save_json(raw_path, payloads if args.all_innings else payloads[0])
    player_map = merge_player_maps(relay_blocks)
    pitch_rows = merge_pitch_rows(relay_blocks, player_map)
    save_csv(csv_path, pitch_rows)

    current_game_state = latest_relay_data.get("currentGameState", {})
    home_catcher = choose_current_catcher(latest_relay_data.get("homeLineup", {}).get("batter", []))
    away_catcher = choose_current_catcher(latest_relay_data.get("awayLineup", {}).get("batter", []))

    print(f"game_id: {args.game_id}")
    print(f"innings_requested: {innings if innings else ['latest_only']}")
    print(f"saved_raw_json: {raw_path}")
    print(f"saved_pitch_csv: {csv_path}")
    print(f"relay_blocks: {len(relay_blocks)}")
    print(f"pitch_rows: {len(pitch_rows)}")
    print(f"has_pitch_location: {any(row['cross_plate_x'] is not None for row in pitch_rows)}")
    print(f"has_plate_z: {any(row['plate_z'] is not None for row in pitch_rows)}")
    print(f"has_explicit_pitch_type: {any(row['pitch_type'] for row in pitch_rows)}")
    print(
        f"current_pitcher: {current_game_state.get('pitcher')} "
        f"{player_map.get(str(current_game_state.get('pitcher')))}"
    )
    print(
        f"current_batter: {current_game_state.get('batter')} "
        f"{player_map.get(str(current_game_state.get('batter')))}"
    )
    print(
        "home_catcher:",
        json.dumps(
            {k: home_catcher.get(k) for k in ["name", "pcode", "posName", "batOrder", "seqno"]}
            if home_catcher
            else None,
            ensure_ascii=False,
        ),
    )
    print(
        "away_catcher:",
        json.dumps(
            {k: away_catcher.get(k) for k in ["name", "pcode", "posName", "batOrder", "seqno"]}
            if away_catcher
            else None,
            ensure_ascii=False,
        ),
    )

    print("\nfirst_5_pitch_rows:")
    for row in pitch_rows[:5]:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
