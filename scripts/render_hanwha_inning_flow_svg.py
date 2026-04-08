#!/usr/bin/env python3

from pathlib import Path


INNINGS = [
    {
        "inning": "1회",
        "state": "주자상황 가정: 무사 주자 없음",
        "flow": [
            "오재원: 초구 낮은 직구 -> 2구 낮은 커브 -> 중견수 뜬공",
            "페라자: 초구 바깥 직구 -> 2구 바깥 낮은 커브 -> 헛스윙 삼진",
            "문현빈: 초구 높은 직구 -> 2구 바깥 높은 커브 -> 좌익수 뜬공",
        ],
    },
    {
        "inning": "2회",
        "state": "주자상황 가정: 1사 1루",
        "flow": [
            "노시환: 초구 바깥 높은 커터 -> 2구 슬라이더 -> 루킹 삼진",
            "강백호: 초구 바깥 직구 -> 2구 바깥 커브 -> 볼넷",
            "채은성: 초구 바깥 커터 -> 2구 바깥 낮은 투심 -> 우익수 뜬공",
        ],
    },
    {
        "inning": "3회",
        "state": "주자상황 가정: 2사 1,2루",
        "flow": [
            "하주석: 초구 바깥 직구 -> 2구 바깥 낮은 커브 -> 내야 뜬공",
            "최재훈: 초구 바깥 높은 직구 -> 2구 바깥 커터 -> 3루수 땅볼",
            "심우준: 초구 가운데 높은 직구 -> 2구 바깥 슬라이더 -> 헛스윙 삼진",
        ],
    },
    {
        "inning": "4회",
        "state": "주자상황 가정: 무사 주자 없음, 2번째 타순 시작",
        "flow": [
            "오재원: 초구 직구 비중 유지 -> 2구 커브 전환 -> 유격수 땅볼",
            "페라자: 초구 바깥 커터 -> 2구 바깥 낮은 커브 -> 삼진",
            "문현빈: 초구 높은 직구 -> 2구 바깥 변화구 -> 우익수 뜬공",
        ],
    },
    {
        "inning": "5회",
        "state": "주자상황 가정: 1사 2루",
        "flow": [
            "노시환: 초구 커터 -> 2구 슬라이더 -> 볼카운트 불리하게 유도",
            "강백호: 초구 바깥 직구 -> 2구 변화구 -> 볼넷 또는 우전 안타",
            "채은성: 초구 직구보다 커터/투심 비중 상승 -> 우익수 뜬공",
        ],
    },
    {
        "inning": "6회",
        "state": "주자상황 가정: 2사 1루, 화이트 80구 안팎",
        "flow": [
            "하주석: 초구 직구로 스트라이크 선점 -> 2구 낮은 커브",
            "최재훈: 초구 높은 직구 -> 2구 커터 -> 3루수 땅볼",
            "심우준: 초구 직구 -> 2구 슬라이더, 화이트는 타이밍 차 유도",
        ],
    },
]


def inning_card(parts: list[str], x: int, y: int, inning: dict) -> None:
    w = 520
    h = 152
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append(f'<text x="{x+18}" y="{y+28}" font-size="20" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">{inning["inning"]}</text>')
    parts.append(f'<text x="{x+18}" y="{y+50}" font-size="12" font-family="Segoe UI, Arial" fill="#486581">{inning["state"]}</text>')
    for idx, line in enumerate(inning["flow"]):
        parts.append(f'<text x="{x+18}" y="{y+80 + idx*22}" font-size="12" font-family="Segoe UI, Arial" fill="#102a43">{line}</text>')


def main() -> None:
    width = 1100
    height = 1050
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="24" y="38" font-size="28" font-family="Segoe UI, Arial" font-weight="700" fill="#102a43">White 6-Inning Long Sequence Scenario</text>',
        '<text x="24" y="64" font-size="13" font-family="Segoe UI, Arial" fill="#486581">Assumes White works through 6 innings. Built from White 2025 count flow, pitch-to-pitch transitions, lineup turn, and catcher tendency.</text>',
        '<text x="24" y="86" font-size="12" font-family="Segoe UI, Arial" fill="#486581">Each inning card is a scenario board, not a deterministic forecast.</text>',
    ]

    for idx, inning in enumerate(INNINGS):
        row = idx // 2
        col = idx % 2
        x = 24 + col * 536
        y = 120 + row * 170
        inning_card(parts, x, y, inning)

    parts.append('<rect x="24" y="960" width="1050" height="58" rx="12" fill="#ffffff" stroke="#d9e2ec"/>')
    parts.append('<text x="42" y="993" font-size="13" font-family="Segoe UI, Arial" fill="#102a43">핵심 가정: 초반에는 좌타 상대로 직구-커브 축, 중후반 우타 2번째 타순부터는 커터/투심/슬라이더 전환 비중이 높아진다고 보았습니다.</text>')
    parts.append('</svg>')

    Path("examples/hanwha_white_6inning_sequence_board.svg").write_text("\n".join(parts), encoding="utf-8")
    print("examples/hanwha_white_6inning_sequence_board.svg")


if __name__ == "__main__":
    main()
