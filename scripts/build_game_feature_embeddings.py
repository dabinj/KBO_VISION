from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


PITCHES = ["F", "T", "C", "S", "W", "K", "U", "P", "X"]
STANCES = ["L", "R"]
COUNTS = ["ahead", "behind", "even"]


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pitch_abbrev(raw: str) -> str:
    mapping = {
        "직구": "F",
        "투심": "T",
        "커터": "C",
        "슬라이더": "S",
        "스위퍼": "W",
        "커브": "K",
        "체인지업": "U",
        "포크": "P",
    }
    return mapping.get((raw or "").strip(), "X")


def parse_count_state(count_state: str) -> tuple[int, int]:
    try:
        b, s = (count_state or "0-0").split("-")
        return int(b), int(s)
    except Exception:
        return 0, 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pitch-master-csv", required=True)
    parser.add_argument("--game-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--clusters", type=int, default=8)
    args = parser.parse_args()

    pitch_rows = read_csv(Path(args.pitch_master_csv))
    game_rows = read_csv(Path(args.game_csv))

    game_meta = {(row["game_id"], row["pitcher_code"]): row for row in game_rows}
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in pitch_rows:
        grouped[(row["game_id"], row["pitcher_code"])].append(row)

    feature_rows: list[dict] = []
    numeric_rows: list[dict[str, float]] = []
    for key, rows in grouped.items():
        game_id, pitcher_code = key
        meta = game_meta.get(key, {})
        total = len(rows)
        pitch_counter = Counter()
        first_pitch_counter = Counter()
        two_strike_counter = Counter()
        stance_pitch_counter = {stance: Counter() for stance in STANCES}
        zone_row_counter = Counter()
        zone_col_counter = Counter()
        count_bucket_counter = {bucket: Counter() for bucket in COUNTS}
        bigram_counter = Counter()
        trigram_counter = Counter()
        seq_by_pa: dict[str, str] = {}

        for row in rows:
            p = pitch_abbrev(row.get("pitch_type") or row.get("pitch_seq") or "")
            pitch_counter[p] += 1
            if row.get("pitch_index_in_pa") == "1":
                first_pitch_counter[p] += 1
            if str(row.get("count_state", "")).endswith("-2"):
                two_strike_counter[p] += 1
            stance = (row.get("batter_stance") or "").strip()
            if stance in stance_pitch_counter:
                stance_pitch_counter[stance][p] += 1
            zone = (row.get("zone_25") or "").strip()
            if len(zone) == 2:
                zone_row_counter[zone[0]] += 1
                zone_col_counter[zone[1]] += 1
            balls, strikes = parse_count_state(row.get("count_state", ""))
            if balls > strikes:
                count_bucket_counter["behind"][p] += 1
            elif balls < strikes:
                count_bucket_counter["ahead"][p] += 1
            else:
                count_bucket_counter["even"][p] += 1

        pa_rows = sorted(rows, key=lambda r: (r.get("pa_id", ""), int(r.get("pitch_index_in_pa") or 0)))
        for row in pa_rows:
            pa_id = row["pa_id"]
            seq_by_pa.setdefault(pa_id, "")
            seq_by_pa[pa_id] += pitch_abbrev(row.get("pitch_type") or row.get("pitch_seq") or "")
        for seq in seq_by_pa.values():
            for i in range(len(seq) - 1):
                bigram_counter[seq[i : i + 2]] += 1
            for i in range(len(seq) - 2):
                trigram_counter[seq[i : i + 3]] += 1

        numeric: dict[str, float] = {}
        for pitch in PITCHES:
            numeric[f"pitch_share_{pitch}"] = round(pitch_counter[pitch] / total, 6) if total else 0.0
            numeric[f"first_pitch_share_{pitch}"] = round(first_pitch_counter[pitch] / max(sum(first_pitch_counter.values()), 1), 6)
            numeric[f"two_strike_share_{pitch}"] = round(two_strike_counter[pitch] / max(sum(two_strike_counter.values()), 1), 6)
        for stance in STANCES:
            stance_total = sum(stance_pitch_counter[stance].values())
            for pitch in PITCHES:
                numeric[f"stance_{stance}_share_{pitch}"] = round(stance_pitch_counter[stance][pitch] / max(stance_total, 1), 6)
        for bucket in COUNTS:
            bucket_total = sum(count_bucket_counter[bucket].values())
            for pitch in PITCHES:
                numeric[f"count_{bucket}_share_{pitch}"] = round(count_bucket_counter[bucket][pitch] / max(bucket_total, 1), 6)
        for row_label in ["A", "B", "C", "D", "E"]:
            numeric[f"zone_row_share_{row_label}"] = round(zone_row_counter[row_label] / max(sum(zone_row_counter.values()), 1), 6)
        for col_label in ["1", "2", "3", "4", "5"]:
            numeric[f"zone_col_share_{col_label}"] = round(zone_col_counter[col_label] / max(sum(zone_col_counter.values()), 1), 6)

        for motif, count in bigram_counter.most_common(5):
            numeric[f"bigram_{motif}"] = count
        for motif, count in trigram_counter.most_common(5):
            numeric[f"trigram_{motif}"] = count

        feature_rows.append(
            {
                "game_id": game_id,
                "game_date": meta.get("game_date", ""),
                "pitcher_code": pitcher_code,
                "pitcher_name": meta.get("pitcher_name", ""),
                "team_code": meta.get("team_code", ""),
                "team_name": meta.get("team_name", ""),
                "opponent_team_code": meta.get("opponent_team_code", ""),
                "opponent_team_name": meta.get("opponent_team_name", ""),
                "pitch_count_in_game": total,
                "pa_count": meta.get("pa_count", ""),
                **numeric,
            }
        )
        numeric_rows.append(numeric)

    all_numeric_keys = sorted({key for row in numeric_rows for key in row.keys()})
    matrix = [[row.get(key, 0.0) for key in all_numeric_keys] for row in numeric_rows]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    pca = PCA(n_components=2, random_state=42)
    pcs = pca.fit_transform(scaled)
    cluster_count = min(max(2, args.clusters), len(feature_rows))
    kmeans = KMeans(n_clusters=cluster_count, random_state=42, n_init=20)
    labels = kmeans.fit_predict(scaled)

    enriched_rows = []
    for row, label, pc in zip(feature_rows, labels, pcs):
        enriched = dict(row)
        enriched["cluster_id"] = int(label)
        enriched["pc1"] = round(float(pc[0]), 6)
        enriched["pc2"] = round(float(pc[1]), 6)
        enriched_rows.append(enriched)

    cluster_summary = []
    by_cluster: dict[int, list[dict]] = defaultdict(list)
    for row in enriched_rows:
        by_cluster[int(row["cluster_id"])].append(row)
    for cluster_id, rows in sorted(by_cluster.items()):
        pitcher_counts = Counter(row["pitcher_name"] for row in rows)
        cluster_summary.append(
            {
                "cluster_id": cluster_id,
                "game_count": len(rows),
                "top_pitchers": "|".join(name for name, _ in pitcher_counts.most_common(5)),
            }
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_fieldnames = sorted({key for row in enriched_rows for key in row.keys()})
    normalized_rows = [{field: row.get(field, "") for field in all_fieldnames} for row in enriched_rows]
    write_csv(
        output_dir / "game_feature_embedding_2025_100ip.csv",
        normalized_rows,
        all_fieldnames,
    )
    write_csv(
        output_dir / "game_feature_cluster_summary_2025_100ip.csv",
        cluster_summary,
        ["cluster_id", "game_count", "top_pitchers"],
    )
    (output_dir / "game_feature_embedding_2025_100ip_meta.json").write_text(
        json.dumps(
            {
                "clusters": cluster_count,
                "row_count": len(enriched_rows),
                "feature_count": len(all_numeric_keys),
                "pca_explained_variance_ratio": [round(float(x), 6) for x in pca.explained_variance_ratio_],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
