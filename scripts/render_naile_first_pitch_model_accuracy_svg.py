#!/usr/bin/env python3

import json
from pathlib import Path


WIDTH = 1280
HEIGHT = 860


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: float) -> float:
    return round(value * 100, 1)


def bar(width_max: int, value_pct: float, color: str) -> str:
    width = width_max * (value_pct / 100.0)
    return (
        f'<rect x="0" y="0" width="{width_max}" height="26" rx="13" fill="#eadfcd"/>'
        f'<rect x="0" y="0" width="{width:.1f}" height="26" rx="13" fill="{color}"/>'
    )


def render_svg(pitch_data: dict, zone_data: dict) -> str:
    pitch_top1 = pct(pitch_data["test_metrics"]["top1_accuracy"])
    pitch_top3 = pct(pitch_data["test_metrics"]["top3_accuracy"])
    zone_top1 = pct(zone_data["test_metrics"]["top1_accuracy"])
    zone_top3 = pct(zone_data["test_metrics"]["top3_accuracy"])

    pitch_top_features = [row["feature"] for row in pitch_data["feature_importance_gain"][:6]]
    zone_top_features = [row["feature"] for row in zone_data["feature_importance_gain"][:6]]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f5f1e8"/>',
        '<rect x="30" y="30" width="1220" height="800" rx="30" fill="#fcfaf5" stroke="#d4c7ad" stroke-width="2"/>',
        '<text x="70" y="92" font-size="38" font-weight="700" fill="#2d2418">네일 초구 예측 성능 요약</text>',
        '<text x="70" y="128" font-size="20" fill="#665844">피처를 거의 모두 넣은 상태에서, 초구 구종과 초구 위치가 얼마나 맞는지를 비교한 결과입니다.</text>',
        '<rect x="70" y="170" width="540" height="280" rx="28" fill="#fff9f0" stroke="#d8ccb5" stroke-width="2"/>',
        '<rect x="670" y="170" width="540" height="280" rx="28" fill="#f5fbff" stroke="#c7d8e8" stroke-width="2"/>',
        '<text x="100" y="222" font-size="30" font-weight="700" fill="#2d2418">초구 구종 예측</text>',
        '<text x="700" y="222" font-size="30" font-weight="700" fill="#2d2418">초구 위치 예측</text>',
        f'<text x="100" y="300" font-size="72" font-weight="700" fill="#b5542f">{pitch_top1:.1f}%</text>',
        f'<text x="700" y="300" font-size="72" font-weight="700" fill="#2f6fd6">{zone_top1:.1f}%</text>',
        '<text x="100" y="334" font-size="22" fill="#6a5a45">Top-1 accuracy</text>',
        '<text x="700" y="334" font-size="22" fill="#6a5a45">Top-1 accuracy</text>',
        f'<text x="100" y="384" font-size="22" fill="#6a5a45">Top-3: {pitch_top3:.1f}%</text>',
        f'<text x="700" y="384" font-size="22" fill="#6a5a45">Top-3: {zone_top3:.1f}%</text>',
        '<text x="100" y="415" font-size="18" fill="#7a6d57">7개 구종 중 하나를 정확히 맞힌 비율</text>',
        '<text x="700" y="415" font-size="18" fill="#7a6d57">9분할+OUT 위치를 정확히 맞힌 비율</text>',
        '<g transform="translate(100,470)">',
        '<text x="0" y="0" font-size="24" font-weight="700" fill="#2d2418">Top-1 비교</text>',
        f'<g transform="translate(0,30)">{bar(420, pitch_top1, "#c96a3c")}</g>',
        f'<text x="440" y="50" font-size="22" font-weight="700" fill="#2d2418">{pitch_top1:.1f}%</text>',
        f'<g transform="translate(0,90)">{bar(420, zone_top1, "#2f6fd6")}</g>',
        f'<text x="440" y="110" font-size="22" font-weight="700" fill="#2d2418">{zone_top1:.1f}%</text>',
        '<text x="0" y="50" font-size="18" fill="#6a5a45">구종</text>',
        '<text x="0" y="110" font-size="18" fill="#6a5a45">위치</text>',
        '</g>',
        '<text x="70" y="670" font-size="28" font-weight="700" fill="#2d2418">무슨 뜻인가?</text>',
        '<text x="70" y="710" font-size="20" fill="#665844">1. 현재 모델은 구종보다 위치를 더 잘 맞힙니다.</text>',
        '<text x="70" y="742" font-size="20" fill="#665844">2. 즉 네일의 초구는 “무슨 공인가”보다 “어디로 가는가”가 더 규칙적입니다.</text>',
        '<text x="70" y="774" font-size="20" fill="#665844">3. 실전 대응에서는 초구 구종 단일 맞히기보다, 위치 방향을 먼저 읽는 쪽이 더 유리합니다.</text>',
        '<text x="760" y="520" font-size="26" font-weight="700" fill="#2d2418">주요 영향 피처</text>',
        '<text x="760" y="556" font-size="18" fill="#6a5a45">구종 모델 상위</text>',
    ]

    y = 586
    for feature in pitch_top_features:
        parts.append(f'<text x="780" y="{y}" font-size="18" fill="#2d2418">- {feature}</text>')
        y += 28

    parts.append(f'<text x="760" y="{y + 10}" font-size="18" fill="#6a5a45">위치 모델 상위</text>')
    y += 40
    for feature in zone_top_features:
        parts.append(f'<text x="780" y="{y}" font-size="18" fill="#2d2418">- {feature}</text>')
        y += 28

    parts.append('</svg>')
    return "\n".join(parts)


def main() -> None:
    base = Path(r"c:\Users\Dabin Jeon\Documents\DevOps\KBO_VISION\data\matchups\2025_naile")
    pitch_path = base / "xgb_naile_first_pitch_type_with_swing_inning_2025.json"
    zone_path = base / "xgb_naile_first_zone_with_swing_inning_2025.json"
    output_path = base / "naile_first_pitch_model_accuracy_summary_2025.svg"

    pitch_data = load_json(pitch_path)
    zone_data = load_json(zone_path)
    output_path.write_text(render_svg(pitch_data, zone_data), encoding="utf-8")
    print(f"output_svg: {output_path}")


if __name__ == "__main__":
    main()
