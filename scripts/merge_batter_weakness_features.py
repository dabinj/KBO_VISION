#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


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


def relative_side_from_zone(zone_9: str, stance: str) -> str:
    if not zone_9 or zone_9 == "OUT":
        return "OUT"
    parts = zone_9.split("_")
    if len(parts) != 2:
        return "UNKNOWN"
    col = parts[1]
    if col == "MIDDLE":
        return "MIDDLE"
    if stance == "L":
        return "INSIDE" if col == "RIGHT" else "OUTSIDE"
    return "INSIDE" if col == "LEFT" else "OUTSIDE"


def height_from_zone(zone_9: str) -> str:
    if not zone_9 or zone_9 == "OUT":
        return "OUT"
    parts = zone_9.split("_")
    return parts[0] if len(parts) == 2 else "UNKNOWN"


def score_for_side(profile: dict, side: str) -> str:
    mapping = {
        "INSIDE": "weakness_score_inside_2024",
        "MIDDLE": "weakness_score_middle_side_2024",
        "OUTSIDE": "weakness_score_outside_2024",
    }
    return profile.get(mapping.get(side, ""), "0.0")


def score_for_height(profile: dict, height: str) -> str:
    mapping = {
        "HIGH": "weakness_score_high_2024",
        "MIDDLE": "weakness_score_middle_height_2024",
        "LOW": "weakness_score_low_2024",
    }
    return profile.get(mapping.get(height, ""), "0.0")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge 2024 batter weakness profile into 2025 model table.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--weakness-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    profiles = {row["batter_code"]: row for row in read_rows(Path(args.weakness_csv))}

    output_rows = []
    for row in rows:
        batter_code = row.get("batter_code") or ""
        profile = profiles.get(
            batter_code,
            {
                "weak_side_2024": "UNKNOWN",
                "weak_height_2024": "UNKNOWN",
                "weak_pitch_family_2024": "UNKNOWN",
                "weak_zone_2024": "UNKNOWN",
                "weakness_score_inside_2024": "0.0",
                "weakness_score_middle_side_2024": "0.0",
                "weakness_score_outside_2024": "0.0",
                "weakness_score_high_2024": "0.0",
                "weakness_score_middle_height_2024": "0.0",
                "weakness_score_low_2024": "0.0",
                "weakness_score_fastball_2024": "0.0",
                "weakness_score_breaking_2024": "0.0",
                "weakness_score_weak_zone_2024": "0.0",
            },
        )
        stance = row.get("batter_stance") or row.get("stance") or "UNKNOWN"
        current_zone = row.get("current_zone_9") or row.get("zone_9") or ""
        next_zone = row.get("next_zone_9") or ""
        current_side = relative_side_from_zone(current_zone, stance)
        next_side = relative_side_from_zone(next_zone, stance)
        current_height = height_from_zone(current_zone)
        next_height = height_from_zone(next_zone)
        current_family = row.get("current_pitch_family") or row.get("pitch_family") or ""
        next_family = row.get("next_pitch_family") or ""

        merged = {
            **row,
            **{key: value for key, value in profile.items() if key != "batter_code"},
            "current_zone_side_rel": current_side,
            "current_zone_height": current_height,
            "next_zone_side_rel": next_side,
            "next_zone_height": next_height,
            "current_pitch_targets_weak_side_2024": "1" if current_side == profile.get("weak_side_2024") else "0",
            "current_pitch_targets_weak_height_2024": "1" if current_height == profile.get("weak_height_2024") else "0",
            "current_pitch_targets_weak_family_2024": "1" if current_family == profile.get("weak_pitch_family_2024") else "0",
            "next_pitch_targets_weak_side_2024": "1" if next_side == profile.get("weak_side_2024") else "0",
            "next_pitch_targets_weak_height_2024": "1" if next_height == profile.get("weak_height_2024") else "0",
            "next_pitch_targets_weak_family_2024": "1" if next_family == profile.get("weak_pitch_family_2024") else "0",
            "current_zone_side_weakness_score_2024": score_for_side(profile, current_side),
            "current_zone_height_weakness_score_2024": score_for_height(profile, current_height),
        }
        output_rows.append(merged)

    write_rows(Path(args.output_csv), output_rows)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(output_rows)}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
