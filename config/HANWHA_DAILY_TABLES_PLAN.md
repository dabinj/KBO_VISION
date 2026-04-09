# Hanwha Daily Tables Plan

## 1. Goal

리그 전체를 한 번에 다루기보다, 한화 선수단 기준의 운영 테이블을 먼저 만든다.

핵심 목적:

- 한화 타자별 약점과 2스트라이크 이후 헛스윙 위치를 누적 관리
- 한화 투수별 누적 지표를 선발부터 마무리까지 계속 기록
- 매일 경기 종료 후 최신 range CSV를 기준으로 테이블을 재생성

현재 철학:

- 리그 전체보다 한화 선수단 운영 테이블을 먼저 안정화
- 약점 / 헛스윙 / 투수 지표를 매일 같은 포맷으로 누적
- README와 예시 시각화는 이 운영 테이블을 그대로 읽어 생성

## 2. Batter Table

파일:

- `hanwha_batters_2025_summary.csv`
- `hanwha_batters_2025_zone_detail.csv`

요약 테이블 핵심 컬럼:

- `batter_code`
- `batter_name`
- `stance`
- `games`
- `pas`
- `ab`
- `hits`
- `hrs`
- `ba`
- `pitches_seen`
- `swing_rate`
- `whiff_rate`
- `two_strike_pitches`
- `two_strike_whiffs`
- `two_strike_whiff_rate`
- `weakest_zone_2025`
- `two_strike_most_whiff_zone_2025`
- `two_strike_most_whiff_zone_rate_2025`
- `two_strike_most_whiff_family_2025`
- `two_strike_most_whiff_pitch_2025`
- `two_strike_most_whiff_pitch_zone_2025`
- `two_strike_most_whiff_pitch_zone_count_2025`
- `two_strike_in_zone_most_whiff_pitch_2025`
- `two_strike_in_zone_most_whiff_zone_2025`

의미:

- `weakest_zone_2025`: 2025 시즌 전체 pitch disadvantage score 기준 약한 존
- `two_strike_most_whiff_zone_2025`: 2스트라이크 이후 가장 많은 헛스윙이 나온 존
- `two_strike_most_whiff_pitch_2025 + two_strike_most_whiff_pitch_zone_2025`: 2스트라이크 이후 가장 많이 헛스윙한 `구종 + 코스`
- `two_strike_in_zone_*`: `OUT` 유인구에 치우치지 않도록 스트라이크존 안 기준 최다 헛스윙 조합을 별도로 관리

## 2.1 Why zone-only was not enough

초기 버전은 `2스트라이크 최다 헛스윙 존`만 사용했다.

하지만 실제 데이터에서는 많은 타자가 2스트라이크 이후 `OUT` 유인구에 헛스윙을 많이 해서, 존만으로는 해석력이 떨어졌다.

그래서 최신 로직은 아래 두 개를 함께 본다.

- 전체 최다 헛스윙 `구종 + 코스`
- 인존 기준 최다 헛스윙 `구종 + 코스`

이 방식이 실제 타자 약점 해석에 더 유용하다.

## 3. Pitcher Table

파일:

- `hanwha_pitchers_2025_summary.csv`
- `hanwha_pitchers_2025_zone_detail.csv`

요약 테이블 핵심 컬럼:

- `pitcher_code`
- `pitcher_name`
- `games`
- `batters_faced`
- `pitches`
- `strike_rate`
- `whiff_per_pitch`
- `first_pitch_strike_rate`
- `two_strike_pitches`
- `putaway_whiff_rate`
- `avg_velocity`
- `primary_pitch`
- `primary_pitch_pct`

의미:

- 선발 / 불펜 / 마무리를 따로 나누지 않아도, 전 투수의 시즌 누적 지표를 하나의 관리 테이블로 유지
- 필요하면 추후 role tagging만 덧붙이면 됨

## 4. Update Rule

매일 경기 후에는 아래만 다시 실행하면 된다.

```powershell
python scripts\build_hanwha_team_tables.py `
  --input-csv data\ranges\2025-03-01_2025-10-31\pitches_2025-03-01_2025-10-31.csv `
  --output-dir data\team_tables\hanwha_2025
```

즉 기존 파일을 부분 수정하기보다, 최신 pitch CSV를 기준으로 전량 재생성하는 방식이 가장 단순하고 안전하다.

README 시각화까지 갱신하려면 아래도 함께 실행한다.

```powershell
python scripts\render_hanwha_batter_weak_zones_svg.py
```

## 5. Limits

- 현재는 `2025` 시즌 원본 pitch CSV만 사용
- 타자 약점은 한화 타자단 기준으로만 관리
- 투수 지표도 한화 투수단 기준으로만 관리
- 상대팀 전체를 전부 모델링하지 않음

추가 주의:

- 신인이나 신규 표본 부족 타자는 `약점 존`보다 `2스트라이크 헛스윙 조합` 쪽이 더 빠르게 안정될 수 있다
- `OUT` 유인구는 실제로 값이 크지만, 실전 해석을 위해 인존 기준 약점도 함께 봐야 한다

이 범위가 현재 운영과 해석에 가장 효율적이다.
