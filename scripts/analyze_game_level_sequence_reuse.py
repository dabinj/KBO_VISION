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


def token_len(seq: str, sep: str = "") -> int:
    if not seq:
        return 0
    if sep:
        return len([x for x in seq.split(sep) if x])
    return len(seq)


def top_rows(counter: Counter[str], limit: int) -> list[dict[str, object]]:
    total = sum(counter.values())
    rows = []
    for motif, count in counter.most_common(limit):
        rows.append(
            {
                "motif": motif,
                "count": count,
                "share": round(count / total, 4) if total else 0.0,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pa-csv", required=True)
    parser.add_argument("--inning-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    pa_csv = Path(args.pa_csv)
    inning_csv = Path(args.inning_csv)
    output_dir = Path(args.output_dir)

    pitcher_meta: dict[str, dict[str, str]] = {}
    pa_game_repeat_counter: dict[str, Counter[str]] = defaultdict(Counter)
    pa_game_presence_counter: dict[str, Counter[str]] = defaultdict(Counter)
    inning_game_repeat_counter: dict[str, Counter[str]] = defaultdict(Counter)
    inning_game_presence_counter: dict[str, Counter[str]] = defaultdict(Counter)
    game_summaries: list[dict] = []

    pa_by_game_pitcher: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with pa_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = (row["game_id"], row["pitcher_code"])
            pa_by_game_pitcher[key].append(row)
            pitcher_key = f"{row['pitcher_code']}|{row['pitcher_name']}"
            pitcher_meta[pitcher_key] = {
                "pitcher_code": row["pitcher_code"],
                "pitcher_name": row["pitcher_name"],
                "team_code": row.get("team_code", ""),
                "team_name": row.get("team_name", ""),
            }

    inning_by_game_pitcher: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with inning_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = (row["game_id"], row["pitcher_code"])
            inning_by_game_pitcher[key].append(row)

    for key, pa_rows in pa_by_game_pitcher.items():
        game_id, pitcher_code = key
        pitcher_name = pa_rows[0]["pitcher_name"]
        pitcher_key = f"{pitcher_code}|{pitcher_name}"
        pa_counter = Counter(
            row["pitch_seq"]
            for row in pa_rows
            if token_len((row.get("pitch_seq") or "").strip()) >= 2
        )
        repeated_pa = {motif: count for motif, count in pa_counter.items() if count >= 2}
        for motif, count in repeated_pa.items():
            pa_game_repeat_counter[pitcher_key][motif] += count
            pa_game_presence_counter[pitcher_key][motif] += 1

        inning_rows = inning_by_game_pitcher.get(key, [])
        inning_counter = Counter(
            row["pitch_seq"]
            for row in inning_rows
            if token_len((row.get("pitch_seq") or "").strip(), "|") >= 2
        )
        repeated_inning = {motif: count for motif, count in inning_counter.items() if count >= 2}
        for motif, count in repeated_inning.items():
            inning_game_repeat_counter[pitcher_key][motif] += count
            inning_game_presence_counter[pitcher_key][motif] += 1

        game_summaries.append(
            {
                "game_id": game_id,
                "pitcher_code": pitcher_code,
                "pitcher_name": pitcher_name,
                "team_code": pa_rows[0].get("team_code", ""),
                "team_name": pa_rows[0].get("team_name", ""),
                "repeated_pa_motif_count": sum(repeated_pa.values()),
                "unique_repeated_pa_motifs": len(repeated_pa),
                "repeated_inning_motif_count": sum(repeated_inning.values()),
                "unique_repeated_inning_motifs": len(repeated_inning),
                "top_repeated_pa_motif": next(iter(sorted(repeated_pa.items(), key=lambda x: (-x[1], x[0]))), ("", 0))[0],
                "top_repeated_inning_motif": next(iter(sorted(repeated_inning.items(), key=lambda x: (-x[1], x[0]))), ("", 0))[0],
            }
        )

    report = {
        "pa_csv": str(pa_csv),
        "inning_csv": str(inning_csv),
        "top_n": args.top_n,
        "pitchers": [],
    }
    md_lines = [
        "# Game-Level Sequence Reuse Report",
        "",
        f"- pa_csv: `{pa_csv}`",
        f"- inning_csv: `{inning_csv}`",
        "",
    ]
    pa_repeat_rows = []
    inning_repeat_rows = []

    sorted_pitchers = sorted(
        pitcher_meta.keys(),
        key=lambda key: sum(pa_game_presence_counter[key].values()),
        reverse=True,
    )
    for pitcher_key in sorted_pitchers:
        meta = pitcher_meta[pitcher_key]
        top_pa_repeats = top_rows(pa_game_presence_counter[pitcher_key], args.top_n)
        top_inning_repeats = top_rows(inning_game_presence_counter[pitcher_key], args.top_n)
        report["pitchers"].append(
            {
                **meta,
                "top_repeated_pa_motifs_across_games": top_pa_repeats,
                "top_repeated_inning_motifs_across_games": top_inning_repeats,
            }
        )
        md_lines.extend(
            [
                f"## {meta['pitcher_name']} ({meta['team_name']})",
                "",
                "### Repeated PA motifs within games",
                "",
            ]
        )
        for item in top_pa_repeats:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` games ({item['share']:.1%})")
        md_lines.extend(["", "### Repeated inning motifs within games", ""])
        for item in top_inning_repeats:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` games ({item['share']:.1%})")
        md_lines.append("")

        for rank, item in enumerate(top_pa_repeats, start=1):
            pa_repeat_rows.append({**meta, "rank": rank, **item})
        for rank, item in enumerate(top_inning_repeats, start=1):
            inning_repeat_rows.append({**meta, "rank": rank, **item})

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "game_level_sequence_reuse_report_2025_100ip.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "game_level_sequence_reuse_report_2025_100ip.md").write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )
    write_csv(
        output_dir / "repeated_pa_motifs_within_games_2025_100ip.csv",
        pa_repeat_rows,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "repeated_inning_motifs_within_games_2025_100ip.csv",
        inning_repeat_rows,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "rank", "motif", "count", "share"],
    )
    write_csv(
        output_dir / "game_level_reuse_summary_2025_100ip.csv",
        game_summaries,
        [
            "game_id",
            "pitcher_code",
            "pitcher_name",
            "team_code",
            "team_name",
            "repeated_pa_motif_count",
            "unique_repeated_pa_motifs",
            "repeated_inning_motif_count",
            "unique_repeated_inning_motifs",
            "top_repeated_pa_motif",
            "top_repeated_inning_motif",
        ],
    )


if __name__ == "__main__":
    main()
