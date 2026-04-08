#!/usr/bin/env python3

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_rows_timewise(rows: list[dict], train_ratio: float = 0.8) -> tuple[list[dict], list[dict]]:
    rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("pitch_index_in_game") or 0),
        ),
    )
    split_index = max(1, int(len(rows) * train_ratio))
    return rows[:split_index], rows[split_index:]


def build_key(row: dict, feature_names: list[str]) -> tuple:
    return tuple(row.get(name) or "" for name in feature_names)


def fit_frequency_model(rows: list[dict], target: str, feature_sets: list[list[str]]) -> dict:
    model = {"global": Counter(), "levels": []}
    for row in rows:
        model["global"][row[target]] += 1

    for feature_names in feature_sets:
        counter = defaultdict(Counter)
        for row in rows:
            counter[build_key(row, feature_names)][row[target]] += 1
        model["levels"].append({"features": feature_names, "counter": counter})
    return model


def predict_distribution(model: dict, row: dict) -> Counter:
    for level in reversed(model["levels"]):
        key = build_key(row, level["features"])
        counter = level["counter"].get(key)
        if counter:
            return counter
    return model["global"]


def metrics(model: dict, rows: list[dict], target: str) -> dict:
    if not rows:
        return {"rows": 0}

    top1 = 0
    top3 = 0
    log_loss = 0.0

    for row in rows:
        counter = predict_distribution(model, row)
        total = sum(counter.values())
        ordered = [label for label, _ in counter.most_common()]
        actual = row[target]
        if ordered and ordered[0] == actual:
            top1 += 1
        if actual in ordered[:3]:
            top3 += 1

        prob = counter[actual] / total if actual in counter else 1e-9
        log_loss += -math.log(max(prob, 1e-9))

    return {
        "rows": len(rows),
        "top1_accuracy": round(top1 / len(rows), 4),
        "top3_accuracy": round(top3 / len(rows), 4),
        "avg_log_loss": round(log_loss / len(rows), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a simple frequency baseline on a model table.")
    parser.add_argument("--input-csv", required=True, help="Model table CSV")
    parser.add_argument("--target", default="pitch_type", help="Target column")
    parser.add_argument("--feature-sets-json", required=True, help="JSON array of feature-name arrays")
    parser.add_argument("--output-json", required=True, help="Output metrics JSON")
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    train_rows, test_rows = split_rows_timewise(rows)
    feature_sets = json.loads(args.feature_sets_json)
    model = fit_frequency_model(train_rows, args.target, feature_sets)
    report = {
        "input_csv": args.input_csv,
        "target": args.target,
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "feature_sets": feature_sets,
        "train_metrics": metrics(model, train_rows, args.target),
        "test_metrics": metrics(model, test_rows, args.target),
        "global_pitch_mix": model["global"].most_common(),
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
