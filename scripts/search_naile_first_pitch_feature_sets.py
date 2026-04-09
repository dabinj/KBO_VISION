#!/usr/bin/env python3

import csv
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import xgboost as xgb


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_rows_timewise(rows: list[dict], train_ratio: float = 0.8) -> tuple[list[dict], list[dict]]:
    rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            row.get("inning") or "",
            row.get("batter_code") or "",
        ),
    )
    split_index = max(1, int(len(rows) * train_ratio))
    return rows[:split_index], rows[split_index:]


def parse_float(value: str | None) -> float:
    if value in (None, ""):
        return np.nan
    try:
        return float(value)
    except ValueError:
        return np.nan


def infer_numeric_features(rows: list[dict], feature_names: list[str]) -> set[str]:
    numeric = set()
    for name in feature_names:
        if name.endswith("_state") or name in {"count_state", "runner_state", "prev_zone_9_pa_1", "zone_9"}:
            continue
        ok = True
        for row in rows[: min(len(rows), 200)]:
            value = row.get(name)
            if value in (None, ""):
                continue
            try:
                float(value)
            except ValueError:
                ok = False
                break
        if ok:
            numeric.add(name)
    return numeric


def fit_feature_encoders(rows: list[dict], feature_names: list[str], numeric_features: set[str]) -> dict[str, dict[str, int]]:
    encoders = {}
    for name in feature_names:
        if name in numeric_features:
            continue
        values = sorted({(row.get(name) or "__MISSING__") for row in rows})
        encoders[name] = {value: idx for idx, value in enumerate(values)}
    return encoders


def transform_features(rows: list[dict], feature_names: list[str], numeric_features: set[str], encoders: dict[str, dict[str, int]]) -> tuple[np.ndarray, list[str]]:
    matrix = []
    feature_types = []
    for name in feature_names:
        feature_types.append("q" if name in numeric_features else "c")
    for row in rows:
        current = []
        for name in feature_names:
            value = row.get(name)
            if name in numeric_features:
                current.append(parse_float(value))
            else:
                current.append(encoders[name].get(value or "__MISSING__", 0))
        matrix.append(current)
    return np.array(matrix, dtype=np.float32), feature_types


def fit_target_encoder(rows: list[dict], target_name: str) -> dict[str, int]:
    values = sorted({row.get(target_name) or "__MISSING__" for row in rows})
    return {value: idx for idx, value in enumerate(values)}


def transform_target(rows: list[dict], target_name: str, encoder: dict[str, int]) -> np.ndarray:
    return np.array([encoder[row.get(target_name) or "__MISSING__"] for row in rows], dtype=np.int32)


def evaluate_feature_set(rows: list[dict], target_name: str, features: list[str]) -> dict:
    train_rows, test_rows = split_rows_timewise(rows)
    numeric_features = infer_numeric_features(train_rows, features)
    feature_encoders = fit_feature_encoders(train_rows, features, numeric_features)
    target_encoder = fit_target_encoder(rows, target_name)

    x_train, feature_types = transform_features(train_rows, features, numeric_features, feature_encoders)
    x_test, _ = transform_features(test_rows, features, numeric_features, feature_encoders)
    y_train = transform_target(train_rows, target_name, target_encoder)
    y_test = transform_target(test_rows, target_name, target_encoder)

    params = {
        "max_depth": 4,
        "eta": 0.08,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "tree_method": "hist",
        "seed": 42,
        "objective": "multi:softprob",
        "num_class": len(target_encoder),
        "eval_metric": "mlogloss",
        "enable_categorical": True,
    }
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_types=feature_types)
    dtest = xgb.DMatrix(x_test, label=y_test, feature_types=feature_types)
    booster = xgb.train(params=params, dtrain=dtrain, num_boost_round=120, verbose_eval=False)
    prob = booster.predict(dtest)
    pred = np.argmax(prob, axis=1)
    top1 = float((pred == y_test).mean())
    top3 = float(np.mean([y_test[i] in np.argsort(prob[i])[-3:] for i in range(len(y_test))]))
    return {
        "features": features,
        "top1_accuracy": round(top1, 4),
        "top3_accuracy": round(top3, 4),
        "rows_test": int(len(y_test)),
    }


def main() -> None:
    input_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_pitch_drivers_2025.csv")
    output_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_pitch_feature_search_2025.json")
    rows = read_rows(input_path)

    groups = {
        "game_state": ["runner_state", "outs", "inning"],
        "batter_identity": ["batter_stance", "batter_season_ba_bucket", "batter_season_pa_before_pitch"],
        "catcher_team": ["catcher_name", "opponent_team_code"],
        "weakness_labels": ["weak_side_2024", "weak_height_2024", "weak_pitch_family_2024", "weak_zone_2024"],
        "weakness_scores": ["weakness_score_inside_2024", "weakness_score_outside_2024", "weakness_score_high_2024", "weakness_score_low_2024"],
        "first_pitch_tendency": [
            "batter_first_pitch_seen_2025",
            "batter_first_pitch_swing_bucket_2025",
            "batter_first_pitch_swing_rate_2025",
            "batter_first_pitch_whiff_rate_2025",
            "batter_first_pitch_inplay_rate_2025",
            "batter_first_pitch_ball_take_rate_2025",
            "batter_first_pitch_called_strike_take_rate_2025",
            "batter_first_pitch_in_zone_swing_rate_2025",
            "batter_first_pitch_out_zone_swing_rate_2025",
        ],
    }

    fixed = []
    candidates = []
    # single groups
    for name, features in groups.items():
        candidates.append({"name": name, "features": features})
    # combinations of 2 and 3 groups
    keys = list(groups.keys())
    for r in [2, 3]:
        for combo in combinations(keys, r):
            features = []
            for key in combo:
                features.extend(groups[key])
            candidates.append({"name": " + ".join(combo), "features": features})
    # full
    full = []
    for key in keys:
        full.extend(groups[key])
    candidates.append({"name": "full", "features": full})

    results = []
    for candidate in candidates:
        report = evaluate_feature_set(rows, "first_pitch_type", candidate["features"])
        report["name"] = candidate["name"]
        results.append(report)

    results.sort(key=lambda row: (row["top1_accuracy"], row["top3_accuracy"]), reverse=True)
    payload = {"results": results[:20], "all_results_count": len(results)}
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
