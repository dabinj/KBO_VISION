from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def normalized_similarity(a: str, b: str) -> float:
    denom = max(len(a), len(b), 1)
    return round(1.0 - (levenshtein(a, b) / denom), 4)


def needleman_wunsch_score(a: str, b: str, match: int = 2, mismatch: int = -1, gap: int = -1) -> int:
    n = len(a)
    m = len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch)
            up = dp[i - 1][j] + gap
            left = dp[i][j - 1] + gap
            dp[i][j] = max(diag, up, left)

    return dp[n][m]


def smith_waterman_score(a: str, b: str, match: int = 2, mismatch: int = -1, gap: int = -1) -> int:
    n = len(a)
    m = len(b)
    best = 0
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch)
            up = dp[i - 1][j] + gap
            left = dp[i][j - 1] + gap
            dp[i][j] = max(0, diag, up, left)
            if dp[i][j] > best:
                best = dp[i][j]

    return best


def normalize_alignment_score(score: int, a: str, b: str, match: int = 2, allow_local: bool = False) -> float:
    denom = max(match * max(min(len(a), len(b)) if allow_local else max(len(a), len(b)), 1), 1)
    return round(score / denom, 4)


def clean_seq(seq: str) -> str:
    return (seq or "").replace(" ", "").replace("|", "").replace("-", "")


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_pa_pairs(rows: list[dict], top_n: int) -> list[dict]:
    out: list[dict] = []
    by_pitcher: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        seq = (row.get("pitch_seq") or "").strip()
        if len(seq) >= 3:
            key = (row["pitcher_code"], row["pitcher_name"], row.get("team_code", ""), row.get("team_name", ""))
            by_pitcher[key][seq] += 1

    for (pitcher_code, pitcher_name, team_code, team_name), counter in by_pitcher.items():
        motifs = counter.most_common(top_n)
        for rank_a, (seq_a, count_a), rank_b, (seq_b, count_b) in [
            (i + 1, motifs[i], j + 1, motifs[j]) for i, j in combinations(range(len(motifs)), 2)
        ]:
            nw_score = needleman_wunsch_score(seq_a, seq_b)
            sw_score = smith_waterman_score(seq_a, seq_b)
            out.append(
                {
                    "sequence_level": "PA",
                    "pitcher_code": pitcher_code,
                    "pitcher_name": pitcher_name,
                    "team_code": team_code,
                    "team_name": team_name,
                    "seq_id_left": f"PA_MOTIF_{rank_a:02d}",
                    "seq_id_right": f"PA_MOTIF_{rank_b:02d}",
                    "sequence_left": seq_a,
                    "sequence_right": seq_b,
                    "count_left": count_a,
                    "count_right": count_b,
                    "levenshtein_distance": levenshtein(seq_a, seq_b),
                    "normalized_similarity": normalized_similarity(seq_a, seq_b),
                    "needleman_wunsch_score": nw_score,
                    "needleman_wunsch_similarity": normalize_alignment_score(nw_score, seq_a, seq_b),
                    "smith_waterman_score": sw_score,
                    "smith_waterman_similarity": normalize_alignment_score(sw_score, seq_a, seq_b, allow_local=True),
                }
            )
    return out


def build_inning_pairs(rows: list[dict], top_n: int) -> list[dict]:
    out: list[dict] = []
    by_pitcher: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        seq = (row.get("pitch_seq") or "").strip()
        if seq and seq.count("|") >= 1:
            key = (row["pitcher_code"], row["pitcher_name"], row.get("team_code", ""), row.get("team_name", ""))
            by_pitcher[key][seq] += 1

    for (pitcher_code, pitcher_name, team_code, team_name), counter in by_pitcher.items():
        motifs = counter.most_common(top_n)
        for rank_a, (seq_a, count_a), rank_b, (seq_b, count_b) in [
            (i + 1, motifs[i], j + 1, motifs[j]) for i, j in combinations(range(len(motifs)), 2)
        ]:
            a_clean = clean_seq(seq_a)
            b_clean = clean_seq(seq_b)
            nw_score = needleman_wunsch_score(a_clean, b_clean)
            sw_score = smith_waterman_score(a_clean, b_clean)
            out.append(
                {
                    "sequence_level": "INNING",
                    "pitcher_code": pitcher_code,
                    "pitcher_name": pitcher_name,
                    "team_code": team_code,
                    "team_name": team_name,
                    "seq_id_left": f"INNING_MOTIF_{rank_a:02d}",
                    "seq_id_right": f"INNING_MOTIF_{rank_b:02d}",
                    "sequence_left": seq_a,
                    "sequence_right": seq_b,
                    "count_left": count_a,
                    "count_right": count_b,
                    "levenshtein_distance": levenshtein(a_clean, b_clean),
                    "normalized_similarity": normalized_similarity(a_clean, b_clean),
                    "needleman_wunsch_score": nw_score,
                    "needleman_wunsch_similarity": normalize_alignment_score(nw_score, a_clean, b_clean),
                    "smith_waterman_score": sw_score,
                    "smith_waterman_similarity": normalize_alignment_score(sw_score, a_clean, b_clean, allow_local=True),
                }
            )
    return out


def build_game_pairs(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    by_pitcher: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["pitcher_code"], row["pitcher_name"], row.get("team_code", ""), row.get("team_name", ""))
        by_pitcher[key].append(row)

    for (pitcher_code, pitcher_name, team_code, team_name), games in by_pitcher.items():
        games = sorted(games, key=lambda r: (r.get("game_date", ""), r.get("game_id", "")))
        for left, right in combinations(games, 2):
            left_seq = clean_seq(left.get("pa_seq_concat") or left.get("pitch_seq") or "")
            right_seq = clean_seq(right.get("pa_seq_concat") or right.get("pitch_seq") or "")
            nw_score = needleman_wunsch_score(left_seq, right_seq)
            sw_score = smith_waterman_score(left_seq, right_seq)
            out.append(
                {
                    "sequence_level": "GAME",
                    "pitcher_code": pitcher_code,
                    "pitcher_name": pitcher_name,
                    "team_code": team_code,
                    "team_name": team_name,
                    "seq_id_left": left.get("game_id", ""),
                    "seq_id_right": right.get("game_id", ""),
                    "sequence_left": left.get("opening_pa_seq", "") if "opening_pa_seq" in left else left.get("pa_seq_concat", ""),
                    "sequence_right": right.get("opening_pa_seq", "") if "opening_pa_seq" in right else right.get("pa_seq_concat", ""),
                    "count_left": left.get("pa_count", ""),
                    "count_right": right.get("pa_count", ""),
                    "levenshtein_distance": levenshtein(left_seq, right_seq),
                    "normalized_similarity": normalized_similarity(left_seq, right_seq),
                    "needleman_wunsch_score": nw_score,
                    "needleman_wunsch_similarity": normalize_alignment_score(nw_score, left_seq, right_seq),
                    "smith_waterman_score": sw_score,
                    "smith_waterman_similarity": normalize_alignment_score(sw_score, left_seq, right_seq, allow_local=True),
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pa-csv", required=True)
    parser.add_argument("--inning-csv", required=True)
    parser.add_argument("--game-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    pa_rows = read_csv(Path(args.pa_csv))
    inning_rows = read_csv(Path(args.inning_csv))
    game_rows = read_csv(Path(args.game_csv))

    pa_pairs = build_pa_pairs(pa_rows, args.top_n)
    inning_pairs = build_inning_pairs(inning_rows, args.top_n)
    game_pairs = build_game_pairs(game_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "pa_distance_matrix_pairs_2025_100ip.csv",
        pa_pairs,
        ["sequence_level", "pitcher_code", "pitcher_name", "team_code", "team_name", "seq_id_left", "seq_id_right", "sequence_left", "sequence_right", "count_left", "count_right", "levenshtein_distance", "normalized_similarity", "needleman_wunsch_score", "needleman_wunsch_similarity", "smith_waterman_score", "smith_waterman_similarity"],
    )
    write_csv(
        output_dir / "inning_distance_matrix_pairs_2025_100ip.csv",
        inning_pairs,
        ["sequence_level", "pitcher_code", "pitcher_name", "team_code", "team_name", "seq_id_left", "seq_id_right", "sequence_left", "sequence_right", "count_left", "count_right", "levenshtein_distance", "normalized_similarity", "needleman_wunsch_score", "needleman_wunsch_similarity", "smith_waterman_score", "smith_waterman_similarity"],
    )
    write_csv(
        output_dir / "game_distance_matrix_pairs_2025_100ip.csv",
        game_pairs,
        ["sequence_level", "pitcher_code", "pitcher_name", "team_code", "team_name", "seq_id_left", "seq_id_right", "sequence_left", "sequence_right", "count_left", "count_right", "levenshtein_distance", "normalized_similarity", "needleman_wunsch_score", "needleman_wunsch_similarity", "smith_waterman_score", "smith_waterman_similarity"],
    )
    summary = {
        "pa_pairs": len(pa_pairs),
        "inning_pairs": len(inning_pairs),
        "game_pairs": len(game_pairs),
        "top_n": args.top_n,
    }
    (output_dir / "sequence_distance_matrix_summary_2025_100ip.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
