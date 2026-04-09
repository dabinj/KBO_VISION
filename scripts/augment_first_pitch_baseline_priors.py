#!/usr/bin/env python3

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


GROUP_SPECS = {
    "overall": [],
    "catcher": ["catcher_name"],
    "opponent": ["opponent_team_code"],
    "catcher_opponent": ["catcher_name", "opponent_team_code"],
    "stance": ["batter_stance"],
    "count": ["count_state"],
    "runner_outs": ["runner_state", "outs"],
    "count_runner_outs": ["count_state", "runner_state", "outs"],
    "inning_bucket": ["inning_bucket"],
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


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("inning") or 0),
            0 if (row.get("half") or "0") in {"0", "T", "TOP"} else 1,
            int(row.get("outs") or 0),
            row.get("batter_code") or "",
        ),
    )


def inning_bucket(value: str | None) -> str:
    try:
        inning = int(value or 0)
    except ValueError:
        return "UNKNOWN"
    if inning <= 2:
        return "EARLY"
    if inning <= 4:
        return "MID"
    return "LATE"


def make_key(row: dict, columns: list[str]) -> tuple[str, ...]:
    return tuple((row.get(column) or "__MISSING__") for column in columns)


def normalize_label(label: str) -> str:
    safe = []
    for char in label:
        if char.isalnum():
            safe.append(char)
        else:
            safe.append("_")
    normalized = "".join(safe).strip("_")
    return normalized or "MISSING"


def smoothed_distribution(
    counts: Counter,
    global_counts: Counter,
    labels: list[str],
    alpha: float,
) -> dict[str, float]:
    total_local = sum(counts.values())
    total_global = sum(global_counts.values()) or 1
    denominator = total_local + alpha
    probs = {}
    for label in labels:
        global_prob = global_counts[label] / total_global
        probs[label] = (counts[label] + alpha * global_prob) / denominator if denominator else global_prob
    return probs


def best_label_and_prob(distribution: dict[str, float]) -> tuple[str, float]:
    label = max(distribution, key=distribution.get)
    return label, distribution[label]


def augment_rows(rows: list[dict], target: str, alpha: float) -> list[dict]:
    labels = sorted({row.get(target) or "__MISSING__" for row in rows})
    global_counts: Counter = Counter()
    grouped_counts: dict[str, defaultdict[tuple[str, ...], Counter]] = {
        name: defaultdict(Counter) for name in GROUP_SPECS
    }

    augmented = []
    for original in sort_rows(rows):
        row = dict(original)
        row["inning_bucket"] = inning_bucket(row.get("inning"))

        global_dist = smoothed_distribution(Counter(), global_counts, labels, alpha) if sum(global_counts.values()) == 0 else smoothed_distribution(global_counts, global_counts, labels, alpha)
        global_top_label, global_top_prob = best_label_and_prob(global_dist)
        row["baseline_overall_top1_label"] = global_top_label
        row["baseline_overall_top1_prob"] = f"{global_top_prob:.6f}"

        for group_name, columns in GROUP_SPECS.items():
            if group_name == "overall":
                dist = global_dist
            else:
                key = make_key(row, columns)
                local_counts = grouped_counts[group_name][key]
                dist = smoothed_distribution(local_counts, global_counts, labels, alpha)

            top_label, top_prob = best_label_and_prob(dist)
            row[f"baseline_{group_name}_top1_label"] = top_label
            row[f"baseline_{group_name}_top1_prob"] = f"{top_prob:.6f}"
            for label in labels:
                safe_label = normalize_label(label)
                row[f"baseline_{group_name}_prob_{safe_label}"] = f"{dist[label]:.6f}"

        actual_label = row.get(target) or "__MISSING__"
        global_counts[actual_label] += 1
        for group_name, columns in GROUP_SPECS.items():
            if group_name == "overall":
                continue
            key = make_key(row, columns)
            grouped_counts[group_name][key][actual_label] += 1

        del row["inning_bucket"]
        augmented.append(row)
    return augmented


def main() -> None:
    parser = argparse.ArgumentParser(description="Add leakage-safe baseline prior features to first-pitch tables.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--target", default="first_pitch_type")
    parser.add_argument("--alpha", type=float, default=20.0)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    augmented = augment_rows(rows, args.target, args.alpha)
    write_rows(Path(args.output_csv), augmented)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(augmented)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
