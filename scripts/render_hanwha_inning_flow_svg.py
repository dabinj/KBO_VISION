#!/usr/bin/env python3

import csv
import random
from collections import Counter, defaultdict
from pathlib import Path


LINEUP = [
    ("오재원", "L"),
    ("페라자", "L"),
    ("문현빈", "L"),
    ("노시환", "R"),
    ("강백호", "L"),
    ("채은성", "R"),
    ("하주석", "L"),
    ("최재훈", "R"),
    ("심우준", "R"),
]


def read_rows(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pa_groups(rows: list[dict]) -> list[list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["game_id"], row["pa_number_in_game"])
        grouped.setdefault(key, []).append(row)
    return list(grouped.values())


def classify_result(text: str) -> str:
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
    if "1루타" in text or "안타" in text or "땅볼로 출루" in text:
        return "SINGLE"
    if "삼진" in text:
        return "K"
    if "플라이" in text or "뜬공" in text or "직선타" in text:
        return "FLY"
    if "땅볼" in text or "번트 아웃" in text or "병살타" in text:
        return "GROUND"
    return "OTHER"


def tto_bucket(seen_count: int) -> str:
    if seen_count <= 1:
        return "1st"
    if seen_count == 2:
        return "2nd"
    return "3rd+"


def first_pitch_dists(rows: list[dict]) -> dict[str, Counter]:
    counter = defaultdict(Counter)
    for row in rows:
        if row.get("pitch_index_in_pa") != "1":
            continue
        stance = row.get("stance") or row.get("batter_stance") or "UNKNOWN"
        counter[stance][(row.get("pitch_type") or "", row.get("zone_9") or "")] += 1
    return counter


def second_pitch_dists(rows: list[dict]) -> dict[tuple[str, str], Counter]:
    counter = defaultdict(Counter)
    for row in rows:
        stance = row.get("batter_stance") or row.get("stance") or "UNKNOWN"
        current_pitch_type = row.get("current_pitch_type") or ""
        next_tuple = (row.get("next_pitch_type") or "", row.get("next_zone_9") or "")
        counter[(stance, current_pitch_type)][next_tuple] += 1
    return counter


def outcome_dists(rows: list[dict]) -> dict[tuple[str, str], Counter]:
    counts = defaultdict(Counter)
    for pitches in pa_groups(rows):
        last = pitches[-1]
        stance = last.get("stance") or "UNKNOWN"
        seen = int(last.get("batter_seen_count_in_game") or 1)
        bucket = tto_bucket(seen)
        result = classify_result(last.get("plate_result_text") or "")
        if result != "UNKNOWN":
            counts[(stance, bucket)][result] += 1
    return counts


def sample_counter(counter: Counter, rng: random.Random):
    items = list(counter.items())
    total = sum(count for _, count in items)
    if total <= 0:
        return None
    pick = rng.uniform(0, total)
    upto = 0.0
    for value, weight in items:
        upto += weight
        if pick <= upto:
            return value
    return items[-1][0]


def runner_state(bases: list[str | None]) -> str:
    return "".join("1" if runner else "0" for runner in bases)


def apply_result(result: str, batter_name: str, bases: list[str | None], outs: int) -> tuple[list[str | None], int, int]:
    new_bases = bases[:]
    runs = 0
    if result in {"K", "FLY", "GROUND", "OTHER"}:
        return new_bases, outs + 1, runs
    if result == "WALK":
        if new_bases[0] and new_bases[1] and new_bases[2]:
            runs += 1
        new_bases[2] = new_bases[1] if new_bases[1] else new_bases[2]
        new_bases[1] = new_bases[0] if new_bases[0] else new_bases[1]
        new_bases[0] = batter_name
        return new_bases, outs, runs
    if result == "SINGLE":
        if new_bases[2]:
            runs += 1
        new_bases[2] = new_bases[1]
        new_bases[1] = new_bases[0]
        new_bases[0] = batter_name
        return new_bases, outs, runs
    if result == "DOUBLE":
        if new_bases[2]:
            runs += 1
        if new_bases[1]:
            runs += 1
        runner_from_first = new_bases[0]
        new_bases[2] = runner_from_first
        new_bases[1] = batter_name
        new_bases[0] = None
        return new_bases, outs, runs
    if result == "TRIPLE":
        runs += sum(1 for runner in new_bases if runner)
        return [None, None, batter_name], outs, runs
    if result == "HR":
        runs += sum(1 for runner in new_bases if runner) + 1
        return [None, None, None], outs, runs
    return new_bases, outs + 1, runs


def describe_result(result: str) -> str:
    mapping = {
        "K": "삼진",
        "FLY": "뜬공 아웃",
        "GROUND": "땅볼 아웃",
        "WALK": "볼넷",
        "SINGLE": "안타",
        "DOUBLE": "2루타",
        "TRIPLE": "3루타",
        "HR": "홈런",
        "OTHER": "아웃",
    }
    return mapping.get(result, result)


def simulate_innings() -> list[dict]:
    context_rows = read_rows("data/matchups/2025_white/pitcher_55855_white_context_state.csv")
    next_rows = read_rows("data/models/model_white_next_pitch_first_only_2025.csv")

    first_dists = first_pitch_dists(context_rows)
    second_dists = second_pitch_dists(next_rows)
    outcome_dist_map = outcome_dists(context_rows)
    rng = random.Random(42)

    innings = []
    lineup_index = 0
    seen_tracker = Counter()
    score = 0

    for inning_no in range(1, 7):
        outs = 0
        bases: list[str | None] = [None, None, None]
        lines = []
        while outs < 3:
            batter_name, stance = LINEUP[lineup_index % len(LINEUP)]
            lineup_index += 1
            seen_tracker[batter_name] += 1
            bucket = tto_bucket(seen_tracker[batter_name])
            first_pitch_type, first_zone = sample_counter(first_dists.get(stance, Counter({("직구", "OUT"): 1})), rng)
            second_pitch_type, second_zone = sample_counter(
                second_dists.get((stance, first_pitch_type), Counter({("커브", "OUT"): 1})),
                rng,
            )
            result = sample_counter(outcome_dist_map.get((stance, bucket), Counter({"GROUND": 1})), rng)
            before_state = runner_state(bases)
            bases, outs, runs = apply_result(result, batter_name, bases, outs)
            score += runs
            line = (
                f"{before_state} | {batter_name}: "
                f"초구 {first_pitch_type} {first_zone}, "
                f"2구 {second_pitch_type} {second_zone}, "
                f"결과 {describe_result(result)}"
            )
            if runs:
                line += f" (+{runs}점)"
            lines.append(line)
        innings.append(
            {
                "inning": f"{inning_no}회",
                "state": f"종료 점수 가정: 한화 {score}점, 이닝 종료 상태 {runner_state(bases)} / {outs}아웃",
                "faced_batters": len(lines),
                "flow": lines,
            }
        )
    return innings


def inning_card(parts: list[str], x: int, y: int, inning: dict) -> None:
    w = 520
    h = 92 + len(inning["flow"]) * 20
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append(f'<text x="{x+18}" y="{y+28}" font-size="20" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{inning["inning"]}</text>')
    parts.append(f'<text x="{x+18}" y="{y+50}" font-size="12" font-family="Segoe UI, Arial" fill="#486581">{inning["state"]}</text>')
    parts.append(f'<text x="{x+18}" y="{y+68}" font-size="11" font-family="Segoe UI, Arial" fill="#486581">상대한 타자 수: {inning["faced_batters"]}</text>')
    for idx, line in enumerate(inning["flow"]):
        parts.append(f'<text x="{x+18}" y="{y+92 + idx*20}" font-size="11" font-family="Segoe UI, Arial" fill="#102a43">{line}</text>')


def main() -> None:
    innings = simulate_innings()
    width = 1100
    height = 1500
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="38" font-size="28" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">White 6-Inning Sequence Simulation</text>',
        '<text x="24" y="64" font-size="13" font-family="Segoe UI, Arial" fill="#486581">Model-based inning flow using White 2025 first-pitch patterns, next-pitch transitions, and PA outcome modes by stance and times-through-order.</text>',
        '<text x="24" y="86" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Runner state updates follow each predicted PA result, so later innings depend on earlier outcomes.</text>',
    ]

    left_y = 120
    right_y = 120
    for idx, inning in enumerate(innings):
        col = idx % 2
        x = 24 if col == 0 else 560
        y = left_y if col == 0 else right_y
        inning_card(parts, x, y, inning)
        used_h = 92 + len(inning["flow"]) * 20
        if col == 0:
            left_y += used_h + 18
        else:
            right_y += used_h + 18

    footer_y = max(left_y, right_y) + 12
    parts.append(f'<rect x="24" y="{footer_y}" width="1050" height="36" rx="12" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append(f'<text x="42" y="{footer_y + 24}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">표기 형식: 시작 주자상황 000/100/010/001 | 타자 : 초구, 2구, 예상 타석 결과</text>')
    parts.append('</svg>')

    Path("examples/hanwha_white_6inning_sequence_board.svg").write_text("\n".join(parts), encoding="utf-8")
    print("examples/hanwha_white_6inning_sequence_board.svg")


if __name__ == "__main__":
    main()
