#!/usr/bin/env python3

from pathlib import Path


PREDICTIONS = [
    {
        "name": "오재원",
        "stance": "L",
        "prior": "2024 prior 부족",
        "first": "초구: 낮은 코스 직구",
        "next": "다음 공: 바깥쪽 낮은 커브",
        "result": "예상 결과: 2루수 땅볼",
    },
    {
        "name": "페라자",
        "stance": "L",
        "prior": "약점: 바깥쪽 / 낮은 코스 / 변화구",
        "first": "초구: 바깥쪽 낮은 커터",
        "next": "다음 공: 바깥쪽 낮은 커브",
        "result": "예상 결과: 헛스윙 삼진",
    },
    {
        "name": "문현빈",
        "stance": "L",
        "prior": "약점: 몸쪽 / 낮은 코스 / 변화구",
        "first": "초구: 몸쪽 낮은 직구",
        "next": "다음 공: 몸쪽 낮은 커브",
        "result": "예상 결과: 유격수 땅볼",
    },
    {
        "name": "노시환",
        "stance": "R",
        "prior": "약점: 바깥쪽 / 높은 코스 / 변화구",
        "first": "초구: 바깥쪽 높은 커터",
        "next": "다음 공: 바깥쪽 슬라이더",
        "result": "예상 결과: 루킹 삼진",
    },
    {
        "name": "강백호",
        "stance": "L",
        "prior": "약점: 바깥쪽 / 낮은 코스 / 변화구",
        "first": "초구: 바깥쪽 낮은 직구",
        "next": "다음 공: 바깥쪽 낮은 커브",
        "result": "예상 결과: 볼넷",
    },
    {
        "name": "채은성",
        "stance": "R",
        "prior": "약점: 바깥쪽 / 높은 코스 / 속구",
        "first": "초구: 바깥쪽 높은 직구",
        "next": "다음 공: 바깥쪽 낮은 커터",
        "result": "예상 결과: 우익수 뜬공",
    },
    {
        "name": "하주석",
        "stance": "L",
        "prior": "약점: 몸쪽 / 높은 코스 / 변화구",
        "first": "초구: 몸쪽 높은 직구",
        "next": "다음 공: 몸쪽 커브",
        "result": "예상 결과: 내야 뜬공",
    },
    {
        "name": "최재훈",
        "stance": "R",
        "prior": "약점: 몸쪽 / 중간 높이 / 속구",
        "first": "초구: 몸쪽 투심",
        "next": "다음 공: 몸쪽 커터",
        "result": "예상 결과: 3루수 땅볼",
    },
    {
        "name": "심우준",
        "stance": "R",
        "prior": "약점: 가운데 / 높은 코스 / 속구",
        "first": "초구: 높은 코스 직구",
        "next": "다음 공: 바깥쪽 슬라이더",
        "result": "예상 결과: 헛스윙 삼진",
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
        '<text x="24" y="86" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Built from White pitch tendencies, left/right split, and 2024 batter weakness prior where available.</text>',
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
    parts.append('<text x="42" y="648" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">1. 좌타 상대로는 낮은 코스 직구와 커브 축, 우타 상대로는 커터와 슬라이더 축을 더 자주 가정했습니다.</text>')
    parts.append('<text x="42" y="672" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">2. 2024 약점 prior는 현재 실험상 구종보다 위치 예측에 더 잘 작동해서, 카드에서도 코스 방향을 더 강하게 반영했습니다.</text>')
    parts.append('<text x="42" y="696" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">3. 실제 라인업과 카운트 상태가 바뀌면 예측도 달라질 수 있습니다.</text>')
    parts.append('</svg>')

    Path("examples/hanwha_tomorrow_fun_board.svg").write_text("\n".join(parts), encoding="utf-8")
    print("examples/hanwha_tomorrow_fun_board.svg")


if __name__ == "__main__":
    main()
