from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def motif_len(seq: str) -> int:
    return len(seq or "")


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def top_counter(counter: Counter[str], limit: int) -> list[dict[str, object]]:
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
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--min-repeat", type=int, default=2)
    parser.add_argument("--min-motif-length", type=int, default=2)
    args = parser.parse_args()

    pa_csv = Path(args.pa_csv)
    output_dir = Path(args.output_dir)

    by_game_pitcher: dict[tuple[str, str], list[dict]] = defaultdict(list)
    pitcher_meta: dict[str, dict[str, str]] = {}

    with pa_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            by_game_pitcher[(row["game_id"], row["pitcher_code"])].append(row)
            pitcher_key = f"{row['pitcher_code']}|{row['pitcher_name']}"
            pitcher_meta[pitcher_key] = {
                "pitcher_code": row["pitcher_code"],
                "pitcher_name": row["pitcher_name"],
                "team_code": row.get("team_code", ""),
                "team_name": row.get("team_name", ""),
            }

    pitcher_games: dict[str, list[dict]] = defaultdict(list)
    for (game_id, pitcher_code), rows in by_game_pitcher.items():
        rows = sorted(rows, key=lambda r: int(r.get("pa_number_in_game") or 0))
        first = rows[0]
        pitcher_key = f"{pitcher_code}|{first['pitcher_name']}"
        pitch_seq_counter = Counter(
            row["pitch_seq"]
            for row in rows
            if motif_len((row.get("pitch_seq") or "").strip()) >= args.min_motif_length
        )
        pitch_result_counter = Counter(
            row["pitch_result_seq"] for row in rows if (row.get("pitch_result_seq") or "").count("-") >= 1
        )
        repeated_pitch_seq = {motif for motif, count in pitch_seq_counter.items() if count >= args.min_repeat}
        repeated_pitch_result = {motif for motif, count in pitch_result_counter.items() if count >= args.min_repeat}

        pitcher_games[pitcher_key].append(
            {
                "game_id": game_id,
                "game_date": first.get("game_date", ""),
                "team_code": first.get("team_code", ""),
                "team_name": first.get("team_name", ""),
                "opponent_team_code": first.get("opponent_team_code", ""),
                "opponent_team_name": first.get("opponent_team_name", ""),
                "pa_count": len(rows),
                "opening_pa_seq": "|".join(row["pitch_seq"] for row in rows[:3]),
                "closing_pa_seq": "|".join(row["pitch_seq"] for row in rows[-3:]),
                "repeated_pitch_seq_set": repeated_pitch_seq,
                "repeated_pitch_result_set": repeated_pitch_result,
                "top_pitch_seq": [m for m, _ in pitch_seq_counter.most_common(5)],
                "top_pitch_result_seq": [m for m, _ in pitch_result_counter.most_common(5)],
            }
        )

    game_summary_rows: list[dict] = []
    pair_rows: list[dict] = []
    report = {
        "pa_csv": str(pa_csv),
        "top_n": args.top_n,
        "min_repeat": args.min_repeat,
        "min_motif_length": args.min_motif_length,
        "pitchers": [],
    }
    md_lines = [
        "# Within-Pitcher Game Similarity Report",
        "",
        f"- pa_csv: `{pa_csv}`",
        f"- min_repeat: `{args.min_repeat}`",
        f"- min_motif_length: `{args.min_motif_length}`",
        "",
    ]

    for pitcher_key, games in sorted(
        pitcher_games.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    ):
        meta = pitcher_meta[pitcher_key]
        recurring_pitch_seq_games = Counter()
        recurring_pitch_result_games = Counter()
        for game in games:
            recurring_pitch_seq_games.update(game["repeated_pitch_seq_set"])
            recurring_pitch_result_games.update(game["repeated_pitch_result_set"])
            game_summary_rows.append(
                {
                    **meta,
                    "game_id": game["game_id"],
                    "game_date": game["game_date"],
                    "opponent_team_code": game["opponent_team_code"],
                    "opponent_team_name": game["opponent_team_name"],
                    "pa_count": game["pa_count"],
                    "opening_pa_seq": game["opening_pa_seq"],
                    "closing_pa_seq": game["closing_pa_seq"],
                    "repeated_pitch_seq_set": "|".join(sorted(game["repeated_pitch_seq_set"])),
                    "repeated_pitch_result_set": "|".join(sorted(game["repeated_pitch_result_set"])),
                    "top_pitch_seq": "|".join(game["top_pitch_seq"]),
                    "top_pitch_result_seq": "|".join(game["top_pitch_result_seq"]),
                }
            )

        similarity_rows = []
        for left, right in combinations(games, 2):
            pitch_seq_j = jaccard(left["repeated_pitch_seq_set"], right["repeated_pitch_seq_set"])
            pitch_result_j = jaccard(left["repeated_pitch_result_set"], right["repeated_pitch_result_set"])
            opening_match = 1 if left["opening_pa_seq"] == right["opening_pa_seq"] and left["opening_pa_seq"] else 0
            closing_match = 1 if left["closing_pa_seq"] == right["closing_pa_seq"] and left["closing_pa_seq"] else 0
            score = round((pitch_seq_j * 0.5) + (pitch_result_j * 0.4) + (opening_match * 0.05) + (closing_match * 0.05), 4)
            similarity_rows.append(
                {
                    **meta,
                    "game_id_left": left["game_id"],
                    "game_date_left": left["game_date"],
                    "opponent_left": left["opponent_team_code"],
                    "game_id_right": right["game_id"],
                    "game_date_right": right["game_date"],
                    "opponent_right": right["opponent_team_code"],
                    "pitch_seq_jaccard": round(pitch_seq_j, 4),
                    "pitch_result_jaccard": round(pitch_result_j, 4),
                    "opening_match": opening_match,
                    "closing_match": closing_match,
                    "similarity_score": score,
                    "shared_pitch_seq": "|".join(sorted(left["repeated_pitch_seq_set"] & right["repeated_pitch_seq_set"])),
                    "shared_pitch_result_seq": "|".join(sorted(left["repeated_pitch_result_set"] & right["repeated_pitch_result_set"])),
                }
            )
        similarity_rows.sort(key=lambda row: row["similarity_score"], reverse=True)
        pair_rows.extend(similarity_rows[: args.top_n])

        top_recurring_pitch_seq = top_counter(recurring_pitch_seq_games, args.top_n)
        top_recurring_pitch_result = top_counter(recurring_pitch_result_games, args.top_n)
        report["pitchers"].append(
            {
                **meta,
                "game_count": len(games),
                "top_recurring_pitch_seq_across_games": top_recurring_pitch_seq,
                "top_recurring_pitch_result_seq_across_games": top_recurring_pitch_result,
                "top_similar_game_pairs": similarity_rows[: args.top_n],
            }
        )

        md_lines.extend(
            [
                f"## {meta['pitcher_name']} ({meta['team_name']})",
                "",
                f"- game_count: `{len(games)}`",
                "",
                "### Recurring PA motifs across games",
                "",
            ]
        )
        for item in top_recurring_pitch_seq:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` games ({item['share']:.1%})")
        md_lines.extend(["", "### Recurring pitch_result_seq across games", ""])
        for item in top_recurring_pitch_result:
            md_lines.append(f"- `{item['motif']}`: `{item['count']}` games ({item['share']:.1%})")
        md_lines.extend(["", "### Most similar game pairs", ""])
        for row in similarity_rows[: args.top_n]:
            md_lines.append(
                f"- `{row['game_date_left']} {row['opponent_left']}` vs `{row['game_date_right']} {row['opponent_right']}`: "
                f"`score={row['similarity_score']}` "
                f"(shared pitch_seq: `{row['shared_pitch_seq'] or '-'};` shared pitch_result_seq: `{row['shared_pitch_result_seq'] or '-'}')"
            )
        md_lines.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "within_pitcher_game_similarity_report_2025_100ip.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "within_pitcher_game_similarity_report_2025_100ip.md").write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )
    write_csv(
        output_dir / "within_pitcher_game_signatures_2025_100ip.csv",
        game_summary_rows,
        [
            "pitcher_code",
            "pitcher_name",
            "team_code",
            "team_name",
            "game_id",
            "game_date",
            "opponent_team_code",
            "opponent_team_name",
            "pa_count",
            "opening_pa_seq",
            "closing_pa_seq",
            "repeated_pitch_seq_set",
            "repeated_pitch_result_set",
            "top_pitch_seq",
            "top_pitch_result_seq",
        ],
    )
    write_csv(
        output_dir / "within_pitcher_top_similar_game_pairs_2025_100ip.csv",
        pair_rows,
        [
            "pitcher_code",
            "pitcher_name",
            "team_code",
            "team_name",
            "game_id_left",
            "game_date_left",
            "opponent_left",
            "game_id_right",
            "game_date_right",
            "opponent_right",
            "pitch_seq_jaccard",
            "pitch_result_jaccard",
            "opening_match",
            "closing_match",
            "similarity_score",
            "shared_pitch_seq",
            "shared_pitch_result_seq",
        ],
    )


if __name__ == "__main__":
    main()
