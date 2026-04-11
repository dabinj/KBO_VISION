from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def top_items(counter: Counter[str], limit: int) -> list[dict[str, object]]:
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


def motif_length(motif: str) -> int:
    if not motif:
        return 0
    if "-" in motif:
        return len([token for token in motif.split("-") if token])
    return len(motif)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_report(input_csv: Path, output_dir: Path, top_n: int) -> None:
    pitch_seq_counts: dict[str, Counter[str]] = defaultdict(Counter)
    pitch_seq_multi_counts: dict[str, Counter[str]] = defaultdict(Counter)
    pitch_zone_seq_counts: dict[str, Counter[str]] = defaultdict(Counter)
    pitch_zone_seq_multi_counts: dict[str, Counter[str]] = defaultdict(Counter)
    two_strike_counts: dict[str, Counter[str]] = defaultdict(Counter)
    stance_counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    pitcher_meta: dict[str, dict[str, str]] = {}

    with input_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pitcher_code = row["pitcher_code"]
            pitcher_name = row["pitcher_name"]
            pitcher_key = f"{pitcher_code}|{pitcher_name}"
            pitcher_meta[pitcher_key] = {
                "pitcher_code": pitcher_code,
                "pitcher_name": pitcher_name,
                "team_code": row.get("team_code", ""),
                "team_name": row.get("team_name", ""),
            }

            pitch_seq = row.get("pitch_seq", "").strip()
            pitch_zone_seq = row.get("pitch_zone_seq", "").strip()
            batter_stance = (row.get("batter_stance") or "UNK").strip() or "UNK"
            is_two_strike = str(row.get("is_two_strike_sequence", "0")).strip() == "1"

            if pitch_seq:
                pitch_seq_counts[pitcher_key][pitch_seq] += 1
                if motif_length(pitch_seq) >= 2:
                    pitch_seq_multi_counts[pitcher_key][pitch_seq] += 1
                stance_counts[pitcher_key][batter_stance][pitch_seq] += 1
                if is_two_strike:
                    two_strike_counts[pitcher_key][pitch_seq] += 1
            if pitch_zone_seq:
                pitch_zone_seq_counts[pitcher_key][pitch_zone_seq] += 1
                if motif_length(pitch_zone_seq) >= 2:
                    pitch_zone_seq_multi_counts[pitcher_key][pitch_zone_seq] += 1

    report: dict[str, object] = {
        "input_csv": str(input_csv),
        "top_n": top_n,
        "pitchers": [],
    }
    pitch_seq_csv_rows: list[dict[str, object]] = []
    pitch_zone_csv_rows: list[dict[str, object]] = []
    two_strike_csv_rows: list[dict[str, object]] = []
    stance_csv_rows: list[dict[str, object]] = []
    md_lines: list[str] = [
        "# Sequence Motif Report",
        "",
        f"- input: `{input_csv}`",
        f"- top_n: `{top_n}`",
        "",
    ]

    sorted_pitchers = sorted(
        pitch_seq_counts.keys(),
        key=lambda key: sum(pitch_seq_counts[key].values()),
        reverse=True,
    )

    for pitcher_key in sorted_pitchers:
        meta = pitcher_meta[pitcher_key]
        top_pitch = top_items(pitch_seq_counts[pitcher_key], top_n)
        top_pitch_multi = top_items(pitch_seq_multi_counts[pitcher_key], top_n)
        top_pitch_zone = top_items(pitch_zone_seq_counts[pitcher_key], top_n)
        top_pitch_zone_multi = top_items(pitch_zone_seq_multi_counts[pitcher_key], top_n)
        top_two_strike = top_items(two_strike_counts[pitcher_key], top_n)
        stance_split = {
            stance: top_items(stance_counts[pitcher_key][stance], top_n)
            for stance in sorted(stance_counts[pitcher_key].keys())
        }

        report["pitchers"].append(
            {
                **meta,
                "pa_count": sum(pitch_seq_counts[pitcher_key].values()),
                "top_pitch_seq_all": top_pitch,
                "top_pitch_seq": top_pitch_multi,
                "top_pitch_zone_seq_all": top_pitch_zone,
                "top_pitch_zone_seq": top_pitch_zone_multi,
                "top_two_strike_pitch_seq": top_two_strike,
                "stance_split_pitch_seq": stance_split,
            }
        )

        md_lines.extend(
            [
                f"## {meta['pitcher_name']} ({meta['team_name']})",
                "",
                f"- PA count: `{sum(pitch_seq_counts[pitcher_key].values())}`",
                "",
                "### Top 10 pitch_seq (length >= 2)",
                "",
            ]
        )
        for item in top_pitch_multi:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` ({item['share']:.1%})")
        md_lines.extend(["", "### Top 10 pitch_zone_seq (length >= 2)", ""])
        for item in top_pitch_zone_multi:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` ({item['share']:.1%})")
        md_lines.extend(["", "### 2-strike top motif", ""])
        if top_two_strike:
            for item in top_two_strike:
                md_lines.append(f"- `{item['motif']}`: `{item['count']}` ({item['share']:.1%})")
        else:
            md_lines.append("- no rows")
        md_lines.extend(["", "### Stance split pitch_seq", ""])
        for stance, items in stance_split.items():
            md_lines.append(f"- `{stance}`")
            if items:
                summary = ", ".join(
                    f"{entry['motif']} ({entry['count']}, {entry['share']:.1%})" for entry in items[:5]
                )
                md_lines.append(f"  {summary}")
            else:
                md_lines.append("  no rows")
        md_lines.append("")

        for rank, item in enumerate(top_pitch_multi, start=1):
            pitch_seq_csv_rows.append(
                {
                    **meta,
                    "rank": rank,
                    "motif": item["motif"],
                    "count": item["count"],
                    "share": item["share"],
                }
            )
        for rank, item in enumerate(top_pitch_zone_multi, start=1):
            pitch_zone_csv_rows.append(
                {
                    **meta,
                    "rank": rank,
                    "motif": item["motif"],
                    "count": item["count"],
                    "share": item["share"],
                }
            )
        for rank, item in enumerate(top_two_strike, start=1):
            two_strike_csv_rows.append(
                {
                    **meta,
                    "rank": rank,
                    "motif": item["motif"],
                    "count": item["count"],
                    "share": item["share"],
                }
            )
        for stance, items in stance_split.items():
            for rank, item in enumerate(items, start=1):
                stance_csv_rows.append(
                    {
                        **meta,
                        "batter_stance": stance,
                        "rank": rank,
                        "motif": item["motif"],
                        "count": item["count"],
                        "share": item["share"],
                    }
                )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sequence_motif_report_2025_100ip.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "sequence_motif_report_2025_100ip.md").write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )
    write_csv(
        output_dir / "pitch_seq_top10_by_pitcher_2025_100ip.csv",
        pitch_seq_csv_rows,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "pitch_zone_seq_top10_by_pitcher_2025_100ip.csv",
        pitch_zone_csv_rows,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "two_strike_top_motif_2025_100ip.csv",
        two_strike_csv_rows,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "stance_split_motif_2025_100ip.csv",
        stance_csv_rows,
        [
            "pitcher_code",
            "pitcher_name",
            "team_code",
            "team_name",
            "batter_stance",
            "rank",
            "motif",
            "count",
            "share",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    build_report(Path(args.input_csv), Path(args.output_dir), args.top_n)


if __name__ == "__main__":
    main()
