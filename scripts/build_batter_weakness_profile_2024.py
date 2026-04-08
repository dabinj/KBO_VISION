#!/usr/bin/env python3

import argparse
import csv
from collections import defaultdict
from pathlib import Path


ZONE_LEFT = -0.708
ZONE_RIGHT = 0.708


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


def to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def zone_col(cross_plate_x: float | None) -> str:
    if cross_plate_x is None:
        return "UNKNOWN"
    if cross_plate_x < ZONE_LEFT or cross_plate_x > ZONE_RIGHT:
        return "OUT"
    band = (ZONE_RIGHT - ZONE_LEFT) / 3.0
    if cross_plate_x < ZONE_LEFT + band:
        return "LEFT"
    if cross_plate_x < ZONE_LEFT + 2 * band:
        return "MIDDLE"
    return "RIGHT"


def zone_row(plate_z: float | None, bottom_sz: float | None, top_sz: float | None) -> str:
    if plate_z is None or bottom_sz is None or top_sz is None:
        return "UNKNOWN"
    if plate_z < bottom_sz or plate_z > top_sz:
        return "OUT"
    band = (top_sz - bottom_sz) / 3.0
    if plate_z < bottom_sz + band:
        return "LOW"
    if plate_z < bottom_sz + 2 * band:
        return "MIDDLE"
    return "HIGH"


def relative_side(col_label: str, stance: str) -> str:
    if col_label == "OUT":
        return "OUT"
    if col_label == "MIDDLE":
        return "MIDDLE"
    if stance == "L":
        return "INSIDE" if col_label == "RIGHT" else "OUTSIDE"
    return "INSIDE" if col_label == "LEFT" else "OUTSIDE"


def pitch_family(pitch_type: str) -> str:
    return "FASTBALL" if pitch_type in {"직구", "투심", "커터"} else "BREAKING"


def is_hit(result_text: str) -> bool:
    return any(keyword in result_text for keyword in ["안타", "1루타", "2루타", "3루타", "홈런", "내야안타"])


def is_walk_like(result_text: str) -> bool:
    return any(keyword in result_text for keyword in ["볼넷", "고의4구", "몸에 맞는 볼"])


def is_strikeout(result_text: str) -> bool:
    return "삼진" in result_text


def is_out_like(result_text: str) -> bool:
    if not result_text:
        return False
    if is_hit(result_text) or is_walk_like(result_text):
        return False
    keywords = ["아웃", "땅볼", "뜬공", "플라이", "직선타", "병살", "야수선택"]
    return any(keyword in result_text for keyword in keywords)


def pitch_disadvantage_score(row: dict) -> float:
    plate_result = (row.get("plate_result_text") or "").strip()
    event_text = (row.get("event_text") or "").strip()

    if plate_result:
        if is_hit(plate_result):
            return -1.5
        if is_walk_like(plate_result):
            return -1.0
        if is_strikeout(plate_result):
            return 1.4
        if is_out_like(plate_result):
            return 1.0

    if "헛스윙" in event_text:
        return 1.0
    if "스트라이크" in event_text:
        return 0.6
    if "파울" in event_text:
        return 0.2
    if "볼" in event_text:
        return -0.3
    return 0.0


def update_bucket(store: dict, key: str, score: float) -> None:
    store[key]["sum"] += score
    store[key]["count"] += 1


def avg_or_zero(store: dict, key: str) -> float:
    count = store[key]["count"]
    return round(store[key]["sum"] / count, 4) if count else 0.0


def count_or_zero(store: dict, key: str) -> int:
    return int(store[key]["count"])


def best_key(store: dict, keys: list[str], minimum_count: int, fallback: str) -> str:
    eligible = [key for key in keys if store[key]["count"] >= minimum_count]
    if not eligible:
        return fallback
    return max(eligible, key=lambda key: store[key]["sum"] / max(store[key]["count"], 1))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 2024 batter weakness profile from pitch-level results.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--min-samples", type=int, default=8)
    parser.add_argument("--label", default="2024", help="Suffix label for generated weakness columns, e.g. 2024 or 2025")
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    batter_store = defaultdict(
        lambda: {
            "batter_name": "",
            "stance": "",
            "side": defaultdict(lambda: {"sum": 0.0, "count": 0}),
            "height": defaultdict(lambda: {"sum": 0.0, "count": 0}),
            "family": defaultdict(lambda: {"sum": 0.0, "count": 0}),
            "zone": defaultdict(lambda: {"sum": 0.0, "count": 0}),
        }
    )

    for row in rows:
        batter_code = row.get("batter_code") or ""
        if not batter_code:
            continue
        stance = row.get("stance") or "UNKNOWN"
        score = pitch_disadvantage_score(row)
        z_col = zone_col(to_float(row.get("cross_plate_x")))
        z_row = zone_row(to_float(row.get("plate_z")), to_float(row.get("bottom_sz")), to_float(row.get("top_sz")))
        side = relative_side(z_col, stance)
        family = pitch_family(row.get("pitch_type") or "")
        zone_label = "OUT" if "OUT" in {z_col, z_row} else f"{z_row}_{z_col}"

        store = batter_store[batter_code]
        store["batter_name"] = row.get("batter_name") or store["batter_name"]
        store["stance"] = stance

        update_bucket(store["side"], side, score)
        update_bucket(store["height"], z_row, score)
        update_bucket(store["family"], family, score)
        update_bucket(store["zone"], zone_label, score)

    output_rows = []
    suffix = args.label
    for batter_code, store in sorted(batter_store.items()):
        weak_side = best_key(store["side"], ["INSIDE", "MIDDLE", "OUTSIDE"], args.min_samples, "UNKNOWN")
        weak_height = best_key(store["height"], ["HIGH", "MIDDLE", "LOW"], args.min_samples, "UNKNOWN")
        weak_family = best_key(store["family"], ["FASTBALL", "BREAKING"], args.min_samples, "UNKNOWN")
        weak_zone = best_key(
            store["zone"],
            ["HIGH_LEFT", "HIGH_MIDDLE", "HIGH_RIGHT", "MIDDLE_LEFT", "MIDDLE_MIDDLE", "MIDDLE_RIGHT", "LOW_LEFT", "LOW_MIDDLE", "LOW_RIGHT", "OUT"],
            args.min_samples,
            "UNKNOWN",
        )

        output_rows.append(
            {
                "batter_code": batter_code,
                "batter_name": store["batter_name"],
                "stance": store["stance"],
                f"weak_side_{suffix}": weak_side,
                f"weak_height_{suffix}": weak_height,
                f"weak_pitch_family_{suffix}": weak_family,
                f"weak_zone_{suffix}": weak_zone,
                f"weakness_score_inside_{suffix}": avg_or_zero(store["side"], "INSIDE"),
                f"weakness_score_middle_side_{suffix}": avg_or_zero(store["side"], "MIDDLE"),
                f"weakness_score_outside_{suffix}": avg_or_zero(store["side"], "OUTSIDE"),
                f"weakness_score_high_{suffix}": avg_or_zero(store["height"], "HIGH"),
                f"weakness_score_middle_height_{suffix}": avg_or_zero(store["height"], "MIDDLE"),
                f"weakness_score_low_{suffix}": avg_or_zero(store["height"], "LOW"),
                f"weakness_score_fastball_{suffix}": avg_or_zero(store["family"], "FASTBALL"),
                f"weakness_score_breaking_{suffix}": avg_or_zero(store["family"], "BREAKING"),
                f"weakness_score_weak_zone_{suffix}": avg_or_zero(store["zone"], weak_zone) if weak_zone != "UNKNOWN" else 0.0,
                f"samples_inside_{suffix}": count_or_zero(store["side"], "INSIDE"),
                f"samples_middle_side_{suffix}": count_or_zero(store["side"], "MIDDLE"),
                f"samples_outside_{suffix}": count_or_zero(store["side"], "OUTSIDE"),
                f"samples_high_{suffix}": count_or_zero(store["height"], "HIGH"),
                f"samples_middle_height_{suffix}": count_or_zero(store["height"], "MIDDLE"),
                f"samples_low_{suffix}": count_or_zero(store["height"], "LOW"),
                f"samples_fastball_{suffix}": count_or_zero(store["family"], "FASTBALL"),
                f"samples_breaking_{suffix}": count_or_zero(store["family"], "BREAKING"),
            }
        )

    write_rows(Path(args.output_csv), output_rows)
    print(f"output_rows: {len(output_rows)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
