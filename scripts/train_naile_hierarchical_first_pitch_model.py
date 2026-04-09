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

FASTBALL_TYPES = {"직구", "투심", "커터"}
BREAKING_TYPES = {"체인지업", "슬라이더", "스위퍼", "커브", "포크"}


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


def transform_features(
    rows: list[dict],
    feature_names: list[str],
    numeric_features: set[str],
    encoders: dict[str, dict[str, int]],
) -> tuple[np.ndarray, list[str]]:
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


def inverse_map(encoder: dict[str, int]) -> dict[int, str]:
    return {idx: label for label, idx in encoder.items()}


def topk_accuracy(prob: np.ndarray, y_true: np.ndarray, k: int) -> float:
    topk = np.argsort(prob, axis=1)[:, -k:]
    hits = [(y_true[i] in topk[i]) for i in range(len(y_true))]
    return float(np.mean(hits))


def accuracy(prob: np.ndarray, y_true: np.ndarray) -> float:
    pred = np.argmax(prob, axis=1)
    return float((pred == y_true).mean())


def train_multiclass(
    train_rows: list[dict],
    test_rows: list[dict],
    feature_names: list[str],
    target_name: str,
) -> tuple[xgb.Booster, np.ndarray, np.ndarray, dict[str, int], set[str], dict[str, dict[str, int]], list[str]]:
    numeric_features = infer_numeric_features(train_rows, feature_names)
    feature_encoders = fit_feature_encoders(train_rows, feature_names, numeric_features)
    target_encoder = fit_target_encoder(train_rows + test_rows, target_name)

    x_train, feature_types = transform_features(train_rows, feature_names, numeric_features, feature_encoders)
    x_test, _ = transform_features(test_rows, feature_names, numeric_features, feature_encoders)
    y_train = transform_target(train_rows, target_name, target_encoder)
    y_test = transform_target(test_rows, target_name, target_encoder)

    params = {
        "max_depth": 5,
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
    booster = xgb.train(params=params, dtrain=dtrain, num_boost_round=140, verbose_eval=False)
    test_prob = booster.predict(dtest)
    return booster, test_prob, y_test, target_encoder, numeric_features, feature_encoders, feature_types


def train_binary_family(
    train_rows: list[dict],
    test_rows: list[dict],
    feature_names: list[str],
) -> tuple[np.ndarray, np.ndarray, set[str], dict[str, dict[str, int]], list[str]]:
    numeric_features = infer_numeric_features(train_rows, feature_names)
    feature_encoders = fit_feature_encoders(train_rows, feature_names, numeric_features)
    x_train, feature_types = transform_features(train_rows, feature_names, numeric_features, feature_encoders)
    x_test, _ = transform_features(test_rows, feature_names, numeric_features, feature_encoders)

    def family_label(row: dict) -> int:
        return 1 if (row.get("first_pitch_type") or "") in FASTBALL_TYPES else 0

    y_train = np.array([family_label(row) for row in train_rows], dtype=np.int32)
    y_test = np.array([family_label(row) for row in test_rows], dtype=np.int32)

    params = {
        "max_depth": 5,
        "eta": 0.08,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "tree_method": "hist",
        "seed": 42,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "enable_categorical": True,
    }
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_types=feature_types)
    dtest = xgb.DMatrix(x_test, label=y_test, feature_types=feature_types)
    booster = xgb.train(params=params, dtrain=dtrain, num_boost_round=140, verbose_eval=False)
    prob_fastball = booster.predict(dtest)
    prob = np.column_stack([1.0 - prob_fastball, prob_fastball])
    return prob, y_test, numeric_features, feature_encoders, feature_types


def majority_baseline(train_rows: list[dict], test_rows: list[dict], target_name: str) -> dict:
    counts = {}
    for row in train_rows:
        label = row.get(target_name) or "__MISSING__"
        counts[label] = counts.get(label, 0) + 1
    majority_label = max(counts.items(), key=lambda item: item[1])[0]
    correct = sum(1 for row in test_rows if (row.get(target_name) or "__MISSING__") == majority_label)
    return {
        "label": majority_label,
        "top1_accuracy": round(correct / len(test_rows), 4),
    }


def family_to_type_probs(
    family_prob: np.ndarray,
    subtype_fast_prob: np.ndarray,
    subtype_break_prob: np.ndarray,
    test_rows: list[dict],
    full_encoder: dict[str, int],
    fast_encoder: dict[str, int],
    break_encoder: dict[str, int],
) -> np.ndarray:
    num_classes = len(full_encoder)
    output = np.zeros((len(test_rows), num_classes), dtype=np.float32)
    for i in range(len(test_rows)):
        p_break = family_prob[i, 0]
        p_fast = family_prob[i, 1]
        for label, idx in fast_encoder.items():
            output[i, full_encoder[label]] = p_fast * subtype_fast_prob[i, idx]
        for label, idx in break_encoder.items():
            output[i, full_encoder[label]] = p_break * subtype_break_prob[i, idx]
    return output


def main() -> None:
    input_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_pitch_drivers_2025.csv")
    output_path = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile\naile_first_pitch_hierarchical_model_2025.json")
    rows = read_rows(input_path)
    train_rows, test_rows = split_rows_timewise(rows)

    baseline = majority_baseline(train_rows, test_rows, "first_pitch_type")

    _, direct_prob, y_test, full_encoder, _, _, _ = train_multiclass(train_rows, test_rows, FEATURES, "first_pitch_type")
    direct_report = {
        "top1_accuracy": round(accuracy(direct_prob, y_test), 4),
        "top3_accuracy": round(topk_accuracy(direct_prob, y_test, 3), 4),
    }

    family_prob, family_y_test, _, _, _ = train_binary_family(train_rows, test_rows, FEATURES)
    family_report = {
        "top1_accuracy": round(accuracy(family_prob, family_y_test), 4),
    }

    fast_train = [row for row in train_rows if (row.get("first_pitch_type") or "") in FASTBALL_TYPES]
    fast_test = test_rows
    _, fast_prob, _, fast_encoder, _, _, _ = train_multiclass(fast_train, fast_test, FEATURES, "first_pitch_type")

    break_train = [row for row in train_rows if (row.get("first_pitch_type") or "") in BREAKING_TYPES]
    break_test = test_rows
    _, break_prob, _, break_encoder, _, _, _ = train_multiclass(break_train, break_test, FEATURES, "first_pitch_type")

    hierarchical_prob = family_to_type_probs(
        family_prob,
        fast_prob,
        break_prob,
        test_rows,
        full_encoder,
        fast_encoder,
        break_encoder,
    )
    hierarchical_report = {
        "top1_accuracy": round(accuracy(hierarchical_prob, y_test), 4),
        "top3_accuracy": round(topk_accuracy(hierarchical_prob, y_test, 3), 4),
    }

    payload = {
        "rows_total": len(rows),
        "rows_train": len(train_rows),
        "rows_test": len(test_rows),
        "majority_baseline": baseline,
        "direct_multiclass": direct_report,
        "family_binary": family_report,
        "hierarchical_family_then_type": hierarchical_report,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
