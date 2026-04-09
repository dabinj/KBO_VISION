#!/usr/bin/env python3

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPORT_DATE = "2026-04-10"
WHITE_CONTEXT_CSV = Path("data/matchups/2025_white/pitcher_55855_white_context_state.csv")
WHITE_NEXT_PITCH_CSV = Path("data/models/model_white_next_pitch_first_only_2025.csv")
FULL_2025_PITCHES_CSV = Path("data/ranges/2025-03-01_2025-10-31/pitches_2025-03-01_2025-10-31.csv")
RAW_2026_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/predictions/white_vs_hanwha_2026-04-10")

FASTBALL_TYPES = {"직구", "투심", "커터"}


@dataclass
class GameState:
    inning: int
    outs: int
    bases: tuple[str | None, str | None, str | None]
    lineup_index: int
    score_for_hanwha: int
    probability: float
    path: list[str]


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def pitch_family(pitch_type: str) -> str:
    return "FASTBALL" if pitch_type in FASTBALL_TYPES else "BREAKING"


def batter_half_from_filename(filename: str) -> str:
    game_code = filename.split("_")[-1].replace(".csv", "")
    matchup = game_code[8:12]
    away_code = matchup[:2]
    return "0" if away_code == "HH" else "1"


def classify_pa_result(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "UNKNOWN"
    if any(keyword in text for keyword in ["볼넷", "고의4구", "몸에 맞는 볼"]):
        return "WALK"
    if "홈런" in text:
        return "HR"
    if "3루타" in text:
        return "TRIPLE"
    if "2루타" in text:
        return "DOUBLE"
    if any(keyword in text for keyword in ["1루타", "안타", "출루"]):
        return "SINGLE"
    return "OUT"


def is_hit(result: str) -> bool:
    return result in {"SINGLE", "DOUBLE", "TRIPLE", "HR"}


def is_ab(result: str) -> bool:
    return result not in {"WALK", "UNKNOWN"}


def group_plate_appearances(rows: list[dict]) -> list[list[dict]]:
    grouped: list[list[dict]] = []
    current: list[dict] = []
    previous_game = None
    previous_batter = None

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("seqno") or 0),
        ),
    )
    for row in sorted_rows:
        game_id = row.get("game_id") or ""
        batter_code = row.get("batter_code") or ""
        should_start = (
            not current
            or game_id != previous_game
            or batter_code != previous_batter
            or (current and current[-1].get("plate_result_text"))
        )
        if should_start and current:
            grouped.append(current)
            current = []
        current.append(row)
        previous_game = game_id
        previous_batter = batter_code
    if current:
        grouped.append(current)
    return grouped


def bases_label(bases: tuple[str | None, str | None, str | None]) -> str:
    return "".join("1" if runner else "0" for runner in bases)


def exact_batter_weight(sample_size: int) -> float:
    if sample_size >= 12:
        return 0.7
    if sample_size >= 6:
        return 0.5
    if sample_size >= 3:
        return 0.3
    return 0.0


def normalize(counter: Counter) -> dict[str, float]:
    total = sum(counter.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in counter.items()}


def blended_distribution(parts: list[tuple[Counter, float]]) -> dict[str, float]:
    blended: Counter = Counter()
    weight_sum = sum(weight for _, weight in parts if weight > 0)
    if weight_sum <= 0:
        return {}
    for counter, weight in parts:
        if weight <= 0:
            continue
        for key, value in normalize(counter).items():
            blended[key] += value * (weight / weight_sum)
    return dict(blended)


def top_probabilities(distribution: dict[str, float], top_n: int = 3) -> list[dict]:
    ranked = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
    return [{"value": value, "probability": round(probability, 4)} for value, probability in ranked[:top_n]]


def infer_projected_lineup() -> dict:
    lineups: list[dict] = []
    slot_votes: dict[int, Counter] = defaultdict(Counter)
    latest_lineup: list[str] = []
    latest_file = ""

    for path in sorted(RAW_2026_DIR.glob("naver_relay_pitches_all_innings_*HH*02026.csv")):
        hh_half = batter_half_from_filename(path.name)
        rows = read_rows(path)
        starters: list[str] = []
        seen = set()
        for row in rows:
            if row.get("half") != hh_half:
                continue
            batter_name = row.get("batter_name") or ""
            if not batter_name or batter_name in seen:
                continue
            seen.add(batter_name)
            starters.append(batter_name)
            if len(starters) == 9:
                break
        if len(starters) < 9:
            continue
        lineups.append({"source_file": path.name, "starters": starters})
        latest_lineup = starters
        latest_file = path.name
        for slot, name in enumerate(starters, start=1):
            slot_votes[slot][name] += 1

    projected: list[str] = []
    slot_alternatives: dict[int, list[dict]] = {}
    for slot in range(1, 10):
        projected_name, _ = slot_votes[slot].most_common(1)[0]
        projected.append(projected_name)
        slot_alternatives[slot] = [
            {"name": name, "count": count}
            for name, count in slot_votes[slot].most_common(3)
        ]

    return {
        "projected_lineup": projected,
        "source_lineups": lineups,
        "slot_alternatives": slot_alternatives,
        "latest_source_file": latest_file,
        "latest_lineup": latest_lineup,
    }


def build_2025_batter_profiles(target_names: list[str]) -> dict[str, dict]:
    rows = read_rows(FULL_2025_PITCHES_CSV)
    target = set(target_names)
    filtered = [row for row in rows if (row.get("batter_name") or "") in target]
    pa_groups = group_plate_appearances(filtered)

    profiles: dict[str, dict] = {}
    for pa in pa_groups:
        batter_name = pa[0].get("batter_name") or ""
        profile = profiles.setdefault(
            batter_name,
            {"pas": 0, "ab": 0, "hits": 0, "whiffs": 0, "pitches": 0, "stance": pa[0].get("stance") or "UNKNOWN"},
        )
        result = classify_pa_result(pa[-1].get("plate_result_text") or "")
        profile["pas"] += 1
        profile["ab"] += 1 if is_ab(result) else 0
        profile["hits"] += 1 if is_hit(result) else 0
        profile["pitches"] += len(pa)
        profile["whiffs"] += sum(1 for pitch in pa if "헛스윙" in (pitch.get("event_text") or ""))

    for profile in profiles.values():
        ab = profile["ab"]
        pitches = profile["pitches"]
        profile["ba"] = round(profile["hits"] / ab, 4) if ab else 0.0
        profile["whiff_rate"] = round(profile["whiffs"] / pitches, 4) if pitches else 0.0
    return profiles


def build_2026_current_profiles(target_names: list[str]) -> dict[str, dict]:
    rows: list[dict] = []
    for path in sorted(RAW_2026_DIR.glob("naver_relay_pitches_all_innings_*HH*02026.csv")):
        hh_half = batter_half_from_filename(path.name)
        for row in read_rows(path):
            if row.get("half") == hh_half:
                row["_source_file"] = path.name
                rows.append(row)

    filtered = [row for row in rows if (row.get("batter_name") or "") in set(target_names)]
    pa_groups = group_plate_appearances(filtered)

    profiles: dict[str, dict] = {}
    for pa in pa_groups:
        batter_name = pa[0].get("batter_name") or ""
        profile = profiles.setdefault(
            batter_name,
            {
                "pas_complete": 0,
                "ab_complete": 0,
                "hits_complete": 0,
                "pitches_seen": 0,
                "games_seen": set(),
                "stance": pa[0].get("stance") or "UNKNOWN",
            },
        )
        profile["pitches_seen"] += len(pa)
        profile["games_seen"].add(pa[0].get("_source_file") or "")
        result_text = pa[-1].get("plate_result_text") or ""
        if not result_text:
            continue
        result = classify_pa_result(result_text)
        profile["pas_complete"] += 1
        profile["ab_complete"] += 1 if is_ab(result) else 0
        profile["hits_complete"] += 1 if is_hit(result) else 0

    for profile in profiles.values():
        ab = profile["ab_complete"]
        profile["ba_complete"] = round(profile["hits_complete"] / ab, 4) if ab else 0.0
        profile["games_seen"] = len(profile["games_seen"])
    return profiles


def tto_bucket(lineup_turn_count: int) -> str:
    if lineup_turn_count <= 1:
        return "1st"
    if lineup_turn_count == 2:
        return "2nd"
    return "3rd+"


def build_first_pitch_reference(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("pitch_index_in_pa") == "1"]


def filtered_first_pitch_rows(first_pitch_rows: list[dict], batter_name: str, stance: str, runner_state: str, outs: int, tto: str) -> dict[str, list[dict]]:
    return {
        "exact_batter": [row for row in first_pitch_rows if row.get("batter_name") == batter_name],
        "stance_state": [
            row for row in first_pitch_rows
            if row.get("batter_stance") == stance
            and row.get("runner_state") == runner_state
            and int(row.get("outs") or 0) == outs
        ],
        "stance_tto": [
            row for row in first_pitch_rows
            if row.get("batter_stance") == stance
            and tto_bucket(int(row.get("batter_seen_count_in_game") or 1)) == tto
        ],
        "stance_only": [row for row in first_pitch_rows if row.get("batter_stance") == stance],
        "all": first_pitch_rows,
    }


def build_first_pitch_summary(first_pitch_rows: list[dict], batter_name: str, stance: str, runner_state: str, outs: int, tto: str) -> dict:
    buckets = filtered_first_pitch_rows(first_pitch_rows, batter_name, stance, runner_state, outs, tto)
    exact_weight = exact_batter_weight(len(buckets["exact_batter"]))
    pitch_parts = []
    zone_parts = []
    count_parts = []
    for key, weight in [
        ("exact_batter", exact_weight),
        ("stance_state", 0.45),
        ("stance_tto", 0.25),
        ("stance_only", 0.2),
        ("all", 0.1),
    ]:
        sample = buckets[key]
        if not sample:
            continue
        pitch_parts.append((Counter(row.get("pitch_type") or "UNKNOWN" for row in sample), weight))
        zone_parts.append((Counter(row.get("zone_9") or "UNKNOWN" for row in sample), weight))
        count_parts.append((Counter(row.get("count_state") or "UNKNOWN" for row in sample), weight))

    pitch_distribution = blended_distribution(pitch_parts)
    zone_distribution = blended_distribution(zone_parts)
    count_distribution = blended_distribution(count_parts)

    family_source = buckets["exact_batter"] or buckets["stance_state"] or buckets["stance_only"] or buckets["all"]
    total = len(family_source) or 1
    fastball_count = sum(1 for row in family_source if pitch_family(row.get("pitch_type") or "") == "FASTBALL")

    return {
        "sample_counts": {key: len(value) for key, value in buckets.items()},
        "fastball_yes_no": {
            "YES": round(fastball_count / total, 4),
            "NO": round((total - fastball_count) / total, 4),
        },
        "pitch_type_top": top_probabilities(pitch_distribution, top_n=4),
        "zone_top": top_probabilities(zone_distribution, top_n=4),
        "post_first_pitch_count_top": top_probabilities(count_distribution, top_n=4),
    }


def build_next_pitch_summary(next_pitch_rows: list[dict], batter_name: str, stance: str, runner_state: str, outs: int, first_pitch_type: str, count_state: str) -> dict:
    exact = [
        row for row in next_pitch_rows
        if row.get("batter_name") == batter_name
        and row.get("count_state") == count_state
        and row.get("current_pitch_type") == first_pitch_type
    ]
    stance_state = [
        row for row in next_pitch_rows
        if row.get("batter_stance") == stance
        and row.get("runner_state") == runner_state
        and int(row.get("outs") or 0) == outs
        and row.get("count_state") == count_state
        and row.get("current_pitch_type") == first_pitch_type
    ]
    stance_count = [
        row for row in next_pitch_rows
        if row.get("batter_stance") == stance
        and row.get("count_state") == count_state
        and row.get("current_pitch_type") == first_pitch_type
    ]
    type_count = [
        row for row in next_pitch_rows
        if row.get("current_pitch_type") == first_pitch_type and row.get("count_state") == count_state
    ]
    all_rows = [row for row in next_pitch_rows if row.get("count_state") == count_state]

    exact_weight = exact_batter_weight(len(exact))
    parts_type = []
    parts_zone = []
    for sample, weight in [
        (exact, exact_weight),
        (stance_state, 0.4),
        (stance_count, 0.25),
        (type_count, 0.25),
        (all_rows, 0.1),
    ]:
        if not sample:
            continue
        parts_type.append((Counter(row.get("next_pitch_type") or "UNKNOWN" for row in sample), weight))
        parts_zone.append((Counter(row.get("next_zone_9") or "UNKNOWN" for row in sample), weight))

    return {
        "sample_counts": {
            "exact": len(exact),
            "stance_state": len(stance_state),
            "stance_count": len(stance_count),
            "type_count": len(type_count),
            "all_rows": len(all_rows),
        },
        "next_pitch_type_top": top_probabilities(blended_distribution(parts_type), top_n=4),
        "next_zone_top": top_probabilities(blended_distribution(parts_zone), top_n=4),
    }


def pa_groups_from_white_context(rows: list[dict]) -> list[list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("game_id") or "", row.get("pa_number_in_game") or "")].append(row)
    return [value for _, value in sorted(grouped.items())]


def build_pa_outcome_summary(pa_rows: list[list[dict]], batter_name: str, stance: str, runner_state: str, outs: int, seen_count: int) -> dict:
    exact = []
    stance_state = []
    stance_tto_rows = []
    all_rows = []
    current_tto = tto_bucket(seen_count)
    for pa in pa_rows:
        first = pa[0]
        last = pa[-1]
        result = classify_pa_result(last.get("plate_result_text") or "")
        if result == "UNKNOWN":
            continue
        start_runner = first.get("runner_state") or ""
        start_outs = int(first.get("outs") or 0)
        start_stance = first.get("stance") or first.get("batter_stance") or "UNKNOWN"
        start_seen = int(first.get("batter_seen_count_in_game") or 1)
        if first.get("batter_name") == batter_name:
            exact.append(result)
        if start_stance == stance and start_runner == runner_state and start_outs == outs:
            stance_state.append(result)
        if start_stance == stance and tto_bucket(start_seen) == current_tto:
            stance_tto_rows.append(result)
        all_rows.append(result)

    exact_weight = exact_batter_weight(len(exact))
    parts = []
    for sample, weight in [
        (Counter(exact), exact_weight),
        (Counter(stance_state), 0.4),
        (Counter(stance_tto_rows), 0.3),
        (Counter(all_rows), 0.1),
    ]:
        if sample:
            parts.append((sample, weight))
    return {
        "sample_counts": {
            "exact": len(exact),
            "stance_state": len(stance_state),
            "stance_tto": len(stance_tto_rows),
            "all_rows": len(all_rows),
        },
        "top_results": top_probabilities(blended_distribution(parts), top_n=4),
    }


def batter_profiles_for_report(lineup: list[str], profile_2025: dict[str, dict], profile_2026: dict[str, dict], white_rows: list[dict]) -> list[dict]:
    white_seen = Counter(row.get("batter_name") or "" for row in white_rows)
    white_stance = {}
    for row in white_rows:
        white_stance[row.get("batter_name") or ""] = row.get("stance") or row.get("batter_stance") or "UNKNOWN"

    report_rows = []
    for slot, batter_name in enumerate(lineup, start=1):
        long_term = profile_2025.get(batter_name, {})
        current = profile_2026.get(batter_name, {})
        report_rows.append(
            {
                "slot": slot,
                "batter_name": batter_name,
                "stance": current.get("stance") or long_term.get("stance") or white_stance.get(batter_name) or "UNKNOWN",
                "white_2025_pitch_sample": white_seen.get(batter_name, 0),
                "season_2025_ba": long_term.get("ba", 0.0),
                "season_2025_whiff_rate": long_term.get("whiff_rate", 0.0),
                "current_2026_complete_pas": current.get("pas_complete", 0),
                "current_2026_complete_ba": current.get("ba_complete", 0.0),
                "current_2026_pitches_seen": current.get("pitches_seen", 0),
            }
        )
    return report_rows


def state_signature(state: GameState) -> tuple:
    occupied_bases = tuple(bool(runner) for runner in state.bases)
    return (state.inning, state.outs, occupied_bases, state.lineup_index, state.score_for_hanwha)


def merge_states(states: list[GameState]) -> list[GameState]:
    merged: dict[tuple, GameState] = {}
    for state in states:
        key = state_signature(state)
        if key not in merged:
            merged[key] = GameState(
                inning=state.inning,
                outs=state.outs,
                bases=state.bases,
                lineup_index=state.lineup_index,
                score_for_hanwha=state.score_for_hanwha,
                probability=state.probability,
                path=state.path[:],
            )
        else:
            merged[key].probability += state.probability
    return sorted(merged.values(), key=lambda item: item.probability, reverse=True)


def apply_pa_result(state: GameState, batter_name: str, result: str, branch_probability: float) -> GameState:
    first, second, third = state.bases
    outs = state.outs
    runs = 0

    if result == "OUT":
        return GameState(state.inning, outs + 1, state.bases, state.lineup_index + 1, state.score_for_hanwha, state.probability * branch_probability, state.path[:])

    if result == "WALK":
        if first and second and third:
            runs += 1
        return GameState(
            state.inning,
            outs,
            (batter_name, first if first else second, second if second else third),
            state.lineup_index + 1,
            state.score_for_hanwha + runs,
            state.probability * branch_probability,
            state.path[:],
        )

    if result == "SINGLE":
        runs += 1 if third else 0
        return GameState(state.inning, outs, (batter_name, first, second), state.lineup_index + 1, state.score_for_hanwha + runs, state.probability * branch_probability, state.path[:])

    if result == "DOUBLE":
        runs += 1 if second else 0
        runs += 1 if third else 0
        return GameState(state.inning, outs, (None, batter_name, first), state.lineup_index + 1, state.score_for_hanwha + runs, state.probability * branch_probability, state.path[:])

    if result == "TRIPLE":
        runs += sum(1 for runner in state.bases if runner)
        return GameState(state.inning, outs, (None, None, batter_name), state.lineup_index + 1, state.score_for_hanwha + runs, state.probability * branch_probability, state.path[:])

    if result == "HR":
        runs += sum(1 for runner in state.bases if runner) + 1
        return GameState(state.inning, outs, (None, None, None), state.lineup_index + 1, state.score_for_hanwha + runs, state.probability * branch_probability, state.path[:])

    return GameState(state.inning, outs + 1, state.bases, state.lineup_index + 1, state.score_for_hanwha, state.probability * branch_probability, state.path[:])


def advance_beam_for_pa(state: GameState, batter_name: str, outcome_summary: dict, branch_text: str, top_n: int = 3) -> list[GameState]:
    branches = outcome_summary["top_results"] or [{"value": "OUT", "probability": 1.0}]
    next_states: list[GameState] = []
    remainder = max(0.0, 1.0 - sum(item["probability"] for item in branches[:top_n]))
    for item in branches[:top_n]:
        new_state = apply_pa_result(state, batter_name, item["value"], item["probability"])
        new_state.path.append(f"{branch_text} -> {item['value']} {item['probability']:.1%}")
        next_states.append(new_state)
    if remainder > 0.03:
        new_state = apply_pa_result(state, batter_name, "OUT", remainder)
        new_state.path.append(f"{branch_text} -> 기타 {remainder:.1%}")
        next_states.append(new_state)
    return next_states


def build_branching_report() -> tuple[str, dict]:
    lineup_info = infer_projected_lineup()
    lineup = lineup_info["projected_lineup"]
    profile_2025 = build_2025_batter_profiles(lineup)
    profile_2026 = build_2026_current_profiles(lineup)
    white_context_rows = read_rows(WHITE_CONTEXT_CSV)
    white_next_rows = read_rows(WHITE_NEXT_PITCH_CSV)
    first_pitch_rows = build_first_pitch_reference(white_context_rows)
    white_pa_rows = pa_groups_from_white_context(white_context_rows)
    batter_profiles = batter_profiles_for_report(lineup, profile_2025, profile_2026, white_context_rows)
    profile_map = {row["batter_name"]: row for row in batter_profiles}

    beam: list[GameState] = [GameState(1, 0, (None, None, None), 0, 0, 1.0, [])]
    inning_sections: list[dict] = []

    for inning in range(1, 6):
        inning_states = [state for state in beam if state.inning == inning] or [GameState(inning, 0, (None, None, None), 0, 0, 1.0, [])]
        working_states = inning_states[:]
        pa_entries: list[dict] = []
        step_index = 1

        while any(state.outs < 3 for state in working_states) and step_index <= 7:
            active_states = merge_states([state for state in working_states if state.outs < 3])[:3]
            completed_states = [state for state in working_states if state.outs >= 3]
            next_states_accum: list[GameState] = completed_states[:]

            for state_rank, state in enumerate(active_states, start=1):
                batter_name = lineup[state.lineup_index % len(lineup)]
                batter_profile = profile_map[batter_name]
                seen_count = (state.lineup_index // len(lineup)) + 1
                stance = batter_profile["stance"]
                runner_state = bases_label(state.bases)

                first_summary = build_first_pitch_summary(first_pitch_rows, batter_name, stance, runner_state, state.outs, tto_bucket(seen_count))
                top_first_pitch_type = first_summary["pitch_type_top"][0]["value"] if first_summary["pitch_type_top"] else "직구"
                next_pitch_summaries = []
                for count_branch in first_summary["post_first_pitch_count_top"][:2]:
                    count_state = count_branch["value"]
                    if count_state == "0-0":
                        continue
                    next_pitch_summaries.append(
                        {
                            "count_state": count_state,
                            "probability": count_branch["probability"],
                            "summary": build_next_pitch_summary(white_next_rows, batter_name, stance, runner_state, state.outs, top_first_pitch_type, count_state),
                        }
                    )

                outcome_summary = build_pa_outcome_summary(white_pa_rows, batter_name, stance, runner_state, state.outs, seen_count)
                before_state = f"{inning}회초 / {state.outs}사 / 주자 {runner_state} / 타순 {((state.lineup_index % 9) + 1)}번 / 한화득점 {state.score_for_hanwha}"
                branch_text = f"{before_state} {batter_name}"

                pa_entries.append(
                    {
                        "inning": inning,
                        "step": step_index,
                        "state_rank": state_rank,
                        "state_probability": round(state.probability, 4),
                        "before_state": before_state,
                        "batter_name": batter_name,
                        "stance": stance,
                        "seen_count": seen_count,
                        "first_pitch": first_summary,
                        "next_pitch": next_pitch_summaries,
                        "pa_outcome": outcome_summary,
                    }
                )
                next_states_accum.extend(advance_beam_for_pa(state, batter_name, outcome_summary, branch_text))

            working_states = merge_states(next_states_accum)[:8]
            step_index += 1

        carry_over = []
        for state in working_states:
            if state.outs >= 3:
                carry_over.append(GameState(inning + 1, 0, (None, None, None), state.lineup_index, state.score_for_hanwha, state.probability, state.path[:]))
            else:
                carry_over.append(state)
        beam = merge_states(carry_over)[:8]
        inning_sections.append(
            {
                "inning": inning,
                "entries": pa_entries,
                "ending_states": [
                    {
                        "next_inning": state.inning,
                        "lineup_index": state.lineup_index,
                        "score_for_hanwha": state.score_for_hanwha,
                        "probability": round(state.probability, 4),
                    }
                    for state in beam[:5]
                ],
            }
        )

    lines = []
    lines.append(f"# 화이트 대 한화 5회까지 조건부 예측 브랜칭 리포트 ({REPORT_DATE})")
    lines.append("")
    lines.append("## 문서 목적")
    lines.append("- 내일 경기 종료 후 실제 투구와 비교할 수 있도록, 화이트의 2025 투구 기록과 2026 현재까지 로컬에 확보된 한화 타순 정보를 이용해 5회초까지의 조건부 예측을 미리 기록합니다.")
    lines.append("- 이 문서는 Git 반영용이 아니라 내부 사전 기록용입니다.")
    lines.append("")
    lines.append("## 사용한 데이터")
    lines.append(f"- 화이트 2025 pitch context: `{WHITE_CONTEXT_CSV.as_posix()}`")
    lines.append(f"- 화이트 초구 이후 next-pitch table: `{WHITE_NEXT_PITCH_CSV.as_posix()}`")
    lines.append(f"- 리그 전체 2025 pitch data: `{FULL_2025_PITCHES_CSV.as_posix()}`")
    lines.append(f"- 한화 2026 현재까지 로컬 raw: `{RAW_2026_DIR.as_posix()}` 아래 `*HH*02026` 파일")
    lines.append("")
    lines.append("## 핵심 가정")
    lines.append("- 라인업은 2026 로컬 raw에 잡힌 최근 4경기의 선발 타순 mode를 기준으로 잡았습니다.")
    lines.append("- 포수 영향은 화이트 2025 수신 비중 전체를 내재적으로 반영합니다. 즉 특정 포수를 고정하지 않고, 화이트의 실제 2025 receiving mix를 포함한 분포입니다.")
    lines.append("- 초구 분기 문서는 `직구계 YES/NO`, `초구 뒤 카운트`, `그 카운트에서의 2구 후보`, `타석 결과 분기`, `그 결과로 인한 다음 주자상황`을 중심으로 적습니다.")
    lines.append("- 5회 전체를 완전 전개하면 경우의수가 폭증하므로, 각 단계에서는 누적 확률이 높은 상태 3개를 중심으로 열고 나머지는 `기타`로 압축했습니다.")
    lines.append("- score_diff는 상대 공격 예측을 따로 두지 않았기 때문에, 한화 득점 누적만 화이트 측 압박 신호로 간주했습니다.")
    lines.append("")
    lines.append("## 예상 라인업 가정")
    for slot, name in enumerate(lineup, start=1):
        alternatives = lineup_info["slot_alternatives"][slot]
        alt_text = ", ".join(f"{item['name']}({item['count']})" for item in alternatives)
        lines.append(f"- {slot}번 {name}: slot vote {alt_text}")
    lines.append("")
    lines.append(f"- latest local lineup source: `{lineup_info['latest_source_file']}`")
    lines.append("")
    lines.append("## 타자별 prior 요약")
    for row in batter_profiles:
        lines.append(
            f"- {row['slot']}번 {row['batter_name']} ({row['stance']}): 2025 BA {row['season_2025_ba']:.4f}, "
            f"2025 whiff {row['season_2025_whiff_rate']:.4f}, 2026 complete PA {row['current_2026_complete_pas']}, "
            f"2026 BA {row['current_2026_complete_ba']:.4f}, 화이트 2025 sample {row['white_2025_pitch_sample']} pitches"
        )
    lines.append("")

    for inning in inning_sections:
        lines.append(f"## {inning['inning']}회초 브랜칭")
        for entry in inning["entries"]:
            first_pitch = entry["first_pitch"]
            lines.append(
                f"### PA step {entry['step']} / 상태 {entry['state_rank']} | 누적확률 {entry['state_probability']:.1%} | "
                f"{entry['before_state']} | {entry['batter_name']} ({entry['stance']})"
            )
            lines.append(f"- 초구 직구계 YES {first_pitch['fastball_yes_no']['YES']:.1%} / NO {first_pitch['fastball_yes_no']['NO']:.1%}")
            lines.append("- 초구 구종 상위: " + ", ".join(f"{item['value']} {item['probability']:.1%}" for item in first_pitch["pitch_type_top"]))
            lines.append("- 초구 위치 상위: " + ", ".join(f"{item['value']} {item['probability']:.1%}" for item in first_pitch["zone_top"]))
            lines.append("- 초구 직후 카운트 상위: " + ", ".join(f"{item['value']} {item['probability']:.1%}" for item in first_pitch["post_first_pitch_count_top"]))
            for branch in entry["next_pitch"]:
                next_types = ", ".join(f"{item['value']} {item['probability']:.1%}" for item in branch["summary"]["next_pitch_type_top"]) or "데이터 부족"
                next_zones = ", ".join(f"{item['value']} {item['probability']:.1%}" for item in branch["summary"]["next_zone_top"]) or "데이터 부족"
                lines.append(f"- {branch['count_state']} 분기 ({branch['probability']:.1%}): 2구 구종 {next_types} | 2구 위치 {next_zones}")
            lines.append("- 타석 결과 분포: " + ", ".join(f"{item['value']} {item['probability']:.1%}" for item in entry["pa_outcome"]["top_results"]))
            top_result = entry["pa_outcome"]["top_results"][0] if entry["pa_outcome"]["top_results"] else {"value": "OUT", "probability": 1.0}
            lines.append(f"- 메인 분기 해석: {top_result['value']} {top_result['probability']:.1%}가 가장 높아, 다음 상태는 이 결과를 기준으로 가장 자주 이어집니다.")
            lines.append("")
        lines.append("- 회 종료 후 carry-over 상위: " + ", ".join(
            f"다음이닝 타순 {((state['lineup_index'] % 9) + 1)}번 / 한화득점 {state['score_for_hanwha']} / 확률 {state['probability']:.1%}"
            for state in inning["ending_states"]
        ))
        lines.append("")

    payload = {
        "report_date": REPORT_DATE,
        "lineup_info": lineup_info,
        "batter_profiles": batter_profiles,
        "inning_sections": inning_sections,
    }
    return "\n".join(lines).strip() + "\n", payload


def main() -> None:
    report_text, payload = build_branching_report()
    write_text(OUTPUT_DIR / "white_hanwha_branching_report.md", report_text)
    write_json(OUTPUT_DIR / "white_hanwha_branching_report.json", payload)
    print((OUTPUT_DIR / "white_hanwha_branching_report.md").as_posix())
    print((OUTPUT_DIR / "white_hanwha_branching_report.json").as_posix())


if __name__ == "__main__":
    main()
