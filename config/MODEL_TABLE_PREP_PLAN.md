# Model Table Preparation Plan

## 1. Objective

다음 단계 모델링을 위해 세 가지 테이블을 먼저 고정한다.

- 투수 기본 루틴 테이블
- 포수 상황 반응 테이블
- 포수 타자 / 볼카운트 반응 테이블

화이트 분석에서는 반드시 `상대 타자 좌 / 우 여부`를 기본 루틴 입력에 포함한다.

## 2. Why Three Tables

우리가 분리해서 보고 싶은 것은 서로 다르다.

### 2.1 Pitcher routine table

질문:

`이 투수는 자기 루틴과 경기 흐름으로 공을 던지는가?`

핵심:

- 투수 중심
- batter stance 포함
- short / mid / long sequence 포함

### 2.2 Catcher situation table

질문:

`이 포수는 상황에 따라 일관된 배합 경향을 보이는가?`

핵심:

- 포수 중심
- inning / outs / zone / sequence / game flow

### 2.3 Catcher batter-count table

질문:

`이 포수는 특정 타자 유형과 볼카운트에서 배합을 어떻게 바꾸는가?`

핵심:

- 포수 중심
- 타자 손잡이 / 타자 ID / 볼카운트 강조

## 3. Table A: Pitcher Routine Table

권장 파일명:

- `model_pitcher_routine_white_2025.csv`

샘플 단위:

- pitch 1개

타깃:

- `pitch_type`

핵심 컬럼:

- pitcher_code
- pitcher_name
- catcher_code
- catcher_name
- batter_code
- batter_name
- stance
- inning
- half
- outs
- count_state
- pitch_index_in_pa
- pitch_index_in_inning
- pitch_index_in_game
- batter_seen_count_in_game
- prev_pitch_type_pa_1
- prev_pitch_type_pa_2
- prev_pitch_type_pa_3
- prev_pitch_type_inning_1
- prev_pitch_type_game_1
- zone_9
- pitch_type

특히 중요한 추가 컬럼:

- `stance`

이 테이블은 화이트가 좌타 / 우타에 따라 배합이 얼마나 달라지는지 보는 최소 단위다.

## 4. Table B: Catcher Situation Table

권장 파일명:

- `model_catcher_situation_jo_2025.csv`
- `model_catcher_situation_lee_2025.csv`

샘플 단위:

- pitch 1개

타깃:

- `pitch_type`

핵심 컬럼:

- catcher_code
- catcher_name
- pitcher_code
- pitcher_name
- inning
- half
- outs
- pitch_index_in_pa
- pitch_index_in_inning
- pitch_index_in_game
- prev_pitch_type_pa_1
- prev_pitch_type_pa_2
- prev_pitch_type_inning_1
- prev_pitch_type_game_1
- zone_9
- pitch_type

이 테이블은 포수가 경기 흐름과 직전 시퀀스에 따라 어떤 배합 경향을 보이는지 본다.

## 5. Table C: Catcher Batter-Count Table

권장 파일명:

- `model_catcher_batter_count_jo_2025.csv`
- `model_catcher_batter_count_lee_2025.csv`

샘플 단위:

- pitch 1개

타깃:

- `pitch_type`

핵심 컬럼:

- catcher_code
- catcher_name
- pitcher_code
- pitcher_name
- batter_code
- batter_name
- stance
- batter_seen_count_in_game
- count_state
- balls
- strikes
- prev_pitch_type_pa_1
- prev_pitch_type_pa_2
- prev_pitch_type_pa_3
- zone_9
- pitch_type

이 테이블은 포수가 특정 타자 유형과 count state에서 얼마나 다르게 부르는지 보는 데 초점을 둔다.

## 6. Source Assets

현재 준비된 원천 파일:

- `data/matchups/2025_white/pitcher_55855_white_context.csv`
- `data/matchups/2025_jo_hyungwoo/catcher_51865_jo_hyungwoo_context.csv`
- `data/matchups/2025_lee_jiyoung/catcher_79456_lee_jiyoung_context.csv`

## 7. Immediate Next Build Order

1. 화이트 routine table 생성
2. 조형우 situation table 생성
3. 조형우 batter-count table 생성
4. 이지영 situation table 생성
5. 이지영 batter-count table 생성

## 8. Notes

- 포수 영향은 반드시 투수 전체를 포함한 전수 데이터로 본다.
- 화이트 분석은 `batter stance`를 필수 feature로 둔다.
- 점수차와 주자상황은 다음 확장 단계에서 추가한다.
