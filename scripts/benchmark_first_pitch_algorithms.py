#!/usr/bin/env python3

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import xgboost as xgb


DEFAULT_FEATURES = [
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
            int(row.get("inning") or 0),
            int(row.get("outs") or 0),
            row.get("batter_code") or "",
        ),
    )
    split_index = max(1, int(len(rows) * train_ratio))
    split_index = min(split_index, len(rows) - 1) if len(rows) > 1 else 1
    return rows[:split_index], rows[split_index:]


def split_train_validation(rows: list[dict], train_ratio: float = 0.8) -> tuple[list[dict], list[dict]]:
    split_index = max(1, int(len(rows) * train_ratio))
    split_index = min(split_index, len(rows) - 1) if len(rows) > 1 else 1
    return rows[:split_index], rows[split_index:]


def parse_float(value: str | None) -> float:
    if value in (None, ""):
        return np.nan
    try:
        return float(value)
    except ValueError:
        return np.nan


def parse_feature_names(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_FEATURES)
    parsed = json.loads(raw)
    return [str(item) for item in parsed]


def infer_numeric_features(rows: list[dict], feature_names: list[str]) -> set[str]:
    numeric = set()
    categorical_overrides = {"count_state", "runner_state", "zone_9", "first_zone_9"}
    for name in feature_names:
        if name in categorical_overrides or name.endswith("_state"):
            continue
        ok = True
        for row in rows[: min(len(rows), 250)]:
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
    encoders: dict[str, dict[str, int]] = {}
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


def inverse_target_map(encoder: dict[str, int]) -> dict[int, str]:
    return {idx: label for label, idx in encoder.items()}


def topk_accuracy(prob: np.ndarray, y_true: np.ndarray, k: int) -> float:
    if prob.ndim == 1:
        pred = (prob >= 0.5).astype(int)
        return float((pred == y_true).mean())
    k = min(k, prob.shape[1])
    topk = np.argsort(prob, axis=1)[:, -k:]
    hits = [(y_true[i] in topk[i]) for i in range(len(y_true))]
    return float(np.mean(hits))


def multiclass_log_loss(prob: np.ndarray, y_true: np.ndarray) -> float:
    eps = 1e-12
    probs = prob[np.arange(len(y_true)), y_true]
    probs = np.clip(probs, eps, 1.0)
    return float(np.mean(-np.log(probs)))


def evaluate_probabilities(prob: np.ndarray, y_true: np.ndarray) -> dict:
    pred = np.argmax(prob, axis=1)
    return {
        "top1_accuracy": round(float((pred == y_true).mean()), 4),
        "top3_accuracy": round(topk_accuracy(prob, y_true, 3), 4),
        "log_loss": round(multiclass_log_loss(prob, y_true), 4),
    }


def prior_from_rows(rows: list[dict], target_name: str, encoder: dict[str, int]) -> np.ndarray:
    counts = np.zeros(len(encoder), dtype=np.float32)
    for row in rows:
        counts[encoder[row.get(target_name) or "__MISSING__"]] += 1
    counts /= counts.sum()
    return counts


def majority_baseline(train_rows: list[dict], test_rows: list[dict], target_name: str, encoder: dict[str, int]) -> dict:
    prior = prior_from_rows(train_rows, target_name, encoder)
    majority_idx = int(np.argmax(prior))
    y_test = transform_target(test_rows, target_name, encoder)
    inv_map = inverse_target_map(encoder)
    prob = np.tile(prior, (len(test_rows), 1))
    metrics = evaluate_probabilities(prob, y_test)
    metrics["label"] = inv_map[majority_idx]
    return metrics


def conditional_majority_baseline(
    train_rows: list[dict],
    test_rows: list[dict],
    target_name: str,
    encoder: dict[str, int],
    group_features: list[str],
) -> dict:
    global_prior = prior_from_rows(train_rows, target_name, encoder)
    grouped_counts: dict[tuple, np.ndarray] = {}
    accumulator: dict[tuple, Counter] = defaultdict(Counter)
    for row in train_rows:
        key = tuple(row.get(name) or "__MISSING__" for name in group_features)
        accumulator[key][row.get(target_name) or "__MISSING__"] += 1
    for key, counts in accumulator.items():
        arr = np.zeros(len(encoder), dtype=np.float32)
        total = sum(counts.values())
        for label, count in counts.items():
            arr[encoder[label]] = count / total
        grouped_counts[key] = arr

    probs = []
    for row in test_rows:
        key = tuple(row.get(name) or "__MISSING__" for name in group_features)
        probs.append(grouped_counts.get(key, global_prior))
    prob = np.vstack(probs)
    y_test = transform_target(test_rows, target_name, encoder)
    metrics = evaluate_probabilities(prob, y_test)
    metrics["group_features"] = group_features
    return metrics


def fit_xgb_variant(
    train_rows: list[dict],
    test_rows: list[dict],
    all_rows: list[dict],
    feature_names: list[str],
    target_name: str,
    params: dict,
    num_boost_round: int,
) -> tuple[np.ndarray, np.ndarray]:
    numeric_features = infer_numeric_features(train_rows, feature_names)
    encoders = fit_feature_encoders(train_rows, feature_names, numeric_features)
    target_encoder = fit_target_encoder(all_rows, target_name)
    x_train, feature_types = transform_features(train_rows, feature_names, numeric_features, encoders)
    x_test, _ = transform_features(test_rows, feature_names, numeric_features, encoders)
    y_train = transform_target(train_rows, target_name, target_encoder)
    y_test = transform_target(test_rows, target_name, target_encoder)

    full_params = {
        "objective": "multi:softprob",
        "num_class": len(target_encoder),
        "eval_metric": "mlogloss",
        "tree_method": "hist",
        "seed": 42,
        "enable_categorical": True,
    }
    full_params.update(params)

    dtrain = xgb.DMatrix(x_train, label=y_train, feature_types=feature_types)
    dtest = xgb.DMatrix(x_test, label=y_test, feature_types=feature_types)
    booster = xgb.train(full_params, dtrain=dtrain, num_boost_round=num_boost_round, verbose_eval=False)
    return booster.predict(dtest), y_test


def tune_prior_adjustment(
    train_rows: list[dict],
    target_name: str,
    feature_names: list[str],
    encoder: dict[str, int],
) -> float:
    inner_train, inner_val = split_train_validation(train_rows)
    val_prob, y_val = fit_xgb_variant(
        inner_train,
        inner_val,
        train_rows,
        feature_names,
        target_name,
        params={
            "max_depth": 6,
            "eta": 0.08,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
        },
        num_boost_round=180,
    )
    prior = prior_from_rows(inner_train, target_name, encoder)
    best_alpha = 0.0
    best_acc = -1.0
    for alpha_step in range(21):
        alpha = alpha_step / 20
        mixed = alpha * prior + (1.0 - alpha) * val_prob
        acc = float((np.argmax(mixed, axis=1) == y_val).mean())
        if acc > best_acc:
            best_acc = acc
            best_alpha = alpha
    return best_alpha


def maybe_import_sklearn() -> tuple[bool, str]:
    try:
        import sklearn  # noqa: F401

        return True, "available"
    except Exception as exc:  # pragma: no cover - environment specific
        return False, str(exc)


def maybe_import_torch() -> tuple[bool, str]:
    try:
        import torch  # noqa: F401

        return True, "available"
    except Exception as exc:  # pragma: no cover - environment specific
        return False, str(exc)


def render_markdown(report: dict) -> str:
    lines = []
    lines.append("# First Pitch Algorithm Benchmark")
    lines.append("")
    lines.append(f"- input_csv: `{report['input_csv']}`")
    lines.append(f"- target: `{report['target']}`")
    lines.append(f"- rows_train: `{report['rows_train']}`")
    lines.append(f"- rows_test: `{report['rows_test']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for row in report["ranked_models"]:
        lines.append(
            f"- `{row['name']}`: Top-1 `{row['top1_accuracy']}`, Top-3 `{row['top3_accuracy']}`, "
            f"delta_vs_majority `{row['delta_vs_majority']:+.4f}`"
        )
    lines.append("")
    lines.append("## Availability")
    lines.append("")
    for key, value in report["availability"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def available_conditional_groups(feature_names: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    if all(name in feature_names for name in ["catcher_name", "opponent_team_code"]):
        groups.append(["catcher_name", "opponent_team_code"])
    if all(name in feature_names for name in ["count_state", "runner_state", "outs"]):
        groups.append(["count_state", "runner_state", "outs"])
    if all(name in feature_names for name in ["count_state", "prev_pitch_type_pa_1"]):
        groups.append(["count_state", "prev_pitch_type_pa_1"])
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark multiple first-pitch algorithms on the same table.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--target", default="first_pitch_type")
    parser.add_argument("--features-json", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    feature_names = parse_feature_names(args.features_json)
    rows = read_rows(Path(args.input_csv))
    train_rows, test_rows = split_rows_timewise(rows)
    target_encoder = fit_target_encoder(rows, args.target)

    results: dict[str, dict] = {}
    majority = majority_baseline(train_rows, test_rows, args.target, target_encoder)
    results["majority"] = majority

    for group_features in available_conditional_groups(feature_names):
        key = "conditional_majority_" + "_".join(group_features)
        results[key] = conditional_majority_baseline(
            train_rows,
            test_rows,
            args.target,
            target_encoder,
            group_features,
        )

    gbtree_prob, y_test = fit_xgb_variant(
        train_rows,
        test_rows,
        rows,
        feature_names,
        args.target,
        params={
            "max_depth": 6,
            "eta": 0.08,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
        },
        num_boost_round=180,
    )
    results["xgboost_gbtree"] = evaluate_probabilities(gbtree_prob, y_test)

    dart_prob, _ = fit_xgb_variant(
        train_rows,
        test_rows,
        rows,
        feature_names,
        args.target,
        params={
            "booster": "dart",
            "max_depth": 6,
            "eta": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "sample_type": "uniform",
            "normalize_type": "tree",
            "rate_drop": 0.1,
            "skip_drop": 0.3,
        },
        num_boost_round=220,
    )
    results["xgboost_dart"] = evaluate_probabilities(dart_prob, y_test)

    rf_prob, _ = fit_xgb_variant(
        train_rows,
        test_rows,
        rows,
        feature_names,
        args.target,
        params={
            "max_depth": 8,
            "eta": 1.0,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "num_parallel_tree": 300,
        },
        num_boost_round=1,
    )
    results["xgboost_random_forest_mode"] = evaluate_probabilities(rf_prob, y_test)

    alpha = tune_prior_adjustment(train_rows, args.target, feature_names, target_encoder)
    global_prior = prior_from_rows(train_rows, args.target, target_encoder)
    prior_adjusted_prob = alpha * global_prior + (1.0 - alpha) * gbtree_prob
    prior_adjusted = evaluate_probabilities(prior_adjusted_prob, y_test)
    prior_adjusted["alpha_on_prior"] = round(alpha, 2)
    results["prior_adjusted_xgboost"] = prior_adjusted

    availability = {}
    sklearn_ok, sklearn_note = maybe_import_sklearn()
    availability["sklearn"] = sklearn_note
    torch_ok, torch_note = maybe_import_torch()
    availability["torch"] = torch_note
    availability["xgboost"] = getattr(xgb, "__version__", "unknown")

    if not sklearn_ok:
        results["random_forest_sklearn"] = {"status": "skipped", "reason": sklearn_note}
        results["extra_trees_sklearn"] = {"status": "skipped", "reason": sklearn_note}
    if not torch_ok:
        results["transformer_sequence"] = {"status": "skipped", "reason": torch_note}

    majority_top1 = majority["top1_accuracy"]
    ranked = []
    for name, metrics in results.items():
        if "top1_accuracy" not in metrics:
            continue
        ranked.append(
            {
                "name": name,
                "top1_accuracy": metrics["top1_accuracy"],
                "top3_accuracy": metrics.get("top3_accuracy"),
                "delta_vs_majority": round(metrics["top1_accuracy"] - majority_top1, 4),
            }
        )
    ranked.sort(key=lambda row: row["top1_accuracy"], reverse=True)

    report = {
        "input_csv": args.input_csv,
        "target": args.target,
        "features": feature_names,
        "rows_total": len(rows),
        "rows_train": len(train_rows),
        "rows_test": len(test_rows),
        "results": results,
        "ranked_models": ranked,
        "availability": availability,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.output_md:
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
