#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


COUNT_ORDER = ["0-0", "0-1", "0-2", "1-0", "1-1", "1-2", "2-0", "2-1", "2-2", "3-0", "3-1", "3-2"]


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pitch_family(pitch_type: str) -> str:
    return "FASTBALL" if pitch_type in {"직구", "투심", "커터"} else "BREAKING"


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
    if "삼진" in text:
        return "K"
    return "OUT"


def pct_rows(counter: Counter, limit: int | None = None) -> list[dict]:
    total = sum(counter.values())
    rows = []
    for name, count in counter.most_common(limit):
        rows.append(
            {
                "name": name,
                "count": count,
                "pct": round((count / total) * 100, 3) if total else 0.0,
            }
        )
    return rows


def seq_string(values: list[str]) -> str:
    return " > ".join(values) if values else "UNKNOWN"


def group_plate_appearances(rows: list[dict]) -> list[list[dict]]:
    grouped = []
    current = []
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


def annotate_pre_pitch_counts(pa_groups: list[list[dict]]) -> list[dict]:
    annotated = []
    for pa in pa_groups:
        balls = 0
        strikes = 0
        for row in pa:
            copied = dict(row)
            copied["pre_count_state"] = f"{balls}-{strikes}"
            annotated.append(copied)

            result = row.get("pitch_result") or ""
            if result == "B":
                balls = min(3, balls + 1)
            elif result in {"T", "S"}:
                strikes = min(2, strikes + 1)
            elif result == "F":
                if strikes < 2:
                    strikes += 1
    return annotated


def summarize_full_sequences(rows: list[dict]) -> dict:
    pa_groups = group_plate_appearances(rows)
    full_sequences = Counter()
    full_family_sequences = Counter()
    sequence_by_length = defaultdict(Counter)
    first_to_last = Counter()
    finish_pitch_by_first = defaultdict(Counter)
    result_by_sequence = defaultdict(Counter)
    pa_length = Counter()

    for pa in pa_groups:
        pitch_types = [row.get("pitch_type") or "UNKNOWN" for row in pa]
        pitch_families = [pitch_family(pitch) for pitch in pitch_types]
        result = classify_pa_result(pa[-1].get("plate_result_text") or "")
        full_seq = seq_string(pitch_types)
        family_seq = seq_string(pitch_families)

        full_sequences[full_seq] += 1
        full_family_sequences[family_seq] += 1
        sequence_by_length[len(pa)][full_seq] += 1
        first_to_last[f"{pitch_types[0]} -> {pitch_types[-1]}"] += 1
        finish_pitch_by_first[pitch_types[0]][pitch_types[-1]] += 1
        result_by_sequence[full_seq][result] += 1
        pa_length[len(pa)] += 1

    return {
        "plate_appearances": len(pa_groups),
        "pa_length_distribution": pct_rows(pa_length, limit=12),
        "top_full_sequences": pct_rows(full_sequences, limit=25),
        "top_full_family_sequences": pct_rows(full_family_sequences, limit=20),
        "top_first_to_last_transitions": pct_rows(first_to_last, limit=20),
        "top_sequences_by_length": {
            str(length): pct_rows(counter, limit=12)
            for length, counter in sorted(sequence_by_length.items())
        },
        "finish_pitch_by_first_pitch": {
            first_pitch: pct_rows(counter, limit=8)
            for first_pitch, counter in finish_pitch_by_first.items()
        },
        "result_by_top_sequences": {
            sequence: pct_rows(result_by_sequence[sequence], limit=6)
            for sequence, _count in full_sequences.most_common(12)
        },
    }


def summarize_count_patterns(rows: list[dict]) -> dict:
    pa_groups = group_plate_appearances(rows)
    annotated_rows = annotate_pre_pitch_counts(pa_groups)
    pitch_mix = defaultdict(Counter)
    family_mix = defaultdict(Counter)
    zone_mix = defaultdict(Counter)
    result_mix = defaultdict(Counter)
    stance_mix = defaultdict(lambda: defaultdict(Counter))

    for row in annotated_rows:
        count_state = row.get("pre_count_state") or "UNKNOWN"
        pitch_type = row.get("pitch_type") or "UNKNOWN"
        stance = row.get("stance") or "UNKNOWN"
        zone = row.get("zone_9") or "UNKNOWN"
        result = row.get("pitch_result") or "UNKNOWN"

        pitch_mix[count_state][pitch_type] += 1
        family_mix[count_state][pitch_family(pitch_type)] += 1
        zone_mix[count_state][zone] += 1
        result_mix[count_state][result] += 1
        stance_mix[count_state][stance][pitch_type] += 1

    ordered_counts = [count for count in COUNT_ORDER if count in pitch_mix] + [
        count for count in sorted(pitch_mix) if count not in COUNT_ORDER
    ]

    count_rows = []
    for count_state in ordered_counts:
        top_pitch = pct_rows(pitch_mix[count_state], limit=5)
        top_family = pct_rows(family_mix[count_state], limit=3)
        top_zone = pct_rows(zone_mix[count_state], limit=5)
        pitch_results = pct_rows(result_mix[count_state], limit=5)
        stance_detail = {
            stance: pct_rows(counter, limit=5)
            for stance, counter in stance_mix[count_state].items()
        }
        total = sum(pitch_mix[count_state].values())
        count_rows.append(
            {
                "count_state": count_state,
                "total_pitches": total,
                "top_pitch_types": top_pitch,
                "top_pitch_family": top_family,
                "top_zones": top_zone,
                "pitch_result_distribution": pitch_results,
                "pitch_types_by_stance": stance_detail,
            }
        )

    return {"count_state_rows": count_rows}


def render_markdown(title: str, full_summary: dict, count_summary: dict) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- 타석 수: `{full_summary['plate_appearances']}`")
    lines.append("")

    lines.append("## 전체 타석 시퀀스 규칙")
    lines.append("### 타석 길이 분포")
    for row in full_summary["pa_length_distribution"]:
        lines.append(f"- {row['name']}구: `{row['count']}`회 (`{row['pct']}%`)")
    lines.append("")

    lines.append("### 가장 많은 전체 시퀀스")
    for row in full_summary["top_full_sequences"]:
        lines.append(f"- {row['name']}: `{row['count']}`회 (`{row['pct']}%`)")
    lines.append("")

    lines.append("### 가장 많은 패밀리 시퀀스")
    for row in full_summary["top_full_family_sequences"]:
        lines.append(f"- {row['name']}: `{row['count']}`회 (`{row['pct']}%`)")
    lines.append("")

    lines.append("### 초구 -> 마지막 공 전이")
    for row in full_summary["top_first_to_last_transitions"]:
        lines.append(f"- {row['name']}: `{row['count']}`회 (`{row['pct']}%`)")
    lines.append("")

    lines.append("### 구간별 상위 시퀀스")
    for length, rows in full_summary["top_sequences_by_length"].items():
        lines.append(f"- {length}구 타석: " + ", ".join(f"{row['name']} {row['pct']}%" for row in rows[:6]))
    lines.append("")

    lines.append("### 시작 구종별 결정구")
    for first_pitch, rows in full_summary["finish_pitch_by_first_pitch"].items():
        lines.append(f"- {first_pitch}: " + ", ".join(f"{row['name']} {row['pct']}%" for row in rows[:5]))
    lines.append("")

    lines.append("## 볼카운트별 투구 규칙")
    for row in count_summary["count_state_rows"]:
        lines.append(f"### {row['count_state']} (`{row['total_pitches']}`구)")
        lines.append("- 가장 많이 나온 공: " + ", ".join(f"{item['name']} {item['pct']}%" for item in row["top_pitch_types"][:5]))
        lines.append("- 속구/변화구: " + ", ".join(f"{item['name']} {item['pct']}%" for item in row["top_pitch_family"][:3]))
        lines.append("- 위치 상위: " + ", ".join(f"{item['name']} {item['pct']}%" for item in row["top_zones"][:5]))
        lines.append("- 결과 분포: " + ", ".join(f"{item['name']} {item['pct']}%" for item in row["pitch_result_distribution"][:5]))
        for stance, items in row["pitch_types_by_stance"].items():
            lines.append(f"- {stance}타 기준: " + ", ".join(f"{item['name']} {item['pct']}%" for item in items[:5]))
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze full PA sequences and count-state pitch rules.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    full_summary = summarize_full_sequences(rows)
    count_summary = summarize_count_patterns(rows)
    payload = {
        "title": args.title,
        "full_sequence_summary": full_summary,
        "count_state_summary": count_summary,
    }
    write_json(Path(args.output_json), payload)
    write_text(Path(args.output_md), render_markdown(args.title, full_summary, count_summary))
    print(f"rows: {len(rows)}")
    print(f"plate_appearances: {full_summary['plate_appearances']}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")


if __name__ == "__main__":
    main()
