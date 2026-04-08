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


def split_rows_timewise(rows: list[dict], train_ratio: float = 0.8) -> tuple[list[dict], list[dict]]:
    rows = sorted(
        rows,
        key=lambda row: (
            row.get("game_date") or "",
            row.get("game_id") or "",
            int(row.get("pitch_index_in_game") or 0),
        ),
    )
    split_index = max(1, int(len(rows) * train_ratio))
    return rows[:split_index], rows[split_index:]


def build_key(row: dict, feature_names: list[str]) -> tuple:
    return tuple(row.get(name) or "" for name in feature_names)


def fit_frequency_model(rows: list[dict], target: str, feature_sets: list[list[str]]) -> dict:
    model = {"global": Counter(), "levels": []}
    for row in rows:
        model["global"][row[target]] += 1

    for feature_names in feature_sets:
        counter = defaultdict(Counter)
        for row in rows:
            counter[build_key(row, feature_names)][row[target]] += 1
        model["levels"].append({"features": feature_names, "counter": counter})
    return model


def predict_distribution(model: dict, row: dict) -> Counter:
    for level in reversed(model["levels"]):
        key = build_key(row, level["features"])
        counter = level["counter"].get(key)
        if counter:
            return counter
    return model["global"]


def compute_metrics(model: dict, rows: list[dict], target: str) -> dict:
    top1 = 0
    top3 = 0
    log_loss = 0.0
    if not rows:
        return {"rows": 0, "top1_accuracy": 0.0, "top3_accuracy": 0.0, "avg_log_loss": 0.0}

    for row in rows:
        counter = predict_distribution(model, row)
        total = sum(counter.values())
        ordered = [label for label, _ in counter.most_common()]
        actual = row[target]
        if ordered and ordered[0] == actual:
            top1 += 1
        if actual in ordered[:3]:
            top3 += 1
        prob = counter[actual] / total if actual in counter else 1e-9
        log_loss += -math.log(max(prob, 1e-9))

    return {
        "rows": len(rows),
        "top1_accuracy": round(top1 / len(rows), 4),
        "top3_accuracy": round(top3 / len(rows), 4),
        "avg_log_loss": round(log_loss / len(rows), 4),
    }


def pct(counter: Counter) -> list[dict]:
    total = sum(counter.values())
    return [
        {"name": name, "count": count, "pct": round((count / total) * 100, 3) if total else 0.0}
        for name, count in counter.most_common()
    ]


def nested_pct(rows: list[dict], group_key: str, value_key: str) -> dict:
    grouped = defaultdict(Counter)
    for row in rows:
        grouped[row.get(group_key) or "UNKNOWN"][row.get(value_key) or "UNKNOWN"] += 1
    return {
        key: pct(counter)
        for key, counter in sorted(grouped.items(), key=lambda item: sum(item[1].values()), reverse=True)
    }


def render_stage_svg(path: Path, stage_rows: list[dict]) -> None:
    width = 760
    height = 320
    margin_left = 110
    margin_bottom = 60
    chart_width = width - margin_left - 40
    chart_height = height - 40 - margin_bottom
    bar_gap = 18
    group_gap = 34
    num_groups = len(stage_rows)
    total_slots = num_groups * 2
    bar_width = (chart_width - (num_groups - 1) * group_gap - total_slots * bar_gap) / total_slots
    if bar_width < 18:
        bar_width = 18

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#fbf9f3"/>',
        '<text x="24" y="30" font-size="20" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">White Baseline Stage Accuracy</text>',
        '<text x="24" y="52" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Top-1 and Top-3 accuracy by cumulative feature stage</text>',
    ]

    for i in range(6):
        y = 70 + (chart_height / 5) * i
        value = 1 - (i / 5)
        parts.append(f'<line x1="{margin_left}" y1="{y}" x2="{width-30}" y2="{y}" stroke="#d9e2ec" stroke-width="1"/>')
        parts.append(f'<text x="{margin_left-12}" y="{y+4}" text-anchor="end" font-size="11" font-family="Segoe UI, Arial" fill="#486581">{value:.1f}</text>')

    x = margin_left + 10
    for row in stage_rows:
        top1_h = row["test_top1"] * chart_height
        top3_h = row["test_top3"] * chart_height
        parts.append(f'<rect x="{x}" y="{70 + chart_height - top1_h}" width="{bar_width}" height="{top1_h}" fill="#d1495b" rx="3"/>')
        parts.append(f'<rect x="{x + bar_width + bar_gap}" y="{70 + chart_height - top3_h}" width="{bar_width}" height="{top3_h}" fill="#2d6a4f" rx="3"/>')
        parts.append(f'<text x="{x + bar_width/2}" y="{70 + chart_height - top1_h - 6}" text-anchor="middle" font-size="10" font-family="Segoe UI, Arial" fill="#7b1e2b">{row["test_top1"]:.3f}</text>')
        parts.append(f'<text x="{x + bar_width + bar_gap + bar_width/2}" y="{70 + chart_height - top3_h - 6}" text-anchor="middle" font-size="10" font-family="Segoe UI, Arial" fill="#1b4332">{row["test_top3"]:.3f}</text>')
        parts.append(f'<text x="{x + bar_width + bar_gap/2}" y="{height-24}" text-anchor="middle" font-size="10" font-family="Segoe UI, Arial" fill="#102a43">{row["label"]}</text>')
        x += bar_width * 2 + bar_gap * 2 + group_gap

    parts.append('<rect x="560" y="20" width="12" height="12" fill="#d1495b" rx="2"/>')
    parts.append('<text x="578" y="30" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">Top-1</text>')
    parts.append('<rect x="630" y="20" width="12" height="12" fill="#2d6a4f" rx="2"/>')
    parts.append('<text x="648" y="30" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">Top-3</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def render_stance_svg(path: Path, left_rows: list[dict], right_rows: list[dict]) -> None:
    pitch_order = []
    seen = set()
    for block in [left_rows, right_rows]:
        for row in block[:6]:
            if row["name"] not in seen:
                pitch_order.append(row["name"])
                seen.add(row["name"])

    left_map = {row["name"]: row["pct"] for row in left_rows}
    right_map = {row["name"]: row["pct"] for row in right_rows}

    width = 760
    height = 360
    margin_left = 120
    margin_bottom = 60
    chart_width = width - margin_left - 50
    chart_height = height - 50 - margin_bottom
    group_gap = 22
    bar_gap = 10
    bar_width = (chart_width - len(pitch_order) * (group_gap + bar_gap)) / (len(pitch_order) * 2)
    if bar_width < 16:
        bar_width = 16

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fbff"/>',
        '<text x="24" y="30" font-size="20" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">White Pitch Mix by Batter Stance</text>',
        '<text x="24" y="52" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Left-handed and right-handed hitter pitch usage split</text>',
    ]

    max_pct = max([left_map.get(name, 0) for name in pitch_order] + [right_map.get(name, 0) for name in pitch_order] + [1])
    max_pct = math.ceil(max_pct / 10) * 10

    for i in range(6):
        y = 70 + (chart_height / 5) * i
        value = max_pct - (max_pct / 5) * i
        parts.append(f'<line x1="{margin_left}" y1="{y}" x2="{width-30}" y2="{y}" stroke="#d9e2ec" stroke-width="1"/>')
        parts.append(f'<text x="{margin_left-12}" y="{y+4}" text-anchor="end" font-size="11" font-family="Segoe UI, Arial" fill="#486581">{value:.0f}%</text>')

    x = margin_left + 10
    for name in pitch_order:
        left_pct = left_map.get(name, 0)
        right_pct = right_map.get(name, 0)
        left_h = (left_pct / max_pct) * chart_height
        right_h = (right_pct / max_pct) * chart_height
        parts.append(f'<rect x="{x}" y="{70 + chart_height - left_h}" width="{bar_width}" height="{left_h}" fill="#3b82f6" rx="3"/>')
        parts.append(f'<rect x="{x + bar_width + bar_gap}" y="{70 + chart_height - right_h}" width="{bar_width}" height="{right_h}" fill="#f97316" rx="3"/>')
        parts.append(f'<text x="{x + bar_width/2}" y="{70 + chart_height - left_h - 6}" text-anchor="middle" font-size="10" font-family="Segoe UI, Arial" fill="#1d4ed8">{left_pct:.1f}</text>')
        parts.append(f'<text x="{x + bar_width + bar_gap + bar_width/2}" y="{70 + chart_height - right_h - 6}" text-anchor="middle" font-size="10" font-family="Segoe UI, Arial" fill="#c2410c">{right_pct:.1f}</text>')
        parts.append(f'<text x="{x + bar_width + bar_gap/2}" y="{height-24}" text-anchor="middle" font-size="10" font-family="Segoe UI, Arial" fill="#102a43">{name}</text>')
        x += bar_width * 2 + bar_gap + group_gap

    parts.append('<rect x="560" y="20" width="12" height="12" fill="#3b82f6" rx="2"/>')
    parts.append('<text x="578" y="30" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">LHB</text>')
    parts.append('<rect x="620" y="20" width="12" height="12" fill="#f97316" rx="2"/>')
    parts.append('<text x="638" y="30" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">RHB</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze White baseline stages and descriptive patterns.")
    parser.add_argument("--input-csv", required=True, help="White pitcher routine table")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    rows = read_rows(Path(args.input_csv))
    train_rows, test_rows = split_rows_timewise(rows)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stage_defs = [
        ("Count", [["count_state"]]),
        ("Count+Stance", [["count_state"], ["count_state", "batter_stance"]]),
        ("+PrevPitch", [["count_state"], ["count_state", "batter_stance"], ["count_state", "batter_stance", "prev_pitch_type_pa_1"]]),
        ("+Catcher", [["count_state"], ["count_state", "batter_stance"], ["count_state", "batter_stance", "prev_pitch_type_pa_1"], ["count_state", "batter_stance", "prev_pitch_type_pa_1", "catcher_name"]]),
    ]

    stage_rows = []
    for label, feature_sets in stage_defs:
        model = fit_frequency_model(train_rows, "pitch_type", feature_sets)
        train_metrics = compute_metrics(model, train_rows, "pitch_type")
        test_metrics = compute_metrics(model, test_rows, "pitch_type")
        stage_rows.append(
            {
                "label": label,
                "feature_sets": feature_sets,
                "train_top1": train_metrics["top1_accuracy"],
                "train_top3": train_metrics["top3_accuracy"],
                "test_top1": test_metrics["top1_accuracy"],
                "test_top3": test_metrics["top3_accuracy"],
                "test_log_loss": test_metrics["avg_log_loss"],
            }
        )

    overall_pitch_mix = pct(Counter(row["pitch_type"] for row in rows))
    stance_mix = nested_pct(rows, "batter_stance", "pitch_type")
    count_mix = nested_pct(rows, "count_state", "pitch_type")
    catcher_mix = nested_pct(rows, "catcher_name", "pitch_type")
    prev_mix = nested_pct(rows, "prev_pitch_type_pa_1", "pitch_type")

    report = {
        "input_csv": args.input_csv,
        "rows": len(rows),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "stage_metrics": stage_rows,
        "overall_pitch_mix": overall_pitch_mix,
        "pitch_mix_by_stance": {
            "L": stance_mix.get("L", []),
            "R": stance_mix.get("R", []),
        },
        "pitch_mix_by_count_state_top": {k: v for k, v in list(count_mix.items())[:8]},
        "pitch_mix_by_catcher": catcher_mix,
        "next_pitch_given_prev_pitch": {k: v for k, v in list(prev_mix.items())[:8]},
        "observations": [
            "기본 구종 분포만으로는 직구 편향이 강하지만, 좌우타를 넣으면 커브/커터 축 분리가 더 잘 드러난다.",
            "좌타 상대로는 직구와 커브 비중이 높고, 우타 상대로는 커터·투심·슬라이더 비중이 더 높다.",
            "직전 구종을 넣으면 같은 타석 안의 연속성, 즉 setup pitch 이후 다음 공 선택 규칙을 일부 포착한다.",
            "포수 정보를 추가했을 때 성능이 더 좋아지면 화이트 개인 루틴만이 아니라 배터리 조합 영향도 존재한다고 해석할 수 있다.",
        ],
    }

    (output_dir / "white_baseline_analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    render_stage_svg(output_dir / "white_baseline_stage_accuracy.svg", stage_rows)
    render_stance_svg(
        output_dir / "white_pitch_mix_by_stance.svg",
        stance_mix.get("L", []),
        stance_mix.get("R", []),
    )
    print(f"output_dir: {output_dir}")


if __name__ == "__main__":
    main()
