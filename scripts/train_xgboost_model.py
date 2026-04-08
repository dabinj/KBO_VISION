#!/usr/bin/env python3

import argparse
import csv
import json
import math
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
            int(row.get("pitch_index_in_game") or 0),
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


def inverse_target_map(encoder: dict[str, int]) -> dict[int, str]:
    return {idx: label for label, idx in encoder.items()}


def parse_feature_names(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass

    cleaned = raw.strip().strip("[]")
    if not cleaned:
        return []
    return [part.strip().strip("'\"") for part in cleaned.split(",") if part.strip()]


def topk_accuracy(prob: np.ndarray, y_true: np.ndarray, k: int) -> float:
    if prob.ndim == 1:
        pred = (prob >= 0.5).astype(int)
        if k == 1:
            return float((pred == y_true).mean())
        return 1.0
    topk = np.argsort(prob, axis=1)[:, -k:]
    hits = [(y_true[i] in topk[i]) for i in range(len(y_true))]
    return float(np.mean(hits))


def multiclass_log_loss(prob: np.ndarray, y_true: np.ndarray) -> float:
    eps = 1e-12
    probs = prob[np.arange(len(y_true)), y_true]
    probs = np.clip(probs, eps, 1.0)
    return float(np.mean(-np.log(probs)))


def binary_log_loss(prob: np.ndarray, y_true: np.ndarray) -> float:
    eps = 1e-12
    prob = np.clip(prob, eps, 1 - eps)
    return float(np.mean(-(y_true * np.log(prob) + (1 - y_true) * np.log(1 - prob))))


def evaluate_predictions(prob, y_true, num_classes: int) -> dict:
    if num_classes == 2:
        if prob.ndim == 2:
            prob_1 = prob[:, 1]
        else:
            prob_1 = prob
        pred = (prob_1 >= 0.5).astype(int)
        return {
            "rows": int(len(y_true)),
            "top1_accuracy": round(float((pred == y_true).mean()), 4),
            "top3_accuracy": 1.0,
            "log_loss": round(binary_log_loss(prob_1, y_true), 4),
        }

    pred = np.argmax(prob, axis=1)
    return {
        "rows": int(len(y_true)),
        "top1_accuracy": round(float((pred == y_true).mean()), 4),
        "top3_accuracy": round(topk_accuracy(prob, y_true, 3), 4),
        "log_loss": round(multiclass_log_loss(prob, y_true), 4),
    }


def build_importance_map(booster: xgb.Booster, feature_names: list[str]) -> list[dict]:
    score = booster.get_score(importance_type="gain")
    rows = []
    for idx, name in enumerate(feature_names):
        rows.append({"feature": name, "gain": round(float(score.get(f"f{idx}", 0.0)), 6)})
    rows.sort(key=lambda row: row["gain"], reverse=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate an XGBoost model on a prepared model table.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--features-json", required=True, help="JSON array of feature names")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--eta", type=float, default=0.08)
    parser.add_argument("--num-boost-round", type=int, default=180)
    parser.add_argument("--subsample", type=float, default=0.9)
    parser.add_argument("--colsample-bytree", type=float, default=0.9)
    args = parser.parse_args()

    feature_names = parse_feature_names(args.features_json)
    rows = read_rows(Path(args.input_csv))
    train_rows, test_rows = split_rows_timewise(rows)

    numeric_features = infer_numeric_features(train_rows, feature_names)
    feature_encoders = fit_feature_encoders(train_rows, feature_names, numeric_features)
    target_encoder = fit_target_encoder(rows, args.target)
    target_map = inverse_target_map(target_encoder)

    x_train, feature_types = transform_features(train_rows, feature_names, numeric_features, feature_encoders)
    x_test, _ = transform_features(test_rows, feature_names, numeric_features, feature_encoders)
    y_train = transform_target(train_rows, args.target, target_encoder)
    y_test = transform_target(test_rows, args.target, target_encoder)

    num_classes = len(target_encoder)
    params = {
        "max_depth": args.max_depth,
        "eta": args.eta,
        "subsample": args.subsample,
        "colsample_bytree": args.colsample_bytree,
        "tree_method": "hist",
        "seed": 42,
        "enable_categorical": True,
    }
    if num_classes == 2:
        params["objective"] = "binary:logistic"
        params["eval_metric"] = "logloss"
    else:
        params["objective"] = "multi:softprob"
        params["num_class"] = num_classes
        params["eval_metric"] = "mlogloss"

    dtrain = xgb.DMatrix(x_train, label=y_train, feature_types=feature_types)
    dtest = xgb.DMatrix(x_test, label=y_test, feature_types=feature_types)
    booster = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=args.num_boost_round,
        evals=[(dtrain, "train"), (dtest, "test")],
        verbose_eval=False,
    )

    train_prob = booster.predict(dtrain)
    test_prob = booster.predict(dtest)
    report = {
        "input_csv": args.input_csv,
        "target": args.target,
        "features": feature_names,
        "numeric_features": sorted(numeric_features),
        "categorical_features": [name for name in feature_names if name not in numeric_features],
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "num_classes": num_classes,
        "classes": [target_map[idx] for idx in sorted(target_map)],
        "params": {
            "max_depth": args.max_depth,
            "eta": args.eta,
            "num_boost_round": args.num_boost_round,
            "subsample": args.subsample,
            "colsample_bytree": args.colsample_bytree,
        },
        "train_metrics": evaluate_predictions(train_prob, y_train, num_classes),
        "test_metrics": evaluate_predictions(test_prob, y_test, num_classes),
        "feature_importance_gain": build_importance_map(booster, feature_names)[:20],
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
