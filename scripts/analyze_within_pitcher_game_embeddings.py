from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def is_feature_col(name: str) -> bool:
    prefixes = (
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
    return name.startswith(prefixes)


def to_float(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def render_svg_page(selected: list[tuple[str, list[dict]]], output_path: Path, page_label: str = "") -> None:
    max_pitchers = len(selected)
    grouped: dict[str, list[dict]] = defaultdict(list)

    width = 1320
    panel_w = 410
    panel_h = 260
    cols = 3
    rows_n = max(1, math.ceil(len(selected) / cols))
    height = 90 + rows_n * (panel_h + 24)
    colors = ["#2563eb", "#d97706", "#059669", "#dc2626", "#7c3aed"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="38" font-size="28" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">Within-Pitcher Game Embedding</text>',
        f'<text x="24" y="62" font-size="13" font-family="Segoe UI, Arial" fill="#486581">Same pitcher games clustered by handcrafted feature embeddings (2025, 100+ IP){page_label}</text>',
    ]

    for idx, (pitcher_key, pts) in enumerate(selected):
        col = idx % cols
        row = idx // cols
        x = 24 + col * (panel_w + 18)
        y = 90 + row * (panel_h + 24)
        parts.append(f'<rect x="{x}" y="{y}" width="{panel_w}" height="{panel_h}" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
        parts.append(f'<text x="{x+16}" y="{y+28}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{pitcher_key}</text>')
        parts.append(f'<text x="{x+16}" y="{y+46}" font-size="11" font-family="Segoe UI, Arial" fill="#486581">games={len(pts)}</text>')

        plot_x = x + 42
        plot_y = y + 66
        plot_w = panel_w - 66
        plot_h = panel_h - 92
        parts.append(f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" stroke="#e5e7eb"/>')
        xs = [to_float(p["within_pc1"]) for p in pts]
        ys = [to_float(p["within_pc2"]) for p in pts]
        min_x, max_x = min(xs, default=-1), max(xs, default=1)
        min_y, max_y = min(ys, default=-1), max(ys, default=1)
        if min_x == max_x:
            min_x, max_x = min_x - 1, max_x + 1
        if min_y == max_y:
            min_y, max_y = min_y - 1, max_y + 1

        def sx(v: float) -> float:
            return plot_x + ((v - min_x) / (max_x - min_x)) * plot_w

        def sy(v: float) -> float:
            return plot_y + plot_h - ((v - min_y) / (max_y - min_y)) * plot_h

        mid_x = sx(0.0) if min_x <= 0 <= max_x else plot_x + plot_w / 2
        mid_y = sy(0.0) if min_y <= 0 <= max_y else plot_y + plot_h / 2
        parts.append(f'<line x1="{plot_x}" y1="{mid_y}" x2="{plot_x+plot_w}" y2="{mid_y}" stroke="#cbd2d9"/>')
        parts.append(f'<line x1="{mid_x}" y1="{plot_y}" x2="{mid_x}" y2="{plot_y+plot_h}" stroke="#cbd2d9"/>')

        for p in pts:
            cx = sx(to_float(p["within_pc1"]))
            cy = sy(to_float(p["within_pc2"]))
            cluster = int(float(p["within_cluster_id"]))
            color = colors[cluster % len(colors)]
            label = f"{p['game_date']} {p['opponent_team_code']}"
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{color}" fill-opacity="0.9"/>')
            parts.append(f'<text x="{cx+7:.1f}" y="{cy-7:.1f}" font-size="9" font-family="Segoe UI, Arial" fill="#334e68">{label}</text>')

    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def render_svg(rows: list[dict], output_path: Path, max_pitchers: int = 9) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['pitcher_name']}|{row['team_name']}"].append(row)
    selected = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:max_pitchers]
    render_svg_page(selected, output_path)


def render_svg_pages(rows: list[dict], output_dir: Path, per_page: int = 9) -> list[Path]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['pitcher_name']}|{row['team_name']}"].append(row)
    ordered = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
    page_paths: list[Path] = []
    for start in range(0, len(ordered), per_page):
        page_num = (start // per_page) + 1
        selected = ordered[start : start + per_page]
        page_path = output_dir / f"within_pitcher_game_embedding_2025_100ip_page_{page_num:02d}.svg"
        render_svg_page(selected, page_path, page_label=f" | page {page_num}")
        page_paths.append(page_path)
    return page_paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-clusters", type=int, default=3)
    args = parser.parse_args()

    rows = read_csv(Path(args.embedding_csv))
    feature_cols = [col for col in rows[0].keys() if is_feature_col(col)] if rows else []
    by_pitcher: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_pitcher[f"{row['pitcher_code']}|{row['pitcher_name']}|{row['team_code']}|{row['team_name']}"].append(row)

    enriched_rows: list[dict] = []
    pair_rows: list[dict] = []
    summary_rows: list[dict] = []
    report = {"pitchers": []}

    for key, games in sorted(by_pitcher.items(), key=lambda item: len(item[1]), reverse=True):
        pitch_matrix = [[to_float(game.get(col, "")) for col in feature_cols] for game in games]
        scaler = StandardScaler()
        scaled = scaler.fit_transform(pitch_matrix)
        if len(games) >= 2:
            pca = PCA(n_components=2, random_state=42)
            pcs = pca.fit_transform(scaled)
        else:
            pcs = [[0.0, 0.0] for _ in games]
        cluster_n = min(args.max_clusters, len(games))
        if cluster_n >= 2:
            kmeans = KMeans(n_clusters=cluster_n, random_state=42, n_init=20)
            labels = kmeans.fit_predict(scaled)
        else:
            labels = [0 for _ in games]
        sims = cosine_similarity(scaled)

        for idx, game in enumerate(games):
            row = dict(game)
            row["within_cluster_id"] = int(labels[idx])
            row["within_pc1"] = round(float(pcs[idx][0]), 6)
            row["within_pc2"] = round(float(pcs[idx][1]), 6)
            enriched_rows.append(row)

        top_pairs = []
        for i, j in combinations(range(len(games)), 2):
            pair = {
                "pitcher_code": games[i]["pitcher_code"],
                "pitcher_name": games[i]["pitcher_name"],
                "team_code": games[i]["team_code"],
                "team_name": games[i]["team_name"],
                "game_id_left": games[i]["game_id"],
                "game_date_left": games[i]["game_date"],
                "opponent_left": games[i]["opponent_team_code"],
                "cluster_left": int(labels[i]),
                "game_id_right": games[j]["game_id"],
                "game_date_right": games[j]["game_date"],
                "opponent_right": games[j]["opponent_team_code"],
                "cluster_right": int(labels[j]),
                "cosine_similarity": round(float(sims[i][j]), 6),
            }
            top_pairs.append(pair)
        top_pairs.sort(key=lambda row: row["cosine_similarity"], reverse=True)
        pair_rows.extend(top_pairs[:10])

        cluster_counts = defaultdict(int)
        for label in labels:
            cluster_counts[int(label)] += 1
        summary_rows.append(
            {
                "pitcher_code": games[0]["pitcher_code"],
                "pitcher_name": games[0]["pitcher_name"],
                "team_code": games[0]["team_code"],
                "team_name": games[0]["team_name"],
                "game_count": len(games),
                "cluster_count": cluster_n,
                "cluster_sizes": "|".join(f"{cid}:{count}" for cid, count in sorted(cluster_counts.items())),
                "top_pair_similarity": top_pairs[0]["cosine_similarity"] if top_pairs else "",
            }
        )
        report["pitchers"].append(
            {
                "pitcher_code": games[0]["pitcher_code"],
                "pitcher_name": games[0]["pitcher_name"],
                "team_code": games[0]["team_code"],
                "team_name": games[0]["team_name"],
                "game_count": len(games),
                "cluster_count": cluster_n,
                "top_pairs": top_pairs[:10],
            }
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_fields = sorted({key for row in enriched_rows for key in row.keys()})
    normalized = [{field: row.get(field, "") for field in all_fields} for row in enriched_rows]
    write_csv(output_dir / "within_pitcher_game_embedding_2025_100ip.csv", normalized, all_fields)
    write_csv(
        output_dir / "within_pitcher_game_embedding_pairs_2025_100ip.csv",
        pair_rows,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "game_id_left", "game_date_left", "opponent_left", "cluster_left", "game_id_right", "game_date_right", "opponent_right", "cluster_right", "cosine_similarity"],
    )
    write_csv(
        output_dir / "within_pitcher_game_embedding_cluster_summary_2025_100ip.csv",
        summary_rows,
        ["pitcher_code", "pitcher_name", "team_code", "team_name", "game_count", "cluster_count", "cluster_sizes", "top_pair_similarity"],
    )
    (output_dir / "within_pitcher_game_embedding_2025_100ip.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    render_svg(enriched_rows, output_dir / "within_pitcher_game_embedding_2025_100ip.svg")
    page_dir = output_dir / "페이지별"
    page_dir.mkdir(parents=True, exist_ok=True)
    page_paths = render_svg_pages(enriched_rows, page_dir, per_page=9)
    index_lines = [
        "# 페이지별 SVG 안내",
        "",
        "동일 투수 경기 embedding 시각화를 9명씩 나누어 저장했습니다.",
        "",
    ]
    for page_path in page_paths:
        index_lines.append(f"- {page_path.name}")
    (page_dir / "페이지별_안내.md").write_text("\n".join(index_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
