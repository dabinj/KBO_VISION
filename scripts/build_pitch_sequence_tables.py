#!/usr/bin/env python3

import argparse
import csv
from collections import defaultdict
from pathlib import Path


PITCH_ABBREV = {
    "직구": "F",
    "투심": "T",
    "커터": "C",
    "슬라이더": "S",
    "스위퍼": "W",
    "커브": "K",
    "체인지업": "U",
    "포크": "P",
}


RAW_RESULT_ABBREV = {
    "B": "B",
    "T": "S",
    "S": "S",
    "F": "F",
    "H": "X",
    "W": "W",
    "V": "X",
}


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    frac = {"1/3": 1, "2/3": 2}.get(parts[1], 0)
    return whole * 3 + frac


def load_pitcher_filter(path: Path, min_ip: float) -> set[str]:
    rows = read_rows(path)
    keep = set()
    for row in rows:
        outs = ip_to_outs(row.get("ip", ""))
        if outs / 3.0 >= min_ip:
            keep.add(row.get("player_id") or "")
    return keep


def load_hitter_stats(path: Path) -> dict[str, dict]:
    rows = read_rows(path)
    return {row.get("player_id") or "": row for row in rows if row.get("player_id")}


def offense_team_info(row: dict) -> tuple[str, str]:
    if (row.get("half") or "") == "0":
        return row.get("away_team_code") or "", row.get("away_team_name") or ""
    return row.get("home_team_code") or "", row.get("home_team_name") or ""


def pitcher_team_info(row: dict) -> tuple[str, str]:
    if (row.get("half") or "") == "0":
        return row.get("home_team_code") or "", row.get("home_team_name") or ""
    return row.get("away_team_code") or "", row.get("away_team_name") or ""


def pitch_abbrev(pitch_type: str) -> str:
    return PITCH_ABBREV.get(pitch_type or "", "X")


def simplify_raw_pitch_result(pitch_result: str) -> str:
    return RAW_RESULT_ABBREV.get((pitch_result or "").strip(), "X")


def terminal_result_code(plate_result_text: str) -> str:
    text = (plate_result_text or "").strip()
    if not text:
        return "X"
    if "볼넷" in text or "고의4구" in text or "몸에 맞는 볼" in text:
        return "W"
    if any(keyword in text for keyword in ["안타", "1루타", "2루타", "3루타", "홈런"]):
        return "H"
    return "O"


def parse_plate_outcome(text: str) -> dict[str, int]:
    text = (text or "").strip()
    if not text:
        return {"pa": 0, "ab": 0, "h": 0, "bb": 0, "hbp": 0, "tb": 0, "sf": 0}

    pa = 1
    bb = 1 if "볼넷" in text or "고의4구" in text else 0
    hbp = 1 if "몸에 맞는 볼" in text else 0
    sf = 1 if "희생플라이" in text or "희생 플라이" in text else 0

    hr = 1 if "홈런" in text else 0
    h3 = 1 if "3루타" in text else 0
    h2 = 1 if "2루타" in text else 0
    hit = 1 if any(keyword in text for keyword in ["안타", "1루타", "2루타", "3루타", "홈런", "내야안타"]) else 0
    single = 1 if hit and not hr and not h2 and not h3 else 0

    ab = 0 if bb or hbp or sf else 1
    tb = single + (2 * h2) + (3 * h3) + (4 * hr)
    return {"pa": pa, "ab": ab, "h": hit, "bb": bb, "hbp": hbp, "tb": tb, "sf": sf}


def format_rate(num: float, den: float) -> str:
    return f"{(num / den):.3f}" if den else ""


def compute_lineup_slots(rows: list[dict]) -> dict[tuple[str, str, str], int]:
    slots: dict[tuple[str, str, str], int] = {}
    seen_orders: dict[tuple[str, str], list[str]] = defaultdict(list)

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("pa_number_in_game") or 0),
            int(row.get("pitch_index_in_pa") or 0),
        ),
    )

    for row in sorted_rows:
        if (row.get("pitch_index_in_pa") or "") != "1":
            continue
        game_id = row.get("game_id") or ""
        offense_code, _ = offense_team_info(row)
        batter_code = row.get("batter_code") or ""
        team_key = (game_id, offense_code)
        if batter_code not in seen_orders[team_key]:
            seen_orders[team_key].append(batter_code)
        slots[(game_id, offense_code, batter_code)] = seen_orders[team_key].index(batter_code) + 1
    return slots


def augment_pitch_master(rows: list[dict], prev_hitter_stats: dict[str, dict], keep_pitchers: set[str]) -> list[dict]:
    lineup_slots = compute_lineup_slots(rows)
    batter_running = defaultdict(lambda: {"pa": 0, "ab": 0, "h": 0, "bb": 0, "hbp": 0, "tb": 0, "sf": 0})

    filtered = []
    for row in sorted(
        rows,
        key=lambda r: (
            r.get("game_date") or "",
            r.get("game_id") or "",
            int(r.get("pitch_index_in_game") or 0),
        ),
    ):
        pitcher_code = row.get("pitcher_code") or ""
        if pitcher_code not in keep_pitchers:
            continue

        offense_code, offense_name = offense_team_info(row)
        team_code, team_name = pitcher_team_info(row)
        batter_code = row.get("batter_code") or ""
        running = batter_running[batter_code]
        prev_row = prev_hitter_stats.get(batter_code, {})

        prev_ba = prev_row.get("hitter_hra", "")
        prev_ops = prev_row.get("hitter_ops", "")
        curr_ba = format_rate(running["h"], running["ab"])
        obp_num = running["h"] + running["bb"] + running["hbp"]
        obp_den = running["ab"] + running["bb"] + running["hbp"] + running["sf"]
        slg = format_rate(running["tb"], running["ab"])
        obp = format_rate(obp_num, obp_den)
        curr_ops = f"{(float(obp) + float(slg)):.3f}" if obp and slg else ""

        lineup_slot = lineup_slots.get((row.get("game_id") or "", offense_code, batter_code), "")
        pitch_symbol = pitch_abbrev(row.get("pitch_type") or "")
        zone25 = row.get("zone_25") or "UNKNOWN"
        pitch_zone = f"{pitch_symbol}{zone25}" if zone25 != "UNKNOWN" else f"{pitch_symbol}UNK"
        final_text = (row.get("plate_result_text") or "").strip()
        raw_result_code = simplify_raw_pitch_result(row.get("pitch_result") or "")
        result_code = terminal_result_code(final_text) if final_text else raw_result_code
        pitch_result_pair = f"{pitch_symbol}{result_code}"

        filtered_row = {
            "sequence_level": "PITCH",
            "season": "2025",
            "game_id": row.get("game_id") or "",
            "game_date": row.get("game_date") or "",
            "team_code": team_code,
            "team_name": team_name,
            "opponent_team_code": offense_code,
            "opponent_team_name": offense_name,
            "pitcher_code": pitcher_code,
            "pitcher_name": row.get("pitcher_name") or "",
            "catcher_code": row.get("catcher_code") or "",
            "catcher_name": row.get("catcher_name") or "",
            "batter_code": batter_code,
            "batter_name": row.get("batter_name") or "",
            "batter_stance": row.get("stance") or "",
            "lineup_slot": str(lineup_slot),
            "batter_prev_season_ba": prev_ba,
            "batter_curr_season_ba_before_unit": curr_ba,
            "batter_prev_season_ops": prev_ops,
            "batter_curr_season_ops_before_unit": curr_ops,
            "inning_start": row.get("inning") or "",
            "half_start": row.get("half") or "",
            "outs_start": row.get("outs") or "",
            "runner_state_start": row.get("runner_state") or "",
            "score_diff_start": row.get("score_diff_pitcher") or "",
            "pitch_seq": pitch_symbol,
            "zone25_seq": zone25,
            "pitch_zone_seq": pitch_zone,
            "result_seq": result_code,
            "raw_result_seq": raw_result_code,
            "pitch_result_seq": pitch_result_pair,
            "sequence_length": "1",
            "final_result": final_text,
            "outs_recorded": "",
            "runs_allowed": "",
            "pa_id": f"{row.get('game_id')}_PA{int(row.get('pa_number_in_game') or 0):03d}",
            "pa_number_in_game": row.get("pa_number_in_game") or "",
            "pitch_count_in_pa": row.get("pitch_index_in_pa") or "",
            "count_end": "",
            "first_pitch_type": pitch_symbol if (row.get("pitch_index_in_pa") or "") == "1" else "",
            "first_zone25": zone25 if (row.get("pitch_index_in_pa") or "") == "1" else "",
            "last_pitch_type": pitch_symbol if final_text else "",
            "last_zone25": zone25 if final_text else "",
            "batting_result_type": row.get("plate_result_type") or "",
            "is_two_strike_sequence": "1" if (row.get("strikes") or "") == "2" else "0",
            "is_runner_in_scoring_position": "1" if (row.get("runner_state") or "000")[1:] != "00" else "0",
            "pitch_type": row.get("pitch_type") or "",
            "pitch_result": row.get("pitch_result") or "",
            "zone_25": zone25,
            "zone_9": row.get("zone_9") or "",
            "count_state": row.get("count_state") or "",
            "pitch_index_in_game": row.get("pitch_index_in_game") or "",
            "pitch_index_in_inning": row.get("pitch_index_in_inning") or "",
            "pitch_index_in_pa": row.get("pitch_index_in_pa") or "",
            "prev_pitch_type_pa_1": row.get("prev_pitch_type_pa_1") or "",
            "prev_zone_9_pa_1": row.get("prev_zone_9_pa_1") or "",
        }
        filtered.append(filtered_row)

        if final_text:
            outcome = parse_plate_outcome(final_text)
            for key, value in outcome.items():
                batter_running[batter_code][key] += value

    return filtered


def build_pa_table(pitch_master: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in pitch_master:
        groups[row["pa_id"]].append(row)

    output = []
    for pa_id, rows in groups.items():
        rows = sorted(rows, key=lambda row: int(row.get("pitch_index_in_pa") or 0))
        first = rows[0]
        last = rows[-1]
        pitch_seq = "".join(row["pitch_seq"] for row in rows)
        zone25_seq = "-".join(row["zone25_seq"] for row in rows)
        pitch_zone_seq = "-".join(row["pitch_zone_seq"] for row in rows)
        result_seq = "".join(row.get("result_seq", "") for row in rows)
        raw_result_seq = "".join(row.get("raw_result_seq", "") for row in rows)
        pitch_result_seq = "-".join(row.get("pitch_result_seq", "") for row in rows)
        count_pre_seq = []
        count_post_seq = []
        count_path_seq = []
        prev_count = "0-0"
        for row in rows:
            post_count = row.get("count_state", "") or ""
            count_pre_seq.append(prev_count)
            count_post_seq.append(post_count)
            count_path_seq.append(f"{prev_count}>{post_count}")
            prev_count = post_count or prev_count
        output.append(
            {
                **{k: first.get(k, "") for k in [
                    "sequence_level","season","game_id","game_date","team_code","team_name","opponent_team_code","opponent_team_name",
                    "pitcher_code","pitcher_name","catcher_code","catcher_name","batter_code","batter_name","batter_stance","lineup_slot",
                    "batter_prev_season_ba","batter_curr_season_ba_before_unit","batter_prev_season_ops","batter_curr_season_ops_before_unit",
                    "inning_start","half_start","outs_start","runner_state_start","score_diff_start","pa_id","pa_number_in_game"
                ]},
                "sequence_level": "PA",
                "pitch_seq": pitch_seq,
                "zone25_seq": zone25_seq,
                "pitch_zone_seq": pitch_zone_seq,
                "result_seq": result_seq,
                "raw_result_seq": raw_result_seq,
                "pitch_result_seq": pitch_result_seq,
                "count_pre_seq": "|".join(count_pre_seq),
                "count_post_seq": "|".join(count_post_seq),
                "count_path_seq": "|".join(count_path_seq),
                "sequence_length": str(len(rows)),
                "final_result": last.get("final_result", ""),
                "outs_recorded": "",
                "runs_allowed": "",
                "pitch_count_in_pa": str(len(rows)),
                "count_end": last.get("count_state", ""),
                "first_pitch_type": first.get("pitch_seq", ""),
                "first_zone25": first.get("zone25_seq", ""),
                "last_pitch_type": last.get("pitch_seq", ""),
                "last_zone25": last.get("zone25_seq", ""),
                "batting_result_type": last.get("batting_result_type", ""),
                "is_two_strike_sequence": "1" if any((row.get("count_state") or "").endswith("-2") for row in rows) else "0",
                "is_runner_in_scoring_position": "1" if first.get("runner_state_start", "000")[1:] != "00" else "0",
            }
        )
    return output


def build_inning_table(pitch_master: list[dict], pa_table: list[dict]) -> list[dict]:
    pa_by_inning: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in pa_table:
        key = (row["game_id"], row["pitcher_code"], row["inning_start"], row["half_start"])
        pa_by_inning[key].append(row)

    output = []
    for key, pa_rows in pa_by_inning.items():
        pa_rows = sorted(pa_rows, key=lambda row: int(row.get("pa_number_in_game") or 0))
        first = pa_rows[0]
        pitch_rows = [row for row in pitch_master if (row["game_id"], row["pitcher_code"], row["inning_start"], row["half_start"]) == key]
        pitch_rows.sort(key=lambda row: int(row.get("pitch_index_in_inning") or 0))
        output.append(
            {
                **{k: first.get(k, "") for k in [
                    "season","game_id","game_date","team_code","team_name","opponent_team_code","opponent_team_name",
                    "pitcher_code","pitcher_name","catcher_code","catcher_name","inning_start","half_start","outs_start",
                    "runner_state_start","score_diff_start"
                ]},
                "sequence_level": "INNING",
                "batter_code": "",
                "batter_name": "",
                "batter_stance": "",
                "lineup_slot": "",
                "batter_prev_season_ba": "",
                "batter_curr_season_ba_before_unit": "",
                "batter_prev_season_ops": "",
                "batter_curr_season_ops_before_unit": "",
                "pitch_seq": "|".join(row["pitch_seq"] for row in pa_rows),
                "zone25_seq": "|".join(row["zone25_seq"] for row in pa_rows),
                "pitch_zone_seq": "|".join(row["pitch_zone_seq"] for row in pa_rows),
                "result_seq": "|".join(row.get("result_seq", "") for row in pa_rows),
                "raw_result_seq": "|".join(row.get("raw_result_seq", "") for row in pa_rows),
                "pitch_result_seq": "|".join(row.get("pitch_result_seq", "") for row in pa_rows),
                "count_pre_seq": " || ".join(row.get("count_pre_seq", "") for row in pa_rows),
                "count_post_seq": " || ".join(row.get("count_post_seq", "") for row in pa_rows),
                "count_path_seq": " || ".join(row.get("count_path_seq", "") for row in pa_rows),
                "sequence_length": str(len(pitch_rows)),
                "final_result": "inning_complete" if len(pa_rows) else "",
                "outs_recorded": "",
                "runs_allowed": "",
                "inning_id": f"{first['game_id']}_{first['pitcher_code']}_{first['inning_start']}_{first['half_start']}",
                "batters_faced": str(len(pa_rows)),
                "pa_count": str(len(pa_rows)),
                "pitch_count_in_inning": str(len(pitch_rows)),
                "pa_seq_concat": "|".join(row["pitch_seq"] for row in pa_rows),
                "zone25_pa_concat": "|".join(row["zone25_seq"] for row in pa_rows),
                "pitch_zone_pa_concat": "|".join(row["pitch_zone_seq"] for row in pa_rows),
                "first_batter_code": pa_rows[0].get("batter_code", ""),
                "first_batter_name": pa_rows[0].get("batter_name", ""),
                "last_batter_code": pa_rows[-1].get("batter_code", ""),
                "last_batter_name": pa_rows[-1].get("batter_name", ""),
                "runs_allowed_in_inning": "",
                "hits_allowed_in_inning": "",
                "walks_allowed_in_inning": "",
            }
        )
    return output


def build_game_table(pitch_master: list[dict], pa_table: list[dict], inning_table: list[dict]) -> list[dict]:
    pa_by_game: dict[tuple[str, str], list[dict]] = defaultdict(list)
    inning_by_game: dict[tuple[str, str], list[dict]] = defaultdict(list)
    pitch_by_game: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in pa_table:
        pa_by_game[(row["game_id"], row["pitcher_code"])].append(row)
    for row in inning_table:
        inning_by_game[(row["game_id"], row["pitcher_code"])].append(row)
    for row in pitch_master:
        pitch_by_game[(row["game_id"], row["pitcher_code"])].append(row)

    output = []
    for key, pa_rows in pa_by_game.items():
        pa_rows.sort(key=lambda row: int(row.get("pa_number_in_game") or 0))
        inning_rows = sorted(inning_by_game[key], key=lambda row: int(row.get("inning_start") or 0))
        pitch_rows = sorted(pitch_by_game[key], key=lambda row: int(row.get("pitch_index_in_game") or 0))
        first = pa_rows[0]
        output.append(
            {
                **{k: first.get(k, "") for k in [
                    "season","game_id","game_date","team_code","team_name","opponent_team_code","opponent_team_name",
                    "pitcher_code","pitcher_name","catcher_code","catcher_name","inning_start","half_start","outs_start",
                    "runner_state_start","score_diff_start"
                ]},
                "sequence_level": "GAME",
                "batter_code": "",
                "batter_name": "",
                "batter_stance": "",
                "lineup_slot": "",
                "batter_prev_season_ba": "",
                "batter_curr_season_ba_before_unit": "",
                "batter_prev_season_ops": "",
                "batter_curr_season_ops_before_unit": "",
                "pitch_seq": " || ".join(row["pitch_seq"] for row in inning_rows),
                "zone25_seq": " || ".join(row["zone25_seq"] for row in inning_rows),
                "pitch_zone_seq": " || ".join(row["pitch_zone_seq"] for row in inning_rows),
                "result_seq": " || ".join(row.get("result_seq", "") for row in inning_rows),
                "raw_result_seq": " || ".join(row.get("raw_result_seq", "") for row in inning_rows),
                "pitch_result_seq": " || ".join(row.get("pitch_result_seq", "") for row in inning_rows),
                "count_pre_seq": " || ".join(row.get("count_pre_seq", "") for row in inning_rows),
                "count_post_seq": " || ".join(row.get("count_post_seq", "") for row in inning_rows),
                "count_path_seq": " || ".join(row.get("count_path_seq", "") for row in inning_rows),
                "sequence_length": str(len(pitch_rows)),
                "final_result": "game_sequence",
                "outs_recorded": "",
                "runs_allowed": "",
                "game_sequence_id": f"{first['game_id']}_{first['pitcher_code']}",
                "innings_pitched": str(len(inning_rows)),
                "batters_faced": str(len(pa_rows)),
                "pitch_count_in_game": str(len(pitch_rows)),
                "pa_count": str(len(pa_rows)),
                "inning_count": str(len(inning_rows)),
                "pa_seq_concat": " || ".join(row["pitch_seq"] for row in pa_rows),
                "inning_seq_concat": " || ".join(row["pitch_seq"] for row in inning_rows),
                "times_through_order_max": "",
                "first_inning_pitch_mix": inning_rows[0].get("pitch_seq", "") if inning_rows else "",
                "late_inning_pitch_mix": inning_rows[-1].get("pitch_seq", "") if inning_rows else "",
                "runs_allowed_total": "",
                "hits_allowed_total": "",
                "walks_allowed_total": "",
                "strikeouts_total": "",
            }
        )
    return output


def build_fasta(records: list[dict], record_id_field: str) -> str:
    chunks = []
    for row in records:
        record_id = row.get(record_id_field, "")
        header = (
            f">{record_id}|game_id={row.get('game_id','')}|pitcher={row.get('pitcher_name','')}|"
            f"catcher={row.get('catcher_name','')}|batter={row.get('batter_name','')}|"
            f"lineup={row.get('lineup_slot','')}|prev_ba={row.get('batter_prev_season_ba','')}|"
            f"curr_ba={row.get('batter_curr_season_ba_before_unit','')}|inning={row.get('inning_start','')}|"
            f"outs={row.get('outs_start','')}|runner={row.get('runner_state_start','')}|result={row.get('final_result','')}"
        )
        chunks.append(
            "\n".join(
                [
                    header,
                    f"PITCH:{row.get('pitch_seq','')}",
                    f"ZONE:{row.get('zone25_seq','')}",
                    f"PAIR:{row.get('pitch_zone_seq','')}",
                    f"RESULT:{row.get('result_seq','')}",
                    f"RAW_RESULT:{row.get('raw_result_seq','')}",
                    f"PITCH_RESULT:{row.get('pitch_result_seq','')}",
                    f"COUNT_PATH:{row.get('count_path_seq','')}",
                ]
            )
        )
    return "\n\n".join(chunks) + ("\n" if chunks else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build sequence tables and FASTA-like outputs for 2025 100+ IP pitchers.")
    parser.add_argument("--input-csv", required=True, help="Context-enriched pitch CSV with zone_25")
    parser.add_argument("--pitcher-stats-csv", required=True, help="Official pitcher stats CSV for IP filter")
    parser.add_argument("--prev-hitter-stats-csv", required=True, help="Previous season hitter stats CSV")
    parser.add_argument("--min-ip", type=float, default=100.0)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    keep_pitchers = load_pitcher_filter(Path(args.pitcher_stats_csv), args.min_ip)
    prev_hitter_stats = load_hitter_stats(Path(args.prev_hitter_stats_csv))

    pitch_master = augment_pitch_master(rows, prev_hitter_stats, keep_pitchers)
    pa_table = build_pa_table(pitch_master)
    inning_table = build_inning_table(pitch_master, pa_table)
    game_table = build_game_table(pitch_master, pa_table, inning_table)

    output_dir = Path(args.output_dir)
    write_rows(output_dir / "pitch_master_2025_100ip.csv", pitch_master)
    write_rows(output_dir / "pa_sequence_table_2025_100ip.csv", pa_table)
    write_rows(output_dir / "inning_sequence_table_2025_100ip.csv", inning_table)
    write_rows(output_dir / "game_sequence_table_2025_100ip.csv", game_table)

    write_text(output_dir / "pa_sequences_2025_100ip.fasta.txt", build_fasta(pa_table, "pa_id"))
    write_text(output_dir / "inning_sequences_2025_100ip.fasta.txt", build_fasta(inning_table, "inning_id"))
    write_text(output_dir / "game_sequences_2025_100ip.fasta.txt", build_fasta(game_table, "game_sequence_id"))

    print(f"pitch_master_rows: {len(pitch_master)}")
    print(f"pa_rows: {len(pa_table)}")
    print(f"inning_rows: {len(inning_table)}")
    print(f"game_rows: {len(game_table)}")
    print(f"output_dir: {output_dir}")


if __name__ == "__main__":
    main()
