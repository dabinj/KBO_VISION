from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


FEATURE_PREFIXES = (
    "pitch_share_",
    "first_pitch_share_",
    "two_strike_share_",
    "stance_",
    "count_",
    "zone_row_share_",
    "zone_col_share_",
    "bigram_",
    "trigram_",
)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_float(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def is_feature_col(name: str) -> bool:
    return name.startswith(FEATURE_PREFIXES)


def simplify_feature_name(name: str) -> str:
    replacements = {
        "pitch_share_": "구종비율 ",
        "first_pitch_share_": "초구비율 ",
        "two_strike_share_": "2스트라이크 ",
        "stance_L_": "좌타상대 ",
        "stance_R_": "우타상대 ",
        "count_ahead_": "유리카운트 ",
        "count_behind_": "불리카운트 ",
        "count_even_": "동일카운트 ",
        "zone_row_share_": "세로 ",
        "zone_col_share_": "가로 ",
        "bigram_": "2구패턴 ",
        "trigram_": "3구패턴 ",
    }
    for old, new in replacements.items():
        if name.startswith(old):
            return new + name[len(old):]
    return name


def mean_feature(rows: list[dict], feature_cols: list[str], target_cluster: int | None = None) -> dict[str, float]:
    subset = rows if target_cluster is None else [r for r in rows if int(float(r["within_cluster_id"])) == target_cluster]
    if not subset:
        return {col: 0.0 for col in feature_cols}
    return {col: sum(to_float(r.get(col, "")) for r in subset) / len(subset) for col in feature_cols}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=8)
    args = parser.parse_args()

    rows = read_csv(Path(args.embedding_csv))
    feature_cols = [c for c in rows[0].keys() if is_feature_col(c)] if rows else []
    by_pitcher: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = f"{row['pitcher_code']}|{row['pitcher_name']}|{row['team_code']}|{row['team_name']}"
        by_pitcher[key].append(row)

    cluster_rows: list[dict] = []
    report: dict[str, list] = {"pitchers": []}
    md_lines = [
        "# Within-Pitcher Cluster Characteristics",
        "",
        "같은 투수의 경기들을 embedding으로 묶은 뒤, 각 클러스터가 시즌 평균 대비 어떤 feature가 두드러졌는지 정리한 문서입니다.",
        "",
    ]

    for key, games in sorted(by_pitcher.items(), key=lambda item: len(item[1]), reverse=True):
        pitcher_code, pitcher_name, team_code, team_name = key.split("|")
        overall = mean_feature(games, feature_cols, None)
        cluster_ids = sorted({int(float(r["within_cluster_id"])) for r in games})
        pitcher_entry = {
            "pitcher_code": pitcher_code,
            "pitcher_name": pitcher_name,
            "team_code": team_code,
            "team_name": team_name,
            "clusters": [],
        }
        md_lines.append(f"## {pitcher_name} ({team_name})")
        md_lines.append("")
        for cluster_id in cluster_ids:
            cluster_games = [r for r in games if int(float(r["within_cluster_id"])) == cluster_id]
            cluster_mean = mean_feature(games, feature_cols, cluster_id)
            deltas = []
            for col in feature_cols:
                delta = cluster_mean[col] - overall[col]
                deltas.append((col, delta, cluster_mean[col], overall[col]))
            deltas.sort(key=lambda item: abs(item[1]), reverse=True)
            top_items = deltas[: args.top_n]
            pitcher_entry["clusters"].append(
                {
                    "cluster_id": cluster_id,
                    "game_count": len(cluster_games),
                    "top_features": [
                        {
                            "feature": col,
                            "feature_label": simplify_feature_name(col),
                            "delta_vs_pitcher_mean": round(delta, 6),
                            "cluster_mean": round(cluster_mean_value, 6),
                            "pitcher_mean": round(overall_value, 6),
                        }
                        for col, delta, cluster_mean_value, overall_value in top_items
                    ],
                }
            )
            for rank, (col, delta, cluster_mean_value, overall_value) in enumerate(top_items, start=1):
                cluster_rows.append(
                    {
                        "pitcher_code": pitcher_code,
                        "pitcher_name": pitcher_name,
                        "team_code": team_code,
                        "team_name": team_name,
                        "cluster_id": cluster_id,
                        "cluster_game_count": len(cluster_games),
                        "feature_rank": rank,
                        "feature": col,
                        "feature_label": simplify_feature_name(col),
                        "delta_vs_pitcher_mean": round(delta, 6),
                        "cluster_mean": round(cluster_mean_value, 6),
                        "pitcher_mean": round(overall_value, 6),
                    }
                )
            md_lines.append(f"### Cluster {cluster_id} ({len(cluster_games)}경기)")
            for _, (col, delta, cluster_mean_value, overall_value) in enumerate(top_items, start=1):
                sign = "+" if delta >= 0 else ""
                md_lines.append(
                    f"- `{simplify_feature_name(col)}`: 군집 평균 `{cluster_mean_value:.4f}`, 시즌 평균 `{overall_value:.4f}`, 차이 `{sign}{delta:.4f}`"
                )
            md_lines.append("")
        report["pitchers"].append(pitcher_entry)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "within_pitcher_cluster_characteristics_2025_100ip.csv",
        cluster_rows,
        [
            "pitcher_code",
            "pitcher_name",
            "team_code",
            "team_name",
            "cluster_id",
            "cluster_game_count",
            "feature_rank",
            "feature",
            "feature_label",
            "delta_vs_pitcher_mean",
            "cluster_mean",
            "pitcher_mean",
        ],
    )
    (output_dir / "within_pitcher_cluster_characteristics_2025_100ip.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "within_pitcher_cluster_characteristics_2025_100ip.md").write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
