#!/usr/bin/env python3

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pct_rows(counter: Counter, limit: int = 8) -> list[dict]:
    total = sum(counter.values())
    rows = []
    for name, count in counter.most_common(limit):
        rows.append(
            {
                "name": name,
                "count": count,
                "pct": round((count / total) * 100, 3) if total else 0.0,
            }
        )
    return rows


def normalize(counter: Counter) -> dict[str, float]:
    total = sum(counter.values())
    if not total:
        return {}
    return {key: value / total for key, value in counter.items()}


def js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    keys = set(p) | set(q)
    m = {key: 0.5 * p.get(key, 0.0) + 0.5 * q.get(key, 0.0) for key in keys}

    def kl(a: dict[str, float], b: dict[str, float]) -> float:
        total = 0.0
        for key, value in a.items():
            if value <= 0.0:
                continue
            total += value * math.log2(value / max(b.get(key, 1e-12), 1e-12))
        return total

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def summarize_factor(rows: list[dict], factor_name: str, pitch_key: str, zone_key: str, min_samples: int) -> dict:
    overall_pitch = Counter(row.get(pitch_key) or "UNKNOWN" for row in rows)
    overall_zone = Counter(row.get(zone_key) or "UNKNOWN" for row in rows)
    overall_pitch_norm = normalize(overall_pitch)
    overall_zone_norm = normalize(overall_zone)

    grouped_pitch = defaultdict(Counter)
    grouped_zone = defaultdict(Counter)
    for row in rows:
        value = row.get(factor_name) or "UNKNOWN"
        grouped_pitch[value][row.get(pitch_key) or "UNKNOWN"] += 1
        grouped_zone[value][row.get(zone_key) or "UNKNOWN"] += 1

    value_rows = []
    weighted_pitch_js = 0.0
    weighted_zone_js = 0.0
    total = len(rows)
    for value, pitch_counter in sorted(grouped_pitch.items(), key=lambda item: sum(item[1].values()), reverse=True):
        count = sum(pitch_counter.values())
        if count < min_samples:
            continue
        zone_counter = grouped_zone[value]
        pitch_js = js_divergence(normalize(pitch_counter), overall_pitch_norm)
        zone_js = js_divergence(normalize(zone_counter), overall_zone_norm)
        weighted_pitch_js += (count / total) * pitch_js
        weighted_zone_js += (count / total) * zone_js
        value_rows.append(
            {
                "value": value,
                "count": count,
                "pitch_js_vs_overall": round(pitch_js, 5),
                "zone_js_vs_overall": round(zone_js, 5),
                "top_pitch_types": pct_rows(pitch_counter, limit=5),
                "top_zones": pct_rows(zone_counter, limit=5),
            }
        )

    return {
        "factor_name": factor_name,
        "weighted_pitch_js": round(weighted_pitch_js, 5),
        "weighted_zone_js": round(weighted_zone_js, 5),
        "values": value_rows,
    }


def render_markdown(title: str, summary: dict) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- first_pitch_rows: `{summary['first_pitch_rows']}`")
    lines.append("- overall pitch mix: " + ", ".join(f"{row['name']} {row['pct']}%" for row in summary["overall_pitch_mix"]))
    lines.append("- overall zone mix: " + ", ".join(f"{row['name']} {row['pct']}%" for row in summary["overall_zone_mix"]))
    lines.append("")
    lines.append("## Factor Ranking")
    lines.append("")
    for row in summary["factor_ranking"]:
        lines.append(
            f"- `{row['factor_name']}`: pitch_shift `{row['weighted_pitch_js']}`, zone_shift `{row['weighted_zone_js']}`"
        )
    lines.append("")
    for factor in summary["factor_summaries"]:
        lines.append(f"## {factor['factor_name']}")
        lines.append(
            f"- weighted shift: pitch `{factor['weighted_pitch_js']}`, zone `{factor['weighted_zone_js']}`"
        )
        for value in factor["values"]:
            lines.append(
                f"- `{value['value']}` ({value['count']}): pitch "
                + ", ".join(f"{row['name']} {row['pct']}%" for row in value["top_pitch_types"])
            )
            lines.append(
                f"  zone: " + ", ".join(f"{row['name']} {row['pct']}%" for row in value["top_zones"])
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze which factors move first-pitch pitch type and zone.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--min-samples", type=int, default=20)
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    factors = [
        "runner_state",
        "outs",
        "inning",
        "batter_stance",
        "catcher_name",
        "opponent_team_code",
        "batter_season_ba_bucket",
        "batter_first_pitch_swing_bucket_2025",
        "weak_side_2024",
        "weak_height_2024",
        "weak_pitch_family_2024",
        "weak_zone_2024",
    ]

    summaries = [
        summarize_factor(rows, factor, "first_pitch_type", "first_zone_9", args.min_samples)
        for factor in factors
    ]
    ranking = sorted(
        [
            {
                "factor_name": item["factor_name"],
                "weighted_pitch_js": item["weighted_pitch_js"],
                "weighted_zone_js": item["weighted_zone_js"],
            }
            for item in summaries
        ],
        key=lambda item: (item["weighted_pitch_js"] + item["weighted_zone_js"]),
        reverse=True,
    )

    payload = {
        "first_pitch_rows": len(rows),
        "overall_pitch_mix": pct_rows(Counter(row.get("first_pitch_type") or "UNKNOWN" for row in rows), limit=10),
        "overall_zone_mix": pct_rows(Counter(row.get("first_zone_9") or "UNKNOWN" for row in rows), limit=10),
        "factor_ranking": ranking,
        "factor_summaries": summaries,
    }
    write_json(Path(args.output_json), payload)
    write_text(Path(args.output_md), render_markdown(args.title, payload))
    print(f"rows: {len(rows)}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")


if __name__ == "__main__":
    main()
