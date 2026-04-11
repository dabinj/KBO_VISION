# Sequence Schema Plan

## 목적

투수별 투구기록을 `PA`, `INNING`, `GAME` 3개 시퀀스 레벨로 재구성하되,
가능한 한 동일한 컬럼 체계를 유지하여 비교, 집계, 모델링, 시각화를 쉽게 만드는 것을 목표로 한다.

핵심 원칙은 아래와 같다.

- 공통 컬럼은 최대한 동일하게 유지
- 레벨별로 꼭 필요한 컬럼만 추가
- 구종 시퀀스와 위치 시퀀스를 함께 보관
- 타자/포수/팀/상황 메타데이터를 모두 헤더 컬럼으로 포함
- 추후 모델링과 motif 분석에 바로 사용할 수 있게 설계

## 레벨 정의

- `PA`
  - 1행 = 1타석
- `INNING`
  - 1행 = 1이닝
- `GAME`
  - 1행 = 1경기

모든 테이블은 `sequence_level` 컬럼을 공통으로 가진다.

## 공통 스키마

아래 컬럼은 `PA`, `INNING`, `GAME` 공통으로 유지한다.

### 식별자

- `sequence_level`
- `season`
- `game_id`
- `game_date`
- `team_code`
- `team_name`
- `opponent_team_code`
- `opponent_team_name`
- `pitcher_code`
- `pitcher_name`
- `catcher_code`
- `catcher_name`

### 시작 상태

- `inning_start`
- `half_start`
- `outs_start`
- `runner_state_start`
- `score_diff_start`

### 타자 헤더

이 컬럼들은 모든 레벨에 유지하되, `INNING`과 `GAME`에서는 일부를 비우거나 요약값으로 채운다.

- `batter_code`
- `batter_name`
- `batter_stance`
- `lineup_slot`
- `batter_prev_season_ba`
- `batter_curr_season_ba_before_unit`
- `batter_prev_season_ops`
- `batter_curr_season_ops_before_unit`

### 시퀀스 본문

- `pitch_seq`
  - 예: `TUS`
- `zone25_seq`
  - 예: `C3-D5-E5`
- `pitch_zone_seq`
  - 예: `TC3-UD5-SE5`
- `sequence_length`

### 결과

- `final_result`
- `outs_recorded`
- `runs_allowed`

## 공통 코드 체계

### 구종 약어

- `F` = 직구
- `T` = 투심
- `C` = 커터
- `S` = 슬라이더
- `W` = 스위퍼
- `K` = 커브
- `U` = 체인지업
- `P` = 포크
- `X` = 기타/미분류

### 위치 코드

25분할 위치는 `A1 ~ E5`를 사용한다.

- 세로
  - `A` = 가장 높음
  - `B` = 높음
  - `C` = 중간
  - `D` = 낮음
  - `E` = 가장 낮음
- 가로
  - `1` = 가장 왼쪽
  - `2` = 왼쪽
  - `3` = 가운데
  - `4` = 오른쪽
  - `5` = 가장 오른쪽

예:

- `C3` = 중앙
- `A1` = 높은 바깥쪽
- `E5` = 낮은 반대쪽 끝

## PA 레벨 추가 컬럼

타석 단위는 가장 정밀한 단위이므로 아래 컬럼을 추가한다.

- `pa_id`
- `pa_number_in_game`
- `pitch_count_in_pa`
- `count_end`
- `first_pitch_type`
- `first_zone25`
- `last_pitch_type`
- `last_zone25`
- `batting_result_type`
- `is_two_strike_sequence`
- `is_runner_in_scoring_position`

### PA 예시

```text
sequence_level: PA
game_id: 20250410...
pitcher_name: 네일
catcher_name: 김태군
batter_name: 오재원
lineup_slot: 1
batter_prev_season_ba: 0.000
batter_curr_season_ba_before_unit: 0.287
inning_start: 1
outs_start: 0
runner_state_start: 000
pitch_seq: TUS
zone25_seq: C3-D5-E5
pitch_zone_seq: TC3-UD5-SE5
sequence_length: 3
final_result: strikeout
```

## INNING 레벨 추가 컬럼

이닝 단위는 여러 타석을 묶는 단위이므로 아래 컬럼을 추가한다.

- `inning_id`
- `batters_faced`
- `pa_count`
- `pitch_count_in_inning`
- `pa_seq_concat`
- `zone25_pa_concat`
- `pitch_zone_pa_concat`
- `first_batter_code`
- `first_batter_name`
- `last_batter_code`
- `last_batter_name`
- `runs_allowed_in_inning`
- `hits_allowed_in_inning`
- `walks_allowed_in_inning`

### INNING 예시

```text
sequence_level: INNING
game_id: 20250410...
pitcher_name: 네일
catcher_name: 김태군
inning_start: 1
outs_start: 0
runner_state_start: 000
batters_faced: 3
pa_count: 3
pitch_count_in_inning: 8
pitch_seq: TUS|TT|USF
zone25_seq: C3-D5-E5|C2-C3|D4-E5-C3
pitch_zone_seq: TC3-UD5-SE5|TC2-TC3|UD4-SE5-FC3
sequence_length: 8
final_result: clean_inning
outs_recorded: 3
runs_allowed: 0
```

## GAME 레벨 추가 컬럼

경기 단위는 전체 운영 흐름을 보는 단위이므로 아래 컬럼을 추가한다.

- `game_sequence_id`
- `innings_pitched`
- `batters_faced`
- `pitch_count_in_game`
- `pa_count`
- `inning_count`
- `pa_seq_concat`
- `inning_seq_concat`
- `times_through_order_max`
- `first_inning_pitch_mix`
- `late_inning_pitch_mix`
- `runs_allowed_total`
- `hits_allowed_total`
- `walks_allowed_total`
- `strikeouts_total`

### GAME 예시

```text
sequence_level: GAME
game_id: 20250410...
pitcher_name: 네일
catcher_name: 김태군
innings_pitched: 6.0
batters_faced: 24
pitch_count_in_game: 92
pa_count: 24
inning_count: 6
pitch_seq: TUS|TT|USF || TT|SU|TF || ...
zone25_seq: C3-D5-E5|C2-C3|D4-E5-C3 || ...
pitch_zone_seq: TC3-UD5-SE5|TC2-TC3|UD4-SE5-FC3 || ...
sequence_length: 92
final_result: quality_start
runs_allowed: 2
```

## 운영 원칙

### 1. 전체 생성 후 필터링

시퀀스 테이블은 우선 전체 생성한다.
분석 대상은 이후 공식 기록 기준으로 필터링한다.

현재 권장 대상:

- `2025`
- `100이닝 이상` 투수

### 2. 타율/OPS는 단위 시작 직전 기준

- `batter_prev_season_ba`
  - 직전년도 고정값
- `batter_curr_season_ba_before_unit`
  - 해당 `PA` 또는 `INNING/GAME` 시작 직전 값
- `OPS`도 같은 규칙 적용

### 3. 포수와 팀 정보는 필수

모든 시퀀스는 아래 조합을 설명할 수 있어야 한다.

- 어떤 `투수`
- 어떤 `포수`
- 어떤 `팀`
- 어떤 `상대팀`
- 어떤 `타자`

### 4. 위치는 반드시 포함

시퀀스 분석에서 `구종`만 보관하면 정보가 크게 손실된다.
따라서 최소 아래 3개를 함께 보관한다.

- `pitch_seq`
- `zone25_seq`
- `pitch_zone_seq`

## 추천 생성 순서

1. `pitch_master`에 `zone25(A1~E5)` 추가
2. `PA` 시퀀스 생성
3. `INNING` 시퀀스 생성
4. `GAME` 시퀀스 생성
5. `100이닝 이상 투수` 필터 적용
6. 투수별 motif / n-gram / transition 분석
