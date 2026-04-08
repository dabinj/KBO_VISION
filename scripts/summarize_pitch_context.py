#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def top_pct(counter: Counter, limit: int | None = None) -> list[dict]:
    total = sum(counter.values())
    rows = []
    items = counter.most_common(limit)
    for key, count in items:
        rows.append(
            {
                "name": key,
                "count": count,
                "pct": round((count / total) * 100, 3) if total else 0.0,
            }
        )
    return rows


def nested_distribution(rows: list[dict], group_key: str, value_key: str, top_groups: int = 20) -> dict:
    grouped = defaultdict(Counter)
    for row in rows:
        grouped[row.get(group_key) or "UNKNOWN"][row.get(value_key) or "UNKNOWN"] += 1

    result = {}
    ordered_groups = sorted(grouped.items(), key=lambda item: sum(item[1].values()), reverse=True)[:top_groups]
    for group_name, counter in ordered_groups:
        result[group_name] = top_pct(counter)
    return result


def transition_distribution(rows: list[dict], prev_key: str, next_key: str, top_prev: int = 12) -> dict:
    grouped = defaultdict(Counter)
    for row in rows:
        prev_value = row.get(prev_key) or "START"
        next_value = row.get(next_key) or "UNKNOWN"
        grouped[prev_value][next_value] += 1

    result = {}
    ordered_prev = sorted(grouped.items(), key=lambda item: sum(item[1].values()), reverse=True)[:top_prev]
    for prev_name, counter in ordered_prev:
        result[prev_name] = top_pct(counter)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a context-enriched pitch CSV.")
    parser.add_argument("--input-csv", required=True, help="Input context CSV")
    parser.add_argument("--output-json", required=True, help="Output JSON summary")
    parser.add_argument("--entity-name", required=True, help="Entity label for the report")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_json)
    rows = load_rows(input_path)

    summary = {
        "entity_name": args.entity_name,
        "input_csv": str(input_path),
        "rows": len(rows),
        "overall_pitch_mix": top_pct(Counter(row.get("pitch_type") or "UNKNOWN" for row in rows)),
        "count_state_to_pitch_mix": nested_distribution(rows, "count_state", "pitch_type"),
        "stance_to_pitch_mix": nested_distribution(rows, "stance", "pitch_type"),
        "catcher_to_pitch_mix": nested_distribution(rows, "catcher_name", "pitch_type"),
        "pitcher_to_pitch_mix": nested_distribution(rows, "pitcher_name", "pitch_type"),
        "zone_9_to_pitch_mix": nested_distribution(rows, "zone_9", "pitch_type"),
        "prev_pa_pitch_to_next_pitch": transition_distribution(rows, "prev_pitch_type_pa_1", "pitch_type"),
        "prev_game_pitch_to_next_pitch": transition_distribution(rows, "prev_pitch_type_game_1", "pitch_type"),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rows: {len(rows)}")
    print(f"output_json: {output_path}")


if __name__ == "__main__":
    main()
