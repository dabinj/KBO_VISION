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


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
        return {"rows": 0, "top1_accuracy": 0.0, "top3_accuracy": 0.0, "avg_log_loss": 0.0}
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


def run_staged_experiment(rows: list[dict], target: str, stages: list[dict]) -> list[dict]:
    train_rows, test_rows = split_rows_timewise(rows)
    results = []
    feature_sets = []
    for stage in stages:
        feature_sets.append(stage["features"])
        model = fit_frequency_model(train_rows, target, feature_sets)
        results.append(
            {
                "label": stage["label"],
                "features": feature_sets.copy(),
                "train": metrics(model, train_rows, target),
                "test": metrics(model, test_rows, target),
            }
        )
    return results


def only_second_pitch(rows: list[dict]) -> list[dict]:
    return [row for row in rows if (row.get("pitch_index_in_pa") or "") == "2"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run White / catcher baseline experiments.")
    parser.add_argument("--white-csv", required=True)
    parser.add_argument("--jo-csv", required=True)
    parser.add_argument("--lee-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    white_rows = read_rows(Path(args.white_csv))
    jo_rows = read_rows(Path(args.jo_csv))
    lee_rows = read_rows(Path(args.lee_csv))

    white_stages = [
        {"label": "Count", "features": ["count_state"]},
        {"label": "Count+Runner", "features": ["count_state", "runner_state"]},
        {"label": "Count+Runner+Score", "features": ["count_state", "runner_state", "score_diff_pitcher"]},
        {"label": "Count+Runner+Score+Stance", "features": ["count_state", "runner_state", "score_diff_pitcher", "batter_stance"]},
        {"label": "Count+Runner+Score+Stance+BA", "features": ["count_state", "runner_state", "score_diff_pitcher", "batter_stance", "batter_season_ba_bucket"]},
        {"label": "Count+Runner+Score+Stance+BA+PrevType", "features": ["count_state", "runner_state", "score_diff_pitcher", "batter_stance", "batter_season_ba_bucket", "prev_pitch_type_pa_1"]},
        {"label": "Count+Runner+Score+Stance+BA+PrevType+PrevZone", "features": ["count_state", "runner_state", "score_diff_pitcher", "batter_stance", "batter_season_ba_bucket", "prev_pitch_type_pa_1", "prev_zone_9_pa_1"]},
        {"label": "Count+Runner+Score+Stance+BA+PrevType+PrevZone+Catcher", "features": ["count_state", "runner_state", "score_diff_pitcher", "batter_stance", "batter_season_ba_bucket", "prev_pitch_type_pa_1", "prev_zone_9_pa_1", "catcher_name"]},
    ]
    catcher_stages = [
        {"label": "Situation", "features": ["count_state", "outs", "runner_state"]},
        {"label": "Situation+Score", "features": ["count_state", "outs", "runner_state", "score_diff_pitcher"]},
        {"label": "Situation+Score+Stance", "features": ["count_state", "outs", "runner_state", "score_diff_pitcher", "batter_stance"]},
        {"label": "Situation+Score+Stance+BA", "features": ["count_state", "outs", "runner_state", "score_diff_pitcher", "batter_stance", "batter_season_ba_bucket"]},
        {"label": "Situation+Score+Stance+BA+PrevType", "features": ["count_state", "outs", "runner_state", "score_diff_pitcher", "batter_stance", "batter_season_ba_bucket", "prev_pitch_type_pa_1"]},
        {"label": "Situation+Score+Stance+BA+PrevType+PrevZone", "features": ["count_state", "outs", "runner_state", "score_diff_pitcher", "batter_stance", "batter_season_ba_bucket", "prev_pitch_type_pa_1", "prev_zone_9_pa_1"]},
    ]
    second_pitch_stages = [
        {"label": "FirstPitchType", "features": ["prev_pitch_type_pa_1"]},
        {"label": "FirstPitchType+FirstPitchZone", "features": ["prev_pitch_type_pa_1", "prev_zone_9_pa_1"]},
        {"label": "FirstPitchType+FirstPitchZone+Count", "features": ["prev_pitch_type_pa_1", "prev_zone_9_pa_1", "count_state"]},
        {"label": "FirstPitchType+FirstPitchZone+Count+Stance", "features": ["prev_pitch_type_pa_1", "prev_zone_9_pa_1", "count_state", "batter_stance"]},
        {"label": "FirstPitchType+FirstPitchZone+Count+Stance+BA", "features": ["prev_pitch_type_pa_1", "prev_zone_9_pa_1", "count_state", "batter_stance", "batter_season_ba_bucket"]},
    ]

    report = {
        "white_overall_pitch_type": run_staged_experiment(white_rows, "pitch_type", white_stages),
        "white_overall_pitch_family": run_staged_experiment(white_rows, "pitch_family", white_stages),
        "white_second_pitch_pitch_type": run_staged_experiment(only_second_pitch(white_rows), "pitch_type", second_pitch_stages),
        "white_second_pitch_pitch_family": run_staged_experiment(only_second_pitch(white_rows), "pitch_family", second_pitch_stages),
        "jo_overall_pitch_type": run_staged_experiment(jo_rows, "pitch_type", catcher_stages),
        "jo_overall_pitch_family": run_staged_experiment(jo_rows, "pitch_family", catcher_stages),
        "lee_overall_pitch_type": run_staged_experiment(lee_rows, "pitch_type", catcher_stages),
        "lee_overall_pitch_family": run_staged_experiment(lee_rows, "pitch_family", catcher_stages),
        "meta": {
            "white_rows": len(white_rows),
            "white_second_pitch_rows": len(only_second_pitch(white_rows)),
            "jo_rows": len(jo_rows),
            "lee_rows": len(lee_rows),
        },
    }

    write_json(Path(args.output_json), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
