#!/usr/bin/env python3

import csv
import json
from pathlib import Path

import numpy as np
import xgboost as xgb


FEATURES = [
    "runner_state",
    "outs",
    "inning",
    "batter_stance",
    "catcher_name",
    "opponent_team_code",
    "batter_season_ba_bucket",
    "batter_season_pa_before_pitch",
    "weak_side_2024",
    "weak_height_2024",
    "weak_pitch_family_2024",
    "weak_zone_2024",
    "weakness_score_inside_2024",
    "weakness_score_outside_2024",
    "weakness_score_high_2024",
    "weakness_score_low_2024",
    "batter_first_pitch_seen_2025",
    "batter_first_pitch_swing_bucket_2025",
    "batter_first_pitch_swing_rate_2025",
    "batter_first_pitch_whiff_rate_2025",
    "batter_first_pitch_inplay_rate_2025",
    "batter_first_pitch_ball_take_rate_2025",
    "batter_first_pitch_called_strike_take_rate_2025",
    "batter_first_pitch_in_zone_swing_rate_2025",
    "batter_first_pitch_out_zone_swing_rate_2025",
]


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


def split_train_validation(rows: list[dict], train_ratio: float = 0.8) -> tuple[list[dict], list[dict]]:
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
    feature_types = ["q" if name in numeric_features else "c" for name in feature_names]
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


def inverse_target_map(encoder: dict[str, int]) -> dict[int, str]:
    return {idx: label for label, idx in encoder.items()}


def accuracy_from_probs(prob: np.ndarray, y_true: np.ndarray) -> float:
    pred = np.argmax(prob, axis=1)
    return float((pred == y_true).mean())


def topk_accuracy(prob: np.ndarray, y_true: np.ndarray, k: int) -> float:
    topk = np.argsort(prob, axis=1)[:, -k:]
    hits = [(y_true[i] in topk[i]) for i in range(len(y_true))]
    return float(np.mean(hits))


def prior_from_rows(rows: list[dict], target_name: str, encoder: dict[str, int]) -> np.ndarray:
    counts = np.zeros(len(encoder), dtype=np.float32)
    for row in rows:
        idx = encoder[row.get(target_name) or "__MISSING__"]
        counts[idx] += 1
    counts /= counts.sum()
    return counts


def train_xgb(train_rows: list[dict], val_rows: list[dict], all_rows: list[dict], feature_names: list[str], target_name: str):
    numeric_features = infer_numeric_features(train_rows, feature_names)
    feature_encoders = fit_feature_encoders(train_rows, feature_names, numeric_features)
    target_encoder = fit_target_encoder(all_rows, target_name)

    x_train, feature_types = transform_features(train_rows, feature_names, numeric_features, feature_encoders)
    x_val, _ = transform_features(val_rows, feature_names, numeric_features, feature_encoders)
    y_train = transform_target(train_rows, target_name, target_encoder)
    y_val = transform_target(val_rows, target_name, target_encoder)

    params = {
        "max_depth": 6,
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
    dval = xgb.DMatrix(x_val, label=y_val, feature_types=feature_types)
    booster = xgb.train(params=params, dtrain=dtrain, num_boost_round=180, verbose_eval=False)
    val_prob = booster.predict(dval)
    return booster, feature_types, numeric_features, feature_encoders, target_encoder, y_val, val_prob


def transform_for_booster(rows: list[dict], feature_names: list[str], numeric_features: set[str], encoders: dict[str, dict[str, int]], booster: xgb.Booster, feature_types: list[str]):
    x_rows, _ = transform_features(rows, feature_names, numeric_features, encoders)
    return booster.predict(xgb.DMatrix(x_rows, feature_types=feature_types))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compare majority, XGBoost, and prior-adjusted models for Naile first-pitch prediction.")
    parser.add_argument("--input-csv", default=r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_pitch_drivers_2025.csv")
    parser.add_argument("--opponent-team-code", default="", help="Optional filter such as HH")
    parser.add_argument("--output-json", default=r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_pitch_prior_adjusted_comparison_2025.json")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_json)
    rows = read_rows(input_path)
    if args.opponent_team_code:
        rows = [row for row in rows if (row.get("opponent_team_code") or "") == args.opponent_team_code]

    train_full, test_rows = split_rows_timewise(rows)
    train_rows, val_rows = split_train_validation(train_full, train_ratio=0.8)

    (
        booster,
        feature_types,
        numeric_features,
        feature_encoders,
        target_encoder,
        y_val,
        val_prob,
    ) = train_xgb(train_rows, val_rows, rows, FEATURES, "first_pitch_type")

    prior = prior_from_rows(train_rows, "first_pitch_type", target_encoder)

    # choose alpha on validation
    best_alpha = 0.0
    best_val_acc = -1.0
    for alpha in [x / 20 for x in range(0, 21)]:
        mixed = alpha * prior + (1.0 - alpha) * val_prob
        acc = accuracy_from_probs(mixed, y_val)
        if acc > best_val_acc:
            best_val_acc = acc
            best_alpha = alpha

    # retrain on full train split and evaluate on test
    (
        booster_full,
        feature_types_full,
        numeric_features_full,
        feature_encoders_full,
        target_encoder_full,
        _,
        _,
    ) = train_xgb(train_full, test_rows, rows, FEATURES, "first_pitch_type")
    # train_xgb with test_rows as val gives test prob but also overuses same procedure; acceptable for comparison since no tuning on test except alpha from earlier split.
    test_prob = transform_for_booster(test_rows, FEATURES, numeric_features_full, feature_encoders_full, booster_full, feature_types_full)
    y_test = transform_target(test_rows, "first_pitch_type", target_encoder_full)
    prior_full = prior_from_rows(train_full, "first_pitch_type", target_encoder_full)
    prior_adjusted_prob = best_alpha * prior_full + (1.0 - best_alpha) * test_prob

    # majority baseline
    inv_map = inverse_target_map(target_encoder_full)
    majority_idx = int(np.argmax(prior_full))
    majority_label = inv_map[majority_idx]
    majority_acc = float(np.mean(y_test == majority_idx))

    payload = {
        "opponent_team_code": args.opponent_team_code or "ALL",
        "rows_total": len(rows),
        "rows_train": len(train_full),
        "rows_test": len(test_rows),
        "majority_baseline": {
            "label": majority_label,
            "top1_accuracy": round(majority_acc, 4),
        },
        "xgboost": {
            "top1_accuracy": round(accuracy_from_probs(test_prob, y_test), 4),
            "top3_accuracy": round(topk_accuracy(test_prob, y_test, 3), 4),
        },
        "prior_adjusted": {
            "alpha_on_prior": round(best_alpha, 2),
            "top1_accuracy": round(accuracy_from_probs(prior_adjusted_prob, y_test), 4),
            "top3_accuracy": round(topk_accuracy(prior_adjusted_prob, y_test, 3), 4),
        },
        "prior_distribution_train": [
            {
                "pitch_type": inv_map[idx],
                "pct": round(float(prior_full[idx]) * 100, 3),
            }
            for idx in np.argsort(prior_full)[::-1]
        ],
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
