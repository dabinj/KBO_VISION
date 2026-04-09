#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


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


def pct_rows(counter: Counter, limit: int = 10) -> list[dict]:
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


def seq_string(values: list[str]) -> str:
    return " > ".join(values) if values else "UNKNOWN"


def summarize_pas(pa_groups: list[list[dict]]) -> dict:
    first_two = Counter()
    first_three = Counter()
    full_seq = Counter()
    family_first_two = Counter()
    family_full = Counter()
    finish_pitch = Counter()
    finish_pitch_by_result = defaultdict(Counter)
    first_pitch = Counter()
    first_pitch_by_stance = defaultdict(Counter)
    first_two_by_stance = defaultdict(Counter)
    result_counter = Counter()
    pa_len_counter = Counter()

    for pa in pa_groups:
        pitch_types = [row.get("pitch_type") or "UNKNOWN" for row in pa]
        families = [pitch_family(name) for name in pitch_types]
        stance = pa[0].get("stance") or "UNKNOWN"
        result = classify_pa_result(pa[-1].get("plate_result_text") or "")

        first_pitch[pitch_types[0]] += 1
        first_pitch_by_stance[stance][pitch_types[0]] += 1
        first_two[seq_string(pitch_types[:2])] += 1
        first_three[seq_string(pitch_types[:3])] += 1
        full_seq[seq_string(pitch_types)] += 1
        family_first_two[seq_string(families[:2])] += 1
        family_full[seq_string(families)] += 1
        finish_pitch[pitch_types[-1]] += 1
        finish_pitch_by_result[result][pitch_types[-1]] += 1
        first_two_by_stance[stance][seq_string(pitch_types[:2])] += 1
        result_counter[result] += 1
        pa_len_counter[len(pa)] += 1

    return {
        "plate_appearances": len(pa_groups),
        "pa_length_distribution": pct_rows(pa_len_counter, limit=12),
        "pa_result_distribution": pct_rows(result_counter, limit=10),
        "first_pitch_distribution": pct_rows(first_pitch, limit=10),
        "top_first_two_sequences": pct_rows(first_two, limit=15),
        "top_first_three_sequences": pct_rows(first_three, limit=15),
        "top_full_sequences": pct_rows(full_seq, limit=15),
        "top_first_two_family_sequences": pct_rows(family_first_two, limit=10),
        "top_full_family_sequences": pct_rows(family_full, limit=10),
        "finish_pitch_distribution": pct_rows(finish_pitch, limit=10),
        "finish_pitch_by_result": {
            result: pct_rows(counter, limit=10)
            for result, counter in finish_pitch_by_result.items()
        },
        "first_pitch_by_stance": {
            stance: pct_rows(counter, limit=10)
            for stance, counter in first_pitch_by_stance.items()
        },
        "first_two_by_stance": {
            stance: pct_rows(counter, limit=10)
            for stance, counter in first_two_by_stance.items()
        },
    }


def render_markdown(title: str, summary: dict) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- 타석 수: `{summary['plate_appearances']}`")
    lines.append("")

    sections = [
        ("타석 길이 분포", "pa_length_distribution"),
        ("타석 결과 분포", "pa_result_distribution"),
        ("초구 분포", "first_pitch_distribution"),
        ("가장 많은 초구-2구 패턴", "top_first_two_sequences"),
        ("가장 많은 초구-2구-3구 패턴", "top_first_three_sequences"),
        ("가장 많은 풀 시퀀스", "top_full_sequences"),
        ("가장 많은 초구-2구 패밀리 패턴", "top_first_two_family_sequences"),
        ("가장 많은 풀 패밀리 패턴", "top_full_family_sequences"),
        ("결정구 분포", "finish_pitch_distribution"),
    ]
    for header, key in sections:
        lines.append(f"## {header}")
        for row in summary[key]:
            lines.append(f"- {row['name']}: `{row['count']}`회 (`{row['pct']}%`)")
        lines.append("")

    lines.append("## 결과별 결정구")
    for result, rows in summary["finish_pitch_by_result"].items():
        joined = ", ".join(f"{row['name']} {row['pct']}%" for row in rows[:5])
        lines.append(f"- {result}: {joined}")
    lines.append("")

    lines.append("## 좌/우타별 초구")
    for stance, rows in summary["first_pitch_by_stance"].items():
        joined = ", ".join(f"{row['name']} {row['pct']}%" for row in rows[:5])
        lines.append(f"- {stance}: {joined}")
    lines.append("")

    lines.append("## 좌/우타별 초구-2구 패턴")
    for stance, rows in summary["first_two_by_stance"].items():
        joined = ", ".join(f"{row['name']} {row['pct']}%" for row in rows[:5])
        lines.append(f"- {stance}: {joined}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a pitcher's plate-appearance level pitch patterns.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    pa_groups = group_plate_appearances(rows)
    summary = summarize_pas(pa_groups)
    write_json(Path(args.output_json), summary)
    write_text(Path(args.output_md), render_markdown(args.title, summary))
    print(f"plate_appearances: {summary['plate_appearances']}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")


if __name__ == "__main__":
    main()
