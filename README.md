# KBO_VISION

KBO 리그 경기 데이터 및 모든 투구 내용(구종, 위치좌표, 속도)을 Naver Sports API에서 수집하고, 향후 투구에 대해 실시간 예측 모델 구축까지 개발하기 위한 프로젝트다. <br>
(사심으로) 한화와 류현진의 우승을 돕기위한 프로젝트

```
Powered by Dabin Jeon
```

## Overview

현재 구현된 범위는 아래와 같다.

- 날짜별 KBO 경기 일정 수집
- 경기별 relay API 수집
- 이닝별 투구 기록에 대한 relay 병합
- 투구 단위 CSV 생성
- 투수 / 타자 / 포수 식별 및 이름 매핑 (볼배합은 포수의 영향도 크기에 중요한 요소)
- 구종, 구속, 투구 위치 추출
- 타석 결과 이벤트 연결 (안타,헛스윙,실책 등)
- 타자 기준 스트라이크존 SVG 시각화

## Current Status

현재는 데이터 수집과 해석 검증 단계다.

확인된 핵심 사항:

- `relay?inning=N` 방식으로 이닝별 데이터 수집 가능
- `ptsOptions`에서 투구 위치와 물리값 추출 가능
- `crossPlateY`는 높이가 아니라 crossing plane
- 실제 높이는 `plate_z`로 계산해야 함
- `playerChange`를 반영해야 경기 중 포수 교체 시점을 추적할 수 있음

## Project Structure

```text
KBO_Sabermatrix/
├── config/
│   ├── ANALYSIS_LOG.md
│   ├── DEVELOPMENT_PLAN.md
│   └── MODULE_SPEC.md
├── data/
│   ├── raw/
│   └── schedule/
├── plots/
├── scripts/
│   ├── fetch_kbo_schedule.py
│   ├── plot_pitch_locations.py
│   └── test_naver_relay.py
└── README.md
```

## Main Scripts

### `scripts/fetch_kbo_schedule.py`

KBO 경기 일정을 날짜 범위 기준으로 수집한다.

예시:

```bash
python3 scripts/fetch_kbo_schedule.py --start-date 2026-04-07 --end-date 2026-04-07
```

출력:

- `data/schedule/kbo_schedule_{start}_{end}.json`
- `data/schedule/kbo_schedule_{start}_{end}.csv`

### `scripts/test_naver_relay.py`

경기 `game_id` 기준으로 relay 데이터를 수집하고 투구 단위 CSV를 생성한다.

예시:

```bash
python3 scripts/test_naver_relay.py --game-id 20260405HHOB02026 --all-innings
```

출력:

- `data/raw/naver_relay_all_innings_{game_id}.json`
- `data/raw/naver_relay_pitches_all_innings_{game_id}.csv`

주요 컬럼:

- `inning`, `half`, `pitch_id`, `pitch_num`
- `pitcher_code`, `pitcher_name`
- `catcher_code`, `catcher_name`
- `batter_code`, `batter_name`
- `pitch_type`, `pitch_result`, `speed`
- `cross_plate_x`, `plate_z`, `top_sz`, `bottom_sz`
- `event_text`, `plate_result_text`

### `scripts/plot_pitch_locations.py`

투구 CSV를 읽어 스트라이크존 시각화를 SVG로 생성한다.

예시:

```bash
python3 scripts/plot_pitch_locations.py \
  --input-csv data/raw/naver_relay_pitches_all_innings_20260403HHOB02026.csv \
  --batter-name 페라자
```

특징:

- 구종별 모양 구분
- 투구 결과별 색상 구분
- 타석별 SVG 생성
- 전체 SVG 및 HTML index 생성

## Data Notes

### Schedule API

사용한 일정 API:

```text
https://api-gw.sports.naver.com/schedule/games?fields=basic,schedule,baseball,manualRelayUrl&upperCategoryId=kbaseball&fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&size=500
```

일정 응답에는 KBO 외 항목도 포함될 수 있으므로 `categoryId == "kbo"` 필터링이 필요하다.

### Relay API

사용한 relay API:

```text
https://api-gw.sports.naver.com/schedule/games/{game_id}/relay
https://api-gw.sports.naver.com/schedule/games/{game_id}/relay?inning=N
```

기본 `relay` 호출은 최신 이닝 구간만 주는 경우가 있어, 전체 경기 복원을 위해서는 inning loop가 필요하다.

### Catcher Tracking

포수는 단순 lineup만으로는 충분하지 않다. 공격 중 대타 / 대주자 교체 후 다음 수비 이닝에서 포지션이 바뀌므로 `playerChange.substitution`, `playerChange.shift`, 수비 포지션 상태 추적을 함께 사용해야 한다.

## Documentation

상세 문서는 `config/` 아래에 정리되어 있다.

- [`config/DEVELOPMENT_PLAN.md`](/Users/dabinjeon/NGS_BI_Analysis/Dev_Pipeline/KBO_Sabermatrix/config/DEVELOPMENT_PLAN.md)
- [`config/MODULE_SPEC.md`](/Users/dabinjeon/NGS_BI_Analysis/Dev_Pipeline/KBO_Sabermatrix/config/MODULE_SPEC.md)
- [`config/ANALYSIS_LOG.md`](/Users/dabinjeon/NGS_BI_Analysis/Dev_Pipeline/KBO_Sabermatrix/config/ANALYSIS_LOG.md)

## Next Steps

- 시즌 단위 경기 자동 수집
- 파생 feature 테이블 생성
- 구종 예측 baseline 모델 구축
- 실시간 polling 기반 next-pitch predictor 구현
