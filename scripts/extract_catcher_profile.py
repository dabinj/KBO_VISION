#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def write_rows_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def pct_counter(counter: Counter) -> list[dict]:
    total = sum(counter.values())
    rows = []
    for key, value in counter.most_common():
        rows.append(
            {
                "name": key,
                "count": value,
                "pct": round((value / total) * 100, 3) if total else 0.0,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract one catcher's received pitch rows and basic profile summary.")
    parser.add_argument("--input-csv", required=True, help="Full pitch table CSV")
    parser.add_argument("--catcher-code", required=True, help="Catcher code")
    parser.add_argument("--catcher-name", help="Optional exact catcher name")
    parser.add_argument("--team-code", help="Optional team code filter such as SK")
    parser.add_argument("--output-dir", default="data/matchups", help="Output directory")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    catcher_code = args.catcher_code.strip()
    catcher_name = (args.catcher_name or "").strip()
    team_code = (args.team_code or "").strip().upper()

    rows = []
    pitch_type_counter = Counter()
    pitcher_counter = Counter()
    batter_counter = Counter()
    game_counter = Counter()
    batter_stance_counter = Counter()

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("catcher_code") != catcher_code:
                continue
            if catcher_name and row.get("catcher_name") != catcher_name:
                continue
            if team_code and row.get("home_team_code") != team_code and row.get("away_team_code") != team_code:
                continue

            rows.append(row)
            pitch_type_counter[row.get("pitch_type") or "UNKNOWN"] += 1
            pitcher_counter[row.get("pitcher_name") or "UNKNOWN"] += 1
            batter_counter[row.get("batter_name") or "UNKNOWN"] += 1
            game_counter[row.get("game_id") or "UNKNOWN"] += 1
            batter_stance_counter[row.get("stance") or "UNKNOWN"] += 1

    stem_name = catcher_name or catcher_code
    stem_name = stem_name.replace(" ", "_")
    file_stem = f"catcher_{catcher_code}_{stem_name}"
    if team_code:
        file_stem += f"_{team_code}"

    write_rows_csv(output_dir / f"{file_stem}.csv", rows)

    summary = {
        "input_csv": str(input_path),
        "catcher_code": catcher_code,
        "catcher_name": catcher_name or None,
        "team_code": team_code or None,
        "total_received_pitches": len(rows),
        "games": len(game_counter),
        "pitchers_worked_with_unique": len(pitcher_counter),
        "batters_faced_unique": len(batter_counter),
        "first_game_date": rows[0]["game_date"] if rows else None,
        "last_game_date": rows[-1]["game_date"] if rows else None,
        "pitch_type_distribution": pct_counter(pitch_type_counter),
        "pitcher_distribution": pct_counter(pitcher_counter),
        "batter_stance_distribution": pct_counter(batter_stance_counter),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{file_stem}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
