#!/usr/bin/env python3

from pathlib import Path


PREDICTIONS = [
    {
        "name": "오재원",
        "stance": "L",
        "prior": "화이트 2025 좌타 상대 직구-커브 축 가정",
        "first": "유력 초구: 낮은 코스 직구",
        "next": "유력 2구: 낮은 코스 커브",
        "result": "유력 결과: 중견수 뜬공",
    },
    {
        "name": "페라자",
        "stance": "L",
        "prior": "화이트 2025 좌타 상대 바깥쪽 승부 가정",
        "first": "유력 초구: 바깥쪽 직구",
        "next": "유력 2구: 바깥쪽 낮은 커브",
        "result": "유력 결과: 헛스윙 삼진",
    },
    {
        "name": "문현빈",
        "stance": "L",
        "prior": "화이트 2025 좌타 상대 높은 직구 뒤 커브 전환 가정",
        "first": "유력 초구: 높은 코스 직구",
        "next": "유력 2구: 바깥쪽 높은 커브",
        "result": "유력 결과: 좌익수 뜬공",
    },
    {
        "name": "노시환",
        "stance": "R",
        "prior": "화이트 2025 우타 상대 커터-슬라이더 축 가정",
        "first": "유력 초구: 바깥쪽 높은 커터",
        "next": "유력 2구: 바깥쪽 슬라이더",
        "result": "유력 결과: 루킹 삼진",
    },
    {
        "name": "강백호",
        "stance": "L",
        "prior": "화이트 2025 좌타 상대 바깥쪽 견제 가정",
        "first": "유력 초구: 바깥쪽 직구",
        "next": "유력 2구: 바깥쪽 커브",
        "result": "유력 결과: 볼넷",
    },
    {
        "name": "채은성",
        "stance": "R",
        "prior": "화이트 2025 우타 상대 커터/투심 비중 상승 가정",
        "first": "유력 초구: 바깥쪽 커터",
        "next": "유력 2구: 바깥쪽 낮은 투심",
        "result": "유력 결과: 우익수 뜬공",
    },
    {
        "name": "하주석",
        "stance": "L",
        "prior": "화이트 2025 좌타 상대 낮은 코스 승부 가정",
        "first": "유력 초구: 바깥쪽 직구",
        "next": "유력 2구: 바깥쪽 낮은 커브",
        "result": "유력 결과: 내야 뜬공",
    },
    {
        "name": "최재훈",
        "stance": "R",
        "prior": "화이트 2025 우타 상대 바깥쪽 직구-커터 가정",
        "first": "유력 초구: 바깥쪽 높은 직구",
        "next": "유력 2구: 바깥쪽 커터",
        "result": "유력 결과: 3루수 땅볼",
    },
    {
        "name": "심우준",
        "stance": "R",
        "prior": "화이트 2025 우타 상대 직구 뒤 슬라이더 전환 가정",
        "first": "유력 초구: 가운데 높은 직구",
        "next": "유력 2구: 바깥쪽 슬라이더",
        "result": "유력 결과: 헛스윙 삼진",
    },
]


def card(parts: list[str], x: int, y: int, row: dict) -> None:
    w = 350
    h = 132
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append(f'<text x="{x+18}" y="{y+28}" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{row["name"]}</text>')
    parts.append(f'<text x="{x+118}" y="{y+28}" font-size="12" font-family="Segoe UI, Arial" fill="#486581">{row["stance"]}HB</text>')
    parts.append(f'<text x="{x+18}" y="{y+50}" font-size="11" font-family="Segoe UI, Arial" fill="#486581">{row["prior"]}</text>')
    parts.append(f'<text x="{x+18}" y="{y+76}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">{row["first"]}</text>')
    parts.append(f'<text x="{x+18}" y="{y+96}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">{row["next"]}</text>')
    parts.append(f'<text x="{x+18}" y="{y+118}" font-size="12" font-family="Segoe UI, Arial" font-weight="700" fill="#0f766e">{row["result"]}</text>')


def main() -> None:
    width = 1130
    height = 1200
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="38" font-size="28" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">Tomorrow Fun Board: Hanwha vs White</text>',
        '<text x="24" y="64" font-size="13" font-family="Segoe UI, Arial" fill="#486581">Experimental and for fun only. Assumes the 2026-04-08 Hanwha lineup carries into the next game.</text>',
        '<text x="24" y="86" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Built from White 2025 pitch history, left-right split, count flow, and catcher-weighted tendencies.</text>',
    ]

    start_y = 120
    idx = 0
    for row_i in range(3):
        for col_i in range(3):
            x = 24 + col_i * 368
            y = start_y + row_i * 152
            card(parts, x, y, PREDICTIONS[idx])
            idx += 1

    parts.append('<rect x="24" y="590" width="1082" height="128" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append('<text x="42" y="622" font-size="18" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">Fun Read</text>')
    parts.append('<text x="42" y="648" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">1. 좌타 상대로는 화이트의 2025 패턴상 직구-커브 축, 우타 상대로는 커터-투심-슬라이더 축을 더 강하게 반영했습니다.</text>')
    parts.append('<text x="42" y="672" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">2. 아직 약점 방향 공략은 검증 전이므로, 카드의 코스 설정은 화이트의 실제 2025 패턴에서만 가져왔습니다.</text>')
    parts.append('<text x="42" y="696" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">3. 포수는 화이트의 2025 수신 비중이 가장 큰 조형우 계열 배합 흐름을 우선 가정했습니다.</text>')
    parts.append('</svg>')

    Path("examples/hanwha_tomorrow_fun_board.svg").write_text("\n".join(parts), encoding="utf-8")
    print("examples/hanwha_tomorrow_fun_board.svg")


if __name__ == "__main__":
    main()
