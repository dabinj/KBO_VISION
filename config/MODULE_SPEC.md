# KBO_Sabermatrix Module Specification

## 1. Directory Overview

- `scripts/`: 수집, 변환, 시각화 스크립트
- `data/raw/`: 경기별 relay raw JSON 및 투구 CSV
- `data/schedule/`: 날짜 범위별 경기 일정 CSV / JSON
- `plots/`: SVG 기반 시각화 산출물
- `config/`: 프로젝트 문서 및 운영 메모

## 2. Script Modules

### 2.1 `scripts/fetch_kbo_schedule.py`

역할:

- 날짜 범위 기준 KBO 경기 일정을 수집한다.

입력:

- `--start-date YYYY-MM-DD`
- `--end-date YYYY-MM-DD`
- `--output-dir` 선택

출력:

- `data/schedule/kbo_schedule_{start}_{end}.json`
- `data/schedule/kbo_schedule_{start}_{end}.csv`

주요 로직:

- Naver schedule API 일자별 호출
- `categoryId == "kbo"` 필터링
- CSV 저장용 정규화 필드 생성

주요 컬럼:

- `game_id`
- `game_date`
- `game_datetime`
- `home_team_code`
- `away_team_code`
- `status_code`
- `stadium`
- `home_starter_name`
- `away_starter_name`

### 2.2 `scripts/test_naver_relay.py`

역할:

- 경기 relay API를 호출해 raw JSON과 pitch table을 생성한다.

입력:

- `--game-id`
- `--all-innings`
- `--inning` 또는 내부 inning list
- `--output-dir`

출력:

- 단일 relay raw JSON
- 이닝별 relay raw JSON 묶음
- 투구 단위 CSV

주요 로직:

- `relay?inning=N` 수집
- player map 생성
- player-team map 생성
- 수비 포지션 상태 초기화
- substitution / shift 기반 수비 포지션 상태 업데이트
- `ptsOptions`와 `textOptions` 결합
- 마지막 투구에 plate result 연결

주요 컬럼:

- 식별: `seqno`, `inning`, `half`, `pitch_id`, `pitch_num`
- 선수: `pitcher_code`, `pitcher_name`, `catcher_code`, `catcher_name`, `batter_code`, `batter_name`
- 판정: `pitch_result`, `event_text`, `plate_result_text`, `plate_result_type`
- 물리: `cross_plate_x`, `cross_plate_y_plane`, `plate_z`, `top_sz`, `bottom_sz`
- 문맥: `balls`, `strikes`, `outs`, `stance`, `pitch_type`, `speed`

주의:

- `cross_plate_y_plane`은 실제 높이가 아니라 crossing plane이다.
- 실제 높이는 `plate_z`를 사용한다.
- 포수는 lineup만으로는 부족하고 `playerChange`를 반영해야 한다.

### 2.3 `scripts/plot_pitch_locations.py`

역할:

- pitch CSV를 읽어 스트라이크존 SVG를 생성한다.

입력:

- `--input-csv`
- `--output-dir`
- `--batter-name`
- `--pitcher-name`

출력:

- 전체 SVG
- 타석별 SVG
- HTML index

주요 로직:

- 투구 row 로드
- 타석 단위 그룹화
- strike zone 렌더링
- 구종별 shape 매핑
- 투구 결과별 색상 매핑
- 하단 이벤트 로그 렌더링

현재 구종 shape 매핑:

- `직구`, `투심`: circle
- `슬라이더`, `커터`: square
- `포크`, `싱커`: diamond
- `커브`: triangle_down
- `체인지업`: triangle_up
- `스위퍼`: triangle_left
- `너클`: hexagon

## 3. Data Artifacts

### 3.1 Raw Relay JSON

용도:

- 원본 보관
- 디버깅
- 포지션 상태 추적 재검증

예시:

- `data/raw/naver_relay_all_innings_20260403HHOB02026.json`

### 3.2 Pitch CSV

용도:

- 분석 기본 테이블
- 시각화 입력
- 예측 모델 입력 전처리의 출발점

예시:

- `data/raw/naver_relay_pitches_all_innings_20260403HHOB02026.csv`

### 3.3 Plot Output

용도:

- 좌표 검증
- 특정 타자/타석 패턴 검토

예시:

- `plots/20260403HHOB02026/batter_페라자/all_pitches.svg`

## 4. Recommended Future Modules

- `scripts/fetch_kbo_season.py`
- `scripts/build_feature_table.py`
- `scripts/train_next_pitch_model.py`
- `scripts/live_polling.py`
- `scripts/live_predict.py`
