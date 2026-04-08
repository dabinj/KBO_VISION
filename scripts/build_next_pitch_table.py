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


def build_next_pitch_rows(rows: list[dict], first_pitch_only: bool) -> list[dict]:
    rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("pa_number_in_game") or 0),
            int(row.get("pitch_index_in_pa") or 0),
        ),
    )

    result = []
    for index in range(len(rows) - 1):
        current = rows[index]
        nxt = rows[index + 1]
        same_pa = (
            current.get("game_id") == nxt.get("game_id")
            and current.get("pa_number_in_game") == nxt.get("pa_number_in_game")
        )
        if not same_pa:
            continue
        if first_pitch_only and current.get("pitch_index_in_pa") != "1":
            continue

        next_pitch_type = nxt.get("pitch_type") or ""
        next_zone_9 = nxt.get("zone_9") or ""
        current_pitch_type = current.get("pitch_type") or ""
        current_zone_9 = current.get("zone_9") or ""

        result.append(
            {
                **current,
                "current_pitch_type": current_pitch_type,
                "current_zone_9": current_zone_9,
                "next_pitch_type": next_pitch_type,
                "next_zone_9": next_zone_9,
                "next_pitch_family": nxt.get("pitch_family") or "",
                "next_pitch_zone_combo": f"{next_pitch_type}__{next_zone_9}",
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build next-pitch prediction table from current-pitch state rows.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--first-pitch-only", action="store_true")
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    output_rows = build_next_pitch_rows(rows, args.first_pitch_only)
    write_rows(Path(args.output_csv), output_rows)
    print(f"input_rows: {len(rows)}")
    print(f"output_rows: {len(output_rows)}")
    print(f"first_pitch_only: {args.first_pitch_only}")
    print(f"output_csv: {args.output_csv}")


if __name__ == "__main__":
    main()
