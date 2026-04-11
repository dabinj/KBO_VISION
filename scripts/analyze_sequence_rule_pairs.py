from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def top_rows(counter: Counter[str], limit: int) -> list[dict[str, object]]:
    total = sum(counter.values())
    rows: list[dict[str, object]] = []
    for motif, count in counter.most_common(limit):
        rows.append(
            {
                "motif": motif,
                "count": count,
                "share": round(count / total, 4) if total else 0.0,
            }
        )
    return rows


def token_count(seq: str, sep: str) -> int:
    if not seq:
        return 0
    if sep:
        return len([token for token in seq.split(sep) if token])
    return len(seq)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)

    pitch_result_counts: dict[str, Counter[str]] = defaultdict(Counter)
    two_strike_pitch_result_counts: dict[str, Counter[str]] = defaultdict(Counter)
    count_path_pitch_counts: dict[str, Counter[str]] = defaultdict(Counter)
    pitch_zone_result_counts: dict[str, Counter[str]] = defaultdict(Counter)
    pitcher_meta: dict[str, dict[str, str]] = {}

    with input_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pitcher_key = f"{row['pitcher_code']}|{row['pitcher_name']}"
            pitcher_meta[pitcher_key] = {
                "pitcher_code": row["pitcher_code"],
                "pitcher_name": row["pitcher_name"],
                "team_code": row.get("team_code", ""),
                "team_name": row.get("team_name", ""),
            }

            pitch_result_seq = (row.get("pitch_result_seq") or "").strip()
            count_path_seq = (row.get("count_path_seq") or "").strip()
            pitch_seq = (row.get("pitch_seq") or "").strip()
            pitch_zone_seq = (row.get("pitch_zone_seq") or "").strip()
            result_seq = (row.get("result_seq") or "").strip()
            is_two_strike = (row.get("is_two_strike_sequence") or "0") == "1"

            if token_count(pitch_result_seq, "-") >= 2:
                pitch_result_counts[pitcher_key][pitch_result_seq] += 1
                if is_two_strike:
                    two_strike_pitch_result_counts[pitcher_key][pitch_result_seq] += 1

            if count_path_seq and pitch_seq and token_count(count_path_seq, "|") >= 2 and len(pitch_seq) >= 2:
                combo = f"{count_path_seq} => {pitch_seq}"
                count_path_pitch_counts[pitcher_key][combo] += 1

            if pitch_zone_seq and result_seq and token_count(pitch_zone_seq, "-") >= 2 and len(result_seq) >= 2:
                combo = f"{pitch_zone_seq} => {result_seq}"
                pitch_zone_result_counts[pitcher_key][combo] += 1

    report: dict[str, object] = {
        "input_csv": str(input_csv),
        "top_n": args.top_n,
        "pitchers": [],
    }
    md_lines: list[str] = [
        "# Sequence Rule Pair Report",
        "",
        f"- input: `{input_csv}`",
        f"- top_n: `{args.top_n}`",
        "",
    ]
    pitch_result_csv: list[dict] = []
    two_strike_csv: list[dict] = []
    count_path_pitch_csv: list[dict] = []
    pitch_zone_result_csv: list[dict] = []

    sorted_pitchers = sorted(
        pitcher_meta.keys(),
        key=lambda key: sum(pitch_result_counts[key].values()),
        reverse=True,
    )

    for pitcher_key in sorted_pitchers:
        meta = pitcher_meta[pitcher_key]
        top_pitch_result = top_rows(pitch_result_counts[pitcher_key], args.top_n)
        top_two_strike = top_rows(two_strike_pitch_result_counts[pitcher_key], args.top_n)
        top_count_path_pitch = top_rows(count_path_pitch_counts[pitcher_key], args.top_n)
        top_pitch_zone_result = top_rows(pitch_zone_result_counts[pitcher_key], args.top_n)

        report["pitchers"].append(
            {
                **meta,
                "top_pitch_result_seq": top_pitch_result,
                "top_two_strike_pitch_result_seq": top_two_strike,
                "top_count_path_pitch_seq": top_count_path_pitch,
                "top_pitch_zone_result_seq": top_pitch_zone_result,
            }
        )

        md_lines.extend(
            [
                f"## {meta['pitcher_name']} ({meta['team_name']})",
                "",
                "### Top pitch_result_seq",
                "",
            ]
        )
        for item in top_pitch_result:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` ({item['share']:.1%})")
        md_lines.extend(["", "### 2-strike pitch_result_seq", ""])
        for item in top_two_strike:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` ({item['share']:.1%})")
        md_lines.extend(["", "### count_path_seq + pitch_seq", ""])
        for item in top_count_path_pitch:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` ({item['share']:.1%})")
        md_lines.extend(["", "### pitch_zone_seq + result_seq", ""])
        for item in top_pitch_zone_result:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` ({item['share']:.1%})")
        md_lines.append("")

        for rank, item in enumerate(top_pitch_result, start=1):
            pitch_result_csv.append({**meta, "rank": rank, **item})
        for rank, item in enumerate(top_two_strike, start=1):
            two_strike_csv.append({**meta, "rank": rank, **item})
        for rank, item in enumerate(top_count_path_pitch, start=1):
            count_path_pitch_csv.append({**meta, "rank": rank, **item})
        for rank, item in enumerate(top_pitch_zone_result, start=1):
            pitch_zone_result_csv.append({**meta, "rank": rank, **item})

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sequence_rule_pair_report_2025_100ip.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "sequence_rule_pair_report_2025_100ip.md").write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )
    write_csv(
        output_dir / "pitch_result_seq_top10_by_pitcher_2025_100ip.csv",
        pitch_result_csv,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "two_strike_pitch_result_seq_top10_2025_100ip.csv",
        two_strike_csv,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "count_path_pitch_seq_top10_2025_100ip.csv",
        count_path_pitch_csv,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "pitch_zone_result_seq_top10_2025_100ip.csv",
        pitch_zone_result_csv,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )


if __name__ == "__main__":
    main()
